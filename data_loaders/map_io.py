import numpy as np

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