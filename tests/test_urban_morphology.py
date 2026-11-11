"""Urban morphology statistics, map georeference and the location search of scripts/jakarta-map-analysis."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from data_loaders.map_georef import ORIENTATIONS, cell_to_crs, image_index, north_up
from physics_core.urban_morphology import (area_weighted_height, building_table, empty_edge_columns,
                                           frontal_area_index, label_buildings, object_heights,
                                           plan_area_fraction, tile_stats, value_stats)

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "jakarta-map-analysis"


def maps_from(hb, topo=None, hv=None):
    hb = np.asarray(hb, float)
    topo = np.zeros_like(hb) if topo is None else np.asarray(topo, float)
    hv = np.zeros_like(hb) if hv is None else np.asarray(hv, float)
    return {"topo": topo, "build": topo + hb, "veg": topo + hv}


def test_object_heights_subtract_ground():
    m = maps_from([[0, 10]], topo=[[5, 5]], hv=[[12, 0]])
    hb, hv = object_heights(m)
    np.testing.assert_array_equal(hb, [[0, 10]])
    np.testing.assert_array_equal(hv, [[12, 0]])


def test_plan_fraction_and_area_weighted_height():
    hb = np.array([[0, 10], [0, 30]], float)
    assert plan_area_fraction(hb) == 0.5
    assert area_weighted_height(hb) == 10.0


def test_frontal_area_single_block():
    # one 2 x 1 cell block of height 10 in a 4 x 4 domain (dx cancels)
    hb = np.zeros((4, 4))
    hb[1, 1:3] = 10.0
    assert frontal_area_index(hb, axis=1) == pytest.approx(10.0 * 1 / 16)   # wind along i meets one cell-wide wall
    assert frontal_area_index(hb, axis=0) == pytest.approx(10.0 * 2 / 16)   # wind along j meets two


def test_labels_and_building_table():
    hb = np.zeros((5, 6))
    hb[0:2, 0:3] = 20.0          # 2 x 3 block
    hb[4, 5] = 7.0               # single cell
    labels, n = label_buildings(hb)
    assert n == 2
    t = building_table(hb, labels, n, dx=2.0)
    big = int(np.argmax(t["n_cells"]))
    assert t["n_cells"][big] == 6 and t["area_m2"][big] == 24.0
    assert t["len_i"][big] == 3 and t["len_j"][big] == 2 and t["min_side"][big] == 2
    assert t["h_max"][1 - big] == 7.0


def test_tile_stats_drop_partial_tiles():
    hb = np.zeros((4, 5))
    hb[0, 0] = 10.0
    hv = np.zeros_like(hb)
    hv[3, 3] = 12.0
    st = tile_stats(hb, hv, 2)
    assert st["lambda_p"].shape == (2, 2)
    assert st["lambda_p"][0, 0] == 0.25 and st["h_mean"][0, 0] == 10.0 and np.isnan(st["h_mean"][1, 1])
    assert st["tree_cover"][1, 1] == 0.25


def test_empty_edge_columns():
    hb = np.zeros((3, 10))
    hb[1, 3] = 5.0
    topo = np.zeros((3, 10))
    topo[:, 7] = 1.0
    assert empty_edge_columns(maps_from(hb, topo)) == (3, 8)


def test_value_stats_empty():
    assert np.isnan(value_stats([], "x_")["x_mean"])


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_north_up_matches_image_index(orientation):
    arr = np.arange(3 * 5).reshape(3, 5)          # ny = 3, nx = 5, [j, i]
    img = north_up(arr, orientation)
    geo = {"orientation": orientation, "nx": 5, "ny": 3}
    for j in range(3):
        for i in range(5):
            r, c = image_index(i, j, geo)
            assert img[int(r), int(c)] == arr[j, i]


def test_cell_to_crs_i_south_j_west():
    geo = {"orientation": "i:S,j:W", "nx": 4, "ny": 2, "cell_size": 2.0, "e_topleft": 100.0, "n_topleft": 50.0}
    # cell i=0, j=0: first row of the north-up image, east-most column (j runs west)
    assert cell_to_crs(0, 0, geo) == (100.0 + 1.5 * 2.0, 50.0 - 0.5 * 2.0)
    assert cell_to_crs(3, 1, geo) == (100.0 + 0.5 * 2.0, 50.0 - 3.5 * 2.0)


def load_fit_script():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("fit_map_location", SCRIPTS / "fit_map_location.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_location_search_finds_shift_and_orientation():
    fit = load_fit_script()
    rng = np.random.default_rng(3)
    ref = (rng.random((200, 160)) < 0.08).astype(np.uint8)
    ref = np.kron(ref, np.ones((2, 2), np.uint8))          # blocky "buildings", 400 x 320
    row, col = 52, 88
    img_true = ref[row:row + 120, col:col + 40]
    mask = img_true[:, ::-1].T                             # the map [j, i] that north_up(., "i:S,j:W") turns into img_true
    best = []
    for o in ORIENTATIONS:
        img = north_up(mask, o)
        s, r, c = fit.coarse_search(ref, img, 4)
        best.append((s, o, r, c))
    s, o, r, c = max(best)
    assert o == "i:S,j:W"
    sc, r, c = fit.refine(ref, north_up(mask, o), r, c, 8)
    assert (r, c) == (row, col) and sc["iou"] == 1.0


def test_image_transform_matches_cell_to_crs():
    from data_loaders.map_georef import image_shape, image_transform
    geo = {"orientation": "i:S,j:W", "nx": 4, "ny": 2, "cell_size": 2.0, "e_topleft": 100.0, "n_topleft": 50.0}
    assert image_shape(geo) == (4, 2)
    t = image_transform(geo)
    for i, j in ((0, 0), (3, 1), (2, 0)):
        r, c = image_index(i, j, geo)
        assert t @ (c + 0.5, r + 0.5) == cell_to_crs(i, j, geo)


# --- cut-out boxes -------------------------------------------------------------
from physics_core.urban_morphology import best_shift, blockage_by_column, box_summary  # noqa: E402


def test_blockage_by_column():
    hb = np.zeros((4, 3))
    hb[0, 1] = 10.0                      # one 10 m cell in column 1
    hb[:, 2] = 50.0                      # a full row of 50 m, cut at a 20 m top
    b = blockage_by_column(hb, top_m=20.0, dx=2.0)
    np.testing.assert_allclose(b, [0.0, 10 * 2 / (8 * 20), 1.0])


def test_best_shift_prefers_fewest_then_smallest():
    counts = np.array([5, 0, 3, 3, 0, 5, 5])
    assert best_shift(counts, 2, 4, 1) in (-1, 1)  # cost 3 either way, 6 unshifted
    assert best_shift(np.array([1, 1, 1, 1]), 1, 3, 1) == 0
    assert best_shift(np.array([0, 9, 9, 9, 9]), 1, 5, 3) == -1  # only -1 fits inside the map


def test_box_summary_numbers():
    hb = np.zeros((20, 40))
    hb[2:6, 2:14] = 6.0                  # 4 x 12 block (min side 4 cells), 6 m
    hb[10, 30] = 12.0                    # one-cell building
    hv = np.zeros_like(hb)
    hv[15:17, 20:22] = 12.0              # 4 tree cells
    topo = np.ones_like(hb)
    m = maps_from(hb, topo=topo, hv=hv)
    s = box_summary(m, (0, 40, 0, 20), dx=2.0, nz=10, run_s=80.0, source_step=1, min_cells=(10,))
    n_b = 48 + 1
    assert s["lambda_p"] == pytest.approx(n_b / 800)
    assert s["h_max_m"] == 12.0 and s["default_height_share"] == pytest.approx(48 / 49)
    assert s["tree_cover"] == pytest.approx(4 / 800)
    assert s["buildings"] == 2 and s["one_cell_buildings_share"] == 0.5
    assert s["narrower_10_cells_share"] == 1.0
    assert s["sources"] == 800 - n_b - 4
    assert s["ground_range_m"] == 0.0
    assert s["top_m"] == 20.0 and s["top_over_hmax"] == pytest.approx(20 / 12)
    # column 2: four 6 m cells over a 40 m wide, 20 m high section
    assert s["blockage_max"] == pytest.approx(4 * 6 * 2 / (40 * 20))
    assert s["edge_build_cells_i0"] == 0 and s["edge_build_cells_j0"] == 0
    assert s["wall_hours_4gpu_est"] > 0


def test_box_summary_street_box_moves_off_buildings():
    hb = np.zeros((10, 30))
    hb[:, 10] = 6.0                      # a wall of buildings on column 10
    s = box_summary(maps_from(hb), (10, 20, 0, 10), seam_search=2)
    assert s["edge_build_cells_i0"] == 10
    i0, i1 = (int(v) for v in s["shifted_box"].split()[:2])
    assert i0 != 10 and abs(i0 - 10) <= 2 and i1 - i0 == 10


def test_box_summary_rejects_outside_box():
    with pytest.raises(ValueError):
        box_summary(maps_from(np.zeros((4, 4))), (0, 5, 0, 4))
