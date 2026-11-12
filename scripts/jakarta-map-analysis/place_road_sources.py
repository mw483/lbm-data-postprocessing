"""
Particle sources along the roads, written in the solver's particle_position format.

Purpose: street sources for the Jakarta runs (vehicle emissions), instead of a
source on every open cell (that put 58 % of sources at sea, jakarta_sim_review.md).
One source every --step metres of road centreline, so the sources per road
length do not depend on the road width and the count stays under the ID limit.

    python scripts/jakarta-map-analysis/place_road_sources.py F:/TSUBAME4_12m/map --georef <out>/georef.yaml \\
        --roads <out>/roads/roads.gpkg --land-columns 1279 7750 --name all  --classes 1 2 3 4
    python scripts/jakarta-map-analysis/place_road_sources.py F:/TSUBAME4_12m/map --georef <out>/georef.yaml \\
        --roads <out>/roads/roads.gpkg --land-columns 1279 7750 --name main --classes 1 2
    # only inside a cut-out (positions then relative to the box corner):
    ... --name A_all --classes 1 2 3 4 --box A --candidates <out>/candidates.yaml

A source point is dropped when its cell is inside a building or a tree on the
map, outside the land columns (sea fetch, south ramp) or outside --box.
Elevated roads (bridges, flyovers, layer > 0) and tunnels are left out unless
--include-elevated: our sources sit at ground + --z-offset.

Outputs (<out>/roads/sources_<name>/):
- road_sources.csv            i, j, x_m, y_m, z_m, ground_m, road_class, highway, osm_id
- particle_position/          particle_position.txt + particle_number.txt, as written by
                              LBM-city tools/lbmcase (x y z u v w group id; id = n x 10^4 + 1)
- sources_summary.csv         rows per class:
  What: points along the roads, points dropped and why, sources kept.
  Why: the source count sets the particles per release (cost) and must stay
  under the int32 ID limit (214,748 with id_digit 4); the dropped shares are
  a data check (how many road points the map has under a building or tree).
  Reference: none [U]. Units: counts, shares [-]; sample: whole map or --box.
- sources_<name>.png          sources on the buildings

z is absolute (ground from topography.dat + --z-offset), as the solver
compares particle z with the absolute map heights.
"""
import argparse

import numpy as np
import pandas as pd

from _common import DX, add_map_args, land_columns, out_dir, resolve_map
from data_loaders.map_georef import load_georef
from data_loaders.map_io import load_map_set
from physics_core.road_network import (CLASS_NAMES, centreline_points, crs_to_map_xy, source_cell_ok,
                                       write_particle_sources)
from physics_core.urban_morphology import object_heights

ID_SOURCE_LIMIT = 214_748
STACK_LIMIT_SOURCES = 250_000   # Generate_Particle.cu keeps 8 x 4-byte arrays per source on the stack (8 MB usual limit) [U]


def find_box(args):
    if args.box is None:
        return None, None
    if len(args.box) == 4:
        return [int(v) for v in args.box], "box"
    from explore_tiles import load_candidates
    for c in load_candidates(args.candidates):
        if c["name"] == args.box[0]:
            return c["box"], c["name"]
    raise SystemExit(f"[ERROR] box {args.box[0]} not in {args.candidates}")


def plot_sources(hb, df, box, title, path):
    import matplotlib.pyplot as plt
    ny, nx = hb.shape
    i0, i1, j0, j1 = box if box else (0, nx, 0, ny)
    s = 1 if box else 4
    sub = hb[j0:j1:s, i0:i1:s]
    fig, ax = plt.subplots(figsize=(16, 6) if not box else (8, 8))
    ax.imshow(np.where(sub > 0, 0.6, 1.0), cmap="gray", vmin=0, vmax=1, origin="lower",
              extent=[i0 * DX / 1000, i1 * DX / 1000, j0 * DX / 1000, j1 * DX / 1000], interpolation="nearest")
    cmap = {1: "#d62728", 2: "#ff7f0e", 3: "#2ca02c", 4: "#1f77b4"}
    for c, g in df.groupby("road_class"):
        ax.scatter((g["i"] + 0.5) * DX / 1000, (g["j"] + 0.5) * DX / 1000, s=0.5 if not box else 3,
                   color=cmap.get(c, "k"), label=f"{c} {CLASS_NAMES.get(c, '')} ({len(g)})", lw=0)
    ax.set_xlabel("map x = i [km] (real north -> south)")
    ax.set_ylabel("map y = j [km] (real east -> west)")
    ax.set_title(title)
    ax.legend(loc="upper right", fontsize=8, markerscale=6)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"Saved {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_map_args(ap)
    ap.add_argument("--georef", required=True)
    ap.add_argument("--roads", required=True, help="roads.gpkg from fetch_osm_roads.py")
    ap.add_argument("--name", required=True, help="label of this source set, e.g. all, main")
    ap.add_argument("--classes", type=int, nargs="+", default=[1, 2, 3, 4], help="road classes to use (1-4)")
    ap.add_argument("--step", type=float, default=16.0, help="distance between sources along a road [m]")
    ap.add_argument("--z-offset", type=float, default=1.0, help="source height above ground [m]")
    ap.add_argument("--include-elevated", action="store_true", help="keep bridges, flyovers and tunnels")
    ap.add_argument("--box", nargs="+", help="i0 i1 j0 j1 (end exclusive) or a name in --candidates")
    ap.add_argument("--candidates", help="candidates.yaml (for --box NAME)")
    ap.add_argument("--velocity", type=float, nargs=3, default=[0.0, 0.0, 0.1], help="u v w written per source")
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()

    import geopandas as gpd

    folder, label = resolve_map(ap, args)
    out = out_dir(args, label) / "roads" / f"sources_{args.name}"
    out.mkdir(parents=True, exist_ok=True)
    geo = load_georef(args.georef)
    maps = load_map_set(folder)
    land = land_columns(maps, args)
    box, box_name = find_box(args)

    roads = gpd.read_file(args.roads).to_crs(geo["crs"])
    roads = roads[roads["road_class"].isin(args.classes)]
    n_elev = int((roads["elevated"] | roads["tunnel"]).sum())
    if not args.include_elevated:
        roads = roads[~(roads["elevated"] | roads["tunnel"])]

    rec = []
    for r in roads.itertuples():
        pts = centreline_points(r.geometry, args.step)
        if not pts:
            continue
        x, y = crs_to_map_xy([p.x for p in pts], [p.y for p in pts], geo)
        for xx, yy in zip(np.atleast_1d(x), np.atleast_1d(y)):
            rec.append((xx, yy, r.road_class, r.highway, r.osm_id))
    pts = pd.DataFrame(rec, columns=["x_m", "y_m", "road_class", "highway", "osm_id"])
    pts["i"] = np.floor(pts["x_m"] / DX).astype(int)
    pts["j"] = np.floor(pts["y_m"] / DX).astype(int)

    ny, nx = maps["topo"].shape
    inside = (pts["i"] >= 0) & (pts["i"] < nx) & (pts["j"] >= 0) & (pts["j"] < ny)
    in_land = inside & (pts["i"] >= land[0]) & (pts["i"] < land[1])
    in_box = in_land if box is None else in_land & (pts["i"] >= box[0]) & (pts["i"] < box[1]) & \
        (pts["j"] >= box[2]) & (pts["j"] < box[3])
    keep = source_cell_ok(pts["i"].to_numpy(), pts["j"].to_numpy(), maps, land, box)
    hb, hv = object_heights(maps)
    ic, jc = pts["i"].clip(0, nx - 1).to_numpy(), pts["j"].clip(0, ny - 1).to_numpy()
    pts["in_building"] = in_box & (hb[jc, ic] > 0)
    pts["in_tree"] = in_box & ~pts["in_building"] & (hv[jc, ic] > 0)

    rows = []
    for c in sorted(args.classes) + ["all"]:
        sel = (pts["road_class"] == c) if c != "all" else np.ones(len(pts), bool)
        rows.append({"class": CLASS_NAMES.get(c, c), "points": int(sel.sum()),
                     "outside_map_or_land": int((sel & ~in_land).sum()),
                     "outside_box": int((sel & in_land & ~in_box).sum()),
                     "in_building": int((sel & pts["in_building"]).sum()),
                     "in_tree": int((sel & pts["in_tree"]).sum()),
                     "sources": int((sel & keep).sum())})
    s = pd.DataFrame(rows)
    s["dropped_in_building_share"] = s["in_building"] / (s["sources"] + s["in_building"] + s["in_tree"])
    s["dropped_in_tree_share"] = s["in_tree"] / (s["sources"] + s["in_building"] + s["in_tree"])
    s["vs_id_limit"] = s["sources"] / ID_SOURCE_LIMIT
    s.to_csv(out / "sources_summary.csv", index=False)
    print(s.to_string(index=False, float_format=lambda v: f"{v:.3g}"))
    if not args.include_elevated:
        print(f"Left out {n_elev} elevated / tunnel ways of classes {args.classes}")

    src = pts[keep].copy()
    src["ground_m"] = maps["topo"][src["j"], src["i"]].astype(float)
    src["z_m"] = src["ground_m"] + args.z_offset
    if box is not None:          # positions relative to the cut-out's corner
        src["x_m"] -= box[0] * DX
        src["y_m"] -= box[2] * DX
        src["i"] -= box[0]
        src["j"] -= box[2]
    src = src.sort_values(["x_m", "y_m"]).reset_index(drop=True)      # x outer loop, as tools/lbmcase
    cols = ["i", "j", "x_m", "y_m", "z_m", "ground_m", "road_class", "highway", "osm_id"]
    src[cols].to_csv(out / "road_sources.csv", index=False)
    n = len(src)
    if n > ID_SOURCE_LIMIT:
        print(f"[WARN] {n} sources > ID limit {ID_SOURCE_LIMIT}; particle_position not written (raise --step)")
    else:
        write_particle_sources(out / "particle_position", src["x_m"].to_numpy(), src["y_m"].to_numpy(),
                               src["z_m"].to_numpy(), velocity=tuple(args.velocity))
        print(f"Wrote {n} sources to {out / 'particle_position'}")
        if n > STACK_LIMIT_SOURCES * 0.5:
            print("[WARN] Generate_Particle.cu holds the sources in stack arrays; at this count check the stack limit")

    if not args.no_figures:
        plot_df = src.copy()
        if box is not None:
            plot_df["i"] += box[0]
            plot_df["j"] += box[2]
        title = f"Road sources '{args.name}': classes {args.classes}, every {args.step:g} m, {n} sources" + \
            (f", box {box_name}" if box else "")
        plot_sources(hb, plot_df, box, title, out / f"sources_{args.name}.png")


if __name__ == "__main__":
    main()
