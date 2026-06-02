import os
import sys

# Ensure modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.trajectory_io import load_source_trajectories
from plotting_core.trajectory_3d import plot_trajectories_with_sensor

def main():
    # --- Configuration ---
    bin_dir = r"Z:\20260527_particle_flat_3072"
    
    target_source_id = 2129  # Change this to whatever the PEAK source ID was in your CSV footprint
    
    # Time step range
    start_step = 1200
    end_step = 1500  # Start with 300 steps, going to 1800 might take longer to parse
    
    # Sensor Parameters
    sensor_center = (600, 128, 10)
    sensor_size = (40, 40, 8) # dx, dy, dz in meters
    
    # Dynamic output path generation based on sensitivity parameters
    sensor_folder = f"sensor_{sensor_size[0]}x{sensor_size[1]}x{sensor_size[2]}"
    loc_folder = f"loc_{sensor_center[0]}_{sensor_center[1]}_{sensor_center[2]}"
    
    output_path = os.path.join(
        "../figures", "trajectories", sensor_folder, loc_folder,
        f"peak_source_{target_source_id}_steps_{start_step}-{end_step}.png"
    )
    
    # --- Execution ---
    print(f"Loading binary data for Source ID {target_source_id} from steps {start_step} to {end_step}...")
    trajectories = load_source_trajectories(bin_dir, target_source_id, start_step, end_step)
    print(f"Tracked {len(trajectories)} unique particles from this source.")
    
    print("Rendering 3D scene with PyVista...")
    plot_trajectories_with_sensor(trajectories, sensor_center, sensor_size, output_path)

if __name__ == "__main__":
    main()