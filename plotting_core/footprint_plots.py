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