import numpy as np

from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from data_loaders.map_io import load_lbm_map
from data_loaders.particle_io import (
    extract_hit_list_from_time_capsule, load_streamed_trajectories, load_trajectories_with_velocities,
)


def write_capsule(path):
    # sensor_id x y z source_id particle_id
    path.write_text("1 100 50 20 0 10001\n1 100 50 20 1 20002\n2 200 50 20 0 10005\n")


def write_traj(path):
    # step,id,x,y,z,u,v,w,u_sgs,v_sgs,w_sgs ; u..w lattice (incl. SGS), *_sgs in m/s
    rows = [
        (1200, 10001, 1, 1, 1, 0.021, 0.0, 0.001, 0.1, 0.0, 0.1),
        (1201, 10001, 2, 1, 1, 0.021, 0.0, 0.001, 0.1, 0.0, 0.1),
        (1200, 20002, 5, 5, 5, 0.010, 0.0, 0.000, 0.0, 0.0, 0.0),
        (1200, 10005, 9, 9, 9, 0.010, 0.0, 0.000, 0.0, 0.0, 0.0),
    ]
    path.write_text("\n".join(",".join(str(v) for v in r) for r in rows) + "\n")


def test_hit_list(tmp_path):
    write_capsule(tmp_path / "hits.txt")
    assert extract_hit_list_from_time_capsule(tmp_path / "hits.txt", target_sensor_id=1) == {10001, 20002}
    assert extract_hit_list_from_time_capsule(tmp_path / "hits.txt", target_coords=(200, 50, 20)) == {10005}


def test_streamed_trajectories_read_11_column_file(tmp_path):
    write_capsule(tmp_path / "hits.txt")
    write_traj(tmp_path / "traj.csv")
    traj = load_streamed_trajectories(tmp_path / "traj.csv", tmp_path / "hits.txt", target_sensor_id=1)
    assert set(traj) == {10001, 20002}
    np.testing.assert_array_equal(traj[10001][:, 0], [1, 2])


def test_trajectory_velocities_scaled_once(tmp_path):
    write_capsule(tmp_path / "hits.txt")
    write_traj(tmp_path / "traj.csv")
    df = load_trajectories_with_velocities(tmp_path / "traj.csv", tmp_path / "hits.txt",
                                           target_sensor_id=1, c_ref=100.0)
    row = df.filter(df["id"] == 10001).row(0, named=True)
    assert abs(row["u"] - 2.1) < 1e-9        # total, lattice * c_ref
    assert abs(row["u_sgs"] - 0.1) < 1e-9    # already m/s, not scaled again
    assert abs(row["u_res"] - 2.0) < 1e-9    # resolved = total - SGS


def test_trajectory_filter_by_coords(tmp_path):
    write_capsule(tmp_path / "hits.txt")
    write_traj(tmp_path / "traj.csv")
    df = load_trajectories_with_velocities(tmp_path / "traj.csv", tmp_path / "hits.txt",
                                           target_coords=(200, 50, 20))
    assert df["id"].unique().to_list() == [10005]


def test_source_positions_and_footprint(tmp_path):
    (tmp_path / "pos.txt").write_text(
        "132.0 4.0 0.1 0 0 0.1 1 10001\n132.0 12.0 0.1 0 0 0.1 1 20001\n")
    src = load_source_positions(tmp_path / "pos.txt")
    assert src[2] == {"x": 132.0, "y": 12.0, "z": 0.1}
    (tmp_path / "fp.csv").write_text("1,2,\n5,7,\n")
    assert load_footprint_counts(tmp_path / "fp.csv") == {1: 5.0, 2: 7.0}


def test_map_loader(tmp_path):
    (tmp_path / "building.dat").write_text("3 2\n0 0 0\n0 16 0\n")
    elev, nx, ny = load_lbm_map(tmp_path / "building.dat")
    assert (nx, ny) == (3, 2)
    assert elev[1, 1] == 16


def test_sensor_cache_builds_once_and_matches_csv(tmp_path):
    from data_loaders.sensor_cache import load_sensor_subset, sensor_cache_path, trajectories_from_frame

    run_dir = tmp_path / "out" / "run1" / "sensor_8x8x8" / "1200-1800_sensor_density"
    run_dir.mkdir(parents=True)
    write_capsule(run_dir / "sensor_hit_ids.txt")
    write_traj(run_dir / "target_trajectories.csv")
    paths = {"particle_outputs": tmp_path / "out", "cache": tmp_path / "cache"}

    df, hits = load_sensor_subset(paths, "run1", 1)
    assert sensor_cache_path(paths, "run1", 1).exists()
    assert set(df["id"].to_list()) == {10001, 20002}
    assert hits["id"].to_list() == [10001, 20002]

    (run_dir / "target_trajectories.csv").unlink()        # second call must not need the CSV
    df2, _ = load_sensor_subset(paths, "run1", 1)
    assert df2.equals(df)

    traj = trajectories_from_frame(df2)
    np.testing.assert_array_equal(traj[10001][:, 0], [1, 2])
