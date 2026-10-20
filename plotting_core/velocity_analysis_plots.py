from pathlib import Path
from typing import Dict, Optional, Union
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator

def plot_transit_time_distribution(
        data_dict: Dict[str, np.ndarray],
        bin_width: float = 5.0,
        max_time: Optional[float] = None,
        save_path: Optional[Union[str, Path]] = None,
        title: str = "Receptor Transit Time Distribution",
        colors: Optional[list] = None,
        density: bool = False
) -> None:
    """
    Renders overlaid transit-time histograms: raw particle counts per bin by default,
    or a probability density with density=True.
    
    Args:
        data_dict: Dictionary mapping case/sensor labels to delta_t numpy arrays.
        bin_width: Histogram bin width in seconds.
        max_time: Optional cutoff for the x-axis.
        save_path: Filepath to save the figure (if None, calls plt.show()).
        title: Plot title.
        colors: Optional list of color codes for the curves.
        density: False = particles per bin (raw counts), True = probability density.
    """
    if not data_dict:
        print("[WARNING] No data provided to plot_transit_time_distribution.")
        return

    # Determine global x-axis span
    all_maxes = [arr.max() for arr in data_dict.values() if len(arr) > 0]
    if not all_maxes:
        print("[WARNING] All provided transit time arrays are empty.")
        return

    upper_limit = max_time if max_time is not None else max(all_maxes)
    bins = np.arange(0.0, upper_limit + bin_width, bin_width)

    fig, ax = plt.subplots(figsize=(8,5))
    default_colors = ["tab:blue", "tab:red", "tab:green", "tab:orange", "tab:purple"]
    palette = colors or default_colors

    for i, (label, tt_array) in enumerate(data_dict.items()):
        valid_tt = tt_array[tt_array <= upper_limit] if max_time else tt_array
        if len(valid_tt) == 0:
            continue

        color = palette[i % len(palette)]
        counts, edge_bins = np.histogram(valid_tt, bins=bins, density=density)
        peak_idx = np.argmax(counts)
        peak_time = 0.5 * (edge_bins[peak_idx] + edge_bins[peak_idx + 1])

        ax.hist(
            valid_tt,
            bins=bins,
            density=density,
            histtype="step",
            linewidth=2.0,
            color=color,
            label=f"{label} (Mode: {peak_time:.1f} s, N={len(valid_tt):,})"
        )

    ax.set_xlabel(r"Transit Time $\Delta t$ [s]", fontsize=11)
    if density:
        ax.set_ylabel(r"Probability Density $P(\Delta t)$ [s$^{-1}$]", fontsize=11)
    else:
        ax.set_ylabel(f"Particles per {bin_width:g} s bin", fontsize=11)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(title, fontsize=12)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(frameon=True, fontsize=10)
    plt.tight_layout()

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=300)
        print(f"[SUCCESS] Figure saved to: {save_path}")
        plt.close(fig)
    else:
        plt.show()


def plot_normalized_ttd_comparison(
    data_dict: Dict[str, np.ndarray],
    xlabel: str,
    bin_width: float = 0.05,
    max_scaled_t: float = 3.5,
    save_path: Optional[Union[str, Path]] = None,
    title: str = "Spanwise-Ensemble Normalized Transit Time Distribution",
    density: bool = False
) -> None:
    """
    Plots overlaid breakthrough curves for multi-height comparison:
    raw particle counts per bin by default, or a probability density with density=True.
    """
    bins = np.arange(0.0, max_scaled_t + bin_width, bin_width)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    
    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple"]
    
    for i, (label, t_scaled) in enumerate(data_dict.items()):
        valid = t_scaled[(t_scaled >= 0.0) & (t_scaled <= max_scaled_t)]
        if len(valid) == 0:
            continue
            
        color = colors[i % len(colors)]
        ax.hist(
            valid,
            bins=bins,
            density=density,
            histtype="step",
            linewidth=2.0,
            color=color,
            label=f"{label} (N={len(valid):,})"
        )

    # Reference indicator for self-similarity / median
    if "t_{50}" in xlabel:
        ax.axvline(1.0, color="gray", linestyle=":", label=r"Median Line ($\tilde{t}=1.0$)")

    ax.set_xlabel(xlabel, fontsize=11)
    if density:
        ax.set_ylabel(r"Scaled Probability Density $\tilde{P}$", fontsize=11)
    else:
        ax.set_ylabel(f"Particles per bin (width {bin_width:g})", fontsize=11)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(title, fontsize=12)
    ax.set_xlim(0.0, max_scaled_t)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(frameon=True, fontsize=9, loc="upper right")
    plt.tight_layout()

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=300)
        print(f"[SUCCESS] Figure saved to: {save_path}")
        plt.close(fig)
    else:
        plt.show()

def plot_velocity_profiles(
    stats_by_case: Dict[str, "pl.DataFrame"],
    components=("u_res", "v_res", "w_res"),
    wind_by_case: Optional[Dict[str, dict]] = None,
    save_path: Optional[Union[str, Path]] = None,
    title: str = "Particle velocity vs height",
    z_max: Optional[float] = None,
) -> None:
    """
    Two rows of panels, one column per velocity component, height on the y axis.
      Row 1: particle mean (solid), median (dashed) and 10-90 % range (shaded).
      Row 2: particle standard deviation.
    stats_by_case maps a label to physics_core.particle_analysis.velocity_stats_by_height output.
    wind_by_case (optional) maps the same labels to physics_core.turbulence.mean_wind_profile
    output; it is drawn as dotted lines (Eulerian mean in row 1, Eulerian std in row 2).
    """
    names = {"u_res": "u", "v_res": "v", "w_res": "w", "u": "u (total)", "v": "v (total)", "w": "w (total)"}
    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red"]
    fig, axes = plt.subplots(2, len(components), figsize=(4.2 * len(components), 9), sharey=True)

    for i, (label, st) in enumerate(stats_by_case.items()):
        color = colors[i % len(colors)]
        z = st["z_mid"].to_numpy()
        for j, c in enumerate(components):
            ax, ax_s = axes[0, j], axes[1, j]
            ax.fill_betweenx(z, st[f"{c}_p10"].to_numpy(), st[f"{c}_p90"].to_numpy(), color=color, alpha=0.18,
                             label=f"{label}: 10-90 %")
            ax.plot(st[f"{c}_mean"].to_numpy(), z, color=color, lw=2.0, label=f"{label}: mean")
            ax.plot(st[f"{c}_median"].to_numpy(), z, color=color, lw=1.4, ls="--", label=f"{label}: median")
            ax_s.plot(st[f"{c}_std"].to_numpy(), z, color=color, lw=2.0, label=f"{label}: particles")

            wind = (wind_by_case or {}).get(label)
            comp = names[c][0]
            if wind is not None:
                ax.plot(wind[f"{comp}_mean"], wind["z"], color=color, lw=1.4, ls=":", label=f"{label}: Eulerian mean")
                ax_s.plot(wind[f"{comp}_std"], wind["z"], color=color, lw=1.4, ls=":", label=f"{label}: Eulerian")

    for j, c in enumerate(components):
        axes[0, j].set_xlabel(f"{names[c]} [m/s]")
        axes[1, j].set_xlabel(rf"$\sigma$ of {names[c]} [m/s]")
        for ax in axes[:, j]:
            ax.grid(True, linestyle="--", alpha=0.5)
            if z_max is not None:
                ax.set_ylim(0, z_max)
    axes[0, 0].set_ylabel("z [m]")
    axes[1, 0].set_ylabel("z [m]")
    axes[0, 0].legend(fontsize=8, loc="upper left")
    axes[1, 0].legend(fontsize=8, loc="upper right")
    fig.suptitle(title, fontsize=12)
    fig.tight_layout()

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=300)
        print(f"[SUCCESS] Figure saved to: {save_path}")
        plt.close(fig)
    else:
        plt.show()
