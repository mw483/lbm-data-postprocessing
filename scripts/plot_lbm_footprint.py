import os
import sys

# Add the project root to the system path to allow module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from physics_core.footprint_processing import merge_counts_with_positions
from plotting_core.footprint_plots import plot_absolute_footprint

def main():
    # --- Configuration ---
    # Update these base paths to match your local/mounted Z: drive setup
    base_dir = r"Z:\Particle_PostProcess_Outputs\20260527_particle_flat_3072\sensor_8x8x8"
    pos_file = r"Z:\particle_position\particle_position.txt"
    output_dir = r"../figures/flat_domain/sensor_8x8x8/20260527_flat_footprints/raw_footprints"
    
    # List of sensors to process (x, y, z)
    sensors = [
        (600, 128, 56),
        (600, 96, 56),
        (600, 160, 56)
    ]
    
    # Known domain bounds: 512 grids * 2m = 1024m (X), 128 grids * 2m = 256m (Y)
    domain_bounds = [0, 1024, 0, 256] 
    
    # 1. Load the universal position map once to save time
    print("Loading source positions...")
    source_map = load_source_positions(pos_file)
    print(f"Loaded {len(source_map)} sources.")
    
    # 2. Loop through each sensor case
    for sx, sy, sz in sensors:
        csv_name = f"footprint_{sx}_{sy}_{sz}.csv"
        csv_path = os.path.join(base_dir, "1200-1800_footprint", csv_name)
        save_path = os.path.join(output_dir, f"raw_footprint_x{sx}_y{sy}_z{sz}.png")
        
        print(f"\nProcessing {csv_name}...")
        
        # Load counts
        count_map = load_footprint_counts(csv_path)
        
        # Merge data
        x, y, counts = merge_counts_with_positions(source_map, count_map)
        print(f"Found {len(x)} active sources contributing to sensor.")
        
        # Plot
        plot_absolute_footprint(x, y, counts, 
                                sensor_x=sx, sensor_y=sy, 
                                save_path=save_path, 
                                domain_extent=domain_bounds)

if __name__ == "__main__":
    main()