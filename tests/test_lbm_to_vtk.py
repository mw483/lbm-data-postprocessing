"""LBM output -> VTK converters (tools/lbm_to_vtk): convert tiny solver-format files, read back with pyvista."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
import pyvista as pv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # repo root, for tools.*

from tools.lbm_to_vtk import maps, particles, slices                      # noqa: E402
from tools.lbm_to_vtk.writer import write_pvd                              # noqa: E402

from test_lbm_output import DX, XG_MIN, run_dir                            # noqa: E402,F401  (fixture)
from test_map_3d import write_map                                         # noqa: E402


def pvd_files(path):
    return [(float(d.get("timestep")), d.get("file")) for d in ET.parse(path).getroot().iter("DataSet")]


# --- particles (bin_dir fixture from conftest: 2 rank groups, step 1600, c_ref = 100) ---

def test_particles_fields_and_units(bin_dir, tmp_path):
    out = tmp_path / "vtk"
    written = particles.convert(bin_dir, out, c_ref=100.0, dt_output=0.8)
    assert [p.name for p in written] == ["particles_001600.vtp"]
    cloud = pv.read(written[0])
    assert cloud.n_points == 3
    np.testing.assert_array_equal(cloud["particle_id"], [10001, 20003, 30002])
    np.testing.assert_array_equal(cloud["source_id"], [1, 2, 3])
    np.testing.assert_array_equal(cloud["release"], [1, 3, 2])
    np.testing.assert_allclose(cloud.points[2], [7, 8, 9])
    # uvw (lattice) * c_ref = resolved + SGS; resolved row 0 = (2, 0, 0), SGS = (0.1, 0.2, 0.3)
    np.testing.assert_allclose(cloud["velocity"][0], [2.1, 0.2, 0.3], rtol=1e-5)
    np.testing.assert_allclose(cloud["velocity_resolved"][0], [2.0, 0.0, 0.0], atol=1e-5)
    np.testing.assert_allclose(cloud["speed"][0], np.linalg.norm([2.1, 0.2, 0.3]), rtol=1e-5)
    assert cloud.n_cells == 3                           # vertex cells, so the points render
    assert pvd_files(out / "particles.pvd") == [(1600 * 0.8, "particles_001600.vtp")]


def test_particles_source_filter_and_thinning(bin_dir, tmp_path):
    only2 = particles.step_cloud(bin_dir, 1600, 100.0, sources=[2])
    np.testing.assert_array_equal(only2["particle_id"], [20003])
    thin = particles.step_cloud(bin_dir, 1600, 100.0, every=2)
    np.testing.assert_array_equal(thin["particle_id"], [10001, 30002])
    assert particles.step_cloud(bin_dir, 1600, 100.0, sources=[99]) is None


# --- legacy CSV slices (run_dir fixture from test_lbm_output: 2 ranks in x, 6 x 2 cells) ---

def test_xy_planes_placed_at_their_height(run_dir, tmp_path):
    counts = slices.convert(run_dir, tmp_path / "vtk", families=("xy_",))
    assert counts == {tmp_path / "vtk" / "xy_z0002.pvd": 2, tmp_path / "vtk" / "xy_z0004.pvd": 2}
    img = pv.read(tmp_path / "vtk" / "xy_z0002" / "xy_z0002_00025001.vti")
    assert img.dimensions == (6, 2, 1)
    np.testing.assert_allclose(img.origin, [XG_MIN + 0.5 * DX, XG_MIN + 0.5 * DX, XG_MIN + 1.5 * DX])
    # x fastest: first row of the stitched plane is [0, 1, 2, 10, 11, 12]
    np.testing.assert_array_equal(img["um"].reshape(2, 6), [[0, 1, 2, 10, 11, 12], [3, 4, 5, 13, 14, 15]])
    times = [t for t, _ in pvd_files(tmp_path / "vtk" / "xy_z0002.pvd")]
    assert times == pytest.approx([200.008, 400.008])


def test_yz_plane_axis_order(run_dir, tmp_path):
    slices.convert(run_dir, tmp_path / "vtk", families=("yz_",))
    # rank 0 wrote label x = 2, rank 1 wrote x = 5: two separate planes
    img = pv.read(tmp_path / "vtk" / "yz_x0002" / "yz_x0002_00025001.vti")
    assert img.dimensions == (1, 2, 4)                 # (x, y, z); arrays are (y rows, z cols)
    arr = img["um"].reshape(4, 2)                       # VTK order: y fastest, then z -> [z, y]
    np.testing.assert_array_equal(arr.T, np.arange(8).reshape(2, 4))


def test_xz_yav_at_y0_and_velocity_vector(tmp_path):
    img = slices.plane_image(("z", "x"), {"z": np.array([1.0, 3.0]), "x": np.array([1.0, 3.0, 5.0])},
                             "y", 0.0, {k: np.full((2, 3), v) for k, v in (("um", 1.0), ("vm", 2.0), ("wm", 3.0))}, 2.0)
    assert img.dimensions == (3, 1, 2) and img.origin[1] == 0.0
    np.testing.assert_array_equal(img["velocity_mean"][0], [1, 2, 3])


def test_slices_variable_filter_errors_when_empty(run_dir, tmp_path):
    with pytest.raises(FileNotFoundError):
        slices.convert(run_dir, tmp_path / "vtk", variables=["nope"])


# --- map set ---

def test_map_buildings_in_metres(tmp_path):
    write_map(tmp_path / "topography.dat", np.zeros((4, 5)), "%5.1f")
    b = np.zeros((4, 5)); b[1, 2] = 10.0
    write_map(tmp_path / "building.dat", b, "%5.1f")
    write_map(tmp_path / "vegetation.dat", np.zeros((4, 5)), "%5.1f")
    written = maps.convert(tmp_path, tmp_path / "vtk", dx=2.0, stride=1)
    assert sorted(p.name for p in written) == ["buildings.vtp", "ground.vtp"]   # no trees
    bld = pv.read(tmp_path / "vtk" / "buildings.vtp")
    np.testing.assert_allclose(bld.bounds, (4, 6, 2, 4, 0, 10))   # cell i=2, j=1, 2 m cells


# --- writer ---

def test_pvd_paths_are_relative_and_sorted(tmp_path):
    a, b = tmp_path / "s" / "a.vti", tmp_path / "s" / "b.vti"
    write_pvd([(2.0, b), (1.0, a)], tmp_path / "s.pvd")
    assert pvd_files(tmp_path / "s.pvd") == [(1.0, "s/a.vti"), (2.0, "s/b.vti")]
