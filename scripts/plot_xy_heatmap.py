import sys
import os
import matplotlib.pyplot as plt
import numpy as np

# Adjust path to import modules from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.lbm_parsers import XYStackedParser
# from plotting_core.theme import REPORT_THEME # You can wire this up later

def create_heatmap(data_matrix, z_height, case_name, output_dir):
    """Generates a clean, standardized heatmap for a 2D velocity array."""
    try:
        fig, ax = plt.subplots(figsize=(10, 4)) # Wider aspect ratio for 1024x256 domains

        # origin='lower' ensures Y=0 is at the bottom, matching physical maps
        # cmap='viridis' is colorblind-friendly and standard for sequential data
        im = ax.imshow(data_matrix, cmap='viridis', origin='lower')

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Mean U-Velocity (m/s)', fontsize=12)

        # Apply basic formatting
        ax.set_title(f'XY Wind Velocity (Case: {case_name}, Z={z_height})', fontsize=14)
        ax.set_xlabel('X-Axis (Grid Index)', fontsize=12)
        ax.set_ylabel('Y-Axis (Grid Index)', fontsize=12)

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the figure cleanly
        output_path = os.path.join(output_dir, f"heatmap_{case_name}_z{z_height}.png")
        fig.tight_layout()
        fig.savefig(output_path, dpi=300) # 300 DPI for report-quality output
        plt.close(fig)

        print(f"[SUCCESS] Saved heatmap to: {output_path}")

    except Exception as e:
        print(f"[ERROR] Failed to generate heatmap for {case_name}: {e}")


if __name__ == "__main__":
    # --- 1. Configuration ---
    # Map your simulation cases to their specific Rclone file paths
    simulation_cases = {
        "Test_Domain_Cubes": "Z:/20260512_output_cubes_waypoints_test/xy_um00025000_0000.csv"
    }
    
    # The specific height layer you want to visualize
    target_z = 30.0 
    output_folder = "C:/Users/Mikael Wijaya/Documents/GitHub/lbm-data-postprocessing/figures"

    # Initialize the parser we built earlier
    parser = XYStackedParser(ny_rows=96)

    # --- 2. Execution Loop ---
    for case_name, file_path in simulation_cases.items():
        print(f"Processing {case_name}...")
        try:
            # Parse the stacked CSV into a dictionary of 2D arrays
            wind_data = parser.parse_file(file_path)

            if target_z in wind_data:
                # Pass only the 2D array for the target height into the plotter
                create_heatmap(wind_data[target_z], target_z, case_name, output_folder)
            else:
                available = list(wind_data.keys())
                print(f"[WARNING] Z={target_z} not found in {file_path}. Available: {available}")

        except FileNotFoundError:
            print(f"[ERROR] Could not find {file_path}. Is your Rclone Z: drive mounted?")