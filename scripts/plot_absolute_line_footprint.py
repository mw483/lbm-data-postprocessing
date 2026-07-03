# scripts/run_absolute_line_footprint.py
import os
import sys
import numpy as np

# Apply your exact modular path and repository management configuration strings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(script_dir, "../figures/spanwise_analysis/cubes/height20"))

# Import your verified modular data loaders and processors
from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from physics_core.footprint_processing import (
    merge_counts_with_positions,
    points_to_grid,
    smooth_footprint_grid
)
# Import your newly appended specialized line visualization core tool
from plotting_core.footprint_plots import plot_absolute_line_integrated_footprint


def main():
    print("=================================================================")
    print("     LBM ABSOLUTE LINE-INTEGRATED FOOTPRINT GENERATOR            ")
    print("=================================================================\n")

    # --- 1. Environmental & Directory Path Configurations ---
    base_dir = "Y:/Particle_PostProcess_Outputs/20260612_particle_cube_3072/sensor_8x8x8/1200-1800_footprint"
    source_dir = "Y:/particle_position"
    source_file = os.path.join(source_dir, "pos_cube_3072.txt")
    
    # Targeted output file inside your specified figures hierarchy
    output_image = os.path.join(repo_root, "absolute_line_integrated_footprint.png")
    os.makedirs(os.path.dirname(output_image), exist_ok=True)
    
    # Simulation Spatial Bounds Configuration
    domain_extent = [0.0, 1024.0, 0.0, 256.0]
    sensor_x_line = 600.0  # Streamwise position of the sensor array
    
    # Regular Grid Resolution Configuration for the Heatmap Canvas
    dx, dy = 2.0, 2.0  # [m]
    x_bounds = [0.0, 1024.0]
    y_bounds_abs = [0.0, 256.0]
    
    # The explicit sequence of the 33 spanwise sensor files
    sensor_y_coords = np.arange(0, 257, 8)
    
    # --- 2. Load Global Source Coordinates ---
    if not os.path.exists(source_file):
        print(f"[ERROR] Global source file missing at: {source_file}")
        return
        
    print("[-] Step 1/4: Loading global source positions map...")
    source_map = load_source_positions(source_file)
    
    # Global directory map to accumulate absolute counts across all crosswind sensors
    accumulated_count_map = {}

    # --- 3. Absolute Data Accumulation Engine ---
    print(f"[-] Step 2/4: Accumulating raw counts across all {len(sensor_y_coords)} files...")
    for y_sensor in sensor_y_coords:
        filename = f"footprint_600_{y_sensor}_20.csv"
        filepath = os.path.join(base_dir, filename)
        
        if not os.path.exists(filepath):
            continue
            
        count_map = load_footprint_counts(filepath)
        
        # Sequentially pile absolute particle weights into our master tracker map
        for source_id, count in count_map.items():
            if count > 0:
                accumulated_count_map[source_id] = accumulated_count_map.get(source_id, 0.0) + count

    if not accumulated_count_map:
        print("[ERROR] No particle counts were collected. Aborting pipeline process.")
        return

    # --- 4. Processing, Gridding & Smoothing Core ---
    print("[-] Step 3/4: Transforming scattered points into an Eulerian grid...")
    x_abs, y_abs, global_counts = merge_counts_with_positions(source_map, accumulated_count_map)
    
    # Convert absolute points list into a synchronized 2D grid matrix canvas
    X, Y, pdf_grid = points_to_grid(
        x_abs, y_abs, global_counts, 
        dx, dy, x_bounds, y_bounds_abs
    )
    
    print("[-] Step 4/4: Applying Gaussian blur filter across the absolute matrix layout...")
    # 2. CORE UPDATE: Incorporate the filter. sigma=4.5 perfectly fills the 8m physical source gaps
    pdf_grid_smoothed = smooth_footprint_grid(pdf_grid, dx, dy, sigma=4.5)
    
    print("[-] Shipping smoothed matrix directly to plotting core...")
    plot_absolute_line_integrated_footprint(
        X=X, Y=Y,
        pdf_grid=pdf_grid_smoothed,
        sensor_x=sensor_x_line,
        save_path=output_image,
        domain_extent=domain_extent
    )
    
    print("\n=================================================================")
    print("[✓] SUCCESS: Absolute line-integrated report exported to:")
    print(f"    {output_image}")
    print("=================================================================")


if __name__ == "__main__":
    main()