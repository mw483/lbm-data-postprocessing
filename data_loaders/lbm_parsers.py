import numpy as np
import pandas as pd
import os

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