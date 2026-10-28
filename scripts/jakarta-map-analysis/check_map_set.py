"""
Internal consistency checks of a map set (topography, building, vegetation .dat).

Purpose: a code/data check before the map is used. Each check answers "will
LBM-city read this map the way we think, and is there anything the 2 m grid
cannot represent?". No outside data is needed.

    python scripts/jakarta-map-analysis/check_map_set.py F:/TSUBAME4_12m/map
    python scripts/jakarta-map-analysis/check_map_set.py --case <case>

Prints a table and writes checks.csv (check, value, unit, status, note).
status: ok, note (worth knowing, not an error) or FAIL.

The checks
- absolute heights: building >= topography and vegetation >= topography in
  every cell (LBM-city read_map marks a cell solid below the map value, so the
  files must hold ground + object). FAIL otherwise.
- whole metres / odd heights: share of non-integer values, and of building
  heights that are odd. With 2 m cells an odd height ends half way through a
  cell layer, so the solver rounds it.
- tree height: the distinct tree heights above ground (the 12 m set should
  have only 12).
- trees on building cells, trees outside the land columns (e.g. in the sea fetch).
- one-cell buildings and one-cell gaps between buildings (along i or j):
  features narrower than one cell, which the grid cannot resolve.
- buildings on the domain edges and the ground step across the y seam
  (j = 0 vs j = ny-1): with periodic y, buildings are cut there.
"""
import argparse

import numpy as np
import pandas as pd

from _common import DX, add_map_args, land_columns, out_dir, resolve_map
from data_loaders.map_io import load_map_set
from physics_core.urban_morphology import label_buildings, object_heights


def one_cell_gaps(is_b, axis):
    """Open cells with a building on both sides along `axis`."""
    a = np.moveaxis(is_b, axis, 0)
    gap = ~a[1:-1] & a[:-2] & a[2:]
    return int(gap.sum())


def run_checks(maps, land):
    t, b, v = maps["topo"], maps["build"], maps["veg"]
    hb, hv = object_heights(maps)
    is_b, is_v = hb > 0, hv > 0
    ny, nx = t.shape
    i0, i1 = land
    rows = []

    def add(check, value, unit, status, note=""):
        rows.append({"check": check, "value": value, "unit": unit, "status": status, "note": note})

    add("grid", f"{nx} x {ny}", "cells", "ok", f"{nx * DX / 1000:.2f} x {ny * DX / 1000:.2f} km at {DX:g} m")
    n_bad_b, n_bad_v = int((b < t).sum()), int((v < t).sum())
    add("building < topography", n_bad_b, "cells", "ok" if n_bad_b == 0 else "FAIL", "building.dat must be absolute (ground + building)")
    add("vegetation < topography", n_bad_v, "cells", "ok" if n_bad_v == 0 else "FAIL", "vegetation.dat must be absolute")
    frac = {k: float((np.mod(a, 1) != 0).mean()) for k, a in maps.items()}
    add("non-integer values", ", ".join(f"{k} {f:.2%}" for k, f in frac.items()), "share",
        "ok" if max(frac.values()) == 0 else "note")
    odd = float((np.mod(np.round(hb[is_b]), 2) == 1).mean()) if is_b.any() else 0.0
    add("odd building heights", f"{odd:.1%}", "of building cells", "note" if odd else "ok",
        f"with {DX:g} m cells an odd height ends mid-layer and is rounded by the solver")
    tree_h = np.unique(hv[is_v])
    add("tree heights above ground", ", ".join(f"{h:g}" for h in tree_h[:10]) + (" ..." if tree_h.size > 10 else ""),
        "m", "ok" if tree_h.size <= 1 else "note")
    add("trees on building cells", int((is_v & is_b).sum()), "cells", "note" if (is_v & is_b).any() else "ok",
        "the building wins in the solver (both solid)")
    outside = np.ones(nx, bool)
    outside[i0:i1] = False
    n_v_out = int(is_v[:, outside].sum())
    add("land columns", f"{i0} - {i1 - 1}", "column index", "ok",
        f"columns 0-{i0 - 1} and {i1}-{nx - 1} are flat 0 m with no building")
    cols = np.nonzero(is_v.any(axis=0) & outside)[0]
    add("trees outside the land columns", n_v_out, "cells", "note" if n_v_out else "ok",
        f"columns {cols[0]}-{cols[-1]} (e.g. the sea fetch)" if n_v_out else "")
    labels, n = label_buildings(hb)
    sizes = np.bincount(labels.ravel())[1:]
    add("buildings (4-connected groups)", n, "count", "ok")
    add("one-cell buildings", int((sizes == 1).sum()), "count", "note" if (sizes == 1).any() else "ok",
        f"{(sizes == 1).sum() / max(n, 1):.1%} of buildings; under one cell wide, poorly resolved")
    add("one-cell gaps along i", one_cell_gaps(is_b, 1), "cells", "note")
    add("one-cell gaps along j", one_cell_gaps(is_b, 0), "cells", "note")
    for name, sl in (("row j = 0", np.s_[0, :]), (f"row j = {ny - 1}", np.s_[-1, :]),
                     ("column i = 0", np.s_[:, 0]), (f"column i = {nx - 1}", np.s_[:, -1])):
        k = int(is_b[sl].sum())
        add(f"building cells on {name}", k, "cells", "note" if k else "ok", "cut at the seam if that boundary is periodic")
    seam = np.abs(t[0, i0:i1] - t[-1, i0:i1])
    add("ground step across the y seam", f"mean {seam.mean():.2f}, max {seam.max():.0f}", "m",
        "note" if seam.max() > 0 else "ok", "|topography(j=0) - topography(j=ny-1)| over the land columns")
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_map_args(ap)
    args = ap.parse_args()
    folder, label = resolve_map(ap, args)
    maps = load_map_set(folder)
    table = run_checks(maps, land_columns(maps, args))
    with pd.option_context("display.max_colwidth", 70, "display.width", 200):
        print(table.to_string(index=False))
    path = out_dir(args, label) / "checks.csv"
    table.to_csv(path, index=False)
    print(f"Saved {path}")
    if (table["status"] == "FAIL").any():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
