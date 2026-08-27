import pyvista as pv
import numpy as np
import os
import sys
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.map_io import create_voxel_buildings, load_lbm_map

def calculate_3d_cumulative_thresholds(volume_3d, voxel_volume, levels=[0.50, 0.80, 0.95]):
    """
    Computes exact scalar isopleth thresholds corresponding to cumulative
    mass contribution envelopes (e.g., the 50%, 80%, and 95% footprint volumes).
    """
    flat = volume_3d.flatten()
    sorted_vals = np.sort(flat)[::-1]
    cumsum = np.cumsum(sorted_vals) * voxel_volume
    total_mass = cumsum[-1]

    if total_mass == 0.0:
        return []

    thresholds = []
    for lev in levels:
        idx = np.argmax(cumsum >= (lev * total_mass))
        thresholds.append(float(sorted_vals[idx]))

    # Return unique, sorted threshold values
    return sorted(list(set(thresholds))) 


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
    plotter.add_mesh(poly, color="cyan", line_width=0.4, opacity=0.4, label="Particle Trajectories")
    plotter.add_mesh(sensor_box, color="magenta", opacity=0.5, style="surface", label="Sensor Volume")
    plotter.add_mesh(sensor_box, color="red", opacity=0.5, style="wireframe", line_width=2)

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


def plot_density_cloud_with_sensor(trajectories, sensor_center, sensor_size, save_path, map_filepath=None, dx=2.0, dz=2.0, voxel_res=8.0, sigma=0.8, z_max=160.0, density_mode="pdf"):

    """
    Bins continuous Lagrangian trajectory coordinates into a 3D volume
    and renders a direct volume density cloud with urban context.
    """
    if not trajectories:
       print("[ERROR] No trajectories available.")
       return

    # --- 1. Pool all 3D trajectory points ---
    all_points = np.vstack([coords for coords in trajectories.values() if len(coords) > 0])
    total_samples = len(all_points)

    # --- 2. Determine Domain Dimensions ---
    if map_filepath and os.path.exists(map_filepath):
        elevation_mat, nx_map, ny_map = load_lbm_map(map_filepath)
        x_domain_max = nx_map * dx
        y_domain_max = ny_map * dx
    else:
        elevation_mat = None
        x_domain_max = np.max(all_points[:, 0]) + 10.0
        y_domain_max = np.max(all_points[:, 1]) + 10.0

    # --- 3. 3D Spatial Binning & Smoothing into 8x8x8 physical voxels ---
    x_edges = np.arange(0.0, x_domain_max + voxel_res, voxel_res)
    y_edges = np.arange(0.0, y_domain_max + voxel_res, voxel_res)
    z_edges = np.arange(0.0, z_max + voxel_res, voxel_res)

    raw_hist, _ = np.histogramdd(
        all_points,
        bins=(x_edges, y_edges, z_edges)
    )

    voxel_volume = voxel_res ** 3

    # --- 4. Compute True Physical Density ---
    if density_mode == "pdf":
        # 3D probability density function [m^-3] (Integrates to 1.0)
        volume_3d = raw_hist / (total_samples * voxel_volume)
        unit_title = "3D Probability Density [m^-3]"
    elif density_mode == "concentration":
        # Volumetric Point Density [points/m^3]
        volume_3d = raw_hist / voxel_volume
        unit_title = "Particle Density [pts/m^3]"
    else:
        volume_3d = raw_hist.astype(np.float32)
        unit_title = "Raw Counts"

    # Apply 3D Gaussian blur across 8m voxel units
    if sigma > 0.0:
        volume_3d = gaussian_filter(raw_hist.astype(np.float32), sigma=sigma)
    else:
        volume_3d = raw_hist.astype(np.float32)

    # Outlier suppression (clipping to 99th percentile of non-zero cells)
    active_cells = volume_3d[volume_3d > 0.0]
    if len(active_cells) == 0:
        print("[ERROR] No particles within the domain grid.")
        return

    p99_max = float (np.percentile(active_cells, 99.5))
    min_thresh = float(np.percentile(active_cells, 5.0))
    clamped_volume = np.clip(volume_3d, a_min=0.0, a_max=p99_max)

    # --- 5. Build PyVista Uniform ImageData Grid ---
    nx_cells, ny_cells, nz_cells = volume_3d.shape
    density_grid = pv.ImageData(
        dimensions=(nx_cells + 1, ny_cells + 1, nz_cells + 1),
        spacing=(voxel_res, voxel_res, voxel_res),
        origin=(0.0, 0.0, 0.0)
    )
    density_grid.cell_data["Density"] = clamped_volume.flatten(order="F")

    # --- 6. Assemble Scene ---
    plotter = pv.Plotter(off_screen=False)

    # A. Add Buildings & Ground Plane
    if elevation_mat is not None:
        building_mesh = create_voxel_buildings(elevation_mat, nx_map, ny_map, resolution=dx)
        if building_mesh:
            plotter.add_mesh(
                building_mesh,
                color="lightgray",
                show_edges=True,
                edge_color="darkgray",
                opacity=1.0,
                label="Buildings"
            )

        ground = pv.Plane(
            center=(x_domain_max / 2.0, y_domain_max / 2.0, 0.0),
            direction=(0, 0, 1),
            i_size=x_domain_max,
            j_size=y_domain_max
        )
        plotter.add_mesh(ground, color="darkgreen", opacity=0.15)

    # B. Add Direct Volume Rendering (DVR)
    # Piecewise opacity: completely transparent at 0, ramps up in dense cores
    cloud_opacity = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    plotter.add_volume(
        density_grid, 
        scalars="Density", 
        cmap="plasma",
        opacity=cloud_opacity, 
        clim=[min_thresh, p99_max],
        mapper="smart",
        show_scalar_bar=True,
        scalar_bar_args={"title": unit_title, "fmt": "%.2e"}
    )

    # C. Add Sensor Bounding Box
    cx, cy, cz = sensor_center
    sx, sy, sz = sensor_size
    bounds = [
        cx - sx / 2.0, cx + sx / 2.0,
        cy - sy / 2.0, cy + sy / 2.0,
        cz - sz / 2.0, cz + sz / 2.0
    ]
    sensor_box = pv.Box(bounds=bounds)
    plotter.add_mesh(sensor_box, color="magenta", opacity=0.4, style="surface", label="Sensor Volume")
    plotter.add_mesh(sensor_box, color="red", style="wireframe", line_width=2.5)

    # --- 6. Environment & Camera Controls ---
    plotter.set_background("white")
    plotter.add_axes()
    plotter.camera_position = 'iso'
    plotter.show_grid(
        font_size=10, 
        fmt="%.0f", 
        xtitle="X [m]", ytitle="Y [m]", ztitle="Z [m]"
    )
    plotter.add_legend()

    # Screenshot callback ('s' key)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    snap_counter = [1]

    def take_snap():
        base_name, ext = os.path.splitext(save_path)
        unique_save_path = f"{base_name}_{snap_counter[0]:02d}{ext}"
        plotter.screenshot(unique_save_path)
        print(f"--> SNAP! Saved view {snap_counter[0]} to: {unique_save_path}")
        snap_counter[0] += 1

    plotter.add_key_event('s', take_snap)
    print("Interactive window opened. Press 's' to save a screenshot.")
    plotter.show()


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
    plotter.add_mesh(poly, color="cyan", line_width=0.4, opacity=0.4, label="Particle Trajectories")
    plotter.add_mesh(sensor_box, color="magenta", opacity=0.5, style="surface", label="Sensor Volume")
    plotter.add_mesh(sensor_box, color="red", opacity=0.5, style="wireframe", line_width=2)

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


def plot_density_isopleths_with_sensor(trajectories, sensor_center, sensor_size, save_path, map_filepath=None, dx=2.0, dz=2.0, voxel_res=8.0, sigma=0.8, z_max=160.0, density_mode="pdf", cumulative_levels=[0.50, 0.80, 0.95], manual_thresholds=None,  shell_opacity=0.45):
    """
    Bins Lagrangian trajectories into an 8x8x8m 3D grid and extracts nested 
    continuous 3D isopleth shells (enclosed probability/mass envelopes).
    """
    if not trajectories:
       print("[ERROR] No trajectories available.")
       return

    # --- 1. Pool all 3D trajectory points ---
    all_points = np.vstack([coords for coords in trajectories.values() if len(coords) > 0])
    total_samples = len(all_points)

    # --- 2. Determine Domain Dimensions ---
    if map_filepath and os.path.exists(map_filepath):
        elevation_mat, nx_map, ny_map = load_lbm_map(map_filepath)
        x_domain_max = nx_map * dx
        y_domain_max = ny_map * dx
    else:
        elevation_mat = None
        x_domain_max = np.max(all_points[:, 0]) + 10.0
        y_domain_max = np.max(all_points[:, 1]) + 10.0

    # --- 3. 3D Spatial Binning & Smoothing into 8x8x8 physical voxels ---
    x_edges = np.arange(0.0, x_domain_max + voxel_res, voxel_res)
    y_edges = np.arange(0.0, y_domain_max + voxel_res, voxel_res)
    z_edges = np.arange(0.0, z_max + voxel_res, voxel_res)

    raw_hist, _ = np.histogramdd(
        all_points,
        bins=(x_edges, y_edges, z_edges)
    )

    voxel_volume = voxel_res ** 3

    # Apply 3D Gaussian blur across 8m voxel units
    if sigma > 0.0:
        smoothed_hist = gaussian_filter(raw_hist.astype(np.float32), sigma=sigma)
    else:
        smoothed_hist = raw_hist.astype(np.float32)

    # --- 4. Compute True Physical Density ---
    if density_mode == "pdf":
        total_integral = np.sum(smoothed_hist) * voxel_volume
        volume_3d = smoothed_hist / total_integral if total_integral > 0 else smoothed_hist
        unit_title = "3D Probability Density [m^-3]"
    elif density_mode == "concentration":
        # Volumetric Point Density [points/m^3]
        volume_3d = smoothed_hist / voxel_volume
        unit_title = "Particle Density [pts/m^3]"
    elif density_mode == "normalized":
        v_max = np.max(smoothed_hist)
        volume_3d = smoothed_hist / v_max if v_max > 0 else smoothed_hist
        unit_title = "Normalized Density (P / Pmax)"
    else:
        volume_3d = smoothed_hist
        unit_title = "Raw Counts"

    # --- 5. Determine Isosurface Thresholds ---
    if manual_thresholds is not None:
        isosurface_values = sorted(manual_thresholds)
    else:
        isosurface_values = calculate_3d_cumulative_thresholds(volume_3d, voxel_volume, levels=cumulative_levels)

    # --- 6. Build PyVista Grid & Convert Cell Data to Point Data ---
    nx_cells, ny_cells, nz_cells = volume_3d.shape
    density_grid = pv.ImageData(
        dimensions=(nx_cells + 1, ny_cells + 1, nz_cells + 1),
        spacing=(voxel_res, voxel_res, voxel_res),
        origin=(0.0, 0.0, 0.0)
    )
    density_grid.cell_data["Density"] = volume_3d.flatten(order="F")

    # Marching cubes requires scalar values interpolated onto grid points (corners)
    point_grid = density_grid.cell_data_to_point_data()

    # Extract continuous 3D contour meshes
    try:
        contours = point_grid.contour(isosurfaces=isosurface_values, scalars="Density")
    except Exception as e:
        print(f"[ERROR] Failed to extract contours: {e}")
        return

    # --- 7. Assemble Scene ---
    plotter = pv.Plotter(off_screen=False)

    # A. Add Buildings & Ground Plane
    if elevation_mat is not None:
        building_mesh = create_voxel_buildings(elevation_mat, nx_map, ny_map, resolution=dx)
        if building_mesh:
            plotter.add_mesh(
                building_mesh,
                color="lightgray",
                show_edges=True,
                edge_color="darkgray",
                opacity=1.0,
                label="Buildings"
            )

        ground = pv.Plane(
            center=(x_domain_max / 2.0, y_domain_max / 2.0, 0.0),
            direction=(0, 0, 1),
            i_size=x_domain_max,
            j_size=y_domain_max
        )
        plotter.add_mesh(ground, color="darkgreen", opacity=0.15)

    # B. Add 3D Isosurface shells
    plotter.add_mesh(
        contours,
        scalars="Density",
        cmap="plasma",
        opacity=shell_opacity,
        smooth_shading=True,
        show_scalar_bar=True,
        scalar_bar_args={"title": unit_title, "fmt": "%.2e"},
        label="Contributing Isopleths"
    )

    # C. Add Sensor Bounding Box
    cx, cy, cz = sensor_center
    sx, sy, sz = sensor_size
    bounds = [
        cx - sx / 2.0, cx + sx / 2.0,
        cy - sy / 2.0, cy + sy / 2.0,
        cz - sz / 2.0, cz + sz / 2.0
    ]
    sensor_box = pv.Box(bounds=bounds)
    plotter.add_mesh(sensor_box, color="magenta", opacity=0.4, style="surface", label="Sensor Volume")
    plotter.add_mesh(sensor_box, color="red", style="wireframe", line_width=2.5)

    # --- 8. Environment & Camera Controls ---
    plotter.set_background("white")
    plotter.add_axes()
    plotter.camera_position = 'iso'
    plotter.show_grid(
        font_size=10, 
        fmt="%.0f", 
        xtitle="X [m]", ytitle="Y [m]", ztitle="Z [m]"
    )
    plotter.add_legend()

    # Screenshot callback ('s' key)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    snap_counter = [1]

    def take_snap():
        base_name, ext = os.path.splitext(save_path)
        unique_save_path = f"{base_name}_{snap_counter[0]:02d}{ext}"
        plotter.screenshot(unique_save_path)
        print(f"--> SNAP! Saved view {snap_counter[0]} to: {unique_save_path}")
        snap_counter[0] += 1

    plotter.add_key_event('s', take_snap)
    print("Interactive window opened. Press 's' to save a screenshot.")
    plotter.show()

