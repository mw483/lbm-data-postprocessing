import os
import sys
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.config_loader import load_json_config
from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from data_loaders.lbm_parsers import XZMatrixParser  # <-- Imported your parser
from physics_core.footprint_processing import (
    smooth_footprint_grid, refine_footprint_grid, 
    get_contour_thresholds, merge_counts_with_positions, points_to_grid
)
from physics_core.kljun_wrapper import calculate_kljun_ffp_grid
from physics_core.turbulence import calc_sigma_v, calc_u_star
from plotting_core.footprint_plots import plot_model_comparison

def main():
    # 1. Paths and Setup
    sensor_size_x = 8
    sensor_size_y = 8
    sensor_size_z = 8

    base_dir = rf"Y:\Particle_PostProcess_Outputs\20260703_particle_flat_shortroughness\sensor_{sensor_size_x}x{sensor_size_y}x{sensor_size_z}"
    pos_file = r"Y:\particle_position\particle_position.txt"
    params_path = r"../physics_core/metrics/schmid_params.json"
    # lbm_profile_csv = r"Z:\20260527_output_flat_3072\prof00180000_0000.csv"

    # NEW: XZ Matrix Paths
    base_out = r"Y:\20260703_output_flat_shortroughness"
    um_csv = os.path.join(base_out, "xz_yav_um00180000_0000.csv")
    vm_csv = os.path.join(base_out, "xz_yav_vm00180000_0000.csv")
    vv_csv = os.path.join(base_out, "xz_yav_vv00180000_0000.csv")

    output_dir = rf"../figures/flat_domain/sensor_{sensor_size_x}x{sensor_size_y}x{sensor_size_z}/20260703_particle_flat_shortroughness"
    os.makedirs(output_dir, exist_ok=True)
    
    x_bounds = [0, 1280]
    y_bounds = [0, 256]
    sensor_x = 728.0
    sensor_y = 128.0
    contour_levels = [0.8, 0.6, 0.4, 0.2]

    # Grid properties for matrix indexing
    dx_lbm = 2.0
    dz_lbm = 2.0

    # 2. Load Parameters
    params = load_json_config(params_path)
    u_star = params["u_star"]
    z0 = params["z0"]
    # sigma_v_dict = params["sigma_v"]
    sensor_heights = [20]
    
    print("Loading Virtual Tower XZ fluid matrices...")
    um_mat = XZMatrixParser.parse_file(um_csv)
    vm_mat = XZMatrixParser.parse_file(vm_csv)
    vv_mat = XZMatrixParser.parse_file(vv_csv)
    
    if any(m is None for m in [um_mat, vm_mat, vv_mat]):
        print("[ERROR] Failed to load one or more XZ matrices. Exiting.")
        sys.exit(1)

    # Calculate the exact X index for the sensor (e.g., 600m / 2m = index 300)
    # Using int() combined with min() to ensure we don't accidentally index out of bounds
    x_idx = min(int(sensor_x / dx_lbm), um_mat.shape[1] - 1)

    # Kljun specific Boundary Conditions
    h = 160.0       # Domain Height
    ol = 100000.0   # Extreme limit for Neutral Atmosphere
    wind_dir = 270.0 # Default wind dir for wind blowing from +x direction
    
    print("Loading source positions...")
    source_map = load_source_positions(pos_file)
    
    print("--- Commencing Kljun (2015) FFP vs LBM (short roughness) Comparison ---")
    
    for sz in sensor_heights:
        # Calculate exact Z index
        # (Subtracting 1 in case Z=160m maps to index 79 rather than 80 on an 80-grid system)
        z_idx = min(int(sz / dz_lbm), um_mat.shape[0] - 1)

        # 1. Mean Wind Speed (Streamwise)
        umean_zm = um_mat[z_idx, x_idx]
        
        # 2. Local Lateral Turbulence (Reynolds Decomposition)
        vv_val = vv_mat[z_idx, x_idx]
        vm_val = vm_mat[z_idx, x_idx]
        sigma_v_local = calc_sigma_v(vv_val, vm_val)
        
        print(f"\nProcessing Z={sz}m | Virtual Tower Data:")
        print(f"  -> U_mean: {umean_zm:.2f} m/s, sigma_v: {sigma_v_local:.4f}, u*: {u_star:.4f}")
        
        # ==========================================
        # STEP A: LOAD LBM DATA
        # ==========================================
        csv_path = os.path.join(base_dir, "1200-1800_footprint", f"footprint_{int(sensor_x)}_{int(sensor_y)}_{sz}.csv")
        if not os.path.exists(csv_path):
            print(f"  [!] Skipping {csv_path} - not found.")
            continue
            
        count_map = load_footprint_counts(csv_path)
        x_pts, y_pts, counts = merge_counts_with_positions(source_map, count_map)
        
        X_low, Y_low, raw_pdf = points_to_grid(x_pts, y_pts, counts, dx=8.0, dy=8.0, x_bounds=x_bounds, y_bounds=y_bounds)
        
        target_sigma = 0.4 + (sz / 31.25)
        smoothed_pdf = smooth_footprint_grid(raw_pdf, dx=8.0, dy=8.0, sigma=target_sigma)
        
        X_fine, Y_fine, lbm_pdf_fine = refine_footprint_grid(
            X_low, Y_low, smoothed_pdf, x_bounds=x_bounds, y_bounds=y_bounds, target_res=1.0
        )
        lbm_thresholds = get_contour_thresholds(lbm_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)
        
        # ==========================================
        # STEP B: KLJUN 2015 FFP MODEL
        # ==========================================
        kljun_pdf_fine = calculate_kljun_ffp_grid(
            X_fine, Y_fine, sensor_x, sensor_y, 
            zm=sz, z0=z0, umean=umean_zm, h=h, ol=ol, sigmav=sigma_v_local, ustar=u_star, wind_dir=wind_dir
        )
        kljun_thresholds = get_contour_thresholds(kljun_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)
        
        # ==========================================
        # STEP C: PLOT COMPARISON
        # ==========================================
        save_path = os.path.join(output_dir, f"side_by_side_lbmShortRoughness_kljun_z{sz}.png")
        plot_model_comparison(
            X=X_fine, Y=Y_fine, 
            lbm_pdf=lbm_pdf_fine, model_pdf=kljun_pdf_fine, 
            lbm_thresholds=lbm_thresholds, model_thresholds=kljun_thresholds,
            sensor_pos=(sensor_x, sensor_y), 
            title=f"Footprint Comparison: LBM (Short Roughness) vs Kljun FFP (Zm = {sz}m), {sensor_size_x}x{sensor_size_y}x{sensor_size_z} Sensor",
            model_title="Kljun et al. (2015) FFP",
            save_path=save_path, x_bounds=x_bounds, y_bounds=y_bounds
        )
        print(f"  -> Saved FFP comparison to {save_path}")

if __name__ == "__main__":
    main()