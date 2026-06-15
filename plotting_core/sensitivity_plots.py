import matplotlib.pyplot as plt
import numpy as np
import os

def plot_vertical_detection_profile(z_heights, total_counts, title, save_path):
    """
    Plots the total number of particles detected against the sensor height (Z).
    Height is plotted on the Y-axis to mirror a physical atmospheric profile.
    """
    fig, ax = plt.subplots(figsize=(6, 8))
    
    # Plot the profile
    ax.plot(total_counts, z_heights, marker='o', linestyle='-', color='indigo', 
            linewidth=2, markersize=8, markerfacecolor='white', markeredgewidth=2)
    
    # Formatting
    ax.set_title(title, fontsize=14, pad=15)
    ax.set_xlabel('Total Particles Detected [Count]', fontsize=12)
    ax.set_ylabel('Sensor Height Z [m]', fontsize=12)
    
    # Set y-limits to start at ground level
    ax.set_ylim(0, max(z_heights) + 5)
    
    # Optional: Log scale for X-axis if the drop-off is extreme
    # ax.set_xscale('log')
    
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Save output securely
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)