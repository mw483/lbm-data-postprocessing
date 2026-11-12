"""
Burn the road lines (fetch_osm_roads.py) into the map's 2 m grid and check them against the buildings.

Purpose: a road layer on the simulation grid, so that particle sources can be
put on streets, and a data check that the roads and the map's buildings line
up (both come from OSM, drawn separately).

    python scripts/jakarta-map-analysis/rasterize_roads.py F:/TSUBAME4_12m/map --georef <out>/georef.yaml \\
        --roads <out>/roads/roads.gpkg --land-columns 1279 7750 --candidates <out>/candidates.yaml

How: each line is buffered by half its width (width tag, else lanes x 3.5 m,
else the class default; physics_core/road_network.py) and a cell is road when
its centre is inside. Elevated roads are burnt first and ground roads on top,
larger classes over smaller ones, so a cell holds the class that wins there.

Outputs (<out>/roads/):
- road_class.npy, road.dat   (ny, nx) uint8 [j, i]: 0 none, 1-4 class, 11-14 elevated class.
                             road.dat has the LBM-city map layout (line 1 "nx ny", rows = j);
                             it is NOT read by the solver, it is for the viewer and the source script.
- roads_summary.csv          rows below
- roads_overlay.png          whole map: buildings grey, roads by class
- roads_zoom_<box>.png       one per candidate box, full 2 m resolution

roads_summary.csv, per class (1-4, elevated, all):
1. length_km: road centreline length inside the map.
   Why: the size of the network that sources are put on; source count = length / step.
   Reference: none for this exact area [U].
2. road_cells, road_area_km2, road_fraction_land: cells, area and share of the
   land columns covered by road.
   Why: how much of the city surface is street. Reference: UN-Habitat (2013,
   "Streets as public spaces") gives a street share of land of about 6-36 %,
   lower in fast-grown Asian cities [U, not checked against the source].
3. under_building_share, under_tree_share: share of the class's road cells
   that are inside a building / tree on the map.
   Why: a code and data check. OSM roads and buildings are drawn separately, so
   a few percent at the edges is normal; much more means a shift or a too-wide
   default width. Expected: a few percent [U, no reference].
4. open_land_road_share (row "all"): share of building-free, tree-free land
   that is road. Answers how much of the "open ground" sources used before is street.
Units: km, km2, fractions [-]. Sample: whole map for length; land columns for the fractions.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from _common import DX, add_map_args, land_columns, out_dir, resolve_map
from data_loaders.map_georef import image_shape, load_georef
from data_loaders.map_io import load_map_set
from physics_core.road_network import (CLASS_NAMES, ELEVATED, burn_order, rasterize_roads,
                                       write_map_dat)
from physics_core.urban_morphology import object_heights

COLOURS = {1: "#d62728", 2: "#ff7f0e", 3: "#2ca02c", 4: "#1f77b4", ELEVATED: "#9467bd"}


def map_polygon(geo):
    from shapely.geometry import box
    rows, cols = image_shape(geo)
    d = geo["cell_size"]
    return box(geo["e_topleft"], geo["n_topleft"] - rows * d, geo["e_topleft"] + cols * d, geo["n_topleft"])


def summary(roads, raster, maps, land, poly):
    hb, hv = object_heights(maps)
    land_mask = np.zeros(hb.shape, bool)
    land_mask[:, land[0]:land[1]] = True
    cell_km2 = DX * DX / 1e6
    clipped = roads.geometry.intersection(poly).length / 1000.0
    rows = []
    groups = [(CLASS_NAMES[c], (~roads["elevated"]) & (roads["road_class"] == c), raster == c) for c in CLASS_NAMES]
    groups.append(("elevated", roads["elevated"], raster > ELEVATED))
    groups.append(("all", np.ones(len(roads), bool), raster > 0))
    for name, sel, cells in groups:
        n = int(cells.sum())
        nl = int((cells & land_mask).sum())
        rows.append({"class": name, "ways": int(np.sum(sel)), "length_km": float(clipped[sel].sum()),
                     "road_cells": n, "road_area_km2": n * cell_km2,
                     "road_fraction_land": nl / land_mask.sum(),
                     "under_building_share": float((hb[cells] > 0).mean()) if n else np.nan,
                     "under_tree_share": float((hv[cells] > 0).mean()) if n else np.nan,
                     "outside_land_share": 1 - nl / n if n else np.nan})
    open_land = land_mask & (hb <= 0) & (hv <= 0)
    rows[-1]["open_land_road_share"] = float((raster[open_land] > 0).mean())
    return pd.DataFrame(rows)


def colour_image(hb, raster):
    """RGB image [j, i]: white open ground, grey buildings (darker = taller), roads by class on top."""
    from matplotlib.colors import to_rgb
    g = 1.0 - 0.6 * np.clip(hb / 30.0, 0, 1)
    img = np.where(hb[..., None] > 0, np.stack([g * 0.85] * 3, axis=-1), 1.0)
    for c, col in COLOURS.items():
        sel = (raster >= ELEVATED) if c == ELEVATED else (raster == c)
        img[sel] = to_rgb(col)
    return img


def legend_handles():
    from matplotlib.patches import Patch
    names = {**CLASS_NAMES, ELEVATED: "elevated"}
    return [Patch(color=COLOURS[c], label=f"{c} {names[c]}" if c != ELEVATED else "elevated")
            for c in COLOURS] + [Patch(color="0.6", label="building")]


def plot_overlay(hb, raster, land, path, stride=4):
    """Whole map, every stride-th cell (max of the class codes kept by taking the block's smallest non-zero)."""
    import matplotlib.pyplot as plt
    ny, nx = hb.shape
    s = stride
    hb_s = hb[: ny // s * s, : nx // s * s].reshape(ny // s, s, nx // s, s).max(axis=(1, 3))
    r = raster[: ny // s * s, : nx // s * s].astype(int)
    r = np.where(r == 0, 99, r).reshape(ny // s, s, nx // s, s).min(axis=(1, 3))
    r[r == 99] = 0
    fig, ax = plt.subplots(figsize=(16, 6))
    ax.imshow(colour_image(hb_s, r), origin="lower", extent=[0, nx * DX / 1000, 0, ny * DX / 1000],
              interpolation="nearest")
    for i in land:
        ax.axvline(i * DX / 1000, color="k", ls=":", lw=0.8)
    ax.set_xlabel("map x = i [km] (real north -> south)")
    ax.set_ylabel("map y = j [km] (real east -> west)")
    ax.set_title("OSM roads on the Jakarta map (blocks of %d x %d cells shown; dotted = land columns)" % (s, s))
    ax.legend(handles=legend_handles(), loc="upper right", fontsize=8, ncol=3)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"Saved {path}")


def plot_zoom(hb, raster, box, name, path):
    import matplotlib.pyplot as plt
    i0, i1, j0, j1 = box
    fig, ax = plt.subplots(figsize=(8, 8 * (j1 - j0) / (i1 - i0) + 1))
    ax.imshow(colour_image(hb[j0:j1, i0:i1], raster[j0:j1, i0:i1]), origin="lower",
              extent=[i0, i1, j0, j1], interpolation="nearest")
    ax.set_xlabel("i (map x, 2 m cells)")
    ax.set_ylabel("j (map y, 2 m cells)")
    ax.set_title(f"Box {name}: roads at 2 m")
    ax.legend(handles=legend_handles(), loc="upper right", fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"Saved {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_map_args(ap)
    ap.add_argument("--georef", required=True)
    ap.add_argument("--roads", required=True, help="roads.gpkg from fetch_osm_roads.py")
    ap.add_argument("--candidates", help="candidates.yaml; one zoom figure per box")
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()

    import geopandas as gpd
    from explore_tiles import load_candidates

    folder, label = resolve_map(ap, args)
    out = out_dir(args, label) / "roads"
    out.mkdir(parents=True, exist_ok=True)
    geo = load_georef(args.georef)
    maps = load_map_set(folder)
    if maps["build"].shape != (geo["ny"], geo["nx"]):
        raise SystemExit(f"[ERROR] map {maps['build'].shape} does not match georef ({geo['ny']}, {geo['nx']})")
    land = land_columns(maps, args)

    roads = gpd.read_file(args.roads).to_crs(geo["crs"])
    order = sorted(range(len(roads)), key=lambda k: burn_order(roads["road_class"].iat[k], roads["elevated"].iat[k]))
    roads = roads.iloc[order].reset_index(drop=True)
    polys = roads.geometry.buffer(roads["width_m"] / 2.0)
    codes = roads["road_class"] + np.where(roads["elevated"], ELEVATED, 0)
    print(f"Burning {len(roads)} roads ...")
    raster = rasterize_roads(polys, codes, geo)

    np.save(out / "road_class.npy", raster)
    write_map_dat(out / "road.dat", raster)
    print(f"Saved {out / 'road_class.npy'} and road.dat")
    s = summary(roads, raster, maps, land, map_polygon(geo))
    s.to_csv(out / "roads_summary.csv", index=False)
    print(s.to_string(index=False, float_format=lambda v: f"{v:.4g}"))

    if not args.no_figures:
        hb, _ = object_heights(maps)
        plot_overlay(hb, raster, land, out / "roads_overlay.png")
        for c in load_candidates(args.candidates):
            plot_zoom(hb, raster, c["box"], c["name"], out / f"roads_zoom_{c['name']}.png")


if __name__ == "__main__":
    main()
