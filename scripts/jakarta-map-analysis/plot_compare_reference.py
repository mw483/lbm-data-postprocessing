"""
Figures for compare_reference.py (called from there; not run on its own).

All maps are drawn like the other figures of this folder: map x (column i,
north to south for the Jakarta map) to the right, the other axis upwards.

1. terrain_compare.png - per terrain reference, three panels: mean ground
   height along x of the map and of the reference; the map - reference
   difference per cell; the histogram of that difference over open and over
   building cells. What: whether the map terrain is the reference terrain.
   Why: an offset = datum difference; a difference only on building cells =
   the reference is a surface model or the map lowered the ground under
   buildings. Units: m. Reference: DEMNAS [U], the map's source file.
2. ghsl_scatter.png - map against GHSL per 100 m pixel: built-up fraction,
   AGBH (volume / pixel area) and ANBH (volume / building area), 1:1 line.
   What: whether the map is as built-up and as tall as GHSL says. Units: -, m, m.
3. ghsl_maps.png - built-up fraction and AGBH of the map and of GHSL as 100 m
   pixel maps on shared colour scales. What: where they differ.
"""
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DX = 2.0
INK = "#333333"
MUTED = "#8a8a8a"
LINE = "#2f6db5"
LINE2 = "#d9822b"
FILL = "#9dbce3"
FILL2 = "#f2c48d"

plt.rcParams.update({"axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 9,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6})

NAMES = {"dem": "DEMNAS", "source_topo": "source topography file"}


def x_label(geo):
    d = geo["orientation"].split(",")[0][2]
    return f"map x, column i [km] (towards {dict(N='north', S='south', E='east', W='west')[d]})"


def save(fig, path):
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_terrain(topo_img, terrain, land, is_b, out, geo):
    n = len(terrain)
    fig, axes = plt.subplots(n, 3, figsize=(13, 3.6 * n), squeeze=False, layout="constrained",
                             gridspec_kw={"width_ratios": [1.3, 2.2, 1]})
    x = np.arange(topo_img.shape[0]) * DX / 1000
    for row, (name, ref) in zip(axes, terrain.items()):
        a, b, c = row
        a.plot(x, topo_img.mean(axis=1), color=LINE, lw=1.0, label="map")
        with warnings.catch_warnings():                 # rows the reference does not cover
            warnings.simplefilter("ignore", RuntimeWarning)
            ref_mean = np.nanmean(ref, axis=1)
        a.plot(x, ref_mean, color=LINE2, lw=1.0, label=NAMES.get(name, name))
        a.set_xlabel(x_label(geo))
        a.set_ylabel("mean ground height [m]")
        a.set_title(f"Ground along x, vs {NAMES.get(name, name)}", loc="left", color=INK)
        a.legend(frameon=False)
        d = (topo_img - ref)[land]
        lim = float(np.nanpercentile(np.abs(d), 98)) or 1.0
        im = b.imshow(d.T, origin="lower", cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto",
                      extent=(land.start * DX / 1000, land.stop * DX / 1000, 0, d.shape[1] * DX / 1000))
        b.grid(False)
        b.set_xlabel(x_label(geo))
        b.set_ylabel("km")
        b.set_title(f"map - {NAMES.get(name, name)} [m], land columns", loc="left", color=INK)
        fig.colorbar(im, ax=b, shrink=0.9, pad=0.01)
        b_land = is_b[land]
        edges = np.linspace(-lim, lim, 61)
        c.hist(d[~b_land & np.isfinite(d)], bins=edges, histtype="step", color=LINE, lw=1.2, label="open cells")
        c.hist(d[b_land & np.isfinite(d)], bins=edges, histtype="step", color=LINE2, lw=1.2, label="building cells")
        c.legend(frameon=False)
        c.set_yscale("log")
        c.set_xlabel("map - reference [m]")
        c.set_ylabel("cells")
        c.set_title("Difference", loc="left", color=INK)
    save(fig, out / "terrain_compare.png")


def plot_ghsl_scatter(px, out):
    fields = (("frac", "built-up fraction [-]"), ("agbh", "AGBH = volume / pixel area [m]"),
              ("anbh", "ANBH = volume / building area [m]"))
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, (k, title) in zip(axes, fields):
        m, g = px[f"map_{k}"].to_numpy(), px[f"ghsl_{k}"].to_numpy()
        ok = np.isfinite(m) & np.isfinite(g)
        hi = float(np.nanpercentile(np.r_[m[ok], g[ok]], 99.5))
        ax.hexbin(g[ok], m[ok], gridsize=50, extent=(0, hi, 0, hi), bins="log", cmap="Blues", mincnt=1)
        ax.plot([0, hi], [0, hi], color=MUTED, lw=0.8)
        ax.set_xlim(0, hi)
        ax.set_ylim(0, hi)
        ax.set_aspect("equal")
        ax.set_xlabel("GHSL")
        ax.set_ylabel("map")
        r = np.corrcoef(m[ok], g[ok])[0, 1]
        ax.set_title(f"{title}\nr = {r:.2f}, bias = {np.mean(m[ok] - g[ok]):.3g}", loc="left", color=INK)
    save(fig, out / "ghsl_scatter.png")


def plot_ghsl_maps(px, out, geo):
    r0, c0 = px["pix_row"].min(), px["pix_col"].min()
    shape = (px["pix_row"].max() - r0 + 1, px["pix_col"].max() - c0 + 1)
    panels = (("map_frac", "map: built-up fraction [-]"), ("ghsl_frac", "GHSL: built-up fraction [-]"),
              ("map_agbh", "map: AGBH [m]"), ("ghsl_agbh", "GHSL: AGBH [m]"))
    fig, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True)
    for ax, (k, title) in zip(axes, panels):
        grid = np.full(shape, np.nan)
        grid[px["pix_row"] - r0, px["pix_col"] - c0] = px[k]
        pair = k.split("_")[1]
        top = float(np.nanpercentile(np.r_[px[f"map_{pair}"], px[f"ghsl_{pair}"]], 99))
        im = ax.imshow(grid.T, origin="lower", cmap="Blues", vmin=0, vmax=top, aspect="equal",
                       extent=(0, shape[0] * 0.1, 0, shape[1] * 0.1))
        ax.grid(False)
        ax.set_title(title, loc="left", color=INK)
        ax.set_ylabel("km (west to east)")
        fig.colorbar(im, ax=ax, shrink=0.9, pad=0.01)
    axes[-1].set_xlabel("km from the north end of the compared area (100 m pixels)")
    save(fig, out / "ghsl_maps.png")


def plot_all(figs, out, geo):
    out = Path(out)
    if "terrain" in figs:
        plot_terrain(*figs["terrain"], out, geo)
    if "ghsl" in figs:
        plot_ghsl_scatter(figs["ghsl"], out)
        plot_ghsl_maps(figs["ghsl"], out, geo)
