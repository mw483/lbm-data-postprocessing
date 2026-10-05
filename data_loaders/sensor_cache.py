"""
Per-sensor cache of target_trajectories.csv, so the 3D demo opens in seconds.

target_trajectories.csv holds every hit particle of every sensor (~600 MB per run) and
each script used to re-read all of it. The first call for a (run, sensor) reads the CSV
once, keeps only that sensor's particles (velocities in m/s, as
load_trajectories_with_velocities returns them) and writes a small Parquet file under
the cache folder from local_paths.yaml. Later calls read the Parquet file.
"""
from pathlib import Path

import numpy as np
import polars as pl

from data_loaders.local_paths import sensor_output_dir
from data_loaders.particle_io import load_hit_table, load_trajectories_with_velocities


def sensor_cache_path(paths, run, sensor_id, sensor_folder="sensor_8x8x8", window="1200-1800_sensor_density"):
    return Path(paths["cache"]) / run / sensor_folder / window / f"sensor_{sensor_id}.parquet"


def load_sensor_subset(paths, run, sensor_id, c_ref=100.0, rebuild=False,
                       sensor_folder="sensor_8x8x8", window="1200-1800_sensor_density"):
    """
    Returns (trajectory frame, hit table) for one sensor of one run.
    Trajectory columns: step, id, x, y, z, u, v, w, u_sgs, v_sgs, w_sgs, u_res, v_res, w_res
    (sorted by id, step). c_ref converts the lattice uvw to m/s (100 for -velocity_lbm 2.0 0.02,
    the 16 m approach runs). Set rebuild=True after the C++ outputs change.
    """
    run_dir = sensor_output_dir(paths, run, sensor_folder, window)
    hits = load_hit_table(run_dir / "sensor_hit_ids.txt").filter(pl.col("sensor_id") == sensor_id)

    cache_file = sensor_cache_path(paths, run, sensor_id, sensor_folder, window)
    if cache_file.exists() and not rebuild:
        print(f"[cache] {run} sensor {sensor_id}: {cache_file}")
        return pl.read_parquet(cache_file), hits

    print(f"[cache] Building {cache_file.name} for {run} from target_trajectories.csv (one-off, can take minutes)...")
    df = load_trajectories_with_velocities(
        csv_path=run_dir / "target_trajectories.csv",
        time_capsule_path=run_dir / "sensor_hit_ids.txt",
        target_sensor_id=sensor_id,
        c_ref=c_ref,
    )
    if df is None:
        raise ValueError(f"[ERROR] No particles for sensor {sensor_id} in {run_dir}")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(cache_file)
    print(f"[cache] Saved {df.height:,} rows to {cache_file}")
    return df, hits


def trajectories_from_frame(df):
    """{particle id: (n, 3) array of x, y, z} from a frame sorted by id and step."""
    ids = df["id"].to_numpy()
    xyz = np.column_stack((df["x"].to_numpy(), df["y"].to_numpy(), df["z"].to_numpy()))
    unique_ids, starts = np.unique(ids, return_index=True)
    return {int(pid): part for pid, part in zip(unique_ids, np.split(xyz, starts[1:]))}
