import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.particle_io import load_streamed_trajectories
from plotting_core.particle_3d_plots import plot_density_cloud_with_sensor

def main():
    # --- Configuration ---
    # map_dir = r"Z:\map\map_flat_16m_approach.dat"
    # time_capsule_file = r"Z:\Particle_PostProcess_Outputs\20260630_particle_flat_16mapproach\sensor_8x8x8\1200-1800_sensor_density\sensor_hit_ids.txt"
    # trajectory_csv = r"Z:\Particle_PostProcess_Outputs\20260630_particle_flat_16mapproach\sensor_8x8x8\1200-1800_sensor_density\target_trajectories.csv"
    map_dir = r"C:\Users\Mikael Wijaya\Documents\GitHub\lbm-cuda-project\map\map_cube_16m_approach.dat"
    time_capsule_file = r"D:\lbm_results\Particle_PostProcess_Outputs\20260803_particle_cube_16mapproach\sensor_8x8x8\1200-1800_sensor_density\sensor_hit_ids.txt"
    trajectory_csv = r"D:\lbm_results\Particle_PostProcess_Outputs\20260803_particle_cube_16mapproach\sensor_8x8x8\1200-1800_sensor_density\target_trajectories.csv"

    dx = 2.0
    dz = 2.0
    target_sensor_id = 4
    sensor_center = (3672, 256, 90)
    sensor_size = (8, 8, 8)

    sensor_folder = f"sensor_{sensor_size[0]}x{sensor_size[1]}x{sensor_size[2]}"
    loc_folder = f"loc_{sensor_center[0]}_{sensor_center[1]}_{sensor_center[2]}"
    
    output_path = os.path.join(
        "../figures", "20260803_particle_cube_16mapproach_clouds", sensor_folder, loc_folder,
        f"density_cloud_sensor_{target_sensor_id}.png"
    )

    # --- Load Data ---
    trajectories = load_streamed_trajectories(trajectory_csv, time_capsule_file, target_sensor_id)
    if not trajectories:
        return

    # --- Render ---
    plot_density_cloud_with_sensor(
        trajectories=trajectories,
        sensor_center=sensor_center,
        sensor_size=sensor_size,
        save_path=output_path,
        map_filepath=map_dir,
        dx=dx,
        dz=dz,
        voxel_res=8.0,    # 2.0m isotropic voxel grid
        sigma=1.2,        # Gaussian smoothing radius (increase for a softer plume)
        z_max=160.0,       # Domain top boundary
        density_mode="concentration",
        crop_approach=True,
        x_start=3072.0
    )

if __name__ == "__main__":
    main()