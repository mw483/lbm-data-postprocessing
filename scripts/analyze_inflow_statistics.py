import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Ensure Python can find the modular packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.lbm_parsers import XZMatrixParser
from physics_core.turbulence import calc_sigma_v

def main():
    # 1. Paths and Configuration
    base_out = r"Y:\20260703_output_flat_shortroughness"
    t_step = "00180000"  # The specific suffix for time step 1200
    
    um_csv = os.path.join(base_out, f"xz_yav_um{t_step}_0000.csv")
    vm_csv = os.path.join(base_out, f"xz_yav_vm{t_step}_0000.csv")
    vv_csv = os.path.join(base_out, f"xz_yav_vv{t_step}_0000.csv")
    
    output_dir = r"../figures/flat_domain/inflow_analysis"
    os.makedirs(output_dir, exist_ok=True)

    dx_lbm = 2.0
    dz_lbm = 2.0
    x_targets = [0, 128, 428, 728] # Locations to extract vertical columns
    colors = ['#d62728', '#2ca02c', '#1f77b4', "#6c1fb4"] # Red, Green, Blue, Purple

    print(f"Loading XZ fluid matrices for step {t_step}...")
    um_mat = XZMatrixParser.parse_file(um_csv)
    vm_mat = XZMatrixParser.parse_file(vm_csv)
    vv_mat = XZMatrixParser.parse_file(vv_csv)
    
    if um_mat is None or vm_mat is None or vv_mat is None:
        print("[ERROR] Failed to load one or more XZ matrices. Check file paths.")
        return

    z_indices = np.arange(um_mat.shape[0])
    z_heights = z_indices * dz_lbm

    # 2. Generate the Side-by-Side Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    fig.suptitle(f"Boundary Layer & Turbulence Development over Flat Fetch (T={t_step[2:6]})", fontsize=15, fontweight='bold')

    for x_loc, color in zip(x_targets, colors):
        # Map X-coordinate to grid index
        x_idx = min(int(x_loc / dx_lbm), um_mat.shape[1] - 1)
        
        # Extract columns
        u_profile = um_mat[:, x_idx]
        vm_profile = vm_mat[:, x_idx]
        vv_profile = vv_mat[:, x_idx]
        
        # Calculate true resolved lateral turbulence
        sig_v_profile = calc_sigma_v(vv_profile, vm_profile)
        
        # Plot Mean Streamwise Velocity (U)
        ax1.plot(u_profile, z_heights, color=color, linewidth=2.5, 
                 label=f'Fetch X = {x_loc}m')
        
        # Plot Lateral Turbulence (Sigma_v)
        ax2.plot(sig_v_profile, z_heights, color=color, linewidth=2.5, 
                 label=f'Fetch X = {x_loc}m')

    # Formatting Panel 1 (Mean Wind)
    ax1.set_title("Mean Streamwise Wind Speed ($U$)", fontsize=13)
    ax1.set_xlabel("Velocity $U$ [m/s]", fontsize=12)
    ax1.set_ylabel("Domain Height Z [m]", fontsize=12)
    ax1.grid(True, linestyle=':', alpha=0.7)
    ax1.legend(loc='upper left')
    ax1.set_xlim(0, np.max(um_mat) * 1.1)

    # Formatting Panel 2 (Turbulence)
    ax2.set_title(r"Resolved Lateral Turbulence ($\sigma_v$)", fontsize=13)
    ax2.set_xlabel(r"Velocity Fluctuation $\sigma_v$ [m/s]", fontsize=12)
    ax2.grid(True, linestyle=':', alpha=0.7)
    ax2.legend(loc='upper right')
    
    # Optional: Highlight the "target" Kljun turbulence (0.25 m/s)
    ax2.axvline(x=0.25, color='k', linestyle='--', alpha=0.6, 
                label=r'Kljun Required $\sigma_v$ (~0.25)')
    ax2.legend(loc='upper right')

    plt.tight_layout()
    save_path = os.path.join(output_dir, f"shortroughness_inflow_turbulence_development_{t_step}.png")
    plt.savefig(save_path, dpi=300)
    
    print(f"Success! Saved inflow development plot to: {save_path}")

if __name__ == "__main__":
    main()