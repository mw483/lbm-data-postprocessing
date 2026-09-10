import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from data_loaders.particle_io import load_trajectories_with_velocities
from plotting_core.particle_3d_plots import plot_particles_with_velocity

def main():
    # --- Configuration ---
    map_dir = r"C:\Users\Mikael Wijaya\Documents\GitHub\lbm-cuda-project\map\map_cube_16m_approach.dat"
    time_capsule_file = r"D:\lbm_results\Particle_PostProcess_Outputs\20260803_particle_cube_16mapproach\sensor_8x8x8\1200-1800_sensor_density\sensor_hit_ids.txt"
    trajectory_csv = r"D:\lbm_results\Particle_PostProcess_Outputs\20260803_particle_cube_16mapproach\sensor_8x8x8\1200-1800_sensor_density\target_trajectories.csv"

    case_name = "cube"

    dx = 2.0
    sensor_center = (3672.0, 256.0, 90.0)
    sensor_size = (8.0, 8.0, 8.0)
    target_sensor_id = 4   # Or set target_coords=sensor_center in the loader call

    # Visual toggles
    scalar_field = "w"              # Options: 'u', 'v', 'w', 'w_total', 'vel_mag', 'tke_sgs'
    display_mode = "lines"         # Options: 'points' (discrete colored dots) or 'lines' (colored streamlines)
    point_size = 4.0
    stride = 1                      # Subsampling factor (stride=1 keeps all points)
    crop_approach = True
    x_start = 3072.0

    sensor_folder = f"sensor_{int(sensor_size[0])}x{int(sensor_size[1])}x{int(sensor_size[2])}"
    loc_folder = f"loc_{int(sensor_center[0])}_{int(sensor_center[1])}_{int(sensor_center[2])}"
    
    output_path = os.path.join(
        "../figures", "velocity_particle_cloud", case_name, sensor_folder, loc_folder,
        f"particles_{scalar_field}_{display_mode}_sensor_{target_sensor_id}.png"
    )

    # --- Load Data ---
    df = load_trajectories_with_velocities(
        csv_path=trajectory_csv,
        time_capsule_path=time_capsule_file,
        target_sensor_id=target_sensor_id
    )

    if df is None:
        return

    # --- Render ---
    plot_particles_with_velocity(
        particle_df=df,
        sensor_center=sensor_center,
        sensor_size=sensor_size,
        save_path=output_path,
        scalar_field=scalar_field,
        display_mode=display_mode,
        point_size=point_size,
        stride=stride,
        map_filepath=map_dir,
        dx=dx,
        crop_approach=crop_approach,
        x_start=x_start
    )

if __name__ == "__main__":
    main()