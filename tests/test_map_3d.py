"""Map set reader and the face-only column meshes used by scripts/view_map_3d.py."""
import numpy as np
import pytest

from data_loaders.map_io import create_voxel_buildings, load_map_set, read_map_dat
from plotting_core.map_3d import auto_stride, blocky_columns, crop_and_coarsen, map_set_meshes


def write_map(path, rows, fmt):
    rows = np.asarray(rows)
    with open(path, "w") as f:
        f.write(f"{rows.shape[1]} {rows.shape[0]}\n")
        for r in rows:
            f.write("".join(fmt % v for v in r) + "\n")


def test_read_orientation_rows_are_y(tmp_path):
    write_map(tmp_path / "m.dat", [[0, 1, 2], [3, 4, 5]], "%5.1f")
    h, nx, ny = read_map_dat(tmp_path / "m.dat")
    assert (nx, ny) == (3, 2)
    assert h[1, 0] == 3 and h[0, 2] == 2      # [j, i]


def test_read_fixed_width_when_values_touch(tmp_path):
    # f5.1 writes 386.0 with no leading blank, so it touches the value before it
    write_map(tmp_path / "m.dat", [[12, 386, 0], [100, 5, 250]], "%5.1f")
    assert "12.0386.0" in (tmp_path / "m.dat").read_text()
    h, _, _ = read_map_dat(tmp_path / "m.dat")
    np.testing.assert_array_equal(h, [[12, 386, 0], [100, 5, 250]])


def test_map_set_size_mismatch(tmp_path):
    write_map(tmp_path / "topography.dat", [[0, 0]], "%3d")
    write_map(tmp_path / "building.dat", [[0, 0, 0]], "%5.1f")
    write_map(tmp_path / "vegetation.dat", [[0, 0]], "%5.1f")
    with pytest.raises(ValueError):
        load_map_set(tmp_path)


def test_crop_and_coarsen_mean_ground_max_objects():
    topo = np.array([[0, 2, 4, 6], [0, 2, 4, 6]], np.float32)
    build = topo.copy()
    build[0, 1] = 30
    maps = {"topo": topo, "build": build, "veg": topo.copy()}
    out, origin = crop_and_coarsen(maps, crop=(0, 4, 0, 2), stride=2)
    assert origin == (0, 0)
    np.testing.assert_array_equal(out["topo"], [[1, 5]])
    np.testing.assert_array_equal(out["build"], [[30, 6]])


def test_auto_stride():
    assert auto_stride((100, 100), target=10_000) == 1
    assert auto_stride((2560, 8000)) == 4


def test_single_column_has_top_and_four_walls():
    top = np.array([[10.0]])
    mesh = blocky_columns(top, np.zeros_like(top), top > 0, dx=2.0)
    assert mesh.n_cells == 5
    assert mesh.bounds[1] - mesh.bounds[0] == pytest.approx(2.0)
    assert mesh.bounds[5] == pytest.approx(10.0)


def test_equal_neighbours_share_no_wall():
    top = np.array([[10.0, 10.0]])
    mesh = blocky_columns(top, np.zeros_like(top), top > 0, dx=1.0)
    assert mesh.n_cells == 2 + 6


def test_walls_start_at_ground_on_raised_terrain():
    topo = np.full((1, 3), 5.0, np.float32)
    build = topo.copy()
    build[0, 1] = 20.0                         # absolute height: 15 m building on 5 m ground
    maps = {"topo": topo, "build": build, "veg": topo.copy()}
    meshes = map_set_meshes(maps, dx=2.0)
    b = meshes["buildings"]
    assert b.bounds[4] == pytest.approx(5.0) and b.bounds[5] == pytest.approx(20.0)
    assert meshes["trees"] is None


def test_create_voxel_buildings_keeps_old_interface():
    elev = np.array([[0, 16, 0]], np.float32)
    mesh = create_voxel_buildings(elev, 3, 1, resolution=2.0)
    assert mesh.bounds[0] == pytest.approx(2.0) and mesh.bounds[1] == pytest.approx(4.0)
    assert mesh.bounds[5] == pytest.approx(16.0)
    assert create_voxel_buildings(np.zeros((2, 2)), 2, 2) is None


# --- roads, map.yaml and view names (view_map_3d.py, 2026-11-16) ---------------------------------
def test_codes_coarsen_keeps_biggest_road_and_ground_over_elevated():
    from plotting_core.map_3d import crop_and_coarsen_codes
    codes = np.array([[0, 4, 12, 0],
                      [2, 0, 0, 3]], np.uint8)
    np.testing.assert_array_equal(crop_and_coarsen_codes(codes, (0, 4, 0, 2), 2), [[2, 3]])
    np.testing.assert_array_equal(crop_and_coarsen_codes(codes, (2, 4, 0, 1), 1), [[12, 0]])


def test_road_layers_one_tile_per_cell_above_ground():
    from plotting_core.map_3d import road_layers
    codes = np.array([[1, 4, 4], [0, 11, 0]], np.uint8)
    topo = np.full(codes.shape, 3.0)
    layers = road_layers(codes, topo, dx=2.0, lift=0.2)
    assert {k: m.n_cells for k, m in layers.items()} == {"motorway": 1, "local": 2, "elevated": 1}
    assert layers["local"].bounds[4] == pytest.approx(3.2)


def test_map_meta_paths_relative_to_map_folder(tmp_path):
    from data_loaders.map_meta import load_map_meta, map_label
    d = tmp_path / "TSUBAME4_12m" / "map"
    d.mkdir(parents=True)
    assert load_map_meta(d) == {} and map_label(d) == "TSUBAME4_12m"
    (d / "map.yaml").write_text("name: Jakarta12\nroads: ../roads/road_class.npy\n")
    meta = load_map_meta(d)
    assert map_label(d, meta) == "Jakarta12"
    assert meta["roads"] == d / "../roads/road_class.npy"


def test_box_location_corners_are_cell_edges():
    pytest.importorskip("pyproj")
    from data_loaders.map_georef import box_location
    geo = {"crs": "EPSG:23834", "cell_size": 2.0, "orientation": "i:S,j:W", "nx": 8000, "ny": 2560,
           "e_topleft": 234370.0, "n_topleft": 826440.0}
    loc = box_location((0, 8000, 0, 2560), geo)
    # i:S, j:W -> cell (0, 0) is the north-east corner of the map
    assert loc["corners_crs"]["i0_j0"] == [234370.0 + 2560 * 2.0, 826440.0]
    assert loc["corners_crs"]["i1_j1"] == [234370.0, 826440.0 - 8000 * 2.0]
    assert (loc["x_points"], loc["y_points"]) == ("south", "west")
    assert loc["size_m"] == [16000.0, 5120.0]


def test_view_names():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "view_map_3d", Path(__file__).resolve().parents[1] / "scripts" / "view_map_3d.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.view_name("TSUBAME4_12m", "J1", [1, 2, 3, 4], (10, 10)) == "TSUBAME4_12m_J1"
    assert mod.view_name("M", None, [1, 5, 2, 8], (10, 10)) == "M_crop_1-5_2-8"
    assert mod.view_name("M", None, None, (10, 10)) == "M"
