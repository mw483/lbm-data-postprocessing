"""
Find where a map set sits on the globe by matching its building cells with
building polygons from GIS data, and write georef.yaml.

Purpose: a data check. The map files carry no coordinates; to compare them
with real data tile by tile we need the map's position, orientation and
scale, and the match itself shows which data the map was made from.

    pip install -e .[gis]          # geopandas, rasterio, pyproj
    python scripts/jakarta-map-analysis/fit_map_location.py F:/TSUBAME4_12m/map \\
        --reference E:/Jakarta/Bldg/east/w_height.shp E:/Jakarta/Bldg/east/wo_height.shp \\
        --compare E:/Jakarta/Bldg/west/buildingJakarta.shp

How
1. The reference polygons are drawn on a grid of the map's cell size in their
   own metric CRS (or --crs).
2. The map's building mask is turned into a north-up image for each of the 8
   axis-aligned orientations and slid over the reference at 4 x the cell size
   (FFT correlation). The best orientation and offset win.
3. The offset is refined cell by cell at full resolution.
4. Scores, printed and saved in georef.yaml:
   - ncc: normalised correlation of the two building masks (1 = identical)
   - map_in_ref: share of map building cells that are buildings in the reference
   - ref_in_map: share of reference building cells (inside the map) that are map buildings
   - iou: shared building cells / cells that are a building in either
5. --compare: the same scores for other polygon sets at the fitted position,
   their extent, and how far each edge of it lies from the map's edge
   (reference edge - map edge in CRS metres; positive = further east / north),
   e.g. to see whether the map was cut from them.
Only shifts and 90 degree turns / mirrors are searched; scale 1 (one map cell =
one cell size in the CRS) is assumed, --scales tests others.
"""
import argparse

import numpy as np
import yaml

from _common import DX, add_map_args, out_dir, resolve_map
from data_loaders.map_georef import ORIENTATIONS, north_up, save_georef
from data_loaders.map_io import load_map_set
from physics_core.urban_morphology import object_heights

COARSE = 4    # coarse search step, in cells


def read_polygons(paths, crs):
    import geopandas as gpd
    import pandas as pd
    frames = []
    for p in paths:
        g = gpd.read_file(p)
        target = crs or g.crs
        frames.append(g.to_crs(target))
        print(f"{p}: {len(g):,} polygons, CRS {g.crs}")
    g = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(g, geometry="geometry", crs=frames[0].crs)


def rasterize(g, bounds, res):
    """Building mask of polygons g on a north-up grid covering bounds (x0, y0, x1, y1)."""
    import rasterio.features as rf
    from rasterio.transform import from_origin
    x0, y0, x1, y1 = bounds
    shape = (int(np.ceil((y1 - y0) / res)), int(np.ceil((x1 - x0) / res)))
    geoms = ((geom, 1) for geom in g.geometry if geom is not None and not geom.is_empty)
    return rf.rasterize(geoms, out_shape=shape, transform=from_origin(x0, y1, res, res), dtype="uint8")


def block_mean(a, k):
    h, w = a.shape[0] // k * k, a.shape[1] // k * k
    return a[:h, :w].reshape(h // k, k, w // k, k).mean(axis=(1, 3))


def coarse_search(ref, img, k):
    """Best (score, row, col) of img over ref at k x k blocks; ref is zero-padded so img may stick out."""
    from scipy.signal import fftconvolve
    r = block_mean(ref.astype(np.float32), k)
    t = block_mean(img.astype(np.float32), k)
    r = np.pad(r, ((t.shape[0], t.shape[0]), (t.shape[1], t.shape[1])))
    corr = fftconvolve(r, t[::-1, ::-1], mode="valid")
    energy = fftconvolve(r * r, np.ones_like(t), mode="valid")
    tt = (t * t).sum()
    score = corr / np.sqrt(np.maximum(energy, 1e-9) * tt)
    score[energy < 0.25 * tt] = 0.0     # ignore offsets where the map mostly sticks out of the reference
    row, col = np.unravel_index(np.argmax(score), score.shape)
    return float(score[row, col]), (row - t.shape[0]) * k, (col - t.shape[1]) * k


def window(ref, row, col, shape):
    """ref[row:row+h, col:col+w] with zeros outside ref."""
    out = np.zeros(shape, dtype=ref.dtype)
    r0, c0 = max(row, 0), max(col, 0)
    r1, c1 = min(row + shape[0], ref.shape[0]), min(col + shape[1], ref.shape[1])
    if r1 > r0 and c1 > c0:
        out[r0 - row:r1 - row, c0 - col:c1 - col] = ref[r0:r1, c0:c1]
    return out


def scores(ref_win, img):
    a, b = ref_win > 0, img > 0
    inter = (a & b).sum()
    fa, fb = a.astype(float), b.astype(float)
    ncc = (fa * fb).sum() / np.sqrt((fa * fa).sum() * (fb * fb).sum()) if a.any() and b.any() else 0.0
    return {"ncc": float(ncc), "map_in_ref": float(inter / max(b.sum(), 1)),
            "ref_in_map": float(inter / max(a.sum(), 1)), "iou": float(inter / max((a | b).sum(), 1))}


def refine(ref, img, row, col, reach):
    best = None
    for dr in range(-reach, reach + 1):
        for dc in range(-reach, reach + 1):
            s = scores(window(ref, row + dr, col + dc, img.shape), img)
            if best is None or s["ncc"] > best[0]["ncc"]:
                best = (s, row + dr, col + dc)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_map_args(ap)
    ap.add_argument("--reference", nargs="+", required=True, help="polygon files the map is matched to")
    ap.add_argument("--compare", nargs="*", default=[], help="other polygon files scored at the fitted position")
    ap.add_argument("--crs", help="metric CRS for the match (default: CRS of the first reference file)")
    ap.add_argument("--orientations", nargs="*", default=list(ORIENTATIONS))
    args = ap.parse_args()
    folder, label = resolve_map(ap, args)
    out = out_dir(args, label)

    maps = load_map_set(folder)
    hb, _ = object_heights(maps)
    mask = hb > 0
    ny, nx = mask.shape
    g = read_polygons(args.reference, args.crs)
    crs = g.crs.to_string()
    bounds = g.total_bounds
    ref = rasterize(g, bounds, DX)
    print(f"Reference grid {ref.shape} at {DX:g} m, building cover {ref.mean():.1%}")

    results = []
    for o in args.orientations:
        img = north_up(mask, o)
        s, row, col = coarse_search(ref, img, COARSE)
        print(f"  {o}: coarse score {s:.3f}")
        results.append((s, o, row, col))
    s, o, row, col = max(results)
    img = north_up(mask, o)
    best, row, col = refine(ref, img, row, col, COARSE * 2)
    x0, y0, x1, y1 = bounds
    geo = {"crs": crs, "cell_size": DX, "orientation": o, "nx": int(nx), "ny": int(ny),
           "e_topleft": float(x0 + col * DX), "n_topleft": float(y1 - row * DX),
           "fit": {"reference": [str(p) for p in args.reference], **{k: round(v, 4) for k, v in best.items()},
                   "coarse_scores": {r[1]: round(r[0], 4) for r in results}}}
    from data_loaders.map_georef import cell_to_lonlat
    corners = {"i=0,j=0": (0, 0), f"i=0,j={ny - 1}": (0, ny - 1), f"i={nx - 1},j=0": (nx - 1, 0),
               f"i={nx - 1},j={ny - 1}": (nx - 1, ny - 1)}
    geo["corners_lonlat"] = {k: [round(float(v), 6) for v in cell_to_lonlat(i, j, geo)] for k, (i, j) in corners.items()}

    print(f"\nBest: orientation {o} (map i runs {o[2]}, j runs {o[6]}), scores {best}")
    print(f"North-west corner of the map ({crs}): E {geo['e_topleft']:.1f}, N {geo['n_topleft']:.1f}")
    for k, v in geo["corners_lonlat"].items():
        print(f"  cell {k}: lon {v[0]:.5f}, lat {v[1]:.5f}")

    compare = {}
    for p in args.compare:
        gc = read_polygons([p], crs)
        rc = rasterize(gc, bounds, DX)        # same grid as the reference
        win = window(rc, row, col, img.shape)
        s_all = scores(win, img)
        cols = np.nonzero(win.any(axis=0))[0]
        rows = np.nonzero(win.any(axis=1))[0]
        inside = np.zeros_like(img, dtype=bool)
        if cols.size:
            inside[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1] = True
        s_in = scores(win & inside, img & inside)
        cb = gc.total_bounds
        compare[str(p)] = {
            "scores_whole_map": {k: round(v, 4) for k, v in s_all.items()},
            "scores_inside_its_extent": {k: round(v, 4) for k, v in s_in.items()},
            "extent_crs": [round(float(v), 1) for v in cb],
            "map_building_cells_outside_its_extent": round(float((img & ~inside).sum() / img.sum()), 4),
            "offset_m_vs_map": {"west": round(float(cb[0] - geo["e_topleft"]), 1),
                                "east": round(float(cb[2] - (geo["e_topleft"] + img.shape[1] * DX)), 1),
                                "north": round(float(cb[3] - geo["n_topleft"]), 1),
                                "south": round(float(cb[1] - (geo["n_topleft"] - img.shape[0] * DX)), 1)},
        }
        print(f"\nCompare {p}:\n" + yaml.safe_dump(compare[str(p)], sort_keys=False))
    if compare:
        geo["compare"] = compare
    path = out / "georef.yaml"
    save_georef(path, geo)
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
