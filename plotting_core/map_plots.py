import matplotlib.pyplot as plt
import numpy as np
import os
from matplotlib.colors import ListedColormap

def plot_birdseye_domain(elevation_matrix, source_map, sensor_pos, title, save_path, dx=2.0, dy=2.0):
    """
    Plots a top-down view of the domain, overlaying building footprints, 
    particle sources, and the sensor location.
    """
    ny, nx = elevation_matrix.shape
    
    # Create physical coordinate grids for plotting
    x_physical = np.arange(0, nx * dx, dx)
    y_physical = np.arange(0, ny * dy, dy)
    X, Y = np.meshgrid(x_physical, y_physical)

    # Wide aspect ratio (e.g., 1024m x 256m -> 4:1)
    fig, ax = plt.subplots(figsize=(16, 4)) 
    
    # 1. Plot the Building Map
    # Binary threshold: 0 is empty space (light gray), >0 is a building block (dark gray)
    building_mask = elevation_matrix > 0
    cmap = ListedColormap(['#f0f0f0', '#505050'])
    
    # pcolormesh perfectly aligns grid data with absolute coordinates
    ax.pcolormesh(X, Y, building_mask, cmap=cmap, shading='nearest')

    # 2. Plot the Sources
    # Extract coordinates from the dictionary returned by load_source_positions
    source_x = [src['x'] for src in source_map.values()]
    source_y = [src['y'] for src in source_map.values()]
    
    ax.scatter(source_x, source_y, c='red', s=8, alpha=0.8, edgecolors='none', label='Particle Sources')

    # 3. Plot the Sensor
    ax.plot(sensor_pos[0], sensor_pos[1], marker='*', color='blue', markersize=16, 
            markeredgecolor='black', label=f'Sensor Box Center')

    # Formatting
    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel('Downwind Distance X [m]', fontsize=12)
    ax.set_ylabel('Crosswind Distance Y [m]', fontsize=12)
    
    ax.set_xlim(0, nx * dx)
    ax.set_ylim(0, ny * dy)
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, linestyle=':', alpha=0.6)
    
    # Place legend outside the main plot area so it doesn't cover data
    ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1.0))

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()