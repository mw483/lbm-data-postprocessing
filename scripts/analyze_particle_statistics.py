import os
import numpy as np
import matplotlib.pyplot as plt

def main():
    # 1. Paths
    bin_dir = r"Z:\20260527_particle_flat_3072"
    time_step = 1600
    
    uvw_file = os.path.join(bin_dir, f"uvw0-{time_step}.bin")
    sgs_file = os.path.join(bin_dir, f"uvw_sgs0-{time_step}.bin")
    output_dir = r"../figures/flat_domain/metrics"
    os.makedirs(output_dir, exist_ok=True)

    print(f"--- Analyzing Particle Kinematics at T={time_step} ---")

    # 2. Load and parse the binaries (Stripping the 1-item header)
    if not os.path.exists(uvw_file) or not os.path.exists(sgs_file):
        print("[ERROR] Binary files not found.")
        return

    # Reshape into N rows by 3 columns (U, V, W)
    gs_velocities = np.fromfile(uvw_file, dtype=np.float32)[1:].reshape(-1, 3)
    sgs_velocities = np.fromfile(sgs_file, dtype=np.float32)[1:].reshape(-1, 3)

    num_particles = len(gs_velocities)
    print(f"Successfully loaded {num_particles} particles.")

    # 3. Extract Lateral (Crosswind) Velocities (Index 1 is the 'V' component)
    v_gs = gs_velocities[:, 1]
    v_sgs = sgs_velocities[:, 1]

    # 4. Calculate Core Turbulence Statistics
    # Standard deviation of velocity = Sigma_v
    sigma_v_gs = np.std(v_gs)
    sigma_v_sgs = np.std(v_sgs)
    
    # Total effective lateral turbulence via variance addition
    sigma_v_eff = np.sqrt(sigma_v_gs**2 + sigma_v_sgs**2)

    print("\n--- LATERAL TURBULENCE (SIGMA_V) RESULTS ---")
    print(f"Resolved Grid Sigma_v  : {sigma_v_gs:.4f} m/s")
    print(f"Sub-Grid Scale Sigma_v : {sigma_v_sgs:.4f} m/s")
    print(f"--------------------------------------------")
    print(f"TOTAL EFFECTIVE SIGMA_V: {sigma_v_eff:.4f} m/s")
    print(f"--------------------------------------------")

    # 5. Plot the Probability Distributions (Histograms)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    fig.suptitle(f"Lateral Velocity Distributions across {num_particles:,} Particles (T={time_step})", fontsize=15)

    # Panel 1: Resolved Grid Velocity
    ax1.hist(v_gs, bins=100, color='blue', alpha=0.7, density=True)
    ax1.set_title(f"Resolved Grid Velocity ($v$)\n$\\sigma = {sigma_v_gs:.4f}$ m/s", fontsize=13)
    ax1.set_xlabel("Lateral Velocity [m/s]")
    ax1.set_ylabel("Probability Density")
    ax1.grid(True, linestyle='--', alpha=0.6)
    
    # Panel 2: SGS Random Walk Velocity
    ax2.hist(v_sgs, bins=100, color='red', alpha=0.7, density=True)
    ax2.set_title(f"SGS Random Walk Velocity ($v_{{sgs}}$)\n$\\sigma = {sigma_v_sgs:.4f}$ m/s", fontsize=13)
    ax2.set_xlabel("Lateral Velocity [m/s]")
    ax2.grid(True, linestyle='--', alpha=0.6)

    # Force both X-axes to have the same scale for visual comparison
    max_val = max(np.max(np.abs(v_gs)), np.max(np.abs(v_sgs)))
    ax1.set_xlim(-max_val, max_val)
    ax2.set_xlim(-max_val, max_val)

    plt.tight_layout()
    save_path = os.path.join(output_dir, f"velocity_distribution_T{time_step}.png")
    plt.savefig(save_path, dpi=300)
    plt.close()
    
    print(f"\nSaved distribution histogram to: {save_path}")

if __name__ == "__main__":
    main()