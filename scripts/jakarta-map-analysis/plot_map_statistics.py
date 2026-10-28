"""
Figures from the CSV files written by map_statistics.py (run that first).

    python scripts/jakarta-map-analysis/plot_map_statistics.py --stats <output folder of map_statistics.py>

Purpose: a data check of the map set; the figures show the same numbers as
summary.csv as distributions and maps, for comparison with real data.

Figures (PNG in the same folder):
1. terrain.png - ground height along the map x axis (mean over y) and its
   histogram over land cells. What: the shape of the terrain. Why: Jakarta is a
   flat coastal plain rising gently inland; steps would be tile seams from map
   making. Reference: bare-earth DEM (FABDEM, Hawker et al. 2022; DEMNAS) [U].
   Units: m above map zero.
2. built_along_x.png - plan area fraction lambda_p and area-weighted mean
   height H_av per map column (two panels, one axis each). What: how built-up
   and how tall the city is from the sea inland. Why: shows the sea fetch, the
   centre and the outlet strip. Reference: none on its own; tiles go to GHSL.
3. building_heights.png - histogram (log counts) of building height over
   building cells and over buildings (max per building). What: the skyline.
   Why: a spike at one height points to a default height for buildings without
   data. Reference: GHS-BUILT-H, Open Buildings 2.5D [U]. Units: m above ground.
4. building_widths.png - smallest bounding-box side of each building in cells,
   as share of buildings and share of building volume, with the 16-cell line.
   What: how well the 2 m grid resolves the buildings. Why: the professor's rule
   is >= 16 cells across a building. Reference: that rule.
5. tiles.png - lambda_p, mean building height, max building height and tree
   cover per tile (default 500 m). What: where the dense, tall and green parts
   are. Why: this is what gets compared pixel by pixel with GHS-BUILT-S/H.
   Units: -, m, m, -. Drawn in map axes (x = i, y = j) with the compass
   directions from georef.yaml when it is next to the CSV files.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

DX = 2.0
INK = "#333333"
MUTED = "#8a8a8a"
LINE = "#2f6db5"         # one series per panel: a single blue
FILL = "#9dbce3"
RULE_COLOR = "#c0392b"   # the 16-cell rule line
MIN_CELLS_RULE = 16

plt.rcParams.update({"axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 9,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6})


def compass(stats_dir):
    p = stats_dir / "georef.yaml"
    if not p.exists():
        return None
    o = yaml.safe_load(open(p))["orientation"]          # e.g. "i:S,j:W"
    return {"i": o[2], "j": o[6]}


def axis_label(axis, comp):
    names = {"N": "north", "S": "south", "E": "east", "W": "west"}
    base = "map x, column i [km]" if axis == "i" else "map y, row j [km]"
    return base if comp is None else f"{base} (towards {names[comp[axis]]})"


def save(fig, path):
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_terrain(tr, summary, out, comp):
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.2), gridspec_kw={"width_ratios": [2.2, 1]})
    a.plot(tr["i"] * DX / 1000, tr["ground_mean"], color=LINE, lw=1.2)
    a.set_xlabel(axis_label("i", comp))
    a.set_ylabel("mean ground height [m]")
    a.set_title("Ground height along x (mean over y)", loc="left", color=INK)
    vals = summary.set_index("statistic")["value"]
    b.barh(["p5", "p25", "p50", "p75", "p95", "max"],
           [float(vals[f"ground_{k}"]) for k in ("p5", "p25", "p50", "p75", "p95", "max")], color=FILL, height=0.6)
    b.set_xlabel("ground height [m]")
    b.set_title("Land cells: percentiles", loc="left", color=INK)
    b.grid(axis="y", visible=False)
    save(fig, out / "terrain.png")


def plot_built_along_x(tr, out, comp):
    fig, (a, b) = plt.subplots(2, 1, figsize=(10, 4.4), sharex=True)
    x = tr["i"] * DX / 1000
    a.plot(x, tr["lambda_p"], color=LINE, lw=0.9)
    a.set_ylabel("lambda_p [-]")
    a.set_title("Plan area fraction per column", loc="left", color=INK)
    b.plot(x, tr["H_av"], color=LINE, lw=0.9)
    b.set_ylabel("H_av [m]")
    b.set_title("Area-weighted mean building height per column", loc="left", color=INK)
    b.set_xlabel(axis_label("i", comp))
    save(fig, out / "built_along_x.png")


def plot_heights(bld, cells_hist, out):
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.2), sharey=False)
    edges = np.arange(0, max(400, bld["h_max"].max() + 10), 5)
    a.bar(cells_hist[0][:-1], cells_hist[1], width=np.diff(cells_hist[0]), align="edge", color=FILL, edgecolor="white", lw=0.3)
    a.set_yscale("log")
    a.set_xlabel("building height above ground [m]")
    a.set_ylabel("cells")
    a.set_title("Building cells by height", loc="left", color=INK)
    b.hist(bld["h_max"], bins=edges, color=FILL, edgecolor="white", lw=0.3)
    b.set_yscale("log")
    b.set_xlabel("max height of the building [m]")
    b.set_ylabel("buildings")
    b.set_title("Buildings by max height", loc="left", color=INK)
    save(fig, out / "building_heights.png")


def plot_widths(bld, out):
    vol = bld["h_mean"] * bld["area_m2"]
    edges = np.arange(1, 101)
    side = bld["min_side"].clip(upper=100)
    n_share = np.histogram(side, bins=edges)[0] / len(bld)
    v_share = np.histogram(side, bins=edges, weights=vol)[0] / vol.sum()
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.2), sharex=True)
    for ax, share, title in ((a, n_share, "Share of buildings"), (b, v_share, "Share of building volume")):
        ax.bar(edges[:-1], share, width=1.0, color=FILL, edgecolor="white", lw=0.3)
        ax.axvline(MIN_CELLS_RULE, color=RULE_COLOR, lw=1.2)
        ax.text(MIN_CELLS_RULE + 1, ax.get_ylim()[1] * 0.9, "16 cells", color=INK)
        ax.set_xlabel("smallest side of the building [cells, 100 = 100 or more]")
        ax.set_title(title, loc="left", color=INK)
    a.set_ylabel("share")
    save(fig, out / "building_widths.png")


def plot_tiles(tiles, out, comp, tile_m):
    nxt, nyt = tiles["tile_i"].max() + 1, tiles["tile_j"].max() + 1
    fields = (("lambda_p", "plan area fraction [-]", "Blues"), ("h_mean", "mean building height [m]", "Blues"),
              ("h_max", "max building height [m]", "Blues"), ("tree_cover", "tree cover [-]", "Greens"))
    fig, axes = plt.subplots(len(fields), 1, figsize=(10, 2.0 * len(fields) + 0.6), sharex=True)
    i0 = (tiles["i_center"].min() - tile_m / DX / 2) * DX / 1000
    extent = (i0, i0 + nxt * tile_m / 1000, 0, nyt * tile_m / 1000)
    for ax, (k, title, cmap) in zip(axes, fields):
        grid = np.full((nyt, nxt), np.nan)
        grid[tiles["tile_j"], tiles["tile_i"]] = tiles[k]
        im = ax.imshow(grid, origin="lower", extent=extent, cmap=cmap, aspect="equal")
        ax.grid(False)
        ax.set_title(f"{title}, {tile_m:g} m tiles", loc="left", color=INK)
        ax.set_ylabel(axis_label("j", comp).replace("map y, ", ""))
        fig.colorbar(im, ax=ax, shrink=0.9, pad=0.01)
    axes[-1].set_xlabel(axis_label("i", comp))
    save(fig, out / "tiles.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stats", required=True, help="output folder of map_statistics.py")
    ap.add_argument("--tile", type=float, default=500.0)
    args = ap.parse_args()
    d = Path(args.stats)
    comp = compass(d)
    summary = pd.read_csv(d / "summary.csv")
    tr = pd.read_csv(d / "transect_i.csv")
    bld = pd.read_csv(d / "buildings.csv")
    tiles = pd.read_csv(d / f"tiles_{args.tile:g}m.csv")
    hist = np.load(d / "building_cell_heights_hist.npz")
    plot_terrain(tr, summary, d, comp)
    plot_built_along_x(tr, d, comp)
    plot_heights(bld, (hist["edges"], hist["counts"]), d)
    plot_widths(bld, d)
    plot_tiles(tiles, d, comp, args.tile)


if __name__ == "__main__":
    main()
