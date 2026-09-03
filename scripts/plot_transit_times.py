import os
import sys
from pathlib import Path
# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from data_loaders.particle_io import extract_hit_list_from_time_capsule
from physics_core.particle_analysis import compute_transit_times
from plotting_core.velocity_analysis_plots import plot_transit_time_distribution

def main():
    # =========================================================================
    # User Configuration
    # =========================================================================
    dt_output = 1.0       # Time resolution per step in seconds
    bin_width = 4.0       # PDF histogram bin size in seconds
    max_time = 600.0      # Set maximum x-axis transit time (or None for auto)

    sensor_x, sensor_y, sensor_z = 3672.0, 128.0, 90.0

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
        
        # 1. Harvest target particle IDs using spatial coordinates
        if config["capsule"].exists() and config.get("target_coords"):
            coords = config["target_coords"]
            print(f"  -> Reading Time Capsule for Sensor at {coords}...")
            target_ids = extract_hit_list_from_time_capsule(
                str(config["capsule"]), 
                target_coords=coords
            )
            print(f"  -> Found {len(target_ids):,} matching particles.")
        else:
            print("  -> No valid time capsule or coordinates specified; skipping filtering.")
            target_ids = None

        # 2. Extract transit times using Polars
        if target_ids is not None and len(target_ids) > 0:
            print(f"  -> Parsing transit times from: {config['csv'].name}...")
            delta_t = compute_transit_times(
                csv_path=config["csv"],
                target_ids=target_ids,
                dt_output=dt_output,
                separator=","
            )
            print(f"  -> Successfully computed {len(delta_t):,} arrival values.")
            transit_data[label] = delta_t
        else:
            print("  -> Zero valid IDs found. Skipping transit time computation.")

    # =========================================================================
    # Render & Export
    # =========================================================================
    if transit_data:
        plot_transit_time_distribution(
            data_dict=transit_data,
            bin_width=bin_width,
            max_time=max_time,
            save_path=output_figure,
            title="Receptor Transit Time Distribution (Flat vs. Cube Array)"
        )

if __name__ == "__main__":
    main()