import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.config_loader import load_json_config

def main():
    # 1. Paths
    params_path = r"../physics_core/metrics/schmid_params.json"
    lbm_profile_csv = r"Z:\20260527_output_flat_3072\prof00180000_0000.csv"
    output_dir = r"../figures/flat_domain/metrics"
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Load Parameters
    params = load_json_config(params_path)
    sigma_v_dict = params["sigma_v"]
    
    # Extract Z heights and sigma_v values, sort them by Z
    z_sig = []
    sig_v = []
    for z_str, val in sigma_v_dict.items():
        z_sig.append(float(z_str))
        sig_v.append(float(val))
        
    # Sort lists together based on Z
    sorted_pairs = sorted(zip(z_sig, sig_v))
    z_sig = [p[0] for p in sorted_pairs]
    sig_v = [p[1] for p in sorted_pairs]
    
    # 3. Load LBM Vertical Wind Profile
    df_lbm = pd.read_csv(lbm_profile_csv, delim_whitespace=False, skiprows=1, header=0)
    z_lbm = df_lbm['z'].values
    u_lbm = df_lbm['U'].values
    
    # 4. Create the Side-by-Side Seminar Figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    fig.suptitle("LBM Boundary Layer Statistics (The 'Plume Memory' Drivers)", fontsize=16)
    
    # PANEL 1: Lateral Turbulence (sigma_v)
    ax1.plot(sig_v, z_sig, 'ro-', linewidth=2, markersize=8, markerfacecolor='white', markeredgewidth=2)
    ax1.set_title(r"Lateral Turbulence ($\sigma_v$)", fontsize=14)
    ax1.set_xlabel(r"$\sigma_v$ [m/s]", fontsize=12)
    ax1.set_ylabel("Height Z [m]", fontsize=12)
    ax1.grid(True, linestyle=':', alpha=0.7)
    
    # Add an annotation explaining the physics
    ax1.annotate('High ground-level mixing\nwidens the LBM plume.', 
                 xy=(sig_v[0], z_sig[0]), xytext=(sig_v[0]-0.01, z_sig[0]+15),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=6),
                 fontsize=10, bbox=dict(boxstyle="round", fc="w", alpha=0.8))

    # PANEL 2: Mean Wind Speed (U)
    ax2.plot(u_lbm, z_lbm, 'bo-', linewidth=2, markersize=4, alpha=0.7)
    ax2.set_title("Mean Streamwise Wind Speed ($U$)", fontsize=14)
    ax2.set_xlabel("$U$ [m/s]", fontsize=12)
    ax2.set_xlim(0, max(u_lbm) * 1.1)
    ax2.grid(True, linestyle=':', alpha=0.7)
    
    # Ensure limits focus on the relevant sensor area
    ax1.set_ylim(0, max(z_sig) + 20)
    
    plt.tight_layout()
    save_path = os.path.join(output_dir, "seminar_meteorological_profiles.png")
    plt.savefig(save_path, dpi=300)
    plt.close()
    
    print(f"Successfully generated boundary layer statistics plot: {save_path}")

if __name__ == "__main__":
    main()