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

def create_vectorfield(u_matrix, v_matrix, z_height, case_name, output_dir, stride=8, zoom_config=None):
    """Generates a clean, standardized vector field for a 2D velocity array."""
    try:
        fig, ax = plt.subplots(figsize=(10, 4)) # Wider aspect ratio for 1024x256 domains

        # 1. Calculate velocity magnitude for background sequential coloring
        magnitude = np.sqrt(u_matrix**2 + v_matrix**2)
        im = ax.imshow(magnitude, cmap='viridis', origin='lower')
        
        # 2. Create Building Background (0 = Building/Black, 1 = Fluid/White)
        # Condition: black if and only if u_matrix == 0
        bg_matrix = np.where(u_matrix == 0, 0, 1)
        building_cmap = ListedColormap(['black', 'white'])
        ax.imshow(bg_matrix, cmap=building_cmap, origin='lower')

        # 3. Generate grid coordinates and downsample with a stride for readability
        ny, nx = u_matrix.shape
        X, Y = np.meshgrid(np.arange(nx), np.arange(ny))

        # Downsample with stride to increase/decrease vector density
        s = slice(None, None, stride)
        X_s, Y_s = X[s, s], Y[s, s]
        U_s, V_s = u_matrix[s, s], v_matrix[s, s]
        M_s = magnitude[s, s]

        # Filter out vectors inside the building blocks (where magnitude is 0)
        fluid_mask = M_s > 0
        
        # 4. Plot colored arrows on the white canvas
        # Passing M_s[fluid_mask] as the 5th argument maps arrow colors to their speed
        im = ax.quiver(
            X_s[fluid_mask], Y_s[fluid_mask], 
            U_s[fluid_mask], V_s[fluid_mask], 
            M_s[fluid_mask], 
            cmap='viridis',      # 'plasma' or 'inferno' stand out beautifully on white backgrounds
            pivot='middle', 
            scale=30,           # Adjust scale if arrows look too long or short
            width=0.005        # Slightly thicker lines for visibility
        )

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Velocity Magnitude (m/s)', fontsize=12)

        # Apply basic formatting
        ax.set_title(f'XY Vector Field (Case: {case_name}, Z={z_height})', fontsize=14)
        ax.set_xlabel('X-Axis (Grid Index)', fontsize=12)
        ax.set_ylabel('Y-Axis (Grid Index)', fontsize=12)

        # 3. Apply the Zoom Config via function defined in utils.py (The anti-God-Script technique)
        apply_axis_zoom(ax, zoom_config)

        # Save and close
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"vectorfield_{case_name}_z{z_height}.png")
        fig.tight_layout()
        fig.savefig(output_path, dpi=300)
        plt.close(fig)
        print(f"[SUCCESS] Saved vectorfield to: {output_path}")

    except Exception as e:
        print(f"[ERROR] Failed to generate heatmap for {case_name}: {e}")


if __name__ == "__main__":
    # --- 1. Configuration ---
    # Map your simulation cases to their specific Rclone file paths
    simulation_cases = {
        "Takamatsu_1" : {
        "u_path": "Z:/20260525_output_takamatsu/xy_um00120000_0000.csv",
        "v_path": "Z:/20260525_output_takamatsu/xy_vm00120000_0000.csv"
    }
    }
    
    
    # The specific height layer you want to visualize
    target_z = 4.0 
    output_folder = "C:/Users/Mikael Wijaya/Documents/GitHub/lbm-data-postprocessing/figures"

    # Initialize the parser we built earlier
    parser = XYStackedParser(ny_rows=160)

    # --- 2. Execution Loop ---
    for case_name, paths in simulation_cases.items():
        print(f"Processing {case_name}...")
        try:
            # Parse the stacked CSV of both u and v into a dictionary of 2D arrays
            u_data = parser.parse_file(paths["u_path"])
            v_data = parser.parse_file(paths["v_path"])

            if target_z in u_data and target_z in v_data:
                # Zoom configuration: 80x80 grid centered at a building (e.g., x=150, y=80)
                zoom_settings = {"x_center": 170, "y_center": 80, "grid_size": 80, "enabled": True}

                # Pass only the 2D array for the target height into the plotter
                create_vectorfield(
                u_matrix=u_data[target_z], 
                v_matrix=v_data[target_z], 
                z_height=target_z, 
                case_name=case_name, 
                output_dir=output_folder,
                stride=4, # Plot an arrow every 8 grid points to avoid a black block
                zoom_config=zoom_settings
                )
            else:
                available = list(u_data.keys())
                print(f"[WARNING] Z={target_z} not found in {u_data} and/or {v_data}. Available: {available}")

        except FileNotFoundError:
            print(f"[ERROR] Could not find {u_data} and/or {v_data}. Is your Rclone Z: drive mounted?")