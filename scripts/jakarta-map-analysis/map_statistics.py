"""
Terrain, building and tree statistics of a map set, for comparison with real data.

Purpose: show that the map describes a realistic city (data check, not a
physics validation). The numbers are compared with independent data on
Jakarta in a later step (see planning/jakarta_map_check_plan_2026-10-28.md).

    python scripts/jakarta-map-analysis/map_statistics.py F:/TSUBAME4_12m/map --georef georef.yaml

Region: the land columns (default: the domain without the flat 0 m strips at
both ends, i.e. without the Jakarta sea fetch). Heights are above ground
(h_b = building - topography, h_v = vegetation - topography), in m.

Writes to the output folder:
- summary.csv            one row per statistic: name, value, unit, what it measures
- buildings.csv          one row per building (4-connected group of building cells)
- tallest_buildings.csv  the N tallest buildings, with lon/lat when --georef is given
- tiles_<size>m.csv      statistics per square tile (default 500 m)
- building_cell_heights_hist.npz  histogram of building heights over building cells (5 m bins)
- transect_i.csv         per map column i: mean ground, lambda_p, H_av, tree cover (all rows)

What each statistic is for (reference data in the plan, section 3.3):
- ground min/mean/percentiles/max: is the terrain a realistic flat coastal plain?
  Compare with a bare-earth DEM (FABDEM, DEMNAS).
- lambda_p (plan area fraction): how built-up the city is; first-order control
  on the drag the wind feels. Compare with GHS-BUILT-S, Google Open Buildings.
- h_b statistics over building cells: typical height and spread. Compare with
  GHS-BUILT-H, WSF3D, Open Buildings 2.5D.
- H_av (area-weighted mean height = building volume per ground area): enters
  roughness length estimates. Grimmond & Oke (1999).
- lambda_f along i and j (frontal area index): windward wall area per ground
  area, for wind along the map x (i) and y (j) axes. Grimmond & Oke (1999).
- buildings by height class and by smallest width in cells: how much of the
  city the 2 m grid resolves (professor's rule: >= 16 cells across).
- tree cover and tree heights: the 12 m map should have one tree height.
"""
import argparse

import numpy as np
import pandas as pd

from _common import DX, add_map_args, land_columns, out_dir, resolve_map
from data_loaders.map_io import load_map_set
from physics_core.urban_morphology import (area_weighted_height, building_table, frontal_area_index,
                                           label_buildings, object_heights, plan_area_fraction, value_stats)

HEIGHT_CLASSES = (50, 100, 150, 200, 300)   # m
MIN_CELLS_RULE = 16                         # professor: >= 16 cells across a building


def summary_rows(maps, hb, hv, table, land):
    i0, i1 = land
    t, b_, v_ = (a[:, i0:i1] for a in (maps["topo"], hb, hv))
    is_b, is_v = b_ > 0, (v_ > 0) & (b_ <= 0)
    rows = []

    def add(name, value, unit, what):
        rows.append({"statistic": name, "value": value, "unit": unit, "what it measures": what})

    area_km2 = t.size * DX * DX / 1e6
    add("land area", area_km2, "km2", f"columns {i0}-{i1 - 1}, all rows")
    for k, val in value_stats(t, "ground_").items():
        add(k, val, "m" if k != "ground_count" else "cells", "ground height above map zero, land cells")
    add("lambda_p", plan_area_fraction(b_), "-", "share of land cells with a building")
    for k, val in value_stats(b_[is_b], "h_b_").items():
        add(k, val, "m" if k != "h_b_count" else "cells", "building height above ground, building cells")
    if is_b.any():
        vals, counts = np.unique(np.round(b_[is_b]), return_counts=True)
        add("h_b_mode", vals[counts.argmax()], "m", "most common building height (a default height for buildings without data?)")
        add("h_b_mode_share", counts.max() / counts.sum(), "share of building cells", "building cells at the most common height")
    add("H_av", area_weighted_height(b_), "m", "building volume / land area")
    add("lambda_f_i", frontal_area_index(b_, axis=1), "-", "windward wall area / land area, wind along map x (i)")
    add("lambda_f_j", frontal_area_index(b_, axis=0), "-", "windward wall area / land area, wind along map y (j)")
    for h in HEIGHT_CLASSES:
        add(f"buildings_taller_than_{h}m", int((table["h_max"] > h).sum()), "count", "buildings (4-connected groups) by max height")
    n = len(table["id"])
    add("buildings", n, "count", "4-connected groups of building cells (whole domain)")
    for k, val in value_stats(table["area_m2"], "footprint_m2_").items():
        add(k, val, "m2" if k != "footprint_m2_count" else "buildings", "building footprint area")
    narrow = table["min_side"] < MIN_CELLS_RULE
    vol = table["h_mean"] * table["area_m2"]
    add(f"buildings_narrower_than_{MIN_CELLS_RULE}_cells", float(narrow.mean()) if n else np.nan, "share of buildings",
        "smallest bounding-box side < 16 cells (professor's resolution rule)")
    add(f"volume_in_buildings_narrower_than_{MIN_CELLS_RULE}_cells", float(vol[narrow].sum() / vol.sum()) if n else np.nan,
        "share of building volume", "same, weighted by building volume")
    add("tree_cover", float(is_v.mean()), "-", "share of land cells with a tree and no building")
    heights = np.unique(v_[v_ > 0])
    add("tree_heights", " ".join(f"{h:g}" for h in heights[:10]), "m", "distinct tree heights above ground")
    return pd.DataFrame(rows)


def add_coordinates(df, geo):
    from data_loaders.map_georef import cell_to_crs, cell_to_lonlat
    e, n = cell_to_crs(df["i_center"].to_numpy(), df["j_center"].to_numpy(), geo)
    df["easting"], df["northing"] = e, n
    try:
        df["lon"], df["lat"] = cell_to_lonlat(df["i_center"].to_numpy(), df["j_center"].to_numpy(), geo)
    except ImportError:
        print("[INFO] pyproj not installed: no lon/lat columns")
    return df


def tiles_frame(hb, hv, land, tile_cells):
    from physics_core.urban_morphology import tile_stats
    i0, i1 = land
    st = tile_stats(hb[:, i0:i1], hv[:, i0:i1], tile_cells)
    nyt, nxt = st["lambda_p"].shape
    tj, ti = np.meshgrid(np.arange(nyt), np.arange(nxt), indexing="ij")
    df = pd.DataFrame({"tile_i": ti.ravel(), "tile_j": tj.ravel(),
                       "i_center": i0 + (ti.ravel() + 0.5) * tile_cells, "j_center": (tj.ravel() + 0.5) * tile_cells})
    for k, a in st.items():
        df[k] = a.ravel()
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_map_args(ap)
    ap.add_argument("--georef", help="georef.yaml from fit_map_location.py: adds easting/northing and lon/lat")
    ap.add_argument("--tile", type=float, default=500.0, help="tile size in m (default 500)")
    ap.add_argument("--n-tallest", type=int, default=20)
    args = ap.parse_args()
    folder, label = resolve_map(ap, args)
    out = out_dir(args, label)
    maps = load_map_set(folder)
    land = land_columns(maps, args)
    hb, hv = object_heights(maps)
    labels, n = label_buildings(hb)
    table = building_table(hb, labels, n, DX)

    summary = summary_rows(maps, hb, hv, table, land)
    with pd.option_context("display.max_colwidth", 60, "display.width", 200, "display.float_format", "{:.4g}".format):
        print(summary.to_string(index=False))
    summary.to_csv(out / "summary.csv", index=False)

    buildings = pd.DataFrame(table)
    geo = None
    if args.georef:
        from data_loaders.map_georef import load_georef
        geo = load_georef(args.georef)
        buildings = add_coordinates(buildings, geo)
    buildings.to_csv(out / "buildings.csv", index=False)
    tallest = buildings.sort_values("h_max", ascending=False).head(args.n_tallest)
    shown = tallest.round({"h_mean": 1, "i_center": 0, "j_center": 0, "easting": 1, "northing": 1, "lon": 5, "lat": 5})
    print(shown.drop(columns=["id", "n_cells"]).to_string(index=False))
    tallest.to_csv(out / "tallest_buildings.csv", index=False)

    tile_cells = int(round(args.tile / DX))
    tiles = tiles_frame(hb, hv, land, tile_cells)
    if geo is not None:
        tiles = add_coordinates(tiles, geo)
    tiles.to_csv(out / f"tiles_{args.tile:g}m.csv", index=False)
    is_b = hb > 0
    edges = np.arange(0, max(400.0, float(hb.max()) + 10), 5.0)
    np.savez(out / "building_cell_heights_hist.npz", edges=edges,
             counts=np.histogram(hb[:, land[0]:land[1]][is_b[:, land[0]:land[1]]], bins=edges)[0])
    pd.DataFrame({"i": np.arange(hb.shape[1]), "ground_mean": maps["topo"].mean(axis=0),
                  "lambda_p": is_b.mean(axis=0), "H_av": hb.mean(axis=0),
                  "tree_cover": ((hv > 0) & ~is_b).mean(axis=0)}).to_csv(out / "transect_i.csv", index=False)
    print(f"Saved transect_i.csv, summary.csv, buildings.csv ({n} rows), tallest_buildings.csv, tiles_{args.tile:g}m.csv to {out}")


if __name__ == "__main__":
    main()
