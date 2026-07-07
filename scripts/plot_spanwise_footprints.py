# scripts/run_spanwise_footprint_pipeline.py
import os
import sys
import numpy as np

# 1. Clean Path Management: Separate Python path tracking from file export paths
script_dir = os.path.dirname(os.path.abspath(__file__))
python_root = os.path.abspath(os.path.join(script_dir, '..'))
if python_root not in sys.path:
    sys.path.insert(0, python_root)

# Explicitly point to your professor's requested figures subdirectory
figure_output_dir = os.path.abspath(os.path.join(script_dir, "../figures/spanwise_analysis/flat_shortroughness/height20"))

# Import your verified modular I/O and Processing libraries
from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from physics_core.footprint_processing import (
    merge_counts_with_positions, 
    points_to_grid, 
    smooth_footprint_grid, 
    get_contour_thresholds
)
from plotting_core.footprint_plots import plot_lbm_comparison


def main():
    print("=================================================================")
    print("      LBM SPANWISE SENSOR FOOTPRINT ENSEMBLE PIPELINE            ")
    print("=================================================================\n")

    # --- 2. Environmental Configurations ---
    base_dir = "Y:/Particle_PostProcess_Outputs/20260703_particle_flat_shortroughness/sensor_8x8x8/1200-1800_footprint"
    source_dir = "Y:/particle_position"
    source_file = os.path.join(source_dir, "particle_position.txt")
    output_image = os.path.join(figure_output_dir, "spanwise_ensemble_comparison.png")
    
    # Ensure targeted figure subdirectory exists
    os.makedirs(os.path.dirname(output_image), exist_ok=True)
    
    # Physical Domain Attributes
    domain_width_y = 256.0  # [m]
    half_width_y = domain_width_y / 2.0
    
    # Eulerian Binning Resolution Configs
    dx, dy = 2.0, 2.0  # Grid mesh resolution [m]
    x_bounds = [0.0, 1280.0]
    y_bounds_ensemble = [0.0, 256.0]
    
    # Re-centered virtual sensor position coordinates
    sensor_pos = [728.0, 128.0] 
    
    # Sequence of the 33 spanwise sensor coordinates evaluated
    sensor_y_coords = np.arange(0, 257, 8)
    
    # --- 3. Load Global Source Coordinates ---
    if not os.path.exists(source_file):
        print(f"[ERROR] Global source location file missing at: {source_file}")
        return
        
    print("[-] Step 1/4: Loading global source positions map...")
    source_map = load_source_positions(source_file)
    
    all_sensor_grids = []
    central_sensor_grids = []

    # --- 4. Processing Loop & Coordinate Alignment ---
    print(f"[-] Step 2/4: Processing and re-centering {len(sensor_y_coords)} files...")
    for y_sensor in sensor_y_coords:
        filename = f"footprint_{str(int(sensor_pos[0]))}_{y_sensor}_20.csv"
        filepath = os.path.join(base_dir, filename)
        
        if not os.path.exists(filepath):
            continue
            
        # A. Load absolute counts via modular loader
        count_map = load_footprint_counts(filepath)
        x_abs, y_abs, counts = merge_counts_with_positions(source_map, count_map)
        
        if len(counts) == 0:
            continue
            
        # B. Periodic Relative Shift Math
        y_raw_relative = y_abs - y_sensor
        y_periodic_relative = ((y_raw_relative + half_width_y) % domain_width_y) - half_width_y
        
        # C. Re-Center Math to scale from [-128, 128] back to [0, 256] 
        y_ensemble_abs = y_periodic_relative + half_width_y
        
        # D. Map scattered points into high-resolution regular grid meshes
        X, Y, pdf_grid = points_to_grid(
            x_abs, y_ensemble_abs, counts, 
            dx, dy, x_bounds, y_bounds_ensemble
        )
        
        # CRITICAL FIX: Scale up sigma from 1.2 to 4.5 to eliminate the 8-meter source aliasing gap
        pdf_grid_smoothed = smooth_footprint_grid(pdf_grid, dx, dy, sigma=3)
        
        # E. Sort into corresponding ensemble masks
        all_sensor_grids.append(pdf_grid_smoothed)
        if 64 <= y_sensor <= 192:
            central_sensor_grids.append(pdf_grid_smoothed)

    if not all_sensor_grids:
        print("[ERROR] No footprint files could be processed. Aborting execution loop.")
        return

    # --- 5. Synthesis & Comparison Execution ---
    print("[-] Step 3/4: Synthesizing statistical ensemble averages...")
    ensemble_all = np.mean(all_sensor_grids, axis=0)
    ensemble_central = np.mean(central_sensor_grids, axis=0)
    
    print("[-] Step 4/4: Extracting high-contrast contour thresholds...")
    # Pass exactly 4 levels to safely match your library's 4 linestyles 
    contour_levels = [0.8, 0.6, 0.4, 0.2]
    thresh_all = get_contour_thresholds(ensemble_all, dx, dy, levels=contour_levels)
    thresh_central = get_contour_thresholds(ensemble_central, dx, dy, levels=contour_levels)
    
    print("[-] Executing plot core rendering...")
    plot_lbm_comparison(
        X=X, Y=Y, 
        lbm1_pdf=ensemble_all, 
        lbm2_pdf=ensemble_central, 
        lbm1_thresholds=thresh_all, 
        lbm2_thresholds=thresh_central,
        sensor_pos=sensor_pos,
        title="Spanwise Ensemble Footprint Analysis (Re-Centered at Y=128m)",
        case1_title="Full Domain Ensemble (All 33 Sensors Averaged)",
        case2_title="Central Baseline Ensemble (Sensors 64m to 192m Averaged)",
        save_path=output_image,
        x_bounds=x_bounds,
        y_bounds=y_bounds_ensemble
    )
    
    print("\n=================================================================")
    print("[✓] RUN COMPLETE: High-contrast footprint comparison saved to:")
    print(f"    {output_image}")
    print("=================================================================")


if __name__ == "__main__":
    main()