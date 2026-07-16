import os
import sys
from pathlib import Path

# Ensure the script can find the root repository directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the plotting function from the core module
from plotting_core.density_plots import plot_3d_isopleths

output_dir = Path(f"../figures/density/3d_isosurfaces")
output_dir.mkdir(parents=True, exist_ok=True)

def main():
    # ==========================================
    # 1. Define File Paths
    # ==========================================
    # Adjust these to match your actual lab server or TSUBAME layout
    map_file = os.path.join("Y:", "map", "map_01_flat_plane.dat")
    density_directory = os.path.join("Y:", "Particle_PostProcess_Outputs", "20260527_particle_flat_3072", "1200-1800_density")
    
    # ==========================================
    # 2. Define Physics and Scaling Parameters
    # ==========================================
    grid_dx = 2.0  # Horizontal resolution in meters
    grid_dz = 2.0  # Vertical resolution in meters (based on your H_AVE / 2 logic)
    
    # Define the exact density thresholds you want to wrap in 3D shells.
    # Start with a wide range, then narrow it down based on what you see.
    target_isopleths = [0, 100, 500, 2000]

    # ==========================================
    # 3. Execute
    # ==========================================
    print("--- Starting 3D Isosurface Visualization ---")
    plot_3d_isopleths(
        map_filepath=map_file,
        density_dir=density_directory,
        isopleth_values=target_isopleths,
        dx=grid_dx,
        dz=grid_dz
    )
    print("--- Execution Complete ---")

if __name__ == "__main__":
    main()