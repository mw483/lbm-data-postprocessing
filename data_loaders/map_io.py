import numpy as np
import pyvista as pv

def load_lbm_map(filepath):
    """
    Loads an LBM .dat map file.
    Extracts grid dimensions from the first line and reads the elevation matrix.
    """
    with open(filepath, 'r') as f:
        header = f.readline().strip().split()
        nx = int(header[0])
        ny = int(header[1])

    # Load the matrix, skipping the dimension header
    elevation_matrix = np.loadtxt(filepath, skiprows=1)
    
    # Ensure standard matrix orientation (Y-axis = rows, X-axis = columns)
    if elevation_matrix.shape != (ny, nx):
        elevation_matrix = elevation_matrix.reshape((ny, nx))
        
    return elevation_matrix, nx, ny


def create_voxel_buildings(elevation_matrix, nx, ny, resolution=2.0):
    """
    Converts a 2D LBM elevation matrix into a 3D voxel mesh for PyVista.
    X/Y are assumed to be in grids, while the matrix values (Z) are in meters.
    """
    # max_h is now in METERS
    max_h_meters = int(np.max(elevation_matrix))
    if max_h_meters <= 0:
        return None 
        
    # Create a 3D uniform grid
    # Spacing: X/Y get multiplied by 'resolution' (dx), Z gets multiplied by 1.0
    grid = pv.ImageData(
        dimensions=(nx + 1, ny + 1, max_h_meters + 1),
        spacing=(resolution, resolution, 1.0), 
        origin=(0, 0, 0)
    )
    
    cell_data = np.zeros((nx, ny, max_h_meters), dtype=bool)
    
    for y in range(ny):
        for x in range(nx):
            h_meters = int(elevation_matrix[y, x])
            if h_meters > 0:
                # Mark cells from ground up to the height in meters as solid
                cell_data[x, y, 0:h_meters] = True
                
    grid.cell_data['Building_Mask'] = cell_data.flatten(order='F')
    building_mesh = grid.threshold(0.5, scalars='Building_Mask')
    
    return building_mesh