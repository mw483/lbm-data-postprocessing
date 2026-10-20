from pathlib import Path

import polars as pl

from data_loaders.local_paths import load_local_paths, sensor_output_dir
from data_loaders.particle_io import load_hit_table
from physics_core.particle_analysis import (
    compute_transit_times,
    compute_depth_averaged_u,
    normalize_transit_distribution
)
from plotting_core.velocity_analysis_plots import plot_normalized_ttd_comparison

def main():
    # =========================================================================
    # Configuration
    # =========================================================================
    sensor_x = 3672.0
    delta_x = 600.0         # Source to receptor fetch distance
    heights = [20.0, 50.0, 90.0]
    sensor_size = (8.0, 8.0, 8.0)   # SIZE_SENSOR_DENSITY used by the C++ run (sensor_8x8x8)
    dt_output = 1.0         # Seconds between particle .bin outputs (1 s, confirmed by kaka 2026-10-05)
    scaling_method = "no_normalization"  # Options: "median", "advective", "eddy_turnover", "no_normalization"

    # Set parameters conditionally based on the method
    if scaling_method == "no_normalization":
        bin_w = 4.0        # 4-second histogram bins
        max_t = 600.0      # Physical second window
    else:
        bin_w = 0.04       # Dimensionless bin width
        max_t = 3.0        # Dimensionless scale limit
    
    # Target case: Switch between Flat and Cube cases
    case_name = "Flat"
    run = "20260630_particle_flat_16mapproach"   # folder under particle_outputs
    paths = load_local_paths()   # per-machine folders, see local_paths.example.yaml
    csv_path = sensor_output_dir(paths, run) / "target_trajectories.csv"
    capsule_path = sensor_output_dir(paths, run) / "sensor_hit_ids.txt"
    prof_path = Path(r"Z:\20260527_output_flat_3072\prof00180000_0000.csv") # Used if scaling_method="advective"[cite: 1]

    output_fig = paths["figures"] / "comparative" / f"ensemble_ttd_{case_name.lower().replace(' ', '_')}_{scaling_method}.png"

    # =========================================================================
    # Process Line-Ensembles per Height
    # =========================================================================
    normalized_data = {}
    xlabel_final = ""

    for z in heights:
        print(f"\n--- Processing Height Z = {z:.1f} m ---")
        
        # 1. Hits at every spanwise (Y) sensor at (sensor_x, z)
        hits = load_hit_table(capsule_path).filter(
            ((pl.col("sx") - sensor_x).abs() <= 0.5) & ((pl.col("sz") - z).abs() <= 0.5)
        )
        print(f"  -> {hits.height:,} hits along the spanwise line.")

        if hits.height == 0:
            continue

        # 2. Release -> first entry into a sensor box; a particle that hit several sensors
        #    on the line counts once, at its earliest arrival (same N as the old unique-ID set)
        transit = compute_transit_times(csv_path, hits, sensor_size, dt_output=dt_output)
        delta_t = transit.group_by("id").agg(pl.col("delta_t").min())["delta_t"].to_numpy()
        print(f"  -> {len(delta_t):,} unique particles with an arrival time.")

        # 3. Apply normalization
        u_bar = compute_depth_averaged_u(prof_path, target_z=z) if scaling_method == "advective" else None
        
        scaled_t, xlabel_final = normalize_transit_distribution(
            delta_t=delta_t,
            method=scaling_method,
            u_bar=u_bar,
            delta_x=delta_x,
            u_star=0.15,     # Friction velocity if method == "eddy_turnover"
            sensor_z=z
        )
        
        normalized_data[f"Z = {int(z)} m (Line Ensemble)"] = scaled_t

    # =========================================================================
    # Render Overlaid Curves
    # =========================================================================
    plot_normalized_ttd_comparison(
        data_dict=normalized_data,
        xlabel=xlabel_final,
        bin_width=bin_w,
        max_scaled_t=max_t,
        save_path=output_fig,
        title=f"{case_name}: Spanwise-Ensemble Normalized TTD ({scaling_method.capitalize()} Scaling)",
        density=False   # raw counts (professor's request, 2026-10-05)
    )

if __name__ == "__main__":
    main()