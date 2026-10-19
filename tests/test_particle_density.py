"""Reader and statistics for the C++ particle post-processing, on tiny files in the C++ formats."""
import numpy as np
import pytest

from data_loaders.particle_postprocess import (
    list_density, list_windows, read_density, read_log_settings, read_profile, read_total_num, read_xy_stack,
)
from physics_core.particle_density import (
    block_stats, concentration, count_summary, profile_concentration, release_rate, slab_cell_volume,
    spanwise_stats, vertical_stats,
)

LOG = """--- Basic setting ---
NUM_RANK     = 4
dX           = 2
dT           = 0.008
--- For density ---
Z_OUT[2]     = [2 10]
Y_OUT[1]     = [128]
H_AVE        = 2

Current processing :: 10 ( 10 - 12 ) ----------
number of particles = 5
Current processing :: 11 ( 10 - 12 ) ----------
Current processing :: 12 ( 10 - 12 ) ----------
"""


@pytest.fixture
def window(tmp_path):
    w = tmp_path / "10-12_basic"
    w.mkdir()
    (tmp_path / "1-5_basic").mkdir()
    (tmp_path / "notes").mkdir()
    (w / "log_analysis.txt").write_text(LOG)
    (w / "total_num.csv").write_text(",".join(str(i) for i in range(13)) + "\n"
                                     + ",".join(["0"] * 10 + ["4", "6", "8"]) + "\n")
    # Two rank blocks (x split): counts per z cell, then fluid cells per z cell
    (w / "profile.csv").write_text("Rank X:: 0 : Rank Y:: 0\n3,1,0,\n4,4,4,\n"
                                   "Rank X:: 1 : Rank Y:: 0\n1,1,0,\n4,4,4,\n")
    (w / "xy_number_density_2m.csv").write_text("1,2,3\n3,4,5\n")
    (w / "xy_number_density_10m.csv").write_text("0,0,6\n0,0,0\n")
    (w / "xz_number_density_128m.csv").write_text("1,1,1\n0,0,0\n0,0,0\n")
    return w


def test_list_windows(window):
    windows = list_windows(window.parent)
    assert list(windows) == [(1, 5), (10, 12)]
    assert windows[(10, 12)] == window


def test_log_settings_and_snapshots(window):
    s = read_log_settings(window)
    assert s["dX"] == 2 and s["H_AVE"] == 2 and s["NUM_RANK"] == 4
    assert s["Z_OUT"] == [2.0, 10.0]
    assert s["n_snapshots"] == 3


def test_total_num_keeps_window_outputs(window):
    tn = read_total_num(window)
    assert tn["output"].tolist() == [10, 11, 12]
    assert tn["n_particles"].tolist() == [4, 6, 8]


def test_profile_sums_rank_blocks(window):
    prof = read_profile(window, dx=2.0)
    assert prof["z"].tolist() == [1.0, 3.0, 5.0]
    assert prof["count"].tolist() == [4, 2, 0]
    assert prof["fluid_cells"].tolist() == [8, 8, 8]
    c = profile_concentration(prof, n_snapshots=2, dx=2.0)
    assert c[0] == pytest.approx(4 / (2 * 8 * 8.0))


def test_density_files(window):
    assert list_density(window, "xy") == [2, 10]
    assert read_density(window, "xz", 128).shape == (3, 3)
    heights, stack = read_xy_stack(window)
    assert heights.tolist() == [2.0, 10.0] and stack.shape == (2, 2, 3)
    c = concentration(stack[0], 3, slab_cell_volume(2.0, 2.0))
    assert c[1, 2] == pytest.approx(5 / (3 * 8.0))


def test_vertical_stats():
    z = np.array([1.0, 3.0, 5.0, 7.0])
    s = vertical_stats(z, [1, 1, 1, 1])
    assert s["z_mean"] == pytest.approx(4.0)
    assert s["sigma_z"] == pytest.approx(np.sqrt(5.0))
    assert s["z_q50"] == 3.0 and s["z_q99"] == 7.0 and s["z_max"] == 7.0
    assert np.isnan(vertical_stats(z, [0, 0, 0, 0])["z_mean"])


def test_spanwise_and_block_stats():
    mean, std, cv = spanwise_stats(np.array([[1.0, 0.0], [3.0, 0.0]]))
    assert mean.tolist() == [2.0, 0.0]
    assert std[0] == pytest.approx(np.sqrt(2.0)) and np.isnan(cv[1])
    b = block_stats([np.array([1.0]), np.array([2.0]), np.array([3.0])])
    assert b["mean"][0] == 2.0 and b["std"][0] == 1.0
    assert b["sem"][0] == pytest.approx(1 / np.sqrt(3))
    with pytest.raises(ValueError):
        block_stats([np.array([1.0])])


def test_release_rate_and_count_summary(window):
    rate = release_rate(2816, 0.8)
    assert rate == pytest.approx(3520.0)
    s = count_summary(read_total_num(window), dt_output=1.0, rate=2.0)
    assert s["n_mean"] == 6.0
    assert s["trend_per_s"] == pytest.approx(2.0)
    assert s["trend_vs_rate"] == pytest.approx(1.0)
    assert s["residence_time_s"] == pytest.approx(3.0)
