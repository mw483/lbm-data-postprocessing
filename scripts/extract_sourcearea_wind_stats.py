import numpy as np
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from physics_core.turbulence import fit_boundary_layer_profile
from data_loaders.lbm_parsers import XZMatrixParser

def main():
    # 1. Paths
    base_dir = r"Z:\20260527_output_flat_3072"
    xz_yav_file = os.path.join(base_dir, "xz_yav_um00180000_0000.csv")
    output_json = r"../physics_core/metrics/schmid_params.json"
    
    # 2. Domain Parameters
    grid_res = 2.0  # 1 grid = 2 meters
    # Even though the parser returns a 0-indexed array, we physically align 
    # index 0 to your starting Z-grid of 2.
    start_z_grid = 2 
    
    print(f"Loading XZ-YAV Mean Velocity Profile from: {xz_yav_file}")
    
    # 3. Load and Process the Matrix using your dedicated parser
    matrix = XZMatrixParser.parse_file(xz_yav_file)
    
    if matrix is None:
        print("[ERROR] Failed to load matrix. Exiting.")
        sys.exit(1)
        
    # The number of rows in the matrix determines the Z height array
    num_z_levels = matrix.shape[0]
    
    # Create the physical Z array: [4.0, 6.0, 8.0, ...]
    z_grids = np.arange(start_z_grid, start_z_grid + num_z_levels)
    z_physical = z_grids * grid_res
    
    # Horizontally average the X-axis (columns) to get a pure 1D profile
    u_profile_1d = np.mean(matrix, axis=1)
    
    print(f"Extracted {len(z_physical)} vertical levels. Max height: {z_physical[-1]}m")
    
    # 4. Fit the Log-Law
    # We restrict the fit to the bottom 40 meters (surface layer)
    u_star, z0 = fit_boundary_layer_profile(z_physical, u_profile_1d, max_fit_height=16.0)
    
    print("-" * 30)
    print(f"Log-Law Fit Results:")
    print(f"  Friction Velocity (u*) : {u_star:.4f} m/s")
    print(f"  Roughness Length (z0)  : {z0:.4f} m")
    print("-" * 30)
    
    # 5. Save the Parameters for the Schmid Model
    params = {
        "u_star": float(u_star),
        "z0": float(z0),
        "kappa": 0.40
    }
    
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, 'w') as f:
        json.dump(params, f, indent=4)
        
    print(f"Saved atmospheric parameters to {output_json}")

if __name__ == "__main__":
    main()