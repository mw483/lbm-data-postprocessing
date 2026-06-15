import os
import sys
import glob
import re

# Ensure Python can find the modular packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.footprint_io import load_footprint_counts
from plotting_core.sensitivity_plots import plot_vertical_detection_profile

def main():
    # 1. Paths (Using the newly planned directory architecture)
    input_dir = r"Z:\Particle_PostProcess_Outputs\20260527_particle_flat_3072\sensor_40x40x8\1200-1800_footprint"
    output_dir = r"../figures/flat_domain/sensor_40x40x8/sensitivity"
    
    # Find all footprint CSVs for the specific sensor X, Y location
    sensor_x, sensor_y = 600, 128
    search_pattern = os.path.join(input_dir, f"footprint_{sensor_x}_{sensor_y}_*.csv")
    csv_files = glob.glob(search_pattern)
    
    if not csv_files:
        print(f"[ERROR] No CSV files found in {input_dir}")
        sys.exit(1)
        
    print(f"Found {len(csv_files)} footprint files. Extracting counts...")
    
    data_points = []
    
    # Regex to extract the Z height from the filename (e.g., footprint_600_128_10.csv)
    filename_regex = re.compile(rf"footprint_{sensor_x}_{sensor_y}_(\d+)\.csv")
    
    # 2. Process Files
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        match = filename_regex.match(filename)
        
        if match:
            z_height = int(match.group(1))
            
            # Load the count dictionary {source_id: count}
            count_map = load_footprint_counts(filepath)
            
            # Sum all values to get the total particles detected
            total_particles = sum(count_map.values())
            
            data_points.append((z_height, total_particles))
            print(f"  Z = {z_height:2d}m  -->  {total_particles:8f} particles")
            
    # 3. Sort by Height (Z)
    data_points.sort(key=lambda x: x[0])
    
    # Unpack into separate lists for plotting
    z_heights = [pt[0] for pt in data_points]
    total_counts = [pt[1] for pt in data_points]
    
    # 4. Generate Plot
    save_path = os.path.join(output_dir, "vertical_detection_profile.png")
    title = f"Particle Detection Profile (Sensor: 40x40x8m at X={sensor_x}, Y={sensor_y})"
    
    plot_vertical_detection_profile(z_heights, total_counts, title, save_path)
    
    print(f"\nSuccess! Saved vertical profile to: {save_path}")

if __name__ == "__main__":
    main()