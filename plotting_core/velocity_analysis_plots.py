from pathlib import Path
from typing import Dict, Optional, Union
import matplotlib.pyplot as plt
import numpy as np

def plot_transit_time_distribution(
        data_dict: Dict[str, np.ndarray],
        bin_width: float = 5.0,
        max_time: Optional[float] = None,
        save_path: Optional[Union[str, Path]] = None,
        title: str = "Receptor Transit Time Distribution",
        colors: Optional[list] = None
) -> None:
    """
    Renders an overlay probability density function (PDF) of transit times.
    
    Args:
        data_dict: Dictionary mapping case/sensor labels to delta_t numpy arrays.
        bin_width: Histogram bin width in seconds.
        max_time: Optional cutoff for the x-axis.
        save_path: Filepath to save the figure (if None, calls plt.show()).
        title: Plot title.
        colors: Optional list of color codes for the curves.
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
        counts, edge_bins = np.histogram(valid_tt, bins=bins, density=True)
        peak_idx = np.argmax(counts)
        peak_time = 0.5 * (edge_bins[peak_idx] + edge_bins[peak_idx + 1])

        ax.hist(
            valid_tt,
            bins=bins,
            density=True,
            histtype="step",
            linewidth=2.0,
            color=color,
            label=f"{label} (Mode: {peak_time:.1f} s, N={len(valid_tt):,})"
        )

    ax.set_xlabel(r"Transit Time $\Delta t$ [s]", fontsize=11)
    ax.set_ylabel(r"Probability Density $P(\Delta t)$ [s$^{-1}$]", fontsize=11)
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
    title: str = "Spanwise-Ensemble Normalized Transit Time Distribution"
) -> None:
    """
    Plots overlaid dimensionless breakthrough curves for multi-height comparison.
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
            density=True,
            histtype="step",
            linewidth=2.0,
            color=color,
            label=f"{label} (N={len(valid):,})"
        )

    # Reference indicator for self-similarity / median
    if "t_{50}" in xlabel:
        ax.axvline(1.0, color="gray", linestyle=":", label=r"Median Line ($\tilde{t}=1.0$)")

    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(r"Scaled Probability Density $\tilde{P}$", fontsize=11)
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