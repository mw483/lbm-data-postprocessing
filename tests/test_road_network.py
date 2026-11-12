"""Roads on the map grid (physics_core/road_network.py) and the road scripts of scripts/jakarta-map-analysis."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from data_loaders.map_georef import ORIENTATIONS, cell_to_crs, north_up
from physics_core.road_network import (ELEVATED, burn_order, centreline_points, classify_way, crs_to_map_xy,
                                       map_from_north_up, overpass_query, overpass_ways, road_width,
                                       source_cell_ok, write_map_dat, write_particle_sources)

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "jakarta-map-analysis"


def geo_for(orientation, nx=6, ny=4):
    return {"crs": "EPSG:23834", "cell_size": 2.0, "orientation": orientation, "nx": nx, "ny": ny,
            "e_topleft": 1000.0, "n_topleft": 5000.0}


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_map_from_north_up_inverts_north_up(orientation):
    arr = np.arange(24).reshape(4, 6)
    np.testing.assert_array_equal(map_from_north_up(north_up(arr, orientation), orientation), arr)


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_crs_to_map_xy_inverts_cell_to_crs(orientation):
    geo = geo_for(orientation)
    i, j = np.meshgrid(np.arange(6), np.arange(4))
    e, n = cell_to_crs(i, j, geo)
    x, y = crs_to_map_xy(e, n, geo)
    np.testing.assert_allclose(x, (i + 0.5) * 2.0)      # cell centres
    np.testing.assert_allclose(y, (j + 0.5) * 2.0)


def test_width_rules():
    assert road_width({"width": "7.5 m"}, 4) == (7.5, "width")
    assert road_width({"width": "500"}, 4) == (6.0, "default")          # implausible tag ignored
    assert road_width({"lanes": "4"}, 2) == (14.0, "lanes")
    assert road_width({}, 1) == (20.0, "default")


def test_classify_keeps_roads_only():
    assert classify_way({"highway": "footway"}) is None
    assert classify_way({"highway": "pedestrian", "area": "yes"}) is None
    a = classify_way({"highway": "trunk", "bridge": "yes", "name": "Tol"})
    assert a["road_class"] == 1 and a["elevated"] and not a["tunnel"]
    assert classify_way({"highway": "residential", "layer": "-1"})["tunnel"]


def test_burn_order_puts_big_ground_roads_last():
    keys = sorted([(4, False), (1, False), (2, True), (2, False)], key=lambda k: burn_order(*k))
    assert keys == [(2, True), (4, False), (2, False), (1, False)]


def test_overpass_query_and_parse():
    q = overpass_query(-6.2, 106.8, -6.1, 106.9, date="2024-01-01")
    assert '[date:"2024-01-01T00:00:00Z"]' in q and "(-6.2,106.8,-6.1,106.9)" in q
    data = {"elements": [{"type": "way", "id": 5, "tags": {"highway": "primary"},
                          "geometry": [{"lon": 1, "lat": 2}, {"lon": 3, "lat": 4}]},
                         {"type": "node", "id": 6}]}
    assert list(overpass_ways(data)) == [(5, {"highway": "primary"}, [(1, 2), (3, 4)])]


def test_centreline_points_spacing():
    from shapely.geometry import LineString
    pts = centreline_points(LineString([(0, 0), (40, 0)]), 16)
    assert [p.x for p in pts] == [8, 24]
    assert len(centreline_points(LineString([(0, 0), (10, 0)]), 16)) == 1


def test_rasterize_l_shaped_road():
    pytest.importorskip("rasterio")
    from shapely.geometry import LineString
    from physics_core.road_network import rasterize_roads
    geo = {"crs": "EPSG:23834", "cell_size": 2.0, "orientation": "i:E,j:N", "nx": 10, "ny": 10,
           "e_topleft": 0.0, "n_topleft": 20.0}
    # along x at y = 5 m, then up along y at x = 15 m; 2 m wide -> one cell row/column
    line = LineString([(0, 5), (15, 5), (15, 20)])
    r = rasterize_roads([line.buffer(1.0, cap_style="flat")], [3], geo)
    assert r.shape == (10, 10)
    assert r[2, :7].tolist() == [3] * 7            # y = 5 m is cell row j = 2
    assert r[3:, 7].tolist() == [3] * 7            # x = 15 m is cell column i = 7
    assert r.sum() == 3 * (8 + 7)


def test_source_cell_ok_drops_buildings_trees_and_sea():
    topo = np.zeros((2, 4))
    build = topo.copy(); build[0, 1] = 6
    veg = topo.copy(); veg[1, 2] = 12
    maps = {"topo": topo, "build": build, "veg": veg}
    i = np.array([0, 1, 2, 3, 3, 9])
    j = np.array([0, 0, 1, 1, 0, 0])
    np.testing.assert_array_equal(source_cell_ok(i, j, maps, land_columns=(1, 4)),
                                  [False, False, False, True, True, False])


def test_particle_file_format(tmp_path):
    n = write_particle_sources(tmp_path, [1.0, 2.0], [3.0, 4.0], [5.5, 6.5])
    lines = (tmp_path / "particle_position.txt").read_text().splitlines()
    assert n == 2 and lines[1].split("\t") == ["2.000000", "4.000000", "6.500000",
                                               "0.000000", "0.000000", "0.100000", "1", "20001"]
    assert (tmp_path / "particle_number.txt").read_text() == "2\n"
    with pytest.raises(ValueError):
        write_particle_sources(tmp_path, np.zeros(214_748), np.zeros(214_748), np.zeros(214_748))


def test_scripts_end_to_end(tmp_path):
    """fetch (from a saved answer) -> rasterize -> place sources on a 40 x 20 cell map with one building."""
    pytest.importorskip("geopandas")
    from data_loaders.map_georef import cell_to_lonlat, save_georef
    geo = {"crs": "EPSG:23834", "cell_size": 2.0, "orientation": "i:S,j:W", "nx": 40, "ny": 20,
           "e_topleft": 235000.0, "n_topleft": 820000.0}
    save_georef(tmp_path / "georef.yaml", geo)
    mdir = tmp_path / "map"
    mdir.mkdir()
    topo = np.full((20, 40), 3.0)
    build = topo.copy(); build[8:12, 20:24] = 9.0
    for name, a in (("topography", topo), ("building", build), ("vegetation", topo)):
        write_map_dat(mdir / f"{name}.dat", a, fmt="%.1f")
    # a primary road along map x through the middle of the map (j = 10), and a footway
    ii = np.array([0.0, 39.0])
    lon, lat = cell_to_lonlat(ii, np.array([10.0, 10.0]), geo)
    ways = [{"type": "way", "id": 1, "tags": {"highway": "primary", "width": "4"},
             "geometry": [{"lon": float(a), "lat": float(b)} for a, b in zip(lon, lat)]},
            {"type": "way", "id": 2, "tags": {"highway": "footway"},
             "geometry": [{"lon": float(a), "lat": float(b)} for a, b in zip(lon, lat)]}]
    (tmp_path / "answer.json").write_text(json.dumps({"elements": ways}))
    out = tmp_path / "out"
    run = lambda script, *a: subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, a)],
                                            cwd=ROOT, check=True, capture_output=True, text=True)
    run("fetch_osm_roads.py", "--georef", tmp_path / "georef.yaml", "--from-json", tmp_path / "answer.json",
        "--out", out)
    run("rasterize_roads.py", mdir, "--georef", tmp_path / "georef.yaml", "--roads", out / "roads.gpkg",
        "--out", out, "--no-figures", "--land-columns", "0", "40")
    r = np.load(out / "roads" / "road_class.npy")
    assert r.shape == (20, 40) and set(np.unique(r)) == {0, 2}
    assert (r[:, 5] == 2).sum() == 2                       # 4 m wide = 2 cells
    run("place_road_sources.py", mdir, "--georef", tmp_path / "georef.yaml", "--roads", out / "roads.gpkg",
        "--out", out, "--name", "t", "--step", "8", "--no-figures", "--land-columns", "0", "40")
    import pandas as pd
    s = pd.read_csv(out / "roads" / "sources_t" / "road_sources.csv")
    assert len(s) > 0
    assert not ((s["i"] >= 20) & (s["i"] < 24)).any()      # none inside the building
    np.testing.assert_allclose(s["z_m"], 4.0)              # ground 3 m + 1 m
    n = int((out / "roads" / "sources_t" / "particle_position" / "particle_number.txt").read_text())
    assert n == len(s)
