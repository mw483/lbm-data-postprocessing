import sys
import os
import pyvista as pv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.map_io import load_lbm_map, create_voxel_buildings
from data_loaders.lbm_parsers import build_3d_density_volume


def plot_3d_isopleths(map_filepath, density_dir, isopleth_values, dx=2.0, dz=2.0):
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

    # Extract dynamic shapes (nx, ny, nz)
    nx, ny, nz = volume_3d.shape
    
    # Create the Density Grid (Dimensions are +1 to define cell corners)
    density_grid = pv.ImageData(
        dimensions=(nx + 1, ny + 1, nz + 1),
        spacing=(dx, dx, dz), 
        origin=(0.0, 0.0, 0.0)
    )
    
    # Assign the 3D matrix to the cells (flattened in Fortran order)
    density_grid.cell_data["Density"] = volume_3d.flatten(order="F")
    
    # Convert cell data to point data (REQUIRED for smooth isosurface contouring)
    density_grid = density_grid.cell_data_to_point_data()

    # ==========================================
    # 3. Generate the Isopleths (Contours)
    # ==========================================
    print(f"Calculating 3D isopleths for values: {isopleth_values}...")
    contours = density_grid.contour(isosurfaces=isopleth_values, scalars="Density")

    # ==========================================
    # 4. Render the Scene
    # ==========================================
    print("Initializing PyVista rendering environment...")
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
        opacity=0.6,             # Semi-transparent to show inner cores
        show_scalar_bar=True,
        scalar_bar_args={"title": "Particle Density"},
        name="Plume"
    )

    # Aesthetic environment settings
    plotter.set_background('white')
    plotter.add_axes()
    plotter.show_grid(color='black')
    
    plotter.show()