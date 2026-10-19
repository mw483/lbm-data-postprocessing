"""
Figures for the particle concentration statistics (scripts/analyze_particle_density.py).
"""
import os

import matplotlib.pyplot as plt
import numpy as np


def _save(fig, save_path):
    os.makedirs(os.path.dirname(str(save_path)), exist_ok=True)
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_particle_count(series, save_path, spans=(), lines=(), title=""):
    """
    Particles in the domain against time.

    series: {label: (t [s], N)}; spans: [(t0, t1, label)] shaded; lines: [(t, label)] vertical markers.
    """
    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    for label, (t, n) in series.items():
        ax.plot(t, n, linewidth=1.5, label=label)
    for i, (t0, t1, label) in enumerate(spans):
        ax.axvspan(t0, t1, color=f"C{7 + i % 3}", alpha=0.12, label=label)
    for t, label in lines:
        ax.axvline(t, color="0.4", linestyle="--", linewidth=1.0, label=label)
    ax.set_xlabel("t [s]")
    ax.set_ylabel("particles in the domain")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(frameon=False, fontsize=9)
    if title:
        ax.set_title(title)
    _save(fig, save_path)


def plot_concentration_profiles(panels, save_path, zmax=None, title="", xlabel=r"C [m$^{-3}$]"):
    """
    One panel per case: horizontal-mean concentration against height, log x axis.

    panels: {panel title: {line label: (z, C, style dict)}}.
    """
    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n + 0.6, 5.2), sharey=True, sharex=True, squeeze=False)
    for ax, (name, lines) in zip(axes[0], panels.items()):
        for label, (z, c, style) in lines.items():
            c = np.where(np.asarray(c) > 0, c, np.nan)
            ax.plot(c, z, label=label, **style)
        ax.set_xscale("log")
        ax.set_title(name)
        ax.set_xlabel(xlabel)
        ax.grid(True, which="both", linestyle=":", alpha=0.4)
        ax.legend(frameon=False, fontsize=8)
    axes[0][0].set_ylabel("z [m]")
    if zmax is not None:
        axes[0][0].set_ylim(0, zmax)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    _save(fig, save_path)


def plot_along_x(panels, save_path, source_x=None, title="", ylabel=r"y-mean C [m$^{-3}$]"):
    """
    One panel per height: y-mean concentration against x, one colour per case.

    panels: {panel title: {case: {"x", "steady", "lo", "hi", "full"}}}; lo/hi bound the shaded band
    (block minimum and maximum), "full" is drawn dashed. source_x: (x0, x1) of the source area, marked grey.
    """
    n = len(panels)
    ncol = min(n, 2)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(6.0 * ncol, 3.4 * nrow), sharex=True, squeeze=False)
    flat = axes.ravel()
    for ax, (name, cases) in zip(flat, panels.items()):
        for i, (case, d) in enumerate(cases.items()):
            color = f"C{i}"
            ax.fill_between(d["x"], d["lo"], d["hi"], color=color, alpha=0.25, linewidth=0)
            ax.plot(d["x"], d["steady"], color=color, linewidth=1.4, label=f"{case}, steady window")
            if d.get("full") is not None:
                ax.plot(d["x"], d["full"], color=color, linewidth=1.0, linestyle="--",
                        label=f"{case}, whole release window")
        if source_x is not None:
            ax.axvspan(*source_x, color="0.85", alpha=0.35, zorder=0)
        ax.set_title(name)
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle=":", alpha=0.5)
    for ax in flat[n:]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("x [m]")
    handles, labels = flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=min(len(labels), 4), frameon=False,
               bbox_to_anchor=(0.5, 1.02))
    if title:
        fig.suptitle(title, y=1.07)
    fig.tight_layout()
    _save(fig, save_path)
