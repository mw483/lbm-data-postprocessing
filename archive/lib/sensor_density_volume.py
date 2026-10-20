"""Retired 2026-10-01: sensor density volume from the C++ sensor_*_xy_number_density files.
Replaced in August by binning target_trajectories.csv (plot_sensor_density_isosurfaces).
Not maintained; imports may need fixing before reuse."""

# --- was in data_loaders/lbm_parsers.py ---
def build_sensor_density_volume(directory_path, sensor_x, sensor_y, sensor_z):
    """
    Builds a 3D NumPy volume by parsing only the density planes 
    belonging to a specific Sensor XYZ coordinate.
    """
    parser = XYDensityParser()
    
    # 1. Define the exact search pattern using the provided coordinates
    # Pattern: sensor_{sensor_id}_{x}_{y}_{z}_xy_number_density_*m.csv
    # We use a wildcard (*) for the sensor_id since we just want to match the X, Y, Z.
    search_pattern = os.path.join(
        directory_path, 
        f"sensor_{int(sensor_x)}_{int(sensor_y)}_{int(sensor_z)}_xy_number_density_*m.csv"
    )
    
    files = glob.glob(search_pattern)
    
    if not files:
        print(f"[ERROR] No density files found for Sensor at ({sensor_x}, {sensor_y}, {sensor_z}) in directory.")
        return None

    sorted_files = sorted(files, key=extract_z_height)
    
    # 3. Parse and stack
    layers = []
    for f in sorted_files:
        matrix = parser.parse_file(f)
        if matrix is not None:
            layers.append(matrix)
            
    if not layers:
        return None

    # 4. Construct the physical 3D Volume
    volume_3d = np.stack(layers, axis=2)
    volume_3d = np.transpose(volume_3d, (1, 0, 2))  # Match PyVista (nx, ny, nz)
    
    print(f"Successfully built 3D Sensor Footprint Volume with shape: {volume_3d.shape}")
    return volume_3d


# --- was in plotting_core/density_plots.py ---
def plot_sensor_3d_isosurfaces(map_filepath, save_path, density_dir, isosurface_values, sensor_center, sensor_size, dx=2.0, dz=2.0):
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

    sx, sy, sz = sensor_center
    print(f"Aggregating 3D Footprint for Sensor at ({sx}, {sy}, {sz})...")

    print(f"Aggregating density layers from: {density_dir}...")
    volume_3d = build_sensor_density_volume(density_dir, sx, sy, sz)
    
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
    target_particles = np.array(isosurface_values)
    
    # Convert those target values into Log space for the contour filter
    log_isopleths = np.log10(target_particles + 1).tolist()

    # Generate contours using the Log data and Log thresholds
    contours = density_grid.contour(isosurfaces=log_isopleths, scalars="Log_Density")

    # ==========================================
    # 4. Render the Scene
    # ==========================================
    print("Initializing PyVista rendering environment...")

    plotter = pv.Plotter()

    sdx, sdy, sdz = sensor_size
    bounds = [
        sx - sdx/2, sx + sdx/2,
        sy - sdy/2, sy + sdy/2,
        sz - sdz/2, sz + sdz/2
    ]
    sensor_mesh = pv.Box(bounds=bounds)
    plotter.add_mesh(sensor_mesh, color="red", style="wireframe", line_width=3, name="Sensor")

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
    # Take one snap by default if no screenshots are taken manually
    if snap_counter[0] == 0:
        take_snap()
