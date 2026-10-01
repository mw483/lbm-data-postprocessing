import os
import sys
import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path

from data_loaders.lbm_parsers import load_xz_yav
from physics_core.turbulence import virtual_tower

REPO_ROOT = Path(__file__).resolve().parents[1]

def main():
    # 1. Paths
    base_out = r"Z:\20260527_output_flat_3072"
    t_step = 180000

    output_dir = REPO_ROOT / "figures" / "flat_domain" / "metrics"
    os.makedirs(output_dir, exist_ok=True)

    # 2. Configuration
    sensor_x = 600.0
    dx_lbm = 2.0
    dz_lbm = 2.0
    sensor_heights = [10, 20, 30, 40, 48, 56]

    print("Loading XZ fluid matrices...")
    try:
        fields = load_xz_yav(base_out, t_step, variables=("vm", "vv"))
    except FileNotFoundError as e:
        print(f"[ERROR] Failed to load XZ matrices: {e}")
        sys.exit(1)

    # 3. Virtual tower at X = sensor_x: sigma_v = sqrt(vv - vm^2)
    print(f"Calculating true resolved sigma_v for Virtual Tower at X={sensor_x}m...")
    tower = virtual_tower(fields, sensor_x, dx=dx_lbm, dz=dz_lbm)
    z_heights = tower["z"]
    sigma_v_profile = tower["sigma_v"]

    # 4. Generate the Seminar Plot
    fig, ax = plt.subplots(figsize=(7, 9))
    
    # Plot the full profile as a scatter plot
    ax.scatter(sigma_v_profile, z_heights, color='royalblue', alpha=0.8, 
               edgecolors='black', s=50, label=r'Resolved Grid $\sigma_v$')
    
    # Add a faint connecting line to show the profile shape
    ax.plot(sigma_v_profile, z_heights, color='royalblue', alpha=0.3, linewidth=2)

    # 5. Overlay the Horizontal Sensor Lines
    # Use a visually distinct color palette for the heights
    colors = ['#d62728', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#e377c2']
    
    for h, c in zip(sensor_heights, colors):
        ax.axhline(y=h, color=c, linestyle='--', linewidth=2, alpha=0.8, 
                   label=rf'Sensor $Z_m$ = {h}m')

    # Formatting
    ax.set_title(rf"Vertical Profile of Resolved Lateral Turbulence ($\sigma_v$)"+"\n"+f"at Virtual Tower (X={sensor_x}m)", 
                 fontsize=14, pad=15, fontweight='bold')
    ax.set_xlabel(r"Resolved Lateral Turbulence $\sigma_v$ [m/s]", fontsize=12, fontweight='bold')
    ax.set_ylabel("Domain Height Z [m]", fontsize=12, fontweight='bold')
    
    ax.set_ylim(0, max(z_heights))
    
    # Optional: Force the X-axis to stretch to 0.25 to visually show the "SGS Gap"
    # ax.set_xlim(0, 0.26) 
    
    ax.grid(True, linestyle=':', alpha=0.7)

    # Place legend cleanly outside the plot
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), fontsize=11, frameon=True)

    plt.tight_layout()
    save_path = os.path.join(output_dir, "resolved_sigmav_vertical_profile.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    print(f"Success! Saved profile plot to: {save_path}")

if __name__ == "__main__":
    main()