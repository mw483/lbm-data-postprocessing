import os
import sys
from pathlib import Path

# Ensure the script can find the root repository directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the plotting function from the core module
from plotting_core.density_plots import plot_sensor_3d_isosurfaces

start_step = 1200
end_step = 1800

sensor_center = (3672, 64, 50)
sensor_size = (8, 8, 8)

case_name = "20260630_particle_flat_16mapproach"
# case_name = "20260803_particle_cube_16mapproach"

def main():
    # ==========================================
    # 1. Define File Paths
    # ==========================================
    # Adjust these to match your actual lab server or TSUBAME layout
    map_file = os.path.join("Z:", "map", "map_flat_16m_approach.dat")
    density_directory = os.path.join("D:", "lbm_results", "Particle_PostProcess_Outputs", case_name, f"sensor_{sensor_size[0]}x{sensor_size[1]}x{sensor_size[2]}",f"{start_step}-{end_step}_sensor_density")
    
    output_path = os.path.join(
        "./figures", "sensor_density", "3d_isosurfaces", case_name,
        f"sensor_{sensor_size[0]}x{sensor_size[1]}x{sensor_size[2]}",
        f"{start_step}-{end_step}",
        f"sensor_density_3d_isosurface_{sensor_center[0]}_{sensor_center[1]}_{sensor_center[2]}.png"
    )
    # ==========================================
    # 2. Define Physics and Scaling Parameters
    # ==========================================
    grid_dx = 2.0  # Horizontal resolution in meters
    grid_dz = 2.0  # Vertical resolution in meters (based on your H_AVE / 2 logic)
    
    # Define the exact density thresholds you want to wrap in 3D shells.
    # Start with a wide range, then narrow it down based on what you see.
    target_isosurfaces = [50, 100, 500, 2000, 400000]

    # ==========================================
    # 3. Execute
    # ==========================================
    print("--- Starting 3D Isosurface Visualization ---")
    plot_sensor_3d_isosurfaces(
        map_filepath=map_file,
        save_path=output_path,
        density_dir=density_directory,
        isosurface_values=target_isosurfaces,
        sensor_center=sensor_center,
        sensor_size=sensor_size,
        dx=grid_dx,
        dz=grid_dz
    )
    print("--- Execution Complete ---")

if __name__ == "__main__":
    main()