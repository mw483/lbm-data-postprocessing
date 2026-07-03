import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Ensure Python can find the modular packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.lbm_parsers import XZMatrixParser
from physics_core.turbulence import calc_sigma_v

def main():
    # 1. Paths
    base_out = r"Z:\20260527_output_flat_3072"
    vm_csv = os.path.join(base_out, "xz_yav_vm00180000_0000.csv")
    vv_csv = os.path.join(base_out, "xz_yav_vv00180000_0000.csv")
    
    output_dir = r"../figures/flat_domain/metrics"
    os.makedirs(output_dir, exist_ok=True)

    # 2. Configuration
    sensor_x = 600.0
    dx_lbm = 2.0
    dz_lbm = 2.0
    sensor_heights = [10, 20, 30, 40, 48, 56]

    print("Loading XZ fluid matrices...")
    vm_mat = XZMatrixParser.parse_file(vm_csv)
    vv_mat = XZMatrixParser.parse_file(vv_csv)
    
    if vm_mat is None or vv_mat is None:
        print("[ERROR] Failed to load XZ matrices. Exiting.")
        sys.exit(1)

    # 3. Extract the Vertical Column at X = 600m
    x_idx = min(int(sensor_x / dx_lbm), vm_mat.shape[1] - 1)
    z_indices = np.arange(vm_mat.shape[0])
    z_heights = z_indices * dz_lbm

    sigma_v_profile = []
    
    print(f"Calculating true resolved sigma_v for Virtual Tower at X={sensor_x}m...")
    for z in z_indices:
        # Calculate true variance using Reynolds decomposition: sqrt(vv - vm^2)
        sv = calc_sigma_v(vv_mat[z, x_idx], vm_mat[z, x_idx])
        sigma_v_profile.append(sv)

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