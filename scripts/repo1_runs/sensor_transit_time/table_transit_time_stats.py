"""
Transit-time statistics (release -> first entry into the sensor box) for every sensor,
plus the spanwise line at each height (a particle counts once there, at its earliest
arrival, as in plot_ensemble_ttd.py). Flat vs cube array, one CSV table.

Columns: case, scope (sensor / line), sensor_id, x, y, z, n, mean_s, median_s, std_s,
p10_s, p90_s, min_s, max_s. N counts one particle per source per sensor (the C++ hit list).
"""
import polars as pl

from data_loaders.local_paths import load_local_paths, sensor_output_dir
from data_loaders.particle_io import load_hit_table
from physics_core.particle_analysis import compute_transit_times, transit_time_summary

# =============================================================================
# Settings
# =============================================================================
CASES = [
    ("Flat", "20260630_particle_flat_16mapproach"),
    ("Cube array", "20260803_particle_cube_16mapproach"),
]
SENSOR_SIZE = (8.0, 8.0, 8.0)
DT_OUTPUT = 1.0


def main():
    paths = load_local_paths()
    out_csv = paths["figures"] / "presentation_2026-10-07" / "ttd_stats.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for label, run in CASES:
        run_dir = sensor_output_dir(paths, run)
        hits = load_hit_table(run_dir / "sensor_hit_ids.txt")
        print(f"{label}: {hits.height:,} hits on {hits['sensor_id'].n_unique()} sensors; reading the trajectories...")
        transit = compute_transit_times(run_dir / "target_trajectories.csv", hits, SENSOR_SIZE, dt_output=DT_OUTPUT)
        transit = transit.join(hits.select(["sensor_id", "sx", "sy", "sz"]).unique(), on="sensor_id", how="left")

        for (sid, sx, sy, sz), grp in transit.group_by(["sensor_id", "sx", "sy", "sz"], maintain_order=True):
            rows.append({"case": label, "scope": "sensor", "sensor_id": sid, "x": sx, "y": sy, "z": sz,
                         **transit_time_summary(grp["delta_t"].to_numpy())})
        for (sx, sz), grp in transit.group_by(["sx", "sz"], maintain_order=True):
            first = grp.group_by("id").agg(pl.col("delta_t").min())["delta_t"].to_numpy()
            rows.append({"case": label, "scope": "line", "sensor_id": None, "x": sx, "y": None, "z": sz,
                         **transit_time_summary(first)})

    table = pl.DataFrame(rows).sort(["scope", "z", "y", "case"], descending=[True, False, False, False])
    table.write_csv(out_csv)
    with pl.Config(tbl_rows=100, tbl_cols=20, float_precision=1, tbl_width_chars=250, fmt_str_lengths=12):
        print(table)
    print(f"[SUCCESS] Table saved to: {out_csv}")


if __name__ == "__main__":
    main()
