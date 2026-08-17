import numpy as np
import pandas as pd
import os
import glob
import re

class XYStackedParser:
    """
    Parses stacked 2D matrices (XY planes) from LBM CSV output.
    Format: Header -> Z-Height -> N rows of Y-data -> Z-Height -> ...
    """
    def __init__(self, ny_rows=160):
        self.ny_rows = ny_rows

    def parse_file(self, file_path):
        """Returns a dictionary of {z_height: 2D_numpy_array}."""
        if not os.path.exists(file_path):
            print(f"[ERROR] File not found: {file_path}")
            return None

        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        data_dict = {}
        current_line = 1 # Skip Header
        
        while current_line < len(lines):
            line = lines[current_line].strip()
            if not line:
                current_line += 1
                continue
                
            # Z-height marker
            if ',' not in line:
                try:
                    z_height = float(line)
                except ValueError:
                    current_line += 1
                    continue

                grid_block = []
                
                # Read the Y-rows for this Z-height
                for _ in range(self.ny_rows):
                    current_line += 1
                    if current_line >= len(lines):
                        break
                    
                    row_data = [float(x) for x in lines[current_line].strip().split(',') if x]
                    if row_data:
                        grid_block.append(row_data)
                    
                if grid_block:
                    data_dict[z_height] = np.array(grid_block)
                
            current_line += 1
            
        return data_dict
    

class XYDensityParser:
    """
    Parses a single 2D matrix (XY plane) from LBM Particle Density
    """
    def __init__(self):
        self.nx = None
        self.ny = None

    def parse_file(self, file_path):
        if not os.path.exists(file_path):
            print(f"[ERROR] File not found: {file_path}")
            return None

        matrix = np.loadtxt(file_path, delimiter=',')

        if self.ny is None or self.nx is None:
            self.ny, self.nx = matrix.shape
        
        return matrix


class XZMatrixParser:
    """
    Parses a single 2D matrix (XZ plane) from LBM CSV output.
    Format: Header -> Row 1 (Z=0) -> Row 2 (Z=1) ...
    """
    @staticmethod
    def parse_file(file_path):
        """
        Returns a 2D numpy array: data[z_idx, x_idx].
        Row 0 of the returned array corresponds to the ground level (Z=0).
        """
        if not os.path.exists(file_path):
            print(f"[ERROR] File not found: {file_path}")
            return None

        try:
            # np.genfromtxt handles the matrix natively. skip_header=1 ignores the first line.
            matrix = np.genfromtxt(file_path, delimiter=',', skip_header=1)
            
            # Clean trailing empty columns caused by trailing commas
            # This checks if a column is entirely NaNs and removes it.
            matrix = matrix[:, ~np.isnan(matrix).all(axis=0)]
            
            return matrix
        except Exception as e:
            print(f"[ERROR] Failed to parse XZ matrix {file_path}: {e}")
            return None

        
def extract_z_height(filepath):
        match = re.search(r"density_(\d+)m\.csv", filepath)
        return int(match.group(1)) if match else 0


def build_3d_density_volume(directory_path):
    # Initialize your new parser
    parser = XYDensityParser()
    
    # 1. Glob all the density files in the folder
    search_pattern = os.path.join(directory_path, "xy_number_density_*m.csv")
    files = glob.glob(search_pattern)
    
    if not files:
        print("[ERROR] No density files found in directory.")
        return None

    # 2. Define the sorting logic (extracting the Z-height from the filename)
    # Sort files physically from bottom to top (e.g., 2m, 4m, 6m...)
    sorted_files = sorted(files, key=extract_z_height)
    
    # 3. Parse and collect the 2D arrays
    layers = []
    for f in sorted_files:
        matrix = parser.parse_file(f)
        if matrix is not None:
            layers.append(matrix)
            
    # 4. Stack them into a 3D volume
    # np.stack creates a shape of (ny, nx, nz)
    volume_3d = np.stack(layers, axis=2)
    
    # Transpose to (nx, ny, nz) to match PyVista and standard Cartesian coordinates
    volume_3d = np.transpose(volume_3d, (1, 0, 2))
    
    print(f"Successfully built 3D volume with shape (in grids): {volume_3d.shape}")
    return volume_3d


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