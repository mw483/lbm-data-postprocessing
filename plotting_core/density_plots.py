import sys
import os
import pyvista as pv
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.map_io import load_lbm_map, create_voxel_buildings
from data_loaders.lbm_parsers import build_3d_density_volume


def plot_3d_isopleths(map_filepath, save_path, density_dir, isopleth_values, sensor_center=None, sensor_size=None, dx=2.0, dz=2.0):
    """
    Renders a 3D interactive PyVista plot overlaying voxel buildings with
    continuous 3D density isosurfaces.
    """
    # ==========================================
    # 1. Load the Physical Building Map
    # ==========================================
    print(f"Loading building geometry from: {map_filepath}...")
    try:
        elevation_matrix, nx_map, ny_map = load_lbm_map(map_filepath)
        buildings = create_voxel_buildings(elevation_matrix, nx_map, ny_map, resolution=dx)
    except Exception as e:
        print(f"[ERROR] Failed to load map: {e}")
        return

    # ==========================================
    # 2. Load the 3D Density Volume
    # ==========================================
    print(f"Aggregating density layers from: {density_dir}...")
    volume_3d = build_3d_density_volume(density_dir)
    
    if volume_3d is None:
        print("[ERROR] Missing data. Aborting plot.")
        return

    # --- DEBUG PRINT ---
    # This will tell you exactly what your clim should actually be!
    max_val = np.max(volume_3d)
    print(f"[DEBUG] Maximum density value in this dataset: {max_val}")

    # Extract dynamic shapes (nx, ny, nz)
    nx, ny, nz = volume_3d.shape
    
    # Create the Density Grid (Dimensions are +1 to define cell corners)
    density_grid = pv.ImageData(
        dimensions=(nx + 1, ny + 1, nz + 1),
        spacing=(dx, dx, dz), 
        origin=(0.0, 0.0, 0.0)
    )

    # ==========================================
    # 3. Generate the Isopleths (Contours)
    # ==========================================
    # Log-transform the data (add 1 to avoid log(0) errors)
    log_volume = np.log10(volume_3d + 1)

    density_grid.cell_data["Log_Density"] = log_volume.flatten(order="F")
    density_grid = density_grid.cell_data_to_point_data()

    # Define your original target values
    target_particles = np.array(isopleth_values)
    
    # Convert those target values into Log space for the contour filter
    log_isopleths = np.log10(target_particles + 1).tolist()

    # Generate contours using the Log data and Log thresholds
    contours = density_grid.contour(isosurfaces=log_isopleths, scalars="Log_Density")

    # ==========================================
    # 4. Render the Scene
    # ==========================================
    print("Initializing PyVista rendering environment...")

    if 
        # Define the Sensor Box bounds (Already in meters!)
        cx, cy, cz = sensor_center 
        sx, sy, sz = sensor_size

        bounds = [
            cx - sx/2, cx + sx/2,  # X min, X max
            cy - sy/2, cy + sy/2,  # Y min, Y max
            cz - sz/2, cz + sz/2   # Z min, Z max
        ]
        sensor_box = pv.Box(bounds=bounds)

    plotter = pv.Plotter()

    # Add the buildings
    if buildings is not None:
        plotter.add_mesh(
            buildings, 
            color='lightgrey', 
            pbr=True, metallic=0.2, roughness=0.8, 
            name="Buildings"
        )

    # Add the density isopleths
    plotter.add_mesh(
        contours, 
        cmap="plasma",           
        opacity=0.5,             # Semi-transparent to show inner cores
        show_scalar_bar=True,
        scalar_bar_args={"title": "Particle Density (Log Scale)"},
        name="Plume"
    )

    # Aesthetic environment settings
    plotter.set_background('white')
    plotter.add_axes()
    
    # 5. Configure Camera and Lighting
    plotter.camera_position = 'iso'
    plotter.show_grid(
        font_size=10, 
        fmt="%.0f", 
        xtitle='X [m]', ytitle='Y [m]', ztitle='Z [m]'
    )

    # 6. Save output logic
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    snap_counter = [1] 

    def take_snap():
        base_name, ext = os.path.splitext(save_path)
        unique_save_path = f"{base_name}_{snap_counter[0]:02d}{ext}"
        plotter.screenshot(unique_save_path)
        print(f"--> SNAP! Saved view {snap_counter[0]} to: {unique_save_path}")
        snap_counter[0] += 1

    plotter.add_key_event('s', take_snap)

    print("Interactive window opened.")
    plotter.show()



def plot_3d_dvr(map_filepath, save_path, density_dir, min_visible_density, max_visible_density, dx=2.0, dz=2.0):
    """
    Renders a 3D interactive PyVista plot overlaying voxel buildings with
    continuous 3D Direct Volume Renders
    """
    # ==========================================
    # 1. Load the Physical Building Map
    # ==========================================
    print(f"Loading building geometry from: {map_filepath}...")
    try:
        elevation_matrix, nx_map, ny_map = load_lbm_map(map_filepath)
        buildings = create_voxel_buildings(elevation_matrix, nx_map, ny_map, resolution=dx)
    except Exception as e:
        print(f"[ERROR] Failed to load map: {e}")
        return

    # ==========================================
    # 2. Load the 3D Density Volume
    # ==========================================
    print(f"Aggregating density layers from: {density_dir}...")
    volume_3d = build_3d_density_volume(density_dir)
    
    if volume_3d is None:
        print("[ERROR] Missing data. Aborting plot.")
        return

    # --- DEBUG PRINT ---
    # This will tell you exactly what your clim should actually be!
    max_val = np.max(volume_3d)
    print(f"[DEBUG] Maximum density value in this dataset: {max_val}")

    nx, ny, nz = volume_3d.shape
    
    density_grid = pv.ImageData(
        dimensions=(nx + 1, ny + 1, nz + 1),
        spacing=(dx, dx, dz), 
        origin=(0.0, 0.0, 0.0)
    )

    cloud_opacity = [0.0, 0.1, 0.3, 0.6, 0.9]

    log_volume = np.log10(volume_3d + 1)
    
    # Assign the LOGGED data to the PyVista grid instead of the raw data
    density_grid.cell_data["Log_Density"] = log_volume.flatten(order="F")

    # ==========================================
    # 3. Update the Transfer Function for Log Values
    # ==========================================
    # Now our thresholds must be in log space!
    log_min = np.log10(min_visible_density + 1)
    log_max = np.log10(400000 + 1) # Or use np.max(log_volume)

    # ==========================================
    # 4. Render the Scene (Fail-Safe Mode)
    # ==========================================
    print("Initializing PyVista rendering environment...")
    plotter = pv.Plotter()

    if buildings is not None:
        plotter.add_mesh(
            buildings, 
            color='lightgrey', 
            pbr=True, metallic=0.2, roughness=0.8, 
            name="Buildings"
        )

    # Fail-Safe Volume Rendering
    plotter.add_volume(
        density_grid,
        scalars="Log_Density",       # Point to the newly logged data
        cmap="plasma", 
        opacity=cloud_opacity, 
        clim=[log_min, log_max],     # Use log limits
        mapper="smart",
        show_scalar_bar=True,
        scalar_bar_args={"title": "Log10(Particle Density)"},
        name="Plume"
    )

    # Aesthetic environment settings
    plotter.set_background('white')
    plotter.add_axes()
    
    # 5. Configure Camera and Lighting
    plotter.camera_position = 'iso'
    plotter.show_grid(
        font_size=10, 
        fmt="%.0f", 
        xtitle='X [m]', ytitle='Y [m]', ztitle='Z [m]'
    )

    # 6. Save output logic
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    snap_counter = [1] 

    def take_snap():
        base_name, ext = os.path.splitext(save_path)
        unique_save_path = f"{base_name}_{snap_counter[0]:02d}{ext}"
        plotter.screenshot(unique_save_path)
        print(f"--> SNAP! Saved view {snap_counter[0]} to: {unique_save_path}")
        snap_counter[0] += 1

    plotter.add_key_event('s', take_snap)

    print("Interactive window opened.")
    plotter.show()