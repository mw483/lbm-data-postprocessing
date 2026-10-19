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

def plot_profile_panels(profiles, quantities, save_path, title="", zmax=None, colors=None, styles=None):
    """
    One panel per quantity, height on the shared y-axis, one line per profile.

    profiles:   {line label: DataFrame with a "z" column and the quantity columns}
    quantities: [(column, x-axis label), ...]
    colors:     {line label: color}; default one categorical colour per line in order
    styles:     {line label: line style}; default solid
    """
    plot_profile_grid(profiles, [quantities], save_path, title=title, zmax=zmax, colors=colors, styles=styles)


def plot_profile_grid(profiles, rows, save_path, title="", zmax=None, colors=None, styles=None):
    """
    Like plot_profile_panels, with the panels in rows: rows = [[(column, label), ...], ...].
    A None entry leaves that panel empty (hidden), so rows of different length line up.
    """
    n_rows, n_cols = len(rows), max(len(r) for r in rows)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(2.8 * n_cols + 1.0, 5.0 * n_rows + 1.0),
                             sharey=True, squeeze=False)
    default = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    panels = []
    for r, row in enumerate(rows):
        for c in range(n_cols):
            spec = row[c] if c < len(row) else None
            if spec is None:
                axes[r][c].set_visible(False)
            else:
                panels.append((axes[r][c], spec))
    for i, (label, df) in enumerate(profiles.items()):
        color = (colors or {}).get(label, default[i % len(default)])
        style = (styles or {}).get(label, "-")
        for ax, (col, _) in panels:
            if col in df:
                ax.plot(df[col], df["z"], style, color=color, linewidth=1.5, label=label)
    for ax, (_, xlabel) in panels:
        ax.set_xlabel(xlabel)
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.axvline(0.0, color="0.6", linewidth=0.8)
    for r in range(n_rows):
        axes[r][0].set_ylabel("z [m]")
    if zmax is not None:
        axes[0][0].set_ylim(0, zmax)
    handles, labels = panels[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=min(len(labels), 6), frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    if title:
        fig.suptitle(title, y=1.04 if n_rows > 1 else 1.06)
    fig.tight_layout()
    os.makedirs(os.path.dirname(str(save_path)), exist_ok=True)
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
