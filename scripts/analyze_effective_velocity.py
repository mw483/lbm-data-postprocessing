import os
import sys
import numpy as np
import pandas as pd

# Add project root to path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.config_loader import load_json_config
from plotting_core.profile_plots import plot_advection_vs_fetch, plot_vertical_wind_profile

def main():
    # 1. Paths
    lbm_profile_csv = r"Z:\20260527_output_flat_3072\prof00180000_0000.csv"
    params_path = r"../physics_core/metrics/schmid_params.json"
    
    # Exact output directory requested
    output_dir = r"C:\Users\Mikael Wijaya\Documents\GitHub\lbm-data-postprocessing\figures\20260527_schmid_comparisons\effective_velocity"
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Load Atmospheric Parameters
    params = load_json_config(params_path)
    u_star = params["u_star"]
    z0 = params["z0"]
    kappa = 0.40
    
    # Constants from Van Ulden / Schmid
    p = 1.55
    phi_h = 0.74
    
    print(f"Loaded params: u_star={u_star}, z0={z0}")
    
    # 3. Load LBM Vertical Profile Data
    # Use pandas to easily skip the first row and grab columns (space/tab delimited)
    try:
        # skiprows=1 skips the garbage header, usecols grabs Z and U
        df_lbm = pd.read_csv(lbm_profile_csv, skiprows=1, header=0)
        z_lbm = df_lbm['z'].values
        u_lbm = df_lbm['U'].values
    except Exception as e:
        print(f"[ERROR] Could not load LBM profile: {e}")
        sys.exit(1)
        
    print(f"Loaded LBM profile: {len(z_lbm)} height levels.")

    # 4. Generate Theoretical Log-Law Profile
    # Only calculate where Z > z0 to avoid math domain errors
    z_theory = np.linspace(z0 + 0.001, 160, 500)
    u_theory = (u_star / kappa) * np.log(z_theory / z0)
    
    # 5. Calculate U_e as a function of Fetch (X)
    # Define a theoretical z_bar array
    z_bar_theory = np.linspace(z0/p + 0.001, 160, 5000)
    
    # Integrate to find theoretical fetch (X) for each z_bar
    x_theory = phi_h * ( (z_bar_theory / kappa**2) * (np.log(p * z_bar_theory / z0) - 1) + (z0 / (p * kappa**2)) )
    
    # We want to plot U_e vs X for the length of your domain (0 to 1000m)
    X_arr = np.linspace(1, 1000, 500)
    z_bar_grid = np.interp(X_arr, x_theory, z_bar_theory)
    
    # Calculate Effective Advection Velocity U_e
    Ue_arr = (u_star / kappa) * np.log(p * z_bar_grid / z0)
    
    # 6. Extract specific U_e points to overlay on the vertical profile
    # Let's look at the evaluation height at X=100m and X=600m
    target_fetches = [100.0, 600.0]
    fetch_points = []
    
    for fetch in target_fetches:
        zb = np.interp(fetch, x_theory, z_bar_theory)
        # The physical height where U_e is evaluated is p * z_bar
        z_eval = p * zb
        ue_val = (u_star / kappa) * np.log(z_eval / z0)
        fetch_points.append({'x': fetch, 'z_eval': z_eval, 'u_e': ue_val})
        print(f"At Fetch X={fetch}m -> Plume Hgt: {zb:.2f}m -> Evaluates U_e at Z={z_eval:.2f}m -> Speed: {ue_val:.2f} m/s")

    # 7. Generate Plots
    path_plot1 = os.path.join(output_dir, "schmid_ue_vs_fetch.png")
    plot_advection_vs_fetch(X_arr, Ue_arr, path_plot1)
    print(f"Saved Plot 1: {path_plot1}")
    
    path_plot2 = os.path.join(output_dir, "lbm_vs_theory_profile.png")
    plot_vertical_wind_profile(z_lbm, u_lbm, z_theory, u_theory, fetch_points, path_plot2)
    print(f"Saved Plot 2: {path_plot2}")

if __name__ == "__main__":
    main()