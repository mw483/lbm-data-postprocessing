import matplotlib.pyplot as plt
import numpy as np
import os

def plot_plume_memory_experiment(X, Y, lbm_pdf, kljun_local, kljun_ground, thresholds, 
                                 sensor_pos, save_path, x_bounds=[0, 1024], y_bounds=[0, 256]):
    """Plots a 1x3 comparison for the Sigma_v sensitivity experiment."""
    
    # Peak Normalization
    lbm_norm = lbm_pdf / np.max(lbm_pdf)
    klocal_norm = kljun_local / np.max(kljun_local)
    kground_norm = kljun_ground / np.max(kljun_ground)
    
    thresh_norm = [t / np.max(lbm_pdf) for t in thresholds] # Approximate thresholds
    
    fig, axes = plt.subplots(1, 3, figsize=(20, 5), sharey=True)
    fig.suptitle(r"Plume Memory Experiment: Impact of $\sigma_v$ on Kljun FFP Morphology (Z=40m)", fontsize=16, y=1.05)
    
    mesh_kwargs = {'cmap': 'jet', 'vmin': 0, 'vmax': 1, 'shading': 'auto'}
    
    titles = [
        r"1. Kljun (Local $\sigma_v$ at 20m)", 
        r"2. Kljun (Ground $\sigma_v$ at 2m)", 
        r"3. LBM Truth (Z=20m)"
    ]
    data = [klocal_norm, kground_norm, lbm_norm]
    
    for ax, pdf, title in zip(axes, data, titles):
        im = ax.pcolormesh(X, Y, pdf, **mesh_kwargs)
        ax.contour(X, Y, pdf, levels=[0.2, 0.4, 0.6, 0.8], colors='white', linewidths=1.5, alpha=0.9)
        ax.plot(sensor_pos[0], sensor_pos[1], 'w*', markersize=15, markeredgecolor='k')
        ax.set_title(title, fontsize=13)
        ax.set_xlabel("Downwind Distance X [m]")
        ax.set_xlim(x_bounds)
        ax.set_ylim(y_bounds)
        ax.set_aspect('equal', adjustable='box')

    axes[0].set_ylabel("Crosswind Distance Y [m]")
    fig.colorbar(im, ax=axes, pad=0.02, aspect=30, label='Normalized Contribution Density')

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)


def plot_arbitrary_sigmav_sweep(X, Y, lbm_pdf, kljun_pdfs, test_sigmas, sensor_pos, save_path, x_bounds=[0, 1024], y_bounds=[0, 256]):
    """Plots a 1x5 comparison for the arbitrary Sigma_v sensitivity sweep."""
    
    num_plots = len(kljun_pdfs) + 1
    fig, axes = plt.subplots(1, num_plots, figsize=(5 * num_plots, 5), sharey=True)
    fig.suptitle("Parameter Sweep: Forcing Analytical Crosswind Spread to Match LBM Volume (Z=40m)", fontsize=16, y=1.05)
    
    mesh_kwargs = {'cmap': 'jet', 'vmin': 0, 'vmax': 1, 'shading': 'auto'}
    
    # 1. Plot LBM Truth in the first panel
    lbm_norm = lbm_pdf / np.max(lbm_pdf)
    axes[0].pcolormesh(X, Y, lbm_norm, **mesh_kwargs)
    axes[0].contour(X, Y, lbm_norm, levels=[0.2, 0.4, 0.6, 0.8], colors='white', linewidths=1.5, alpha=0.9)
    axes[0].plot(sensor_pos[0], sensor_pos[1], 'w*', markersize=15, markeredgecolor='k')
    axes[0].set_title("LBM Truth (40m Volumetric Sensor)", fontsize=13)
    axes[0].set_ylabel("Crosswind Distance Y [m]")
    
    # 2. Plot the arbitrary Kljun runs
    for i, (kljun_pdf, sig_v) in enumerate(zip(kljun_pdfs, test_sigmas)):
        ax = axes[i + 1]
        k_norm = kljun_pdf / np.max(kljun_pdf)
        
        im = ax.pcolormesh(X, Y, k_norm, **mesh_kwargs)
        ax.contour(X, Y, k_norm, levels=[0.2, 0.4, 0.6, 0.8], colors='white', linewidths=1.5, alpha=0.9)
        ax.plot(sensor_pos[0], sensor_pos[1], 'w*', markersize=15, markeredgecolor='k')
        
        ax.set_title("Kljun Point-Sensor" + "\n" + rf"Forced $\sigma_v$ = {sig_v:.3f} m/s", fontsize=13)
    
    # Global formatting
    for ax in axes:
        ax.set_xlabel("Downwind Distance X [m]")
        ax.set_xlim(x_bounds)
        ax.set_ylim(y_bounds)
        ax.set_aspect('equal', adjustable='box')

    fig.colorbar(im, ax=axes.ravel().tolist(), pad=0.02, aspect=30, label='Normalized Contribution Density')

    import os
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)