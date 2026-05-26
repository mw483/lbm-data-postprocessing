import sys
import os
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

# Adjust path to import modules from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.lbm_parsers import XYStackedParser
from plotting_core.utils import apply_axis_zoom
# from plotting_core.theme import REPORT_THEME # You can wire this up later

def create_heatmap(data_matrix, z_height, case_name, output_dir, zoom_config=None):
    """Generates a clean, standardized heatmap for a 2D velocity array."""
    try:
        fig, ax = plt.subplots(figsize=(10, 4)) # Wider aspect ratio for 1024x256 domains

        # 1. Create Building Background (0 = Building/Black, 1 = Fluid/White)
        bg_matrix = np.where(data_matrix == 0, 0, 1)
        building_cmap = ListedColormap(['black', 'white'])
        ax.imshow(bg_matrix, cmap=building_cmap, origin='lower')

        # 2. Identify fluid cells (anywhere velocity is not exactly 0)
        fluid_mask = data_matrix != 0

        # 3. Create a plotting matrix where buildings become NaN (transparent)
        # If true, keep data_matrix value; if false (building), make it np.nan
        masked_data = np.where(fluid_mask, data_matrix, np.nan)

        # 4. Overlay the fluid velocity heatmap seamlessly on top
        im = ax.imshow(masked_data, cmap='jet', origin='lower')

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Mean V-Velocity (m/s)', fontsize=12)

        # Apply basic formatting
        ax.set_title(f'XY Wind Velocity (Case: {case_name}, Z={z_height})', fontsize=14)
        ax.set_xlabel('X-Axis (Grid Index)', fontsize=12)
        ax.set_ylabel('Y-Axis (Grid Index)', fontsize=12)

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Apply the Zoom Config via function defined in utils.py (The anti-God-Script technique)
        apply_axis_zoom(ax, zoom_config)

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
        "Takamatsu_1_v_600": "Z:/20260525_output_takamatsu/xy_vm00060000_0000.csv",
        "Takamatsu_1_v_1200": "Z:/20260525_output_takamatsu/xy_vm00120000_0000.csv"
    }
    
    # The specific height layer you want to visualize
    target_z = 4.0 
    output_folder = "C:/Users/Mikael Wijaya/Documents/GitHub/lbm-data-postprocessing/figures"

    # Initialize the parser we built earlier
    parser = XYStackedParser(ny_rows=160)

    # --- 2. Execution Loop ---
    for case_name, file_path in simulation_cases.items():
        print(f"Processing {case_name}...")
        try:
            # Parse the stacked CSV into a dictionary of 2D arrays
            wind_data = parser.parse_file(file_path)

            if target_z in wind_data:
                # Pass only the 2D array for the target height into the plotter
                zoom_settings = {"x_center": 170, "y_center": 80, "grid_size": 80, "enabled": True}
                create_heatmap(wind_data[target_z], target_z, case_name, output_folder, zoom_config=zoom_settings)
            else:
                available = list(wind_data.keys())
                print(f"[WARNING] Z={target_z} not found in {file_path}. Available: {available}")

        except FileNotFoundError:
            print(f"[ERROR] Could not find {file_path}. Is your Rclone Z: drive mounted?")