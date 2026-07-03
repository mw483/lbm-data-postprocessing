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
from plotting_core.footprint_plots import plot_lbm_comparison

def main():
    # 1. Paths and Setup
    sensor_size_x = 40
    sensor_size_y = 40
    sensor_size_z = 8

    base_dir = r"Z:\Particle_PostProcess_Outputs"
    pos_file = r"Z:\particle_position\particle_position.txt"

    case_paths = {"Default V_SGS": "20260527_particle_flat_3072",
                  "0.5 V_SGS": "20260619_particle_flat_halfVSGS"}

    sensor_paths = {"8x8x8": "sensor_8x8x8",
                    "40x40x8": "sensor_40x40x8"}

    output_dir = rf"../figures/flat_domain/sensor_{sensor_size_x}x{sensor_size_y}x{sensor_size_z}/LBM_Case_comparisons"
    os.makedirs(output_dir, exist_ok=True)
    
    x_bounds = [0, 1024]
    y_bounds = [0, 256]
    sensor_x = 600.0
    sensor_y = 128.0
    contour_levels = [0.8, 0.6, 0.4, 0.2]

    # sigma_v_dict = params["sigma_v"]
    sensor_heights = [10, 20, 30, 40]
    
    print("Loading source positions...")
    source_map = load_source_positions(pos_file)
    
    print("--- Commencing Default (1.0) V_SGS LBM vs 0.5 V_SGS LBM Comparison ---")
    
    for sz in sensor_heights:

        target_sigma = 0.4 + (sz / 31.25)
        # ==========================================
        # STEP A: LOAD LBM CASE 1 DATA
        # ==========================================
        csv1_path = os.path.join(base_dir, case_paths["Default V_SGS"], sensor_paths[f"{sensor_size_x}x{sensor_size_y}x{sensor_size_z}"], "1200-1800_footprint", f"footprint_{int(sensor_x)}_{int(sensor_y)}_{sz}.csv")
        if not os.path.exists(csv1_path):
            print(f"  [!] Skipping {csv1_path} - not found.")
            continue
            
        count1_map = load_footprint_counts(csv1_path)
        x1_pts, y1_pts, counts1 = merge_counts_with_positions(source_map, count1_map)
        
        X1_low, Y1_low, raw1_pdf = points_to_grid(x1_pts, y1_pts, counts1, dx=8.0, dy=8.0, x_bounds=x_bounds, y_bounds=y_bounds)

        smoothed1_pdf = smooth_footprint_grid(raw1_pdf, dx=8.0, dy=8.0, sigma=target_sigma)
        
        X1_fine, Y1_fine, lbm1_pdf_fine = refine_footprint_grid(
            X1_low, Y1_low, smoothed1_pdf, x_bounds=x_bounds, y_bounds=y_bounds, target_res=1.0
        )
        lbm1_thresholds = get_contour_thresholds(lbm1_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)

        # ==========================================
        # STEP B: LOAD LBM CASE 2 DATA
        # ==========================================
        csv2_path = os.path.join(base_dir, case_paths["0.5 V_SGS"], sensor_paths[f"{sensor_size_x}x{sensor_size_y}x{sensor_size_z}"], "1200-1800_footprint", f"footprint_{int(sensor_x)}_{int(sensor_y)}_{sz}.csv")
        if not os.path.exists(csv2_path):
            print(f"  [!] Skipping {csv2_path} - not found.")
            continue
            
        count2_map = load_footprint_counts(csv2_path)
        x2_pts, y2_pts, counts2 = merge_counts_with_positions(source_map, count2_map)
        
        X2_low, Y2_low, raw2_pdf = points_to_grid(x2_pts, y2_pts, counts2, dx=8.0, dy=8.0, x_bounds=x_bounds, y_bounds=y_bounds)

        smoothed2_pdf = smooth_footprint_grid(raw2_pdf, dx=8.0, dy=8.0, sigma=target_sigma)
        
        X2_fine, Y2_fine, lbm2_pdf_fine = refine_footprint_grid(
            X2_low, Y2_low, smoothed2_pdf, x_bounds=x_bounds, y_bounds=y_bounds, target_res=1.0
        )
        lbm2_thresholds = get_contour_thresholds(lbm2_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)
        
        # ==========================================
        # STEP C: PLOT COMPARISON
        # ==========================================
        save_path = os.path.join(output_dir, f"side_by_side_lbmDefault_lbmHalfV_z{sz}.png")
        plot_lbm_comparison(
            X=X1_fine, Y=Y1_fine, 
            lbm1_pdf=lbm1_pdf_fine, lbm2_pdf=lbm2_pdf_fine, 
            lbm1_thresholds=lbm1_thresholds, lbm2_thresholds=lbm2_thresholds,
            sensor_pos=(sensor_x, sensor_y), 
            title=f"LBM Footprint Comparison: Default (1.0) V_SGS vs 0.5 V_SGS, {sensor_size_x}x{sensor_size_y}x{sensor_size_z} Sensor",
            case1_title="Default (1.0) V_SGS", case2_title="0.5 V_SGS",
            save_path=save_path, x_bounds=x_bounds, y_bounds=y_bounds
        )
        print(f"  -> Saved LBM Cases comparison to {save_path}")

if __name__ == "__main__":
    main()