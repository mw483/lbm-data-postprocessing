import numpy as np
import polars as pl

from data_loaders.particle_io import load_hit_table
from physics_core.particle_analysis import compute_transit_times


def write_hits(path):
    # sensor_id x y z source_id particle_id ; particle 10001 hit both sensors
    path.write_text("0 100 50 20 0 10001\n1 100 114 20 0 10001\n0 100 50 20 1 20002\n")


def write_traj(path):
    # step,id,x,y,z,... : 10001 enters sensor 0 at step 1203 and keeps moving downstream;
    # 20002 is released at 1201, enters at 1205 (on the box face) and leaves the box later
    rows = []
    for step, x in zip(range(1200, 1210), [60, 70, 80, 97, 103, 110, 120, 130, 140, 150]):
        rows.append((step, 10001, x, 50, 20))
    for step, (x, y) in zip(range(1201, 1208), [(50, 50), (60, 50), (80, 50), (90, 50), (96, 54), (110, 54), (120, 54)]):
        rows.append((step, 20002, x, y, 20))
    path.write_text("\n".join(",".join(str(v) for v in r) + ",0,0,0,0,0,0" for r in rows) + "\n")


def test_arrival_is_first_step_inside_box_not_last_record(tmp_path):
    write_hits(tmp_path / "hits.txt")
    write_traj(tmp_path / "traj.csv")
    hits = load_hit_table(tmp_path / "hits.txt").filter(pl.col("sensor_id") == 0)

    tt = compute_transit_times(tmp_path / "traj.csv", hits, (8, 8, 8), dt_output=1.0)

    assert tt["id"].to_list() == [10001, 20002]
    assert tt["step_release"].to_list() == [1200, 1201]
    assert tt["step_arrival"].to_list() == [1203, 1205]   # inclusive box face (96 = 100 - 4)
    np.testing.assert_allclose(tt["delta_t"].to_numpy(), [3.0, 4.0])


def test_dt_output_scales_and_unreached_hits_are_dropped(tmp_path):
    write_hits(tmp_path / "hits.txt")
    write_traj(tmp_path / "traj.csv")
    hits = load_hit_table(tmp_path / "hits.txt")   # includes sensor 1, which 10001 never enters

    tt = compute_transit_times(tmp_path / "traj.csv", hits, (8, 8, 8), dt_output=2.0)

    assert tt.height == 2
    assert set(tt["sensor_id"].to_list()) == {0}
    np.testing.assert_allclose(sorted(tt["delta_t"].to_list()), [6.0, 8.0])
