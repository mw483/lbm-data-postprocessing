import os
import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path

from data_loaders.footprint_io import load_source_positions
from data_loaders.particle_bin import load_step, source_id

REPO_ROOT = Path(__file__).resolve().parents[1]

def main():
    # 1. Paths
    bin_dir = r"Z:\20260527_particle_flat_3072"
    pos_file = r"Z:\particle_position\particle_position.txt"
    time_step = 1800
    output_dir = REPO_ROOT / "figures" / "flat_domain" / "metrics"
    os.makedirs(output_dir, exist_ok=True)

    print(f"--- Calculating Ensemble Spatial Plume Dispersion at T={time_step} ---")

    # 2. Load Source Map and Particle Binaries
    source_map = load_source_positions(pos_file)
    
    # All rank files for this step
    data = load_step(bin_dir, time_step, fields=("index", "position"))
    positions = data["position"]
    source_ids = source_id(data["index"])

    print(f"Loaded {len(positions)} total particles. Calculating relative displacements...")

    # 3. Calculate Relative Fetch and Displacement for ALL particles
    fetch_x = []
    disp_y = []
    
    for sid, pos in zip(source_ids, positions):
        if sid in source_map:
            s_pos = source_map[sid]
            dx = pos[0] - s_pos['x']
            dy = pos[1] - s_pos['y']
            
            # Only track particles that have moved downwind
            if dx > 0:
                fetch_x.append(dx)
                disp_y.append(dy)

    fetch_x = np.array(fetch_x)
    disp_y = np.array(disp_y)

    # 4. Bin particles by downwind travel distance (Fetch X)
    x_bins = np.arange(0, 820, 20)  # Check every 20m, up to 800m fetch
    sigma_y_list = []
    x_plot = []

    for i in range(len(x_bins) - 1):
        x_min = x_bins[i]
        x_max = x_bins[i+1]
        
        # Find all particles in this travel-distance bin
        slice_mask = (fetch_x >= x_min) & (fetch_x < x_max)
        y_in_slice = disp_y[slice_mask]
        
        # With 656,000 particles, these bins will have thousands of particles each!
        if len(y_in_slice) > 50:  
            sigma_y = np.std(y_in_slice)
            sigma_y_list.append(sigma_y)
            x_plot.append((x_min + x_max) / 2.0)

    # 5. Reverse-Engineer the Effective Sigma_v
    # Using Taylor's short-range diffusion theorem: sigma_y ≈ (sigma_v / U) * x
    # Therefore: d(sigma_y)/dx ≈ sigma_v / U
    
    # We fit the line to the first 400m before boundary conditions or domain limits curve the plume
    valid_fit_idx = [i for i, x in enumerate(x_plot) if x <= 400]
    fit_x = [x_plot[i] for i in valid_fit_idx]
    fit_y = [sigma_y_list[i] for i in valid_fit_idx]
    
    slope, intercept = np.polyfit(fit_x, fit_y, 1)
    
    print("\n--- LAGRANGIAN DISPERSION RESULTS ---")
    print(rf"Plume Expansion Rate (dσ_y/dx) : {slope:.4f}")
    print("---------------------------------------")

    # 6. Plot the Plume Expansion
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(x_plot, sigma_y_list, 'bo-', linewidth=2, markersize=6, 
            label=r"True LBM Ensemble Spread ($\sigma_y$)")
            
    # Plot the line of best fit
    full_fit_line = [slope * x + intercept for x in x_plot]
    ax.plot(x_plot, full_fit_line, 'r--', linewidth=2, 
            label=f"Linear Fit (Slope = {slope:.4f})")

    ax.set_title(rf"Ensemble Lagrangian Dispersion ($\sigma_y$ vs. Fetch) across {len(positions):,} particles", fontsize=14)
    ax.set_xlabel("Downwind Travel Distance (Fetch) [m]", fontsize=12)
    ax.set_ylabel(r"Lateral Plume Spread $\sigma_y$ [m]", fontsize=12)
    
    ax.legend(fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    save_path = os.path.join(output_dir, "ensemble_spatial_dispersion.png")
    plt.savefig(save_path, dpi=300)
    plt.close()
    
    print(f"Saved ensemble spatial dispersion plot to: {save_path}")

if __name__ == "__main__":
    main()