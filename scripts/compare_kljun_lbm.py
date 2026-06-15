import os
import sys
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.config_loader import load_json_config
from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from physics_core.footprint_processing import (
    smooth_footprint_grid, refine_footprint_grid, 
    get_contour_thresholds, merge_counts_with_positions, points_to_grid
)
from physics_core.kljun_wrapper import calculate_kljun_ffp_grid
from plotting_core.footprint_plots import plot_model_comparison

def main():
    # 1. Paths and Setup
    base_dir = r"Z:\Particle_PostProcess_Outputs\20260527_particle_flat_3072"
    pos_file = r"Z:\particle_position\particle_position.txt"
    params_path = r"../physics_core/metrics/schmid_params.json"
    lbm_profile_csv = r"Z:\20260527_output_flat_3072\prof00180000_0000.csv"
    output_dir = r"../figures/20260527_kljun_comparisons"
    os.makedirs(output_dir, exist_ok=True)
    
    x_bounds = [0, 1024]
    y_bounds = [0, 256]
    sensor_x = 600.0
    sensor_y = 128.0
    contour_levels = [0.8, 0.6, 0.4, 0.2]

    # 2. Load Parameters
    params = load_json_config(params_path)
    u_star = params["u_star"]
    z0 = params["z0"]
    sigma_v_dict = params["sigma_v"]
    sensor_heights = [10, 20, 30, 40, 48, 56]
    
    # Load LBM Vertical Profile to extract exact 'umean'
    df_lbm = pd.read_csv(lbm_profile_csv, skiprows=1, header=0)
    z_lbm = df_lbm['z'].values
    u_lbm = df_lbm['U'].values

    # Kljun specific Boundary Conditions
    h = 160.0       # Domain Height
    ol = 100000.0   # Extreme limit for Neutral Atmosphere
    wind_dir = 270.0 # Default wind dir for wind blowing from +x direction
    
    print("Loading source positions...")
    source_map = load_source_positions(pos_file)
    
    print("--- Commencing Kljun (2015) FFP vs LBM Comparison ---")
    
    for sz in sensor_heights:
        sz_str = str(sz)
        if sz_str not in sigma_v_dict:
            continue
            
        sigma_v = sigma_v_dict[sz_str]
        
        # Interpolate exact LBM U-mean at the current sensor height
        umean_zm = np.interp(sz, z_lbm, u_lbm)
        
        print(f"\nProcessing Z={sz}m (sigma_v={sigma_v:.4f}, umean={umean_zm:.2f} m/s)...")
        
        # ==========================================
        # STEP A: LOAD LBM DATA (Mirroring Schmid)
        # ==========================================
        csv_path = os.path.join(base_dir, "1200-1800_footprint", f"footprint_{int(sensor_x)}_{int(sensor_y)}_{sz}.csv")
        if not os.path.exists(csv_path):
            print(f"Skipping {csv_path} - not found.")
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
            zm=sz, z0=z0, umean=umean_zm, h=h, ol=ol, sigmav=sigma_v, ustar=u_star, wind_dir=wind_dir
        )
        kljun_thresholds = get_contour_thresholds(kljun_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)
        
        # ==========================================
        # STEP C: PLOT COMPARISON
        # ==========================================
        save_path = os.path.join(output_dir, f"side_by_side_lbm_kljun_z{sz}.png")
        plot_model_comparison(
            X=X_fine, Y=Y_fine, 
            lbm_pdf=lbm_pdf_fine, model_pdf=kljun_pdf_fine, 
            lbm_thresholds=lbm_thresholds, model_thresholds=kljun_thresholds,
            sensor_pos=(sensor_x, sensor_y), 
            title=f"Footprint Comparison: LBM vs Kljun FFP (Zm = {sz}m)",
            model_title="Kljun et al. (2015) FFP",
            save_path=save_path, x_bounds=x_bounds, y_bounds=y_bounds
        )
        print(f"  -> Saved FFP comparison to {save_path}")

if __name__ == "__main__":
    main()