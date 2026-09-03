import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from data_loaders.particle_io import extract_hit_list_by_plane
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
    dt_output = 1.0
    scaling_method = "no_normalization"  # Options: "median", "advective", "eddy_turnover", "no_normalization"

    # Set parameters conditionally based on the method
    if scaling_method == "no_normalization":
        bin_w = 4.0        # 4-second histogram bins
        max_t = 600.0      # Physical second window
    else:
        bin_w = 0.04       # Dimensionless bin width
        max_t = 3.0        # Dimensionless scale limit
    
    # Target case: Switch between Flat and Cube cases
    case_name = "Cube Array"
    csv_path = Path(r"D:\lbm_results\Particle_PostProcess_Outputs\20260803_particle_cube_16mapproach\sensor_8x8x8\1200-1800_sensor_density\target_trajectories.csv")
    capsule_path = Path(r"D:\lbm_results\Particle_PostProcess_Outputs\20260803_particle_cube_16mapproach\sensor_8x8x8\1200-1800_sensor_density\sensor_hit_ids.txt")
    prof_path = Path(r"Z:\20260527_output_flat_3072\prof00180000_0000.csv") # Used if scaling_method="advective"[cite: 1]

    output_fig = REPO_ROOT / "figures" / "comparative" / f"ensemble_ttd_{case_name.lower().replace(' ', '_')}_{scaling_method}.png"

    # =========================================================================
    # Process Line-Ensembles per Height
    # =========================================================================
    normalized_data = {}
    xlabel_final = ""

    for z in heights:
        print(f"\n--- Processing Height Z = {z:.1f} m ---")
        
        # 1. Harvest particles across all Y sensors at (sensor_x, z)
        hit_ids = extract_hit_list_by_plane(capsule_path, target_x=sensor_x, target_z=z)
        print(f"  -> Intercepted {len(hit_ids):,} unique particles along spanwise line.")
        
        if len(hit_ids) == 0:
            continue

        # 2. Extract transit times using Polars
        delta_t = compute_transit_times(
            csv_path=csv_path,
            target_ids=hit_ids,
            dt_output=dt_output,
            separator=","
        )

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
        title=f"{case_name}: Spanwise-Ensemble Normalized TTD ({scaling_method.capitalize()} Scaling)"
    )

if __name__ == "__main__":
    main()