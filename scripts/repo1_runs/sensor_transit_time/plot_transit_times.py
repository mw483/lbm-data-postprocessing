import os
from pathlib import Path

import polars as pl

from data_loaders.local_paths import load_local_paths, sensor_output_dir
from data_loaders.particle_io import load_hit_table
from physics_core.particle_analysis import compute_transit_times
from plotting_core.velocity_analysis_plots import plot_transit_time_distribution

def main():
    # =========================================================================
    # User Configuration
    # =========================================================================
    dt_output = 1.0       # Seconds between particle .bin outputs (1 s, confirmed by kaka 2026-10-05)
    bin_width = 4.0       # Histogram bin size in seconds
    max_time = None     # Set maximum x-axis transit time (or None for auto)

    sensor_x, sensor_y, sensor_z = 3672.0, 256.0, 90.0
    sensor_size = (8.0, 8.0, 8.0)   # SIZE_SENSOR_DENSITY used by the C++ run (sensor_8x8x8)

    paths = load_local_paths()   # per-machine folders, see local_paths.example.yaml
    output_figure = paths["figures"] / "comparative" / f"ttd_flat_vs_cube_{int(sensor_x)}_{int(sensor_y)}_{int(sensor_z)}.png"

    # Define runs to compare (folder names under particle_outputs)
    RUNS = {
        "Flat Case": {"run": "20260630_particle_flat_16mapproach", "target_coords": (sensor_x, sensor_y, sensor_z)},
        "Cube Array": {"run": "20260803_particle_cube_16mapproach", "target_coords": (sensor_x, sensor_y, sensor_z)},
    }
    for config in RUNS.values():
        run_dir = sensor_output_dir(paths, config["run"])
        config["csv"] = run_dir / "target_trajectories.csv"
        config["capsule"] = run_dir / "sensor_hit_ids.txt"

    # =========================================================================
    # Data Processing Pipeline
    # =========================================================================
    transit_data = {}

    for label, config in RUNS.items():
        print(f"\nProcessing {label}...")
        
        # 1. Hits recorded by the C++ suite for this sensor (one particle per source)
        if not config["capsule"].exists():
            print("  -> Time capsule not found; skipping.")
            continue
        tx, ty, tz = config["target_coords"]
        hits = load_hit_table(config["capsule"]).filter(
            ((pl.col("sx") - tx).abs() < 0.1) & ((pl.col("sy") - ty).abs() < 0.1) & ((pl.col("sz") - tz).abs() < 0.1)
        )
        print(f"  -> Found {hits.height:,} hits for the sensor at {config['target_coords']}.")
        if hits.height == 0:
            continue

        # 2. Release -> first entry into the sensor box
        print(f"  -> Parsing transit times from: {config['csv'].name}...")
        transit = compute_transit_times(config["csv"], hits, sensor_size, dt_output=dt_output)
        print(f"  -> Computed {transit.height:,} arrival times.")
        transit_data[label] = transit["delta_t"].to_numpy()

    # =========================================================================
    # Render & Export
    # =========================================================================
    if transit_data:
        plot_transit_time_distribution(
            data_dict=transit_data,
            bin_width=bin_width,
            max_time=max_time,
            save_path=output_figure,
            title="Receptor Transit Time Distribution (Flat vs. Cube Array)",
            density=False   # raw counts (professor's request, 2026-10-05)
        )

if __name__ == "__main__":
    main()