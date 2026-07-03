import os
import sys

# Ensure modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.particle_io import load_source_trajectories
from plotting_core.trajectory_3d import plot_trajectories_with_sensor

def main():
    # --- Configuration ---
    bin_dir = r"Y:\20260612_particle_cube_3072"
    map_dir = r"Y:\map\map_02_full_roughness.dat"
    
    # IMPORTANT: Set this to your actual LBM grid resolution (usually 2.0m)
    dx = 2.0 
    
    target_source_id = 1229  
    
    # Time step range
    start_step = 1200
    end_step = 1500  
    
    # Sensor Parameters - PASSED IN PHYSICAL METERS
    sensor_center = (600, 128, 20) 
    sensor_size = (8, 8, 8) 
    
    # Dynamic output path generation
    sensor_folder = f"sensor_{sensor_size[0]}x{sensor_size[1]}x{sensor_size[2]}"
    loc_folder = f"loc_{sensor_center[0]}_{sensor_center[1]}_{sensor_center[2]}"
    
    output_path = os.path.join(
        "../figures", "20260612_particle_cube_trajectories", sensor_folder, loc_folder,
        f"peak_source_{target_source_id}_steps_{start_step}-{end_step}.png"
    )
    
    # --- Execution ---
    print(f"Loading binary data for Source ID {target_source_id} from steps {start_step} to {end_step}...")
    trajectories = load_source_trajectories(bin_dir, target_source_id, start_step, end_step)
    print(f"Tracked {len(trajectories)} unique particles from this source.")
    
    print("Rendering 3D scene with PyVista...")
    # NOTE: Ensure plot_trajectories_with_sensor only multiplies particle coordinates by dx, 
    # and leaves the sensor_center/sensor_size alone since they are already in meters!
    plot_trajectories_with_sensor(trajectories, sensor_center, sensor_size, output_path, map_dir, dx)

if __name__ == "__main__":
    main()