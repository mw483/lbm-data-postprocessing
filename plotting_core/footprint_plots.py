import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import os

def plot_absolute_footprint(x, y, counts, sensor_x, sensor_y, save_path, domain_extent=None):
    """
    Plots the 2D raw footprint using absolute coordinates.
    """
    fig, ax = plt.subplots(figsize=(12, 5)) # Wide aspect ratio for LBM domain
    
    # Scatter plot representing the source grids
    # s=150 scales the marker size (you may need to tweak this depending on dpi)
    scatter = ax.scatter(x, y, c=counts, cmap='jet', marker='s', s=80, alpha=0.8)
    
    # Plot the sensor location
    ax.plot(sensor_x, sensor_y, marker='*', color='magenta', markersize=15, 
            markeredgecolor='black', label=f'Sensor ({sensor_x}m, {sensor_y}m)')
    
    # Formatting
    cbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    cbar.set_label('Raw Particle Count', rotation=270, labelpad=15)
    
    ax.set_title(f'Raw LBM Source Footprint (Sensor at y={sensor_y}m)', fontsize=14)
    ax.set_xlabel('Absolute X Coordinate [m]', fontsize=12)
    ax.set_ylabel('Absolute Y Coordinate [m]', fontsize=12)
    
    # Apply domain limits if provided (e.g., [0, 1024, 0, 256])
    if domain_extent:
        ax.set_xlim(domain_extent[0], domain_extent[1])
        ax.set_ylim(domain_extent[2], domain_extent[3])
        
    ax.set_aspect('equal', adjustable='box')
    ax.legend(loc='upper right')
    ax.grid(True, linestyle='--', alpha=0.5)
    
    # Save output securely
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved footprint figure to: {save_path}")

def plot_footprint_overlay(X, Y, lbm_pdf, schmid_pdf, lbm_thresh, schmid_thresh, 
                           sensor_pos, title, save_path, x_bounds=[0, 1024], y_bounds=[0, 256]):
    """
    Overlays the Schmid (1994) analytical contour on top of the LBM footprint contour.
    """
    # 1024x256 is a 4:1 aspect ratio, so a 12x4 figure size works well
    fig, ax = plt.subplots(figsize=(12, 4))
    
    # 1. Plot LBM Footprint (Filled Contour for the 80% area)
    ax.contourf(X, Y, lbm_pdf, levels=[lbm_thresh, np.max(lbm_pdf)], colors=['#aec7e8'], alpha=0.7)
    
    # 2. Plot Schmid Analytical Footprint (Dashed Red Line for the 80% area)
    ax.contour(X, Y, schmid_pdf, levels=[schmid_thresh], colors=['red'], linestyles=['dashed'], linewidths=2)
    
    # 3. Mark the Sensor
    ax.plot(sensor_pos[0], sensor_pos[1], 'k*', markersize=10)
    
    # Formatting
    ax.set_xlabel("Downwind Distance X [m]")
    ax.set_ylabel("Crosswind Distance Y [m]")
    ax.set_title(title)
    ax.set_xlim(x_bounds[0], x_bounds[1])
    ax.set_ylim(y_bounds[0], y_bounds[1])
    ax.grid(True, linestyle=':', alpha=0.6)
    
    # Custom Legend
    legend_elements = [
        Patch(facecolor='#aec7e8', alpha=0.7, label='LBM 80% Contour'),
        Line2D([0], [0], color='red', lw=2, linestyle='dashed', label='Schmid 80% Contour'),
        Line2D([0], [0], marker='*', color='w', markerfacecolor='k', markersize=10, label='Sensor')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()

def plot_side_by_side_comparison(X, Y, lbm_pdf, schmid_pdf, lbm_thresholds, schmid_thresholds, 
                                 sensor_pos, title, save_path, x_bounds=[0, 1024], y_bounds=[0, 256]):
    """
    Plots LBM and Schmid footprints side-by-side as normalized heatmaps with nested white contours.
    """
    # 1. PEAK NORMALIZATION (Forces both grids to span 0.0 to 1.0)
    lbm_max = np.max(lbm_pdf)
    schmid_max = np.max(schmid_pdf)
    
    lbm_norm = lbm_pdf / lbm_max
    schmid_norm = schmid_pdf / schmid_max
    
    # Normalize the contour thresholds to match the new 0-1 scale
    lbm_thresh_norm = [t / lbm_max for t in lbm_thresholds]
    schmid_thresh_norm = [t / schmid_max for t in schmid_thresholds]

    # 2. Setup Figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 5), sharey=True)
    fig.suptitle(title, fontsize=16, y=1.05)
    
    # --- COLOR SCALE OPTIONS ---
    cmap = 'jet'
    
    # OPTION A: Linear Scale (Default)
    mesh_kwargs = {'cmap': cmap, 'vmin': 0, 'vmax': 1, 'shading': 'auto'}
    
    # OPTION B: Logarithmic Scale 
    # (Uncomment the line below to reveal the faint upwind tail)
    # mesh_kwargs = {'cmap': cmap, 'norm': LogNorm(vmin=1e-4, vmax=1), 'shading': 'auto'}

    # Line styles for 20%, 40%, 60%, 80%
    line_styles = ['dotted', 'dashdot', 'dashed', 'solid']

    # ==========================================
    # PANEL 1: LBM DATA
    # ==========================================
    im1 = ax1.pcolormesh(X, Y, lbm_norm, **mesh_kwargs)
    
    # Draw nested contours
    ax1.contour(X, Y, lbm_norm, levels=lbm_thresh_norm, colors='white', 
                linewidths=1.5, linestyles=line_styles, alpha=0.9)
    
    ax1.plot(sensor_pos[0], sensor_pos[1], 'w*', markersize=15, markeredgecolor='k')
    ax1.set_title("LBM-LES Plume (Closed Domain)", fontsize=14)
    ax1.set_xlabel("Downwind Distance X [m]", fontsize=12)
    ax1.set_ylabel("Crosswind Distance Y [m]", fontsize=12)
    ax1.set_xlim(x_bounds[0], x_bounds[1])
    ax1.set_ylim(y_bounds[0], y_bounds[1])
    ax1.set_aspect('equal', adjustable='box')

    # ==========================================
    # PANEL 2: SCHMID (1994) MODEL
    # ==========================================
    im2 = ax2.pcolormesh(X, Y, schmid_norm, **mesh_kwargs)
    
    # Draw nested contours
    ax2.contour(X, Y, schmid_norm, levels=schmid_thresh_norm, colors='white', 
                linewidths=1.5, linestyles=line_styles, alpha=0.9)
    
    ax2.plot(sensor_pos[0], sensor_pos[1], 'w*', markersize=15, markeredgecolor='k')
    ax2.set_title("Schmid 1994 (Infinite Domain)", fontsize=14)
    ax2.set_xlabel("Downwind Distance X [m]", fontsize=12)
    ax2.set_xlim(x_bounds[0], x_bounds[1])
    ax2.set_aspect('equal', adjustable='box')

    # ==========================================
    # GLOBAL FORMATTING
    # ==========================================
    # Add a single shared colorbar for both plots
    cbar = fig.colorbar(im1, ax=[ax1, ax2], pad=0.02, aspect=30)
    cbar.set_label('Normalized Contribution Density ($P / P_{max}$)', rotation=270, labelpad=20, fontsize=12)

    # Save output securely
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)