import numpy as np
import pandas as pd
import time

class LBMWindParser:
    def __init__(self, ny_rows=96):
        # We define how many Y-rows belong to one height slice based on your domain
        self.ny_rows = ny_rows

    def parse_file(self, file_path):
        """Reads the stacked matrix CSV and returns a dictionary of 2D NumPy arrays."""
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        data_dict = {}
        current_line = 1 # Skip Line 0 (The Header)
        
        while current_line < len(lines):
            line = lines[current_line].strip()
            if not line:
                current_line += 1
                continue
                
            # If the line doesn't contain a comma, it is the Z-height marker
            if ',' not in line:
                z_height = float(line)
                grid_block = []
                
                # Read the next block of Y-rows
                for _ in range(self.ny_rows):
                    current_line += 1
                    if current_line >= len(lines):
                        break
                    
                    # Split by comma, ignore empty trailing strings
                    row_data = [float(x) for x in lines[current_line].strip().split(',') if x]
                    grid_block.append(row_data)
                    
                # Convert the list to a 2D NumPy Array and store it
                data_dict[z_height] = np.array(grid_block)
                
            current_line += 1
            
        return data_dict

# ==========================================
# Example Usage Over Rclone Mount
# ==========================================
if __name__ == "__main__":
    # Point this directly to your Rclone Z: drive
    file_path = "Z:/20260512_output_cubes_waypoints_test/xy_um00025000_0000.csv" 
    
    print(f"Parsing {file_path}...")
    start = time.time()
    
    parser = LBMWindParser(ny_rows=96)
    wind_data = parser.parse_file(file_path)
    
    print(f"Loaded {len(wind_data)} height slices in {time.time() - start:.3f} seconds.")

    # ---------------------------------------------------------
    # Use Case 1: Get the Spatial Average for each height
    # ---------------------------------------------------------
    print("\n--- Spatial Averages ---")
    for z, grid in wind_data.items():
        mean_u = np.mean(grid)
        max_u = np.max(grid)
        print(f"Height Z={z}: Mean U = {mean_u:.4f}, Max U = {max_u:.4f}")

    # ---------------------------------------------------------
    # Use Case 2: Extract a Vertical Profile at a specific (X, Y)
    # ---------------------------------------------------------
    # Example: You want to check the wind speed at grid coordinate X=50, Y=20 
    # across all heights to compare with your mathematical model.
    target_x_idx = 50
    target_y_idx = 20
    
    print(f"\n--- Vertical Profile at Grid(X={target_x_idx}, Y={target_y_idx}) ---")
    profile = []
    for z, grid in wind_data.items():
        # grid[y, x] - matrices are indexed row-first
        u_val = grid[target_y_idx, target_x_idx] 
        profile.append({"z_height": z, "u_velocity": u_val})
        print(f"Z={z}: U = {u_val:.4f}")
        
    # Instantly convert the profile to a Pandas DataFrame for plotting
    df_profile = pd.DataFrame(profile)