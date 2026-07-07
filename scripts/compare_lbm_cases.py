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
    sensor_size_x = 8
    sensor_size_y = 8
    sensor_size_z = 8

    base_dir = r"Y:\Particle_PostProcess_Outputs"
    
    pos_file1 = r"Y:\particle_position\pos_flat_3072.txt"
    pos_file2 = r"Y:\particle_position\pos_flat_3072_shortroughness.txt"

    case_paths = {"default_flat": "20260527_particle_flat_3072",
                  "halfVSGS_flat": "20260619_particle_flat_halfVSGS",
                  "shortRoughness_flat": "20260703_particle_flat_shortroughness"}

    sensor_paths = {"8x8x8": "sensor_8x8x8",
                    "40x40x8": "sensor_40x40x8"}

    output_dir = rf"../figures/flat_domain/sensor_{sensor_size_x}x{sensor_size_y}x{sensor_size_z}/LBM_Case_comparisons"
    os.makedirs(output_dir, exist_ok=True)

    # Establish the case conditions:
    case1_name = "default_flat"
    case2_name = "shortRoughness_flat"
    
    x_bounds1 = [0, 1024]
    y_bounds1 = [0, 256]

    x_bounds2 = [128, 1152]
    y_bounds2 = [0, 256]

    sensor_x1 = 600.0
    sensor_y1 = 128.0

    sensor_x2 = 728.0
    sensor_y2 = 128.0

    contour_levels = [0.8, 0.6, 0.4, 0.2]

    # sigma_v_dict = params["sigma_v"]
    sensor_heights = [10, 20, 30, 40]
    
    print("Loading source positions...")
    source1_map = load_source_positions(pos_file1)
    source2_map = load_source_positions(pos_file2)
    
    print(f"--- Commencing LBM Case Comparison ---")
    
    for sz in sensor_heights:

        target_sigma = 0.4 + (sz / 25.0)
        # ==========================================
        # STEP A: LOAD LBM CASE 1 DATA
        # ==========================================
        csv1_path = os.path.join(base_dir, case_paths[case1_name], sensor_paths[f"{sensor_size_x}x{sensor_size_y}x{sensor_size_z}"], "1200-1800_footprint", f"footprint_{int(sensor_x1)}_{int(sensor_y1)}_{sz}.csv")
        if not os.path.exists(csv1_path):
            print(f"  [!] Skipping {csv1_path} - not found.")
            continue
            
        count1_map = load_footprint_counts(csv1_path)
        x1_pts, y1_pts, counts1 = merge_counts_with_positions(source1_map, count1_map)
        
        X1_low, Y1_low, raw1_pdf = points_to_grid(x1_pts, y1_pts, counts1, dx=8.0, dy=8.0, x_bounds=x_bounds1, y_bounds=y_bounds1)

        smoothed1_pdf = smooth_footprint_grid(raw1_pdf, dx=8.0, dy=8.0, sigma=target_sigma)
        
        X1_fine, Y1_fine, lbm1_pdf_fine = refine_footprint_grid(
            X1_low, Y1_low, smoothed1_pdf, x_bounds=x_bounds1, y_bounds=y_bounds1, target_res=1.0
        )
        lbm1_thresholds = get_contour_thresholds(lbm1_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)

        # ==========================================
        # STEP B: LOAD LBM CASE 2 DATA
        # ==========================================
        csv2_path = os.path.join(base_dir, case_paths[case2_name], sensor_paths[f"{sensor_size_x}x{sensor_size_y}x{sensor_size_z}"], "1200-1800_footprint", f"footprint_{int(sensor_x2)}_{int(sensor_y2)}_{sz}.csv")
        if not os.path.exists(csv2_path):
            print(f"  [!] Skipping {csv2_path} - not found.")
            continue
            
        count2_map = load_footprint_counts(csv2_path)
        x2_pts, y2_pts, counts2 = merge_counts_with_positions(source2_map, count2_map)
        
        X2_low, Y2_low, raw2_pdf = points_to_grid(x2_pts, y2_pts, counts2, dx=8.0, dy=8.0, x_bounds=x_bounds2, y_bounds=y_bounds2)

        smoothed2_pdf = smooth_footprint_grid(raw2_pdf, dx=8.0, dy=8.0, sigma=target_sigma)
        
        X2_fine, Y2_fine, lbm2_pdf_fine = refine_footprint_grid(
            X2_low, Y2_low, smoothed2_pdf, x_bounds=x_bounds2, y_bounds=y_bounds2, target_res=1.0
        )
        lbm2_thresholds = get_contour_thresholds(lbm2_pdf_fine, dx=1.0, dy=1.0, levels=contour_levels)
        
        # ==========================================
        # STEP C: PLOT COMPARISON
        # ==========================================
        save_path = os.path.join(output_dir, f"side_by_side_{case1_name}_{case2_name}_z{sz}.png")
        plot_lbm_comparison(
            X1=X1_fine, Y1=Y1_fine, X2=X2_fine, Y2=Y2_fine, 
            lbm1_pdf=lbm1_pdf_fine, lbm2_pdf=lbm2_pdf_fine, 
            lbm1_thresholds=lbm1_thresholds, lbm2_thresholds=lbm2_thresholds,
            sensor_pos1=(sensor_x1, sensor_y1), sensor_pos2=(sensor_x2, sensor_y2), 
            title=f"LBM Footprint Comparison: {case1_name} vs {case2_name}, {sensor_size_x}x{sensor_size_y}x{sensor_size_z} Sensor",
            case1_title=case1_name, case2_title=case2_name,
            save_path=save_path,
            x_bounds1=x_bounds1, y_bounds1=y_bounds1, 
            x_bounds2=x_bounds2, y_bounds2=y_bounds2
        )
        print(f"  -> Saved LBM Cases comparison to {save_path}")

if __name__ == "__main__":
    main()