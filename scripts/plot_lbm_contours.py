import os
import sys
import csv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from physics_core.footprint_processing import merge_counts_with_positions, points_to_grid, get_contour_thresholds, extract_peak_metrics, smooth_footprint_grid
from plotting_core.comparative_plots import plot_footprint_with_contours

def main():
    base_dir = r"Z:\Particle_PostProcess_Outputs\20260527_particle_flat_3072"
    pos_file = r"Z:\particle_position\particle_position.txt"
    output_dir = r"../figures/20260527_flat_footprints/contour_analysis"
    
    sensors = [
        (600, 128, 10),
        (600, 128, 20),
        (600, 128, 30),
        (600, 128, 40),
        (600, 128, 50),
    ]
    
    # Parameters for the Eulerian Grid mapping
    dx = dy = 8.0
    x_bounds = [0, 1024]
    y_bounds = [0, 256]
    contour_levels = [0.2, 0.4, 0.6, 0.8] # Set contour %
    
    # Prepare the CSV Tracker
    os.makedirs(output_dir, exist_ok=True)
    tracker_csv = os.path.join(output_dir, "peak_distance_metrics.csv")
    
    print("Loading source positions...")
    source_map = load_source_positions(pos_file)
    
    with open(tracker_csv, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Sensor_X', 'Sensor_Y', 'Sensor_Z', 'Peak_X', 'Peak_Y', 'Peak_Distance_m', 'Peak_Density_m2'])
        
        for sx, sy, sz in sensors:
            csv_path = os.path.join(base_dir, "1200-1800_footprint", f"footprint_{sx}_{sy}_{sz}.csv")
            if not os.path.exists(csv_path):
                print(f"Skipping {csv_path} - not found.")
                continue
                
            print(f"\nProcessing Sensor Z={sz}...")
            count_map = load_footprint_counts(csv_path)
            x_pts, y_pts, counts = merge_counts_with_positions(source_map, count_map)
            
            # 1. Convert scattered data to an 8-meter raw grid
            X, Y, pdf_grid = points_to_grid(x_pts, y_pts, counts, dx, dy, x_bounds, y_bounds)
            
            # [UPDATED]: Calculate a dynamic sigma based on the sensor height
            # Z=10 -> sigma=0.72 (crisp), Z=20 -> sigma=1.04, Z=50 -> sigma=2.0 (fills holes)
            target_sigma = 0.4 + (sz / 31.25) 
            
            print(f"  -> Applying 2D Gaussian filter with sigma={target_sigma:.2f} cells...")
            pdf_grid = smooth_footprint_grid(pdf_grid, dx, dy, sigma=target_sigma)

            # 2. Extract Math Metrics from the smoothed continuous surface
            thresholds = get_contour_thresholds(pdf_grid, dx, dy, levels=contour_levels)
            peak_x, peak_y, peak_dist, peak_val = extract_peak_metrics(X, Y, pdf_grid, sensor_x=sx)
            
            print(f"  -> Smoothed Peak located {peak_dist:.1f}m upwind.")
            writer.writerow([sx, sy, sz, peak_x, peak_y, round(peak_dist, 2), peak_val])
            
            # 3. Plot overlay
            save_path = os.path.join(output_dir, f"lbm_contours_z{sz}.png")
            plot_footprint_with_contours(X, Y, pdf_grid, thresholds, contour_levels, 
                                         sensor_pos=(sx, sy), save_path=save_path,
                                         title=f"LBM Smoothed Footprint Density & Contours (Z_m={sz}m)")
            print(f"  -> Saved contour plot.")

    print(f"\nAll processing complete. Metrics saved to {tracker_csv}")

if __name__ == "__main__":
    main()