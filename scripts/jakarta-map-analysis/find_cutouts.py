"""
Search a map set for boxes of a given size that meet the cut-out criteria, and
rank them. Made to find a strip of the Jakarta map for a small neutral run.

    python scripts/jakarta-map-analysis/find_cutouts.py MAP --size 512 128 --nz 160 --land-columns 1279 7750
    python scripts/jakarta-map-analysis/find_cutouts.py MAP ... --candidates candidates.yaml   # add the best as J1, J2, ...

Every box on a grid of --stride cells is tested (wind along +i):
1. domain top >= 5 x the tallest building (AIJ, Tominaga et al. 2008, sec. 3.1);
2. box length >= 10 x the tallest building (AIJ outflow rule, used by analogy);
3. blockage < 3% in every y-z cross-section (AIJ, periodic stand-in, see box_summary);
4. ground range <= --max-ground-range (default 2 m = one cell), so the
   terrain can be flattened and the periodic seams have no step;
5. plan area fraction >= --min-lambda-p (default 0.2: a neighbourhood, not a park or river).
Passing boxes are ranked by the share of building volume in buildings at least
--min-cells wide (default 16, the professor's rule; AIJ/COST ask 10), then by
the building cells on the four edges (fewer = cleaner periodic seams).
The best --top boxes that do not overlap are then measured exactly with
box_summary (including the street-aligned shift) and printed.

Outputs in --out (default <figures>/jakarta_map_analysis/<map>/):
find_cutouts_<ni>x<nj>.csv (every passing box, ranked) and
find_cutouts_<ni>x<nj>_best.csv (box_summary of the best boxes).
What: which boxes pass and how they rank. Why: to choose and justify a cut-out
(purpose: simulation planning). Reference: the AIJ/COST limits above. Units:
cells of 2 m, heights in m above ground, shares 0-1. Building width is that of
the whole building, also where the box cuts it.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DX, add_map_args, land_columns, out_dir, resolve_map   # noqa: E402

from data_loaders.map_io import load_map_set                                  # noqa: E402
from physics_core.urban_morphology import (box_summary, building_table, label_buildings,   # noqa: E402
                                           object_heights)


def block_reduce(a, b, fn):
    """fn over b x b blocks of a (trimmed to whole blocks)."""
    ny, nx = a.shape[0] // b, a.shape[1] // b
    return fn(a[:ny * b, :nx * b].reshape(ny, b, nx, b), axis=(1, 3))


def window_reduce(blocks, wj, wi, fn):
    """fn over every wj x wi window of blocks (top-left anchored), shape (ny - wj + 1, nx - wi + 1)."""
    v = np.lib.stride_tricks.sliding_window_view(blocks, (wj, wi))
    return fn(v, axis=(2, 3))


def scan(maps, land, ni, nj, nz, stride, min_cells):
    if ni % stride or nj % stride:
        raise SystemExit(f"[ERROR] --stride {stride} must divide the box size {ni} x {nj}")
    hb_all, hv_all = object_heights(maps)
    i0, i1 = land
    hb = hb_all[:, i0:i1]
    topo = np.asarray(maps["topo"][:, i0:i1], dtype=float)
    top = nz * DX
    wi, wj = ni // stride, nj // stride

    is_b = (hb > 0).astype(float)
    labels, n = label_buildings(hb)
    t = building_table(hb, labels, n, DX)
    wide = np.concatenate([[False], t["min_side"] >= min_cells])[labels]
    blocks = {k: block_reduce(a, stride, np.sum) for k, a in
              {"bcells": is_b, "vol": hb, "vol_wide": np.where(wide, hb, 0.0)}.items()}
    sums = {k: window_reduce(b, wj, wi, np.sum) for k, b in blocks.items()}
    hmax = window_reduce(block_reduce(hb, stride, np.max), wj, wi, np.max)
    gmax = window_reduce(block_reduce(topo, stride, np.max), wj, wi, np.max)
    gmin = window_reduce(block_reduce(topo, stride, np.min), wj, wi, np.min)

    # blockage: per column, sum of heights (cut at the top) over the box rows
    h_cut = np.minimum(hb, top)
    cum = np.vstack([np.zeros((1, hb.shape[1])), np.cumsum(h_cut, axis=0)])
    nyw = hmax.shape[0]
    blk = np.empty_like(hmax)
    for a in range(nyw):
        col = (cum[a * stride + nj] - cum[a * stride]) * DX / (nj * DX * top)
        col_blocks = col[: col.size // stride * stride].reshape(-1, stride).max(axis=1)
        blk[a] = window_reduce(col_blocks[None, :], 1, wi, np.max)[0]

    # building cells on the edges of each box
    cb = np.vstack([np.zeros((1, hb.shape[1])), np.cumsum(is_b, axis=0)])     # per column, over rows
    rb = np.hstack([np.zeros((hb.shape[0], 1)), np.cumsum(is_b, axis=1)])     # per row, over columns
    ja, ia = np.meshgrid(np.arange(hmax.shape[0]) * stride, np.arange(hmax.shape[1]) * stride, indexing="ij")
    edge = (cb[ja + nj, ia] - cb[ja, ia]) + (cb[ja + nj, ia + ni - 1] - cb[ja, ia + ni - 1]) \
        + (rb[ja, ia + ni] - rb[ja, ia]) + (rb[ja + nj - 1, ia + ni] - rb[ja + nj - 1, ia])

    with np.errstate(invalid="ignore", divide="ignore"):
        df = pd.DataFrame({
            "i0": (ia + i0).ravel(), "i1": (ia + i0 + ni).ravel(), "j0": ja.ravel(), "j1": (ja + nj).ravel(),
            "lambda_p": (sums["bcells"] / (ni * nj)).ravel(),
            "H_av_m": (sums["vol"] / (ni * nj)).ravel(),
            "h_max_m": hmax.ravel(), "ground_range_m": (gmax - gmin).ravel(),
            "top_over_hmax": (top / hmax).ravel(), "length_over_hmax": (ni * DX / hmax).ravel(),
            "blockage_max": blk.ravel(),
            f"volume_share_ge_{min_cells}_cells": (sums["vol_wide"] / sums["vol"]).ravel(),
            "edge_build_cells": edge.ravel().astype(int)})
    return df


def pick_non_overlapping(df, k):
    chosen = []
    for _, r in df.iterrows():
        if all(r.i1 <= c.i0 or r.i0 >= c.i1 or r.j1 <= c.j0 or r.j0 >= c.j1 for c in chosen):
            chosen.append(r)
        if len(chosen) == k:
            break
    return pd.DataFrame(chosen)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_map_args(ap)
    ap.add_argument("--size", type=int, nargs=2, default=(512, 128), metavar=("NI", "NJ"), help="box size in cells")
    ap.add_argument("--nz", type=int, default=160, help="vertical cells (domain top = nz x 2 m)")
    ap.add_argument("--stride", type=int, default=16, help="box positions every N cells (must divide the size)")
    ap.add_argument("--max-ground-range", type=float, default=2.0)
    ap.add_argument("--min-lambda-p", type=float, default=0.2)
    ap.add_argument("--min-cells", type=int, default=16, help="building width counted as resolved")
    ap.add_argument("--top", type=int, default=5, help="best non-overlapping boxes to measure and keep")
    ap.add_argument("--candidates", help="candidates YAML: add the best boxes as J1, J2, ... (existing J* replaced)")
    args = ap.parse_args()
    folder, label = resolve_map(ap, args)
    out = out_dir(args, label)
    maps = load_map_set(folder)
    land = land_columns(maps, args)
    ni, nj = args.size
    df = scan(maps, land, ni, nj, args.nz, args.stride, args.min_cells)
    vol_col = f"volume_share_ge_{args.min_cells}_cells"
    ok = ((df.top_over_hmax >= 5) & (df.length_over_hmax >= 10) & (df.blockage_max < 0.03)
          & (df.ground_range_m <= args.max_ground_range) & (df.lambda_p >= args.min_lambda_p))
    print(f"Boxes tested: {len(df):,}; passing all criteria: {int(ok.sum()):,}")
    for name, m in [("top >= 5 H_max", df.top_over_hmax >= 5), ("length >= 10 H_max", df.length_over_hmax >= 10),
                    ("blockage < 3%", df.blockage_max < 0.03),
                    (f"ground range <= {args.max_ground_range:g} m", df.ground_range_m <= args.max_ground_range),
                    (f"lambda_p >= {args.min_lambda_p:g}", df.lambda_p >= args.min_lambda_p)]:
        print(f"  {name:28s} {int(m.sum()):,}")
    good = df[ok].sort_values([vol_col, "edge_build_cells"], ascending=[False, True])
    tag = f"{ni}x{nj}"
    good.to_csv(out / f"find_cutouts_{tag}.csv", index=False)
    print(f"Saved {out / f'find_cutouts_{tag}.csv'}")
    if good.empty:
        print("[WARN] no box passes; loosen --max-ground-range or --min-lambda-p, or raise --nz")
        return
    best = pick_non_overlapping(good, args.top)
    rows = []
    for k, r in enumerate(best.itertuples(), 1):
        s = box_summary(maps, (int(r.i0), int(r.i1), int(r.j0), int(r.j1)), dx=DX, nz=args.nz)
        rows.append({"name": f"J{k}", vol_col: getattr(r, vol_col), **s})
    best_df = pd.DataFrame(rows)
    best_df.to_csv(out / f"find_cutouts_{tag}_best.csv", index=False)
    cols = ["name", "i0", "i1", "j0", "j1", "lambda_p", "h_mean_m", "h_max_m", "default_height_share", "tree_cover",
            "ground_range_m", vol_col, "blockage_max", "top_over_hmax", "shifted_box", "shifted_edge_build_cells"]
    with pd.option_context("display.width", 250, "display.float_format", "{:.3g}".format):
        print(best_df[cols].to_string(index=False))
    print(f"Saved {out / f'find_cutouts_{tag}_best.csv'}")

    if args.candidates:
        path = Path(args.candidates)
        data = yaml.safe_load(open(path, encoding="utf-8")) if path.exists() else {}
        data = data or {}
        cands = [c for c in data.get("candidates", []) if not str(c["name"]).startswith("J")]
        for r in rows:
            cands.append({"name": r["name"], "box": [r["i0"], r["i1"], r["j0"], r["j1"]], "nz": args.nz,
                          "note": f"find_cutouts rank {r['name'][1:]}: {vol_col} {r[vol_col]:.2f}, "
                                  f"max {r['h_max_m']:.0f} m, blockage {r['blockage_max']:.1%}"})
        data["candidates"] = cands
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        print(f"Added {len(rows)} boxes to {path}")


if __name__ == "__main__":
    main()
