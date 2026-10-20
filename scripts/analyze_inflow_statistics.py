import os
import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path

from data_loaders.lbm_parsers import load_xz_yav
from physics_core.turbulence import virtual_tower

REPO_ROOT = Path(__file__).resolve().parents[1]

def main():
    # 1. Paths and Configuration
    base_out = r"Y:\20260707_output_flat_shortroughness_4mvel"
    t_step = 180000  # output step number in the file names (xz_yav_um00180000_0000.csv)
    rank_x = 0

    output_dir = REPO_ROOT / "figures" / "flat_domain" / "inflow_analysis" / "with_ustar"
    os.makedirs(output_dir, exist_ok=True)

    dx_lbm = 2.0
    dz_lbm = 2.0
    x_targets = [0, 128, 428, 728] # Locations to extract vertical columns
    colors = ['#d62728', '#2ca02c', '#1f77b4', "#6c1fb4"] # Red, Green, Blue, Purple

    print(f"Loading XZ fluid matrices for step {t_step}...")
    try:
        fields = load_xz_yav(base_out, t_step, rank=rank_x)
    except FileNotFoundError as e:
        print(f"[ERROR] Missing XZ matrix: {e}")
        return
    um_mat = fields["um"]

    # 2. Generate the Side-by-Side Plot
    fig, (ax1, ax2, ax3) = plt.subplots(nrows=1, ncols=3, figsize=(18, 6), sharey=True)
    fig.suptitle(f"Boundary Layer & Turbulence Development over Flat Fetch (T={t_step})", fontsize=15, fontweight='bold')

    for x_loc, color in zip(x_targets, colors):
        tower = virtual_tower(fields, x_loc, dx=dx_lbm, dz=dz_lbm)
        z_heights = tower["z"]
        u_profile = tower["um"]
        sig_v_profile = tower["sigma_v"]
        u_star_profile = tower["u_star"]

        # Plot Mean Streamwise Velocity (U)
        ax1.plot(u_profile, z_heights, color=color, linewidth=2.5, 
                 label=f'Fetch X = {x_loc}m')
        
        # Plot Lateral Turbulence (Sigma_v)
        ax2.plot(sig_v_profile, z_heights, color=color, linewidth=2.5, 
                 label=f'Fetch X = {x_loc}m')
        
        # Plot Friction Velocity (U_star)
        ax3.plot(u_star_profile, z_heights, color=color, linewidth=2.5, 
                 label=f'Fetch X = {x_loc}m')

    # Formatting Panel 1 (Mean Wind)
    ax1.set_title("Mean Streamwise Wind Speed ($U$)", fontsize=13)
    ax1.set_xlabel("Velocity $U$ [m/s]", fontsize=12)
    ax1.set_ylabel("Domain Height Z [m]", fontsize=12)
    ax1.grid(True, linestyle=':', alpha=0.7)
    ax1.legend(loc='upper left')
    ax1.set_xlim(0, np.max(um_mat) * 1.1)

    # Formatting Panel 2 (Lateral Velocity Fluctuation)
    ax2.set_title(r"Resolved Lateral Turbulence ($\sigma_v$)", fontsize=13)
    ax2.set_xlabel(r"Velocity Fluctuation $\sigma_v$ [m/s]", fontsize=12)
    ax2.grid(True, linestyle=':', alpha=0.7)
    ax2.legend(loc='upper right')

    # Formatting Panel 3 (Friction Velocity)
    ax3.set_title(r"Friction Velocity ($u_*$)", fontsize=13)
    ax3.set_xlabel(r"Friction Velocity $u_*$ [m/s]", fontsize=12)
    ax3.grid(True, linestyle=':', alpha=0.7)
    ax3.legend(loc='upper right')

    # Optional: Highlight the "target" Kljun Lateral Velocity Fluctuation (0.25 m/s)
    ax2.axvline(x=0.25, color='k', linestyle='--', alpha=0.6, 
                label=r'Kljun Required $\sigma_v$ (~0.25)')
    ax2.legend(loc='upper right')

    plt.tight_layout()
    save_path = os.path.join(output_dir, f"4mvel_shortroughness_flat_inflow_turbulence_development_{t_step}.png")
    plt.savefig(save_path, dpi=300)
    
    print(f"Success! Saved inflow development plot to: {save_path}")

if __name__ == "__main__":
    main()