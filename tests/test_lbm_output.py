"""Reader for the solver's CSV statistics, on tiny files written in the solver's formats."""
import numpy as np
import pandas as pd
import pytest

from data_loaders.lbm_output import (
    domain_profile, layout_of, list_steps, load_plane, load_prof, read_header_txt, scan_run,
)
from physics_core.moments import covariance, mixed_third_moment, profile_moments, skewness, third_moment

DX = 2.0
XG_MIN = -0.08


def first_line(rank, rx, ry, rz, step=25001, time=200.008):
    return f"{rank},{rx},{ry},{rz},{step},{time:f},{XG_MIN:f},{XG_MIN:f},{XG_MIN:f}\n"


def write_blocks(path, head, blocks):
    """blocks: list of (label or None, 2D array); rows end with a trailing comma like the solver."""
    with open(path, "w") as f:
        f.write(head)
        for label, arr in blocks:
            if label is not None:
                f.write(f"{label:4d}\n")
            for row in arr:
                f.write("".join("nan," if np.isnan(v) else f"{v:6f}," for v in row) + "\n")


@pytest.fixture
def run_dir(tmp_path):
    """Two ranks split in x (ncpu_x = 2), each 3 x-cells by 2 y-cells, nz = 4 per rank."""
    (tmp_path / "header.txt").write_text(
        "ncpu     =              2\nncpu_x   =              2\nnx       =              7\n"
        f"dx       =       {DX:f}\nkout     =2,4\nkagl     =1,2,4,8,20,40\nt_ave    =     200.000000\n"
    )
    for r in (0, 1):
        base = 10.0 * r
        xy = [(2, base + np.arange(6).reshape(2, 3)), (4, base + 100 + np.arange(6).reshape(2, 3))]
        write_blocks(tmp_path / f"xy_um00025001_{r:04d}.csv", first_line(r, r, 0, 0), xy)
        write_blocks(tmp_path / f"xy_um00050001_{r:04d}.csv", first_line(r, r, 0, 0, 50001, 400.008), xy)
        ag = np.full((2, 3), np.nan) if r == 1 else np.ones((2, 3))
        write_blocks(tmp_path / f"xy_ag_um00025001_{r:04d}.csv", first_line(r, r, 0, 0), [(1, ag)])
        write_blocks(tmp_path / f"xz_yav_um00025001_{r:04d}.csv", first_line(r, r, 0, 0),
                     [(None, base + np.arange(12).reshape(4, 3))])
        write_blocks(tmp_path / f"yz_um00025001_{r:04d}.csv", first_line(r, r, 0, 0),
                     [(2 + 3 * r, base + np.arange(8).reshape(2, 4))])
    return tmp_path


def test_header_txt(run_dir):
    h = read_header_txt(run_dir)
    assert h["ncpu_x"] == 2 and h["dx"] == DX and h["kout"] == [2, 4] and h["t_ave"] == 200.0


def test_layout_prefers_longest_prefix():
    assert layout_of("xz_yav_um")["labelled"] is False
    assert layout_of("xz_um")["labelled"] is True
    assert layout_of("xy_ag_um")["label_axis"] == "agl"
    with pytest.raises(ValueError):
        layout_of("prof")


def test_xy_stitched_in_x(run_dir):
    p = load_plane(run_dir, "xy_um", 25001)
    assert list(p.data) == [2, 4]
    np.testing.assert_array_equal(p.data[2], [[0, 1, 2, 10, 11, 12], [3, 4, 5, 13, 14, 15]])
    np.testing.assert_allclose(p.coords["x"], XG_MIN + (np.arange(6) + 0.5) * DX)
    assert p.labels_m[2] == pytest.approx(XG_MIN + 1.5 * DX)
    assert p.time == pytest.approx(200.008)


def test_ag_nan_stays_nan_and_label_is_above_ground(run_dir):
    p = load_plane(run_dir, "xy_ag_um", 25001)
    assert np.all(p.data[1][:, :3] == 1) and np.all(np.isnan(p.data[1][:, 3:]))
    assert p.labels_m[1] == pytest.approx(0.5 * DX)


def test_xz_yav_without_label(run_dir):
    p = load_plane(run_dir, "xz_yav_um", 25001)
    assert p.data[0].shape == (4, 6) and p.axes == ("z", "x")
    assert p.data[0][3, 5] == 21.0


def test_yz_planes_on_different_ranks(run_dir):
    p = load_plane(run_dir, "yz_um", 25001)
    assert list(p.data) == [2, 5]
    assert p.data[2].shape == (2, 4)        # y rows x z columns, one rank along y and z
    assert p.data[5][0, 0] == 10.0


def test_scan_and_steps(run_dir):
    assert list_steps(run_dir, "xy_um") == [25001, 50001]
    files = scan_run(run_dir)
    assert set(files["name"]) == {"xy_um", "xy_ag_um", "xz_yav_um", "yz_um"}


def test_missing_step_raises(run_dir):
    with pytest.raises(FileNotFoundError):
        load_plane(run_dir, "xy_um", 99999)


def write_prof(path, rank, u):
    cols = ["z", "U", "V", "W", "UU", "VV", "WW", "UV", "UW", "VW", "UUU", "VVV", "WWW",
            "T", "TT", "WT", "uu_SGS", "vv_SGS", "ww_SGS", "wt_MODEL"]
    rows = [[1.0, u, 0, 0.5, u * u + 1, 1, 1.25, 0, 0.5 * u, 0, u**3 + 3 * u, 0, 0.125 + 1.5,
             2.0, 5.0, 1.5, 0.1, 0.1, 0.1, 0.01]]
    with open(path, "w") as f:
        f.write(first_line(rank, rank, 0, 0))
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(f"{v:.15e}" for v in r) + "\n")


def test_prof_ranks_averaged(tmp_path):
    write_prof(tmp_path / "prof00025001_0000.csv", 0, 2.0)
    write_prof(tmp_path / "prof00025001_0001.csv", 1, 4.0)
    prof = load_prof(tmp_path, 25001)
    assert len(prof) == 2 and set(prof["rank"]) == {0, 1}
    dom = domain_profile(prof)
    assert len(dom) == 1 and dom["U"].iloc[0] == pytest.approx(3.0)


def test_profile_moments_central():
    prof = pd.DataFrame({
        "z": [1.0], "U": [2.0], "V": [0.0], "W": [0.5], "UU": [5.0], "VV": [1.0], "WW": [1.25],
        "UV": [0.0], "UW": [1.0], "VW": [0.0], "UUU": [14.0], "VVV": [0.0], "WWW": [2.625],
        "T": [2.0], "TT": [5.0], "WT": [1.5], "uu_SGS": [0.1], "vv_SGS": [0.1], "ww_SGS": [0.1],
        "wt_MODEL": [0.01],
    })
    m = profile_moments(prof).iloc[0]
    assert m["var_u"] == pytest.approx(1.0) and m["var_w"] == pytest.approx(1.0)
    assert m["tke"] == pytest.approx(1.5)
    assert m["skew_u"] == pytest.approx(0.0)           # 14 - 3*2*5 + 2*8 = 0
    assert m["skew_w"] == pytest.approx(1.0)           # 2.625 - 3*0.5*1.25 + 2*0.125 = 1
    assert m["flux_wt"] == pytest.approx(0.5) and m["var_t"] == pytest.approx(1.0)
    assert m["sgs_sum"] == pytest.approx(0.3)


def test_moments_match_sample_statistics():
    rng = np.random.default_rng(0)
    a, b = rng.gamma(2.0, size=200_000), rng.normal(1.0, 2.0, size=200_000)
    raw = lambda x: float(np.mean(x))
    am, bm = raw(a), raw(b)
    assert covariance(raw(a * b), am, bm) == pytest.approx(np.mean((a - am) * (b - bm)), abs=1e-9)
    assert third_moment(raw(a**3), raw(a * a), am) == pytest.approx(np.mean((a - am) ** 3), rel=1e-9)
    assert mixed_third_moment(raw(a * a * b), raw(a * a), raw(a * b), am, bm) == pytest.approx(
        np.mean((a - am) ** 2 * (b - bm)), rel=1e-6, abs=1e-9)
    assert np.isnan(skewness(1.0, -0.1))


def test_plane_moments_central():
    from physics_core.moments import plane_moments
    f = {"um": np.array([2.0]), "vm": np.array([0.0]), "wm": np.array([0.5]),
         "uu": np.array([5.0]), "vv": np.array([1.0]), "ww": np.array([1.25])}
    m = plane_moments(f)
    assert m["U"][0] == 2.0 and m["var_u"][0] == pytest.approx(1.0) and m["var_w"][0] == pytest.approx(1.0)
    assert m["sigma_w"][0] == pytest.approx(1.0) and m["tke"][0] == pytest.approx(1.5)
    assert "tke" not in plane_moments({"um": f["um"], "uu": f["uu"]})


def test_shared_norm_same_scale_and_centred():
    from plotting_core.heatmap_plots import shared_norm
    a, b = np.array([[0.0, 1.0]]), np.array([[np.nan, 3.0]])
    n = shared_norm([a, b])
    assert (n.vmin, n.vmax) == (0.0, 3.0)
    c = shared_norm([np.array([-0.5, 2.0])], center=0.0)
    assert (c.vmin, c.vcenter, c.vmax) == (-2.0, 0.0, 2.0)
