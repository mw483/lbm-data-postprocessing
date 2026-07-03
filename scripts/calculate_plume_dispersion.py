import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Ensure Python can find the modular packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.footprint_io import load_source_positions

def main():
    # 1. Paths
    bin_dir = r"Z:\20260527_particle_flat_3072"
    pos_file = r"Z:\particle_position\particle_position.txt"
    time_step = 1800
    
    idx_file = os.path.join(bin_dir, f"index0-{time_step}.bin")
    pos_file_bin = os.path.join(bin_dir, f"position0-{time_step}.bin")
    output_dir = r"../figures/flat_domain/metrics"
    os.makedirs(output_dir, exist_ok=True)

    print(f"--- Calculating Ensemble Spatial Plume Dispersion at T={time_step} ---")

    # 2. Load Source Map and Particle Binaries
    source_map = load_source_positions(pos_file)
    
    if not os.path.exists(idx_file) or not os.path.exists(pos_file_bin):
        print("[ERROR] Binary files not found.")
        return

    indices = np.fromfile(idx_file, dtype=np.int32)[1:]
    positions = np.fromfile(pos_file_bin, dtype=np.float32)[1:].reshape(-1, 3)
    source_ids = indices // 10000

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