"""
Compare a located map set with independent terrain and building data.

Purpose: a data check of the map before it is used. Stage 1 (map_statistics.py)
gave the map's own numbers; here they are set against data the map was not
made from (DEMNAS, GHSL) and against the files it was made from.

    pip install -e .[gis]
    python scripts/jakarta-map-analysis/compare_reference.py F:/TSUBAME4_12m/map --georef <out>/georef.yaml \\
        --dem D:/LBM_Jakarta_2023/DEMNAS/DEMNAS_1209-44_v1.0.tif \\
        --ghsl-s D:/LBM_Jakarta_2023/GHSL/BUILT_S/GHS_BUILT_S_E2018_GLOBE_R2023A_54009_10_V1_0_R10_C29.tif \\
        --ghsl-h D:/LBM_Jakarta_2023/GHSL/BUILT_H/GHS_BUILT_H_AGBH_E2018_GLOBE_R2023A_54009_100_V1_0_R10_C29.tif \\
        --source-topo D:/LBM_Jakarta_2023/dataset/topo1_new.tif \\
        --source-building "D:/LBM_Jakarta_2023/dataset/w and wo height(6) AREA1 rasterized new new.tif"

Every input is optional; each one adds its own rows to compare_summary.csv and
its own figure. Region: land columns of the map (see _common.land_columns).

1. Terrain (--dem, --source-topo) -> terrain_compare.png, rows "dem_*", "source_topo_*"
   What: map ground height minus the reference ground height, per 2 m cell.
   Why: is the map terrain a real, correctly placed terrain? A constant offset
   is a datum difference; a pattern that follows the buildings means the
   reference is a surface model, not bare earth. Split by open and building cells.
   Reference: DEMNAS (Badan Informasi Geospasial, 0.27 arc-second, heights on
   the EGM2008 geoid [U]); the source topography file the map was made from.
   Units: m; bias = mean(map - ref), RMSE, Pearson r, share of cells where the
   map equals the reference rounded / rounded down to whole metres.
2. Buildings at 100 m (--ghsl-s, --ghsl-h) -> ghsl_scatter.png, ghsl_maps.png, ghsl_pixels.csv
   What: per GHSL 100 m pixel (World Mollweide), the built-up fraction
   (building area / pixel area) and the average gross building height AGBH
   (building volume / pixel area, i.e. H_av) of the map and of GHSL; the net
   height ANBH = volume / building area follows from the two.
   Why: GHSL is the only global, independent building height product; the
   100 m pixel is its native grid, so the map is aggregated rather than GHSL
   interpolated. Only pixels fully inside the map's land columns are used
   (>= 95 % of the median number of map cells per pixel).
   Reference: GHS-BUILT-S and GHS-BUILT-H R2023A (Pesaresi & Politis 2023;
   GHSL Data Package 2023, AGBH = BUVOL / S) [U]. GHSL heights come from 30 m
   global DEMs and are known to underestimate tall buildings [U].
   Units: fraction [-], heights [m]; bias, RMSE, r over pixels; totals in km2 / km3 x 1e-3.
3. Source building raster (--source-building) -> source_building.csv
   What: the map's building heights against the raster named in the dataset
   folder as the map's input, cell by cell, as a table of height classes.
   Why: shows how the map was made from it (e.g. a 6 m default height).
   Rows: mask agreement (building or not), equal heights where both have a
   building, and the same if every source building below 6 m were 6 m.
"""
import argparse

import numpy as np
import pandas as pd

from _common import DX, add_map_args, land_columns, out_dir, resolve_map
from data_loaders.map_georef import load_georef, north_up, warp_to_map
from data_loaders.map_io import load_map_set
from physics_core.urban_morphology import object_heights

GHSL_PIXEL = 100.0     # m
FULL_PIXEL = 0.95      # a pixel is used when it holds >= this share of the median number of map cells per pixel


def diff_stats(m, r, prefix):
    ok = np.isfinite(m) & np.isfinite(r)
    if not ok.any():
        return {f"{prefix}n": 0}
    d = m[ok] - r[ok]
    return {f"{prefix}n": int(ok.sum()), f"{prefix}bias": float(d.mean()), f"{prefix}rmse": float(np.sqrt((d ** 2).mean())),
            f"{prefix}mae": float(np.abs(d).mean()), f"{prefix}r": float(np.corrcoef(m[ok], r[ok])[0, 1]),
            f"{prefix}d_p5": float(np.percentile(d, 5)), f"{prefix}d_p95": float(np.percentile(d, 95))}


def terrain_rows(name, topo, ref, is_b, land_rows):
    """Difference statistics map - ref over land cells, all / open / building cells."""
    t, r, b = topo[land_rows], ref[land_rows], is_b[land_rows]
    rows = {}
    rows.update(diff_stats(t, r, f"{name}_all_"))
    rows.update(diff_stats(np.where(b, np.nan, t), r, f"{name}_open_"))
    rows.update(diff_stats(np.where(b, t, np.nan), r, f"{name}_building_"))
    ok = np.isfinite(r)
    rows[f"{name}_coverage"] = float(ok.mean())
    rows[f"{name}_round_share"] = float((np.round(r[ok]) == t[ok]).mean()) if ok.any() else np.nan
    rows[f"{name}_floor_share"] = float((np.floor(r[ok]) == t[ok]).mean()) if ok.any() else np.nan   # map = whole metres rounded down?
    return rows


def ghsl_pixels(geo, hb, land_rows, s_path, h_path):
    """Map and GHSL values per GHSL pixel fully inside the land rows."""
    import rasterio
    from pyproj import Transformer
    from data_loaders.map_georef import image_transform
    img_rows, img_cols = hb.shape
    rr, cc = np.meshgrid(np.arange(img_rows)[land_rows], np.arange(img_cols), indexing="ij")
    e, n = image_transform(geo) * (cc.ravel() + 0.5, rr.ravel() + 0.5)
    with rasterio.open(h_path) as src:
        ghsl_crs, t100 = src.crs, src.transform
    x, y = Transformer.from_crs(geo["crs"], ghsl_crs, always_xy=True).transform(e, n)
    pc, pr = (~t100) * (x, y)
    pr, pc = np.floor(pr).astype(np.int64), np.floor(pc).astype(np.int64)
    r0, c0 = pr.min(), pc.min()
    key = (pr - r0) * (pc.max() - c0 + 1) + (pc - c0)
    h = hb[land_rows].ravel()
    cells = np.bincount(key)
    area = np.bincount(key, weights=(h > 0) * DX * DX)
    vol = np.bincount(key, weights=h * DX * DX)
    # cell centres fall unevenly into the sheared Mollweide pixels, so "full" is judged against the median count
    use = np.nonzero(cells >= FULL_PIXEL * np.median(cells[cells > 0]))[0]
    width = pc.max() - c0 + 1
    df = pd.DataFrame({"pix_row": use // width + r0, "pix_col": use % width + c0})
    cover = cells[use] * DX * DX
    df["map_frac"] = area[use] / cover
    df["map_agbh"] = vol[use] / cover
    win = rasterio.windows.Window(int(c0), int(r0), int(width), int(pr.max() - r0 + 1))
    with rasterio.open(h_path) as src:
        agbh = src.read(1, window=win).astype(float)
        agbh[agbh == src.nodata] = np.nan
    df["ghsl_agbh"] = agbh[df["pix_row"] - r0, df["pix_col"] - c0]
    with rasterio.open(s_path) as src:
        k = int(round(GHSL_PIXEL / src.res[0]))           # 10 for the 10 m product, 1 for 100 m
        r_off = (src.transform.f - t100.f) / -src.res[1]   # 10 m tile shares the 100 m origin
        c_off = (t100.c - src.transform.c) / src.res[0]
        w10 = rasterio.windows.Window(int(c0 * k - c_off), int(r0 * k + r_off), int(width * k), int((pr.max() - r0 + 1) * k))
        s = src.read(1, window=w10).astype(float)
        s[s == src.nodata] = np.nan
    s = s.reshape(s.shape[0] // k, k, s.shape[1] // k, k).sum(axis=(1, 3))
    df["ghsl_frac"] = s[df["pix_row"] - r0, df["pix_col"] - c0] / GHSL_PIXEL ** 2
    df["map_anbh"] = np.where(df["map_frac"] > 0, df["map_agbh"] / df["map_frac"].where(df["map_frac"] > 0), np.nan)
    df["ghsl_anbh"] = np.where(df["ghsl_frac"] > 0, df["ghsl_agbh"] / df["ghsl_frac"].where(df["ghsl_frac"] > 0), np.nan)
    xc, yc = t100 * (df["pix_col"] + 0.5, df["pix_row"] + 0.5)
    df["lon"], df["lat"] = Transformer.from_crs(ghsl_crs, "EPSG:4326", always_xy=True).transform(xc, yc)
    return df


def ghsl_rows(df):
    rows = {"ghsl_pixels": len(df)}
    for k in ("frac", "agbh", "anbh"):
        st = diff_stats(df[f"map_{k}"].to_numpy(), df[f"ghsl_{k}"].to_numpy(), f"ghsl_{k}_")
        rows.update({kk: v for kk, v in st.items() if not kk.endswith("_n") or k == "anbh"})
        rows[f"ghsl_{k}_map_mean"] = float(np.nanmean(df[f"map_{k}"]))
        rows[f"ghsl_{k}_ref_mean"] = float(np.nanmean(df[f"ghsl_{k}"]))
    a = GHSL_PIXEL ** 2
    rows["built_area_km2_map"] = float(df["map_frac"].sum() * a / 1e6)
    rows["built_area_km2_ghsl"] = float(np.nansum(df["ghsl_frac"]) * a / 1e6)
    rows["built_volume_1e6m3_map"] = float(df["map_agbh"].sum() * a / 1e6)
    rows["built_volume_1e6m3_ghsl"] = float(np.nansum(df["ghsl_agbh"]) * a / 1e6)
    return rows


def source_building_table(hb_img, src_img):
    m, s = np.round(hb_img), np.round(np.nan_to_num(src_img))
    covered = np.isfinite(src_img)
    classes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 50, 100, 1000]
    lab = [f"{a}" if b - a == 1 else f"{a}-{b - 1}" for a, b in zip(classes[:-1], classes[1:])]
    sc = pd.cut(s[covered], classes, right=False, labels=lab)
    mc = pd.cut(m[covered], classes, right=False, labels=lab)
    t = pd.crosstab(sc, mc, rownames=["source [m]"], colnames=["map [m]"], dropna=False)
    both = covered & (m > 0) & (s > 0)
    rows = {"source_cover_share": float(covered.mean()),
            "source_building_share": float((s[covered] > 0).mean()), "map_building_share_in_cover": float((m[covered] > 0).mean()),
            "source_mask_agree": float(((m > 0) == (s > 0))[covered].mean()),
            "source_equal_where_both": float((m[both] == s[both]).mean()),
            "source_equal_where_both_if_min_6m": float((m[both] == np.maximum(s[both], 6)).mean()),
            "source_6m_share": float((s[covered & (s > 0)] == 6).mean()), "map_6m_share_in_cover": float((m[covered & (m > 0)] == 6).mean()),
            "map_2to5m_cells": int(((m >= 2) & (m <= 5)).sum()), "source_2to5m_cells": int(((s >= 2) & (s <= 5) & covered).sum()),
            "map_only_building_cells": int((covered & (m > 0) & (s == 0)).sum()),
            "source_only_building_cells": int((covered & (s > 0) & (m == 0)).sum())}
    rows_out = np.nonzero(~covered.any(axis=1))[0]
    rows["image_rows_without_source"] = f"{rows_out.min()}-{rows_out.max()}" if rows_out.size else "none"
    return t, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_map_args(ap)
    ap.add_argument("--georef", required=True, help="georef.yaml from fit_map_location.py")
    ap.add_argument("--dem", nargs="*", default=[], help="DEMNAS tiles (EPSG:4326 assumed when untagged)")
    ap.add_argument("--dem-crs", default="EPSG:4326", help="CRS for DEM files without a CRS tag")
    ap.add_argument("--ghsl-s", help="GHS-BUILT-S tile (10 m or 100 m, World Mollweide)")
    ap.add_argument("--ghsl-h", help="GHS-BUILT-H AGBH tile (100 m, World Mollweide)")
    ap.add_argument("--source-topo", help="topography raster the map was made from")
    ap.add_argument("--source-building", help="building height raster the map was made from")
    args = ap.parse_args()
    folder, label = resolve_map(ap, args)
    out = out_dir(args, label)
    geo = load_georef(args.georef)
    maps = load_map_set(folder)
    i0, i1 = land_columns(maps, args)
    hb, _ = object_heights(maps)
    o = geo["orientation"]
    if o.split(",")[0][2] not in "NS":
        raise NotImplementedError("[ERROR] land rows assume map i runs north-south")
    topo_img, hb_img = north_up(maps["topo"], o), north_up(hb, o)
    land = slice(i0, i1) if o.startswith("i:S") else slice(geo["nx"] - i1, geo["nx"] - i0)
    summary, figs = {}, {}

    terrain = {}
    if args.dem:
        refs = [warp_to_map(p, geo, "bilinear", src_crs=args.dem_crs) for p in args.dem]
        terrain["dem"] = np.nanmean(np.stack(refs), axis=0) if len(refs) > 1 else refs[0]
    if args.source_topo:
        terrain["source_topo"] = warp_to_map(args.source_topo, geo, "average")
    for name, ref in terrain.items():
        summary.update(terrain_rows(name, topo_img, ref, hb_img > 0, land))
    if terrain:
        figs["terrain"] = (topo_img, terrain, land, hb_img > 0)

    if args.ghsl_s and args.ghsl_h:
        px = ghsl_pixels(geo, hb_img, land, args.ghsl_s, args.ghsl_h)
        px.to_csv(out / "ghsl_pixels.csv", index=False)
        summary.update(ghsl_rows(px))
        figs["ghsl"] = px

    if args.source_building:
        src = warp_to_map(args.source_building, geo, "nearest", use_nodata=False)   # its nodata 0 = no building
        table, rows = source_building_table(hb_img, src)
        table.to_csv(out / "source_building.csv")
        summary.update(rows)
        print(table.to_string())

    s = pd.DataFrame({"statistic": list(summary), "value": list(summary.values())})
    s.to_csv(out / "compare_summary.csv", index=False)
    with pd.option_context("display.float_format", "{:.4g}".format):
        print(s.to_string(index=False))
    from plot_compare_reference import plot_all
    plot_all(figs, out, geo)


if __name__ == "__main__":
    main()
