import pyvista as pv
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.map_io import create_voxel_buildings, load_lbm_map

def plot_trajectories_with_sensor(trajectories, sensor_center, sensor_size, save_path, map_filepath=None, dx=2.0):
    """
    Renders 3D trajectories, a transparent sensor volume, and the building map using PyVista.
    Assumes particle coordinates and sensor parameters are ALREADY in physical meters.
    """
    if not trajectories:
        print("No trajectories to plot!")
        return

    # 1. Format the trajectory data for PyVista (PolyData lines)
    points = []
    lines = []
    for p_id, coords in trajectories.items():
        if len(coords) < 2:  # Need at least 2 points to draw a line
            continue
            
        start_idx = len(points)
        
        # Keep coordinates EXACTLY as they are (already in meters)
        scaled_coords = [(float(x), float(y), float(z)) for x, y, z in coords]
        points.extend(scaled_coords)
        
        # PyVista line format: [number_of_points, index1, index2, ...]
        lines.append(len(coords))
        lines.extend(range(start_idx, start_idx + len(coords)))

    poly = pv.PolyData(points)
    poly.lines = lines

    # 2. Define the Sensor Box bounds (Already in meters!)
    cx, cy, cz = sensor_center 
    sx, sy, sz = sensor_size

    bounds = [
        cx - sx/2, cx + sx/2,  # X min, X max
        cy - sy/2, cy + sy/2,  # Y min, Y max
        cz - sz/2, cz + sz/2   # Z min, Z max
    ]
    sensor_box = pv.Box(bounds=bounds)

    # 3. Setup the PyVista Plotter
    plotter = pv.Plotter(off_screen=False)
    
    # Add Trajectories and Sensor
    plotter.add_mesh(poly, color="cyan", line_width=0.5, opacity=0.5, label="Particle Trajectories")
    plotter.add_mesh(sensor_box, color="magenta", opacity=0.3, style="surface", label="Sensor Volume")
    plotter.add_mesh(sensor_box, color="red", opacity=0.3, style="wireframe", line_width=2)

    # 4. Load and Add the Map (NO TILING)
    if map_filepath and os.path.exists(map_filepath):
        print(f"Loading map from {map_filepath}...")
        elevation_mat, nx, ny = load_lbm_map(map_filepath)
        
        # Generate mesh (X/Y scaled by dx, Z scaled by 1.0 because height is in meters)
        building_mesh = create_voxel_buildings(elevation_mat, nx, ny, resolution=dx)
        
        if building_mesh:
            plotter.add_mesh(building_mesh, color="lightgray", opacity=1.0, 
                             show_edges=True, edge_color="darkgray", label="Buildings")
            print("Map loaded and added to scene.")

        # Add a simple ground plane sized exactly to the map
        ground = pv.Plane(
            center=((nx*dx)/2, (ny*dx)/2, 0), 
            direction=(0, 0, 1), 
            i_size=nx*dx, 
            j_size=ny*dx
        )
        plotter.add_mesh(ground, color="darkgreen", opacity=0.2)

    # 5. Configure Camera and Lighting
    plotter.camera_position = 'iso'
    plotter.show_grid(
        font_size=10, 
        fmt="%.0f", 
        xtitle='X [m]', ytitle='Y [m]', ztitle='Z [m]'
    )
    plotter.add_legend()

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