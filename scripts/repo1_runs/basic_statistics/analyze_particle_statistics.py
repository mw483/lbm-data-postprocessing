import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from data_loaders.particle_bin import load_step, particle_velocities

REPO_ROOT = Path(__file__).resolve().parents[1]


def main():
    # 1. Settings
    bin_dir = r"Z:\20260527_particle_flat_3072"
    time_step = 1600
    c_ref = 100.0          # = velocity / cfl from "-velocity_lbm 2.0 0.02" in mpirun.sh
    flg_particle = 1       # from Define_user.h; 1 means uvw already includes the SGS velocity
    output_dir = REPO_ROOT / "figures" / "flat_domain" / "metrics"
    os.makedirs(output_dir, exist_ok=True)

    print(f"--- Analyzing Particle Kinematics at T={time_step} ---")

    # 2. Load all rank files for this step (uvw in lattice units, uvw_sgs in m/s)
    data = load_step(bin_dir, time_step, fields=("uvw", "uvw_sgs"))
    vel = particle_velocities(data, c_ref=c_ref, flg_particle=flg_particle)

    num_particles = len(vel["total"])
    print(f"Successfully loaded {num_particles} particles.")

    # 3. Lateral (crosswind) velocities, index 1 = v, all in m/s
    v_gs = vel["resolved"][:, 1]
    v_sgs = vel["sgs"][:, 1]
    v_total = vel["total"][:, 1]

    # 4. Turbulence statistics
    sigma_v_gs = np.std(v_gs)
    sigma_v_sgs = np.std(v_sgs)
    # Spread of the velocity each particle actually moves with (resolved + SGS)
    sigma_v_eff = np.std(v_total)

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