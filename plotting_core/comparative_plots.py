import matplotlib.pyplot as plt
import os

def plot_footprint_with_contours(X, Y, pdf_grid, thresholds, levels, sensor_pos, save_path, title="Footprint"):
    """
    Plots the footprint PDF as a heatmap with specified contour boundaries overlaid.
    """
    fig, ax = plt.subplots(figsize=(12, 5))
    
    # Plot the underlying heatmap
    cmap = plt.cm.jet
    heatmap = ax.pcolormesh(X, Y, pdf_grid, cmap=cmap, shading='nearest')
    
    # Plot the contour lines
    if thresholds:
        # Contour levels must be in strictly increasing order for matplotlib
        sorted_thresh = sorted(thresholds)
        
        # We use white dashed lines for high contrast
        cs = ax.contour(X, Y, pdf_grid, levels=sorted_thresh, colors='white', 
                        linewidths=1.25, linestyles='dashed', alpha = 0.8)
        
        # Create a custom label formatter mapping the threshold values back to the percentages (e.g., "50%")
        fmt = {}
        for thresh, pct in zip(thresholds, levels):
            fmt[thresh] = f"{int(pct*100)}%"
            
        ax.clabel(cs, cs.levels, inline=True, fmt=fmt, fontsize=7)

    # Mark the sensor
    ax.plot(sensor_pos[0], sensor_pos[1], marker='*', color='magenta', markersize=15, markeredgecolor='black')
    
    # Formatting
    cbar = fig.colorbar(heatmap, ax=ax, pad=0.02)
    cbar.set_label('Contribution Density [$m^{-2}$]', rotation=270, labelpad=15)
    
    ax.set_title(title, fontsize=14)
    ax.set_xlabel('Absolute X Coordinate [m]', fontsize=12)
    ax.set_ylabel('Absolute Y Coordinate [m]', fontsize=12)
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, linestyle='--', alpha=0.5)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)