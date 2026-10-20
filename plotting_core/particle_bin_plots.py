"""
Figures for the Lagrangian particle statistics (scripts/plot_particle_bin_stats.py).
"""
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm


def _save(fig, save_path):
    os.makedirs(os.path.dirname(str(save_path)), exist_ok=True)
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_lines_grid(panels, save_path, title="", xlabel="", vlines=()):
    """
    Panels of lines sharing the x axis.

    panels: [(y label, {line label: (x, y)})]; vlines: x positions marked with dotted lines (e.g. rank edges).
    """
    n = len(panels)
    ncol = min(n, 2)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(5.6 * ncol, 3.4 * nrow), sharex=True, squeeze=False)
    flat = axes.ravel()
    for ax, (ylabel, lines) in zip(flat, panels):
        for i, (label, (x, y)) in enumerate(lines.items()):
            ax.plot(x, y, color=f"C{i}", linewidth=1.4, label=label)
        for v in vlines:
            ax.axvline(v, color="0.5", linestyle=":", linewidth=1.0)
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle=":", alpha=0.5)
    for ax in flat[n:]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel(xlabel)
    flat[0].legend(frameon=False, fontsize=9)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    _save(fig, save_path)


def plot_age_pdf(panels, age, z, save_path, zmax=None, title="", ylabel="z [m]", overlay=None):
    """
    PDF of height (or another variable) at each age, one panel per case, log colour scale shared by the panels.

    panels: {case: 2D array [age, z] of counts}; each age column is normalised to a PDF [1/m].
    overlay: {case: (age, curve)} drawn in white (e.g. the mean height).
    """
    pdfs = {}
    dz = z[1] - z[0]
    for case, h in panels.items():
        total = h.sum(axis=1, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            pdfs[case] = np.where(total > 0, h / (total * dz), np.nan)
    positive = np.concatenate([p[np.isfinite(p) & (p > 0)] for p in pdfs.values()])
    norm = LogNorm(vmin=max(positive.min(), positive.max() * 1e-5), vmax=positive.max())
    n = len(pdfs)
    fig, axes = plt.subplots(1, n, figsize=(5.2 * n + 1.0, 4.4), sharey=True, squeeze=False, layout="constrained")
    for ax, (case, pdf) in zip(axes[0], pdfs.items()):
        mesh = ax.pcolormesh(age, z, np.where(pdf > 0, pdf, np.nan).T, norm=norm, cmap="magma",
                             shading="nearest", rasterized=True)
        if overlay and case in overlay:
            ax.plot(*overlay[case], color="w", linewidth=1.2, label="mean")
        ax.set_title(case)
        ax.set_xlabel("particle age [s]")
        if zmax is not None:
            ax.set_ylim(z[0] if z[0] < 0 else 0, zmax)
    axes[0][0].set_ylabel(ylabel)
    fig.colorbar(mesh, ax=list(axes[0]), label="PDF [1/m]")
    if title:
        fig.suptitle(title)
    _save(fig, save_path)


def plot_profiles(panels, save_path, zmax=None, title=""):
    """
    Panels of profiles against height. panels: [(x label, {line label: (values, z, style dict)})].
    """
    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(3.6 * n + 0.6, 5.0), sharey=True, squeeze=False)
    for ax, (xlabel, lines) in zip(axes[0], panels):
        for label, (v, z, style) in lines.items():
            ax.plot(v, z, label=label, **style)
        ax.set_xlabel(xlabel)
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.legend(frameon=False, fontsize=8)
    axes[0][0].set_ylabel("z [m]")
    if zmax is not None:
        axes[0][0].set_ylim(0, zmax)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    _save(fig, save_path)
