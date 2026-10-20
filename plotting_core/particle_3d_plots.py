import pyvista as pv
import numpy as np
import os
from scipy.ndimage import gaussian_filter
import polars as pl

from data_loaders.map_io import load_lbm_map
from plotting_core.pyvista_helpers import (
    add_ground_plane,
    add_sensor_box,
    add_snapshot_key,
    add_voxel_buildings,
    show_iso_grid,
)

pv.global_theme.allow_empty_mesh = True # Allow empty mesh (for flat plane maps)

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


def _bin_trajectories(trajectories, map_filepath, dx, voxel_res, z_max):
    """
    Pools all trajectory points and bins them into voxel_res^3 physical voxels
    spanning the map (or the particle extent + 10 m when no map is given).
    Returns (raw_hist, total_samples, elevation_mat, nx_map, ny_map,
    x_domain_max, y_domain_max); elevation_mat/nx_map/ny_map are None without a map.
    """
    # --- 1. Pool all 3D trajectory points ---
    all_points = np.vstack([coords for coords in trajectories.values() if len(coords) > 0])
    total_samples = len(all_points)

    # --- 2. Determine Domain Dimensions ---
    if map_filepath and os.path.exists(map_filepath):
        elevation_mat, nx_map, ny_map = load_lbm_map(map_filepath)
        x_domain_max = nx_map * dx
        y_domain_max = ny_map * dx
    else:
        elevation_mat, nx_map, ny_map = None, None, None
        x_domain_max = np.max(all_points[:, 0]) + 10.0
        y_domain_max = np.max(all_points[:, 1]) + 10.0

    # --- 3. 3D Spatial Binning into voxel_res^3 physical voxels ---
    x_edges = np.arange(0.0, x_domain_max + voxel_res, voxel_res)
    y_edges = np.arange(0.0, y_domain_max + voxel_res, voxel_res)
    z_edges = np.arange(0.0, z_max + voxel_res, voxel_res)

    raw_hist, _ = np.histogramdd(
        all_points,
        bins=(x_edges, y_edges, z_edges)
    )
    return raw_hist, total_samples, elevation_mat, nx_map, ny_map, x_domain_max, y_domain_max


def plot_density_cloud_with_sensor(trajectories, sensor_center, sensor_size, save_path, map_filepath=None, dx=2.0, dz=2.0, voxel_res=8.0, sigma=0.8, z_max=160.0, density_mode="pdf", crop_approach=True, x_start=3072.0):

    """
    Bins continuous Lagrangian trajectory coordinates into a 3D volume
    and renders a direct volume density cloud with urban context.
    """
    if not trajectories:
       print("[ERROR] No trajectories available.")
       return

    (raw_hist, total_samples, elevation_mat, nx_map, ny_map,
     x_domain_max, y_domain_max) = _bin_trajectories(trajectories, map_filepath, dx, voxel_res, z_max)

    voxel_volume = voxel_res ** 3

    # Apply 3D Gaussian blur across 8m voxel units
    if sigma > 0.0:
        smoothed_hist = gaussian_filter(raw_hist.astype(np.float32), sigma=sigma)
    else:
        smoothed_hist = raw_hist.astype(np.float32)

    # --- 4. Compute True Physical Density (on the smoothed field) ---
    if density_mode == "pdf":
        # 3D probability density function [m^-3] (Integrates to 1.0)
        volume_3d = smoothed_hist / (total_samples * voxel_volume)
        unit_title = "3D Probability Density [m^-3]"
    elif density_mode == "concentration":
        # Volumetric Point Density [points/m^3]
        volume_3d = smoothed_hist / voxel_volume
        unit_title = "Particle Density [pts/m^3]"
    else:
        volume_3d = smoothed_hist
        unit_title = "Raw Counts"

    # Outlier suppression (clipping to 99th percentile of non-zero cells)
    active_cells = volume_3d[volume_3d > 0.0]
    if len(active_cells) == 0:
        print("[ERROR] No particles within the domain grid.")
        return

    p99_max = float (np.percentile(active_cells, 99.5))
    min_thresh = float(np.percentile(active_cells, 5.0))
    clamped_volume = np.clip(volume_3d, a_min=0.0, a_max=p99_max)

    # Crop the 3D volume array along the X-axis in NumPy space
    if crop_approach:
        x_idx_start = int(np.floor(x_start / voxel_res))
        cropped_volume = clamped_volume[x_idx_start:, :, :]
        grid_origin_x = x_idx_start * voxel_res
    else:
        cropped_volume = volume_3d
        grid_origin_x = 0.0

    # --- 5. Build PyVista Uniform ImageData Grid ---
    nx_cells, ny_cells, nz_cells = cropped_volume.shape
    density_grid = pv.ImageData(
        dimensions=(nx_cells + 1, ny_cells + 1, nz_cells + 1),
        spacing=(voxel_res, voxel_res, voxel_res),
        origin=(grid_origin_x, 0.0, 0.0)
    )
    density_grid.cell_data["Density"] = cropped_volume.flatten(order="F")

    # --- 6. Assemble Scene ---
    plotter = pv.Plotter(off_screen=False)

    # A. Add Buildings & Ground Plane
    if elevation_mat is not None:
        add_voxel_buildings(plotter, elevation_mat, nx_map, ny_map, dx, opacity=1.0,
                            crop_approach=crop_approach, x_start=x_start)
        add_ground_plane(plotter, x_domain_max, y_domain_max,
                         crop_approach=crop_approach, x_start=x_start, opacity=0.15)

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
    add_sensor_box(plotter, sensor_center, sensor_size, surface_opacity=0.4, line_width=2.5)

    # --- 6. Environment & Camera Controls ---
    plotter.set_background("white")
    plotter.add_axes()
    show_iso_grid(plotter)
    plotter.add_legend()

    # Screenshot callback ('s' key)
    add_snapshot_key(plotter, save_path)
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

    # 2. Setup the PyVista Plotter
    plotter = pv.Plotter(off_screen=False)

    # Add Trajectories and Sensor (sensor parameters already in meters)
    plotter.add_mesh(poly, color="cyan", line_width=0.4, opacity=0.4, label="Particle Trajectories")
    add_sensor_box(plotter, sensor_center, sensor_size, surface_opacity=0.5, line_width=2, wire_opacity=0.5)

    # 3. Load and Add the Map (NO TILING)
    if map_filepath and os.path.exists(map_filepath):
        print(f"Loading map from {map_filepath}...")
        elevation_mat, nx, ny = load_lbm_map(map_filepath)

        # Generate mesh (X/Y scaled by dx, Z scaled by 1.0 because height is in meters)
        if add_voxel_buildings(plotter, elevation_mat, nx, ny, dx, opacity=1.0):
            print("Map loaded and added to scene.")

        # Add a simple ground plane sized exactly to the map
        add_ground_plane(plotter, nx * dx, ny * dx, opacity=0.2)

    # 4. Configure Camera and Lighting
    show_iso_grid(plotter)
    plotter.add_legend()

    # 5. Save output logic
    add_snapshot_key(plotter, save_path)

    print("Interactive window opened.")
    plotter.show()


def plot_density_isopleths_with_sensor(trajectories, sensor_center, sensor_size, save_path, map_filepath=None, dx=2.0, dz=2.0, voxel_res=8.0, sigma=0.8, z_max=160.0, density_mode="pdf", cumulative_levels=[0.50, 0.80, 0.95], manual_thresholds=None,  shell_opacity=0.45, crop_approach=True, x_start=3072.0):
    """
    Bins Lagrangian trajectories into an 8x8x8m 3D grid and extracts nested
    continuous 3D isopleth shells (enclosed probability/mass envelopes).
    Opens an interactive window ('s' saves a screenshot).
    """
    plotter = pv.Plotter(off_screen=False)
    if not add_density_isopleths(plotter, trajectories, sensor_center, sensor_size, map_filepath, dx,
                                 voxel_res, sigma, z_max, density_mode, cumulative_levels,
                                 manual_thresholds, shell_opacity, crop_approach, x_start):
        plotter.close()
        return

    # Screenshot callback ('s' key)
    add_snapshot_key(plotter, save_path)
    print("Interactive window opened. Press 's' to save a screenshot.")
    plotter.show()


def add_density_isopleths(plotter, trajectories, sensor_center, sensor_size, map_filepath=None, dx=2.0, voxel_res=8.0, sigma=0.8, z_max=160.0, density_mode="pdf", cumulative_levels=[0.50, 0.80, 0.95], manual_thresholds=None, shell_opacity=0.45, crop_approach=True, x_start=3072.0, bar_title=None):
    """
    Draws the isopleth scene (buildings, shells, sensor box, grid) into the active
    renderer of `plotter`, so it also works in one subplot of a side-by-side plotter.
    bar_title overrides the scalar-bar title (needed when two subplots share a plotter).
    Returns False when there is nothing to draw.
    """
    if not trajectories:
       print("[ERROR] No trajectories available.")
       return False

    (raw_hist, total_samples, elevation_mat, nx_map, ny_map,
     x_domain_max, y_domain_max) = _bin_trajectories(trajectories, map_filepath, dx, voxel_res, z_max)

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
        return False

    # --- 7. Assemble Scene ---
    # A. Add Buildings & Ground Plane
    if elevation_mat is not None:
        add_voxel_buildings(plotter, elevation_mat, nx_map, ny_map, dx, opacity=1.0,
                            crop_approach=crop_approach, x_start=x_start)
        add_ground_plane(plotter, x_domain_max, y_domain_max,
                         crop_approach=crop_approach, x_start=x_start, opacity=0.15)

    # B. Add 3D Isosurface shells
    if crop_approach and contours.n_points > 0:
        contours = contours.clip(normal='x', origin=(x_start, 0, 0), invert=False)

    plotter.add_mesh(
        contours,
        scalars="Density",
        cmap="plasma",
        opacity=shell_opacity,
        smooth_shading=True,
        show_scalar_bar=True,
        scalar_bar_args={"title": bar_title or unit_title, "fmt": "%.2e"},
        label="Contributing Isopleths"
    )

    # C. Add Sensor Bounding Box
    add_sensor_box(plotter, sensor_center, sensor_size, surface_opacity=0.4, line_width=2.5)

    # --- 8. Environment & Camera Controls ---
    plotter.set_background("white")
    plotter.add_axes()
    show_iso_grid(plotter)
    plotter.add_legend()
    return True


def plot_particles_with_velocity(
    particle_df,
    sensor_center,
    sensor_size,
    save_path,
    scalar_field="vel_mag",
    display_mode="points",       # "points" (dots) or "lines" (streamlines)
    point_size=4.0,
    stride=1,                    # Subsample stride to keep rendering responsive
    map_filepath=None,
    dx=2.0,
    crop_approach=False,
    x_start=3072.0
):
    """
    Renders 3D particles colored by instantaneous velocity components or kinetic energy.
    Supported scalar_field values: 'u', 'v', 'w', 'vel_mag', 'tke_sgs', 'w_total'
    Opens an interactive window ('s' saves a screenshot).
    """
    plotter = pv.Plotter(off_screen=False)
    n_points = add_particles_with_velocity(
        plotter, particle_df, sensor_center, sensor_size, scalar_field, display_mode,
        point_size, stride, map_filepath, dx, crop_approach, x_start)
    if not n_points:
        plotter.close()
        return

    add_snapshot_key(plotter, save_path)
    print(f"Interactive window opened. Rendering {n_points:,} particle points. Press 's' to capture view.")
    plotter.show()


def velocity_scalars(particle_df, scalar_field):
    """
    Returns (scalars, cmap, bar_title, clim) for one scalar_field of a velocity frame
    from load_trajectories_with_velocities.
    u, v, w = resolved (grid-scale); *_total = what the particle moves with (resolved + SGS).
    """
    u = particle_df["u_res"].to_numpy()
    v = particle_df["v_res"].to_numpy()
    w = particle_df["w_res"].to_numpy()
    u_total = particle_df["u"].to_numpy()
    v_total = particle_df["v"].to_numpy()
    w_total = particle_df["w"].to_numpy()
    u_sgs = particle_df["u_sgs"].to_numpy()
    v_sgs = particle_df["v_sgs"].to_numpy()
    w_sgs = particle_df["w_sgs"].to_numpy()

    if scalar_field == "u":
        scalars = u
        cmap = "viridis"
        bar_title = "Streamwise u [m/s]"
        clim = None
    elif scalar_field == "v":
        scalars = v
        cmap = "coolwarm"
        bar_title = "Spanwise v [m/s]"
        max_abs = max(abs(np.percentile(scalars, 2)), abs(np.percentile(scalars, 98)))
        clim = [-max_abs, max_abs]
    elif scalar_field == "w":
        scalars = w
        cmap = "coolwarm"
        bar_title = "Vertical w [m/s]"
        max_abs = max(abs(np.percentile(scalars, 2)), abs(np.percentile(scalars, 98)))
        clim = [-max_abs, max_abs]
    elif scalar_field == "w_total":
        scalars = w_total
        cmap = "coolwarm"
        bar_title = "Total Vertical w [m/s]"
        max_abs = max(abs(np.percentile(scalars, 2)), abs(np.percentile(scalars, 98)))
        clim = [-max_abs, max_abs]
    elif scalar_field == "tke_sgs":
        scalars = 0.5 * (u_sgs**2 + v_sgs**2 + w_sgs**2)
        cmap = "inferno"
        bar_title = "SGS TKE [m$^2$/s$^2$]"
        clim = [0.0, np.percentile(scalars, 99)]
    elif scalar_field == "vel_mag":
        scalars = np.sqrt(u_total**2 + v_total**2 + w_total**2)
        cmap = "plasma"
        bar_title = "Velocity Magnitude |U| [m/s]"
        clim = [0.0, np.percentile(scalars, 99)]
    else:
        raise ValueError(f"Unknown scalar_field: {scalar_field}")
    return scalars, cmap, bar_title, clim


def add_particles_with_velocity(
    plotter,
    particle_df,
    sensor_center,
    sensor_size,
    scalar_field="vel_mag",
    display_mode="points",
    point_size=4.0,
    stride=1,
    map_filepath=None,
    dx=2.0,
    crop_approach=False,
    x_start=3072.0,
    clim=None,
    bar_title=None
):
    """
    Draws the velocity-coloured particle scene into the active renderer of `plotter`,
    so it also works in one subplot of a side-by-side plotter.
    clim / bar_title override the colour range and scalar-bar title (e.g. one shared
    range for two cases). Returns the number of points drawn (0 = nothing drawn).
    """
    if particle_df is None or len(particle_df) == 0:
        print("[ERROR] No particle data provided to plot.")
        return 0

    #1. Subsample points if needed for interactive performance
    if stride > 1:
        particle_df = particle_df.gather_every(stride)

    if crop_approach:
        particle_df = particle_df.filter(pl.col("x") >= x_start)

    # 2. Extract coordinates
    pts = np.column_stack((
        particle_df["x"].to_numpy(),
        particle_df["y"].to_numpy(),
        particle_df["z"].to_numpy()
    ))

    # 3. Compute requested scalar field and select colormap
    scalars, cmap, default_title, default_clim = velocity_scalars(particle_df, scalar_field)
    clim = clim if clim is not None else default_clim
    bar_title = bar_title or default_title

    # 4. Construct PyVista PolyData
    poly = pv.PolyData(pts)
    poly.point_data[bar_title] = scalars

    # If lines mode is selected, connect IDs into continuous polylines
    if display_mode == "lines":
        particle_ids = particle_df["id"].to_numpy()
        unique_ids, split_indices = np.unique(particle_ids, return_index=True)
        id_groups = np.split(np.arange(len(pts)), split_indices[1:])

        line_cells = []
        for group in id_groups:
            if len(group) >= 2:
                line_cells.append(len(group))
                line_cells.extend(group)
        poly.lines = np.array(line_cells)

    # 5. Setup Plotter Scene
    plotter.set_background("white")

    # Add Particle Geometry
    if display_mode == "points":
        plotter.add_mesh(
            poly,
            scalars=bar_title,
            cmap=cmap,
            clim=clim,
            render_points_as_spheres=True,
            point_size=point_size,
            opacity=0.85,
            show_scalar_bar=True,
            scalar_bar_args={"title": bar_title, "vertical": True, "title_font_size": 10}
        )
    else:
        plotter.add_mesh(
            poly,
            scalars=bar_title,
            cmap=cmap,
            clim=clim,
            line_width=1.5,
            opacity=0.7,
            show_scalar_bar=True,
            scalar_bar_args={"title": bar_title, "vertical": True, "title_font_size": 10}
        )

    # Add Sensor Indicator
    add_sensor_box(plotter, sensor_center, sensor_size, surface_opacity=0.35, line_width=2, wire_opacity=0.8)

    # 6. Add Map Geometry
    if map_filepath and os.path.exists(map_filepath):
        elevation_mat, nx_map, ny_map = load_lbm_map(map_filepath)
        add_voxel_buildings(plotter, elevation_mat, nx_map, ny_map, dx, opacity=0.9,
                            crop_approach=crop_approach, x_start=x_start)

        # Snapped Ground Plane
        add_ground_plane(plotter, nx_map * dx, ny_map * dx,
                         crop_approach=crop_approach, x_start=x_start, opacity=0.15)

    # 7. Viewport & Screenshot Control
    show_iso_grid(plotter)
    return poly.n_points
