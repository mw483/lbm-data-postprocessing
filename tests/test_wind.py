import numpy as np

from data_loaders.lbm_parsers import XZMatrixParser, XYStackedParser, load_xz_yav, xz_yav_path
from physics_core.turbulence import virtual_tower, calc_sigma_v


def write_xz(path, mat):
    # Header line, then one row per z with a trailing comma (as the solver writes it)
    with open(path, "w") as f:
        f.write("header\n")
        for row in mat:
            f.write(",".join(f"{v}" for v in row) + ",\n")


def test_xz_parser_drops_trailing_comma_column(tmp_path):
    mat = np.arange(12, dtype=float).reshape(3, 4)
    write_xz(tmp_path / "a.csv", mat)
    np.testing.assert_array_equal(XZMatrixParser.parse_file(tmp_path / "a.csv"), mat)


def test_xz_path_format():
    assert xz_yav_path("out", "um", 180000, 0).endswith("xz_yav_um00180000_0000.csv")


def test_virtual_tower(tmp_path):
    nz, nx = 4, 10
    um = np.tile(np.arange(nz)[:, None], (1, nx)).astype(float)   # U = z index
    vm = np.zeros((nz, nx))
    vv = np.full((nz, nx), 0.04)                                    # sigma_v = 0.2
    wm = np.zeros((nz, nx))
    uw = np.full((nz, nx), -0.01)                                   # u* = 0.1
    for name, m in dict(um=um, vm=vm, vv=vv, wm=wm, uw=uw).items():
        write_xz(xz_yav_path(tmp_path, name, 180000), m)

    fields = load_xz_yav(tmp_path, 180000)
    tower = virtual_tower(fields, x=7.9, dx=2.0, dz=2.0)
    np.testing.assert_array_equal(tower["z"], [0, 2, 4, 6])
    np.testing.assert_array_equal(tower["um"], [0, 1, 2, 3])
    np.testing.assert_allclose(tower["sigma_v"], 0.2)
    np.testing.assert_allclose(tower["u_star"], 0.1)
    # x beyond the domain clamps to the last column instead of failing
    assert virtual_tower(fields, x=1e6)["um"].shape == (nz,)


def test_sigma_v_never_negative():
    assert calc_sigma_v(np.array([0.0]), np.array([0.1]))[0] == 0.0


def test_xy_stacked_parser(tmp_path):
    p = tmp_path / "xy.csv"
    with open(p, "w") as f:
        f.write("header\n")
        for z in (5, 10):
            f.write(f"{z}\n")
            for j in range(2):
                f.write(",".join(str(z + j) for _ in range(3)) + ",\n")
    planes = XYStackedParser(ny_rows=2).parse_file(p)
    assert sorted(planes) == [5.0, 10.0]
    assert planes[10.0].shape == (2, 3)
    assert planes[10.0][1, 0] == 11
