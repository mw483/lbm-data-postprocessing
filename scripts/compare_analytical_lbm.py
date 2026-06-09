import os
import sys
import numpy as np

# Add project root to path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.config_loader import load_json_config
from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from physics_core.schmid_model import calculate_analytical_footprint
from physics_core.footprint_processing import (
    smooth_footprint_grid, 
    refine_footprint_grid, 
    get_contour_thresholds,
    merge_counts_with_positions,
    points_to_grid
)
from plotting_core.footprint_plots import plot_footprint_overlay


def main():
    # 1. Paths and Setup
    base_dir = r"Z:\Particle_PostProcess_Outputs\20260527_particle_flat_3072"
    pos_file = r"Z:\particle_position\particle_position.txt"
    params_path = r"../physics_core/metrics/schmid_params.json"
    output_dir = r"../figures/20260527_schmid_comparisons"
    os.makedirs(output_dir, exist_ok=True)
    
    x_bounds = [0, 1024]
    y_bounds = [0, 256]
    sensor_x = 600
    sensor_y = 128
    contour_levels = [0.2, 0.4, 0.6, 0.8] # Set contour %

    # 2. Load Atmospheric Parameters
    params = load_json_config(params_path)
    u_star = params["u_star"]
    z0 = params["z0"]
    sigma_v_dict = params["sigma_v"]
    
    # Assuming these are the exact physical heights you processed
    sensor_heights = [10, 20, 30, 40, 48, 56]

    print("Loading source positions...")
    source_map = load_source_positions(pos_file)
    
    print("--- Commencing Schmid Analytical vs LBM Comparison ---")
    
    for sz in sensor_heights:
        sz_str = str(sz)
        if sz_str not in sigma_v_dict:
            print(f"Skipping Z={sz}m (No sigma_v found in params).")
            continue
            
        sigma_v = sigma_v_dict[sz_str]
        print(f"\nProcessing Sensor Z={sz}m (sigma_v = {sigma_v:.4f})...")
        
        # ==========================================================
        # STEP A: LOAD AND PROCESS LBM DATA
        # ==========================================================
        # [Insert your data loading logic here to get X_low, Y_low, and raw pdf_grid]
        # Example:
        csv_path = os.path.join(base_dir, "1200-1800_footprint", f"footprint_{sensor_x}_{sensor_y}_{sz}.csv")
        if not os.path.exists(csv_path):
            print(f"Skipping {csv_path} - not found.")
            continue
            
        print(f"\nProcessing Sensor Z={sz}...")
        count_map = load_footprint_counts(csv_path)
        x_pts, y_pts, counts = merge_counts_with_positions(source_map, count_map)
        
        # Step A: Map to raw 8-meter grid (matches our source physics)
        X_low, Y_low, raw_pdf = points_to_grid(x_pts, y_pts, counts, dx=8.0, dy=8.0, 
                                                x_bounds=x_bounds, y_bounds=y_bounds)
        
        # For demonstration, assume X_low, Y_low, and raw_pdf are loaded here.
        # Ensure your LBM matrix is properly normalized to sum to 1.0.
        
        # Apply Gaussian Smoothing
        target_sigma = 0.4 + (sz / 31.25)
        smoothed_pdf = smooth_footprint_grid(raw_pdf, dx=8.0, dy=8.0, sigma=target_sigma)
        
        # Apply Bivariate Spline Refinement (1.0m resolution)
        X_fine, Y_fine, lbm_pdf_fine = refine_footprint_grid(
            X_low, Y_low, smoothed_pdf, 
            x_bounds=x_bounds, y_bounds=y_bounds, target_res=1.0
        )
        
        # Extract LBM 80% Threshold
        # get_contour_thresholds returns levels [0.2, 0.4, 0.6, 0.8], so index 3 is 80%
        lbm_thresholds = get_contour_thresholds(lbm_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)
        lbm_thresh_80 = lbm_thresholds[3]
        
        # ==========================================================
        # STEP B: GENERATE SCHMID ANALYTICAL DATA
        # ==========================================================
        # Calculate Schmid footprint directly onto the same high-res refined grid
        schmid_pdf_fine = calculate_analytical_footprint(
            X=X_fine, Y=Y_fine, 
            sensor_x=sensor_x, sensor_y=sensor_y, 
            zm=sz, u_star=u_star, z0=z0, sigma_v=sigma_v
        )
        
        # [NEW CODE: BOUNDARY NORMALIZATION]
        # Force the Schmid probability mass inside the wind tunnel to equal 1.0
        # This matches the LBM normalization and allows contours to generate!
        schmid_mass_in_domain = np.sum(schmid_pdf_fine) * (1.0 * 1.0)
        if schmid_mass_in_domain > 0:
            schmid_pdf_fine = schmid_pdf_fine / schmid_mass_in_domain

        # Extract Schmid 80% Threshold
        schmid_thresholds = get_contour_thresholds(schmid_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)
        schmid_thresh_80 = schmid_thresholds[3]

        # ==========================================================
        # [NEW] DIAGNOSTIC PROBE
        # ==========================================================
        schmid_mass = np.sum(schmid_pdf_fine) * (1.0 * 1.0)
        schmid_max = np.max(schmid_pdf_fine)
        print(f"    [DEBUG] Schmid Total Mass in Grid: {schmid_mass:.4f}")
        print(f"    [DEBUG] Schmid Max Density: {schmid_max:.2e}")
        print(f"    [DEBUG] Schmid 80% Threshold: {schmid_thresh_80:.2e}")
        
        if schmid_thresh_80 == schmid_max:
            print("    [WARNING] Threshold collapsed to Maximum! Contour will be invisible.")
        if np.isnan(schmid_mass) or schmid_mass == 0:
            print("    [FATAL] Schmid matrix is empty or contains NaNs!")
        
        # ==========================================================
        # STEP C: VISUAL OVERLAY
        # ==========================================================
        save_path = os.path.join(output_dir, f"overlay_lbm_schmid_z{sz}.png")
        plot_footprint_overlay(
            X=X_fine, Y=Y_fine, 
            lbm_pdf=lbm_pdf_fine, schmid_pdf=schmid_pdf_fine, 
            lbm_thresh=lbm_thresh_80, schmid_thresh=schmid_thresh_80,
            sensor_pos=(sensor_x, sensor_y), 
            title=f"Footprint Overlay: LBM vs Schmid (Zm = {sz}m)", 
            save_path=save_path, x_bounds=x_bounds, y_bounds=y_bounds
        )
        print(f"  -> Saved overlay to {save_path}")

if __name__ == "__main__":
    main()