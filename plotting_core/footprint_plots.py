import matplotlib.pyplot as plt
import matplotlib.cm as cm
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