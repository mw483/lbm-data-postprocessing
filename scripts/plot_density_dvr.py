import os
import sys
from pathlib import Path

# Ensure the script can find the root repository directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the plotting function from the core module
from plotting_core.density_plots import plot_3d_dvr

start_step = 1600
end_step = 1699

def main():
    # ==========================================
    # 1. Define File Paths
    # ==========================================
    # Adjust these to match your actual lab server or TSUBAME layout
    map_file = os.path.join("Y:", "map", "map_02_full_roughness.dat")
    density_directory = os.path.join("Y:", "Particle_PostProcess_Outputs", "20260612_particle_cube_3072", f"{start_step}-{end_step}_density")
    
    output_path = os.path.join(
        "../figures", "density", "3d_dvr", "20260612_particle_cube_3072",
        f"{start_step}-{end_step}",
        f"density_3d_dvr_{start_step}-{end_step}.png"
    )
    # ==========================================
    # 2. Define Physics and Scaling Parameters
    # ==========================================
    grid_dx = 2.0  # Horizontal resolution in meters
    grid_dz = 2.0  # Vertical resolution in meters (based on your H_AVE / 2 logic)
    
    # Define the exact density thresholds you want to wrap in 3D shells.
    # Start with a wide range, then narrow it down based on what you see.

    min_visible_density, max_visible_density = 50, 2000

    # ==========================================
    # 3. Execute
    # ==========================================
    print("--- Starting 3D Isosurface Visualization ---")
    plot_3d_dvr(
        map_filepath=map_file,
        save_path=output_path,
        density_dir=density_directory,
        min_visible_density=min_visible_density,
        max_visible_density=max_visible_density,
        dx=grid_dx,
        dz=grid_dz
    )
    print("--- Execution Complete ---")

if __name__ == "__main__":
    main()