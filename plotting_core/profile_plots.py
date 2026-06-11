import matplotlib.pyplot as plt
import numpy as np
import os

def plot_advection_vs_fetch(X_arr, Ue_arr, save_path):
    """
    Plots Schmid's Effective Advection Velocity (U_e) as a function of upwind fetch distance.
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    
    ax.plot(X_arr, Ue_arr, color='red', linewidth=2, label='$U_e(x)$ (Schmid SAM)')
    
    # Mark your wind tunnel length
    ax.axvline(x=600, color='gray', linestyle='--', label='Sensor Fetch (600m)')
    
    ax.set_title('Effective Advection Velocity vs. Upwind Fetch', fontsize=14)
    ax.set_xlabel('Upwind Fetch Distance X [m]', fontsize=12)
    ax.set_ylabel('Effective Advection Velocity $U_e$ [m/s]', fontsize=12)
    ax.grid(True, linestyle=':', alpha=0.7)
    ax.legend(loc='lower right')
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_vertical_wind_profile(z_lbm, u_lbm, z_theory, u_theory, fetch_points, save_path):
    """
    Plots the LBM velocity profile against the Theoretical Log-Law, 
    highlighting the specific U_e evaluation heights.
    """
    fig, ax = plt.subplots(figsize=(6, 8))
    
    # Plot Theoretical Log-Law
    ax.plot(u_theory, z_theory, color='black', linestyle='--', linewidth=2, label='Theoretical Log-Law')
    
    # Plot LBM Profile
    ax.plot(u_lbm, z_lbm, 'bo-', markersize=4, alpha=0.7, label='LBM Resolved Profile')
    
    # Plot specific U_e points
    colors = ['red', 'orange', 'purple']
    for idx, pt in enumerate(fetch_points):
        x_val, z_val, u_val = pt['x'], pt['z_eval'], pt['u_e']
        ax.plot(u_val, z_val, marker='*', color=colors[idx % len(colors)], markersize=12,
                label=f'Schmid $U_e$ (Fetch = {x_val}m)')
        # Draw a subtle horizontal line to show the height
        ax.axhline(y=z_val, xmin=0, xmax=u_val/2.5, color=colors[idx % len(colors)], linestyle=':', alpha=0.5)

    ax.set_title('Vertical Wind Profile & Advection Evaluation', fontsize=14)
    ax.set_xlabel('Mean Wind Speed U [m/s]', fontsize=12)
    ax.set_ylabel('Height Z [m]', fontsize=12)
    
    ax.set_ylim(0, 160)
    ax.set_xlim(0, 2.5)
    ax.grid(True, linestyle=':', alpha=0.7)
    ax.legend(loc='upper left')
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()