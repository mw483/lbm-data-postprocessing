import os
from pathlib import Path
# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parents[1]

import polars as pl

from data_loaders.particle_io import load_hit_table
from physics_core.particle_analysis import compute_transit_times
from plotting_core.velocity_analysis_plots import plot_transit_time_distribution

def main():
    # =========================================================================
    # User Configuration
    # =========================================================================
    dt_output = 1.0       # Seconds between particle .bin outputs (1 s, confirmed by kaka 2026-10-05)
    bin_width = 4.0       # Histogram bin size in seconds
    max_time = 600.0      # Set maximum x-axis transit time (or None for auto)

    sensor_x, sensor_y, sensor_z = 3672.0, 128.0, 90.0
    sensor_size = (8.0, 8.0, 8.0)   # SIZE_SENSOR_DENSITY used by the C++ run (sensor_8x8x8)

    # Output path

    output_figure = REPO_ROOT / "figures" / "comparative" / f"ttd_flat_vs_cube_{int(sensor_x)}_{int(sensor_y)}_{int(sensor_z)}.png"

    # Define runs to compare
    # sensor_id: ID corresponding to sensor location in sensor_hit_ids.txt
    RUNS = {
        "Flat Case": {
            "csv": Path(r"D:\lbm_results\Particle_PostProcess_Outputs\20260630_particle_flat_16mapproach\sensor_8x8x8\1200-1800_sensor_density\target_trajectories.csv"),
            "capsule": Path(r"D:\lbm_results\Particle_PostProcess_Outputs\20260630_particle_flat_16mapproach\sensor_8x8x8\1200-1800_sensor_density\sensor_hit_ids.txt"),
            "target_coords": (sensor_x, sensor_y, sensor_z)
        },
        "Cube Array": {
            "csv": Path(r"D:\lbm_results\Particle_PostProcess_Outputs\20260803_particle_cube_16mapproach\sensor_8x8x8\1200-1800_sensor_density\target_trajectories.csv"),
            "capsule": Path(r"D:\lbm_results\Particle_PostProcess_Outputs\20260803_particle_cube_16mapproach\sensor_8x8x8\1200-1800_sensor_density\sensor_hit_ids.txt"),
            "target_coords": (sensor_x, sensor_y, sensor_z)
        }
    }

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