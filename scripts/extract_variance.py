import os
import sys
import json
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from physics_core.turbulence import calc_sigma_v
from data_loaders.lbm_parsers import XYStackedParser

def main():
    # 1. Paths and File Names
    base_dir = r"Z:\20260527_output_flat_3072"
    # Assuming the naming convention matches the um file
    vv_file = os.path.join(base_dir, "xy_vv00180000_0000.csv")
    vm_file = os.path.join(base_dir, "xy_vm00180000_0000.csv")
    json_path = r"../physics_core/metrics/schmid_params.json"
    
    # 2. Domain and Sensor Setup
    grid_res = 2.0
    # The parser uses the raw Z-grid index as the dictionary key
    # Grid 5 = 10m, 10 = 20m, 15 = 30m, 20 = 40m, 24 = 48m, 28 = 56m
    target_grids = [5, 10, 15, 20, 24, 28] 
    
    # Instantiate parser. 
    # (Note: Set ny_rows to 257 since you previously observed the Y-matrix spanning Rows 3 to 259)
    parser = XYStackedParser(ny_rows=257)
    
    print(f"Loading XY Variance (vv) from: {vv_file}")
    vv_data = parser.parse_file(vv_file)
    
    print(f"Loading XY Mean V (vm) from: {vm_file}")
    vm_data = parser.parse_file(vm_file)
    
    if not vv_data or not vm_data:
        print("[ERROR] Failed to load one or both XY matrices. Exiting.")
        sys.exit(1)
        
    # Load the existing Schmid params to append our new data
    if not os.path.exists(json_path):
        print(f"[ERROR] {json_path} not found. Run 01_extract_wind_stats.py first.")
        sys.exit(1)
        
    with open(json_path, 'r') as f:
        schmid_params = json.load(f)
        
    # Create a sub-dictionary to hold sigma_v for each height
    sigma_v_dict = {}
    
    print("\n--- Extracting Lateral Standard Deviation (sigma_v) ---")
    for z_grid in target_grids:
        # Float matching depending on how the C++ writer formatted the grid index
        grid_key = float(z_grid) 
        
        if grid_key in vv_data and grid_key in vm_data:
            # Extract the 2D planes
            vv_plane = vv_data[grid_key]
            vm_plane = vm_data[grid_key]
            
            # Spatially average the entire flat plane to eliminate local turbulent noise
            vv_mean = np.mean(vv_plane)
            vm_mean = np.mean(vm_plane)
            
            # Calculate sigma_v using your physics core
            sigma_v = calc_sigma_v(vv_mean, vm_mean)
            
            # Convert back to physical height for the JSON
            z_physical = int(z_grid * grid_res)
            
            print(f"  Z = {z_physical}m (Grid {z_grid}): sigma_v = {sigma_v:.4f} m/s")
            
            # Save to dictionary mapped by a string of the physical height (e.g., "10")
            sigma_v_dict[str(z_physical)] = float(sigma_v)
        else:
            print(f"  [WARNING] Grid Z={z_grid} missing from parsed data.")
            
    # Append to our JSON parameters
    schmid_params["sigma_v"] = sigma_v_dict
    
    with open(json_path, 'w') as f:
        json.dump(schmid_params, f, indent=4)
        
    print(f"\nSuccessfully appended sigma_v values to {json_path}!")

if __name__ == "__main__":
    main()