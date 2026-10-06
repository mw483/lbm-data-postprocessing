import numpy as np
import polars as pl

from physics_core.particle_analysis import transit_time_summary, until_arrival, velocity_stats_by_height
from physics_core.turbulence import mean_wind_profile


def test_until_arrival_keeps_release_to_arrival_only():
    df = pl.DataFrame({"step": [1, 2, 3, 4, 1, 2], "id": [7, 7, 7, 7, 8, 8], "z": [1.0] * 6})
    transit = pl.DataFrame({"sensor_id": [0], "id": [7], "step_arrival": [3]})
    out = until_arrival(df, transit)
    assert out["step"].to_list() == [1, 2, 3]          # 4 is after arrival; particle 8 never arrived
    assert "step_arrival" not in out.columns


def test_velocity_stats_by_height_bins_and_moments():
    df = pl.DataFrame({"z": [1.0, 3.0, 5.0, 6.0, 7.9], "w_res": [1.0, 3.0, -1.0, 1.0, 3.0]})
    st = velocity_stats_by_height(df, ("w_res",), z_bin=4.0)
    assert st["z_low"].to_list() == [0.0, 4.0]
    assert st["z_mid"].to_list() == [2.0, 6.0]
    assert st["n"].to_list() == [2, 3]
    np.testing.assert_allclose(st["w_res_mean"].to_numpy(), [2.0, 1.0])
    np.testing.assert_allclose(st["w_res_std"].to_numpy(), [np.sqrt(2.0), 2.0])
    assert velocity_stats_by_height(df, ("w_res",), z_bin=4.0, min_count=3)["z_low"].to_list() == [4.0]


def test_transit_time_summary():
    s = transit_time_summary(np.array([10.0, 20.0, 30.0]))
    assert s["n"] == 3 and s["median_s"] == 20.0 and s["min_s"] == 10.0
    assert np.isclose(s["std_s"], 10.0)
    assert transit_time_summary(np.array([])) == {"n": 0}


def test_mean_wind_profile_uses_x_range_and_raw_second_moments():
    um = np.array([[1.0, 2.0, 4.0]])          # one height, three x cells (dx = 2 m)
    uu = um**2 + np.array([[9.0, 1.0, 1.0]])  # variance 9 upstream, 1 in the area
    zero = np.zeros_like(um)
    fields = {"um": um, "vm": zero, "wm": zero, "uu": uu, "vv": zero, "ww": zero}
    prof = mean_wind_profile(fields, x_min=2.0)  # keeps x cells 1 and 2
    np.testing.assert_allclose(prof["u_mean"], [3.0])
    np.testing.assert_allclose(prof["u_std"], [1.0])
