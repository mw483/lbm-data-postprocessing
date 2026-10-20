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
