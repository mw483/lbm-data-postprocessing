"""
Urban morphology statistics of an LBM-city map set.

All functions work on (ny, nx) arrays indexed [j, i], as data_loaders.map_io
returns them. building.dat and vegetation.dat hold ABSOLUTE heights, so the
object heights are building - topography and vegetation - topography.

Terms (Grimmond & Oke 1999, J. Appl. Meteor. 38, 1262-1292):
  plan area fraction  lambda_p = building plan area / total plan area
  frontal area index  lambda_f = windward wall area / total plan area
  area-weighted mean height H_av = building volume / total plan area
"""
import numpy as np
from scipy import ndimage

PERCENTILES = (5, 25, 50, 75, 90, 95, 99)


def object_heights(maps):
    """(h_b, h_v): building and tree heights above ground, 0 where there is none."""
    hb = np.clip(maps["build"] - maps["topo"], 0, None)
    hv = np.clip(maps["veg"] - maps["topo"], 0, None)
    return hb, hv


def empty_edge_columns(maps):
    """
    (i0, i1): the first and one-past-last column that hold any building or
    ground above 0 m. Columns outside are the flat 0 m strips at the ends of the
    domain (Jakarta: the sea fetch and the outlet strip). Trees are ignored here.
    """
    hb, _ = object_heights(maps)
    used = ((hb > 0) | (maps["topo"] > 0)).any(axis=0)
    if not used.any():
        return 0, used.size
    idx = np.nonzero(used)[0]
    return int(idx[0]), int(idx[-1]) + 1


def value_stats(values, prefix=""):
    """count, mean, std, min, max and PERCENTILES of a 1D sample (empty -> NaN)."""
    v = np.asarray(values, dtype=float).ravel()
    out = {f"{prefix}count": v.size}
    if v.size == 0:
        for k in ("mean", "std", "min", "max", *(f"p{p}" for p in PERCENTILES)):
            out[f"{prefix}{k}"] = np.nan
        return out
    out.update({f"{prefix}mean": v.mean(), f"{prefix}std": v.std(),
                f"{prefix}min": v.min(), f"{prefix}max": v.max()})
    for p, q in zip(PERCENTILES, np.percentile(v, PERCENTILES)):
        out[f"{prefix}p{p}"] = q
    return out


def plan_area_fraction(hb):
    """lambda_p: share of cells with a building."""
    return float((hb > 0).mean())


def area_weighted_height(hb):
    """H_av = sum of building heights / number of cells (building volume per ground area) [m]."""
    return float(hb.mean())


def frontal_area_index(hb, axis, dx=1.0):
    """
    lambda_f for wind along +x (axis=1, along i) or +y (axis=0, along j):
    windward wall area / total plan area = sum of the positive height steps met
    by the wind x dx / (cells x dx^2) = sum of steps / (cells x dx).
    hb in m and dx in m per cell (dx = 1 when heights are in cells).
    Walls in the lee of taller ones count only by the part that sticks out
    (raster definition). Inflow edge walls count in full.
    """
    s = np.asarray(hb, dtype=float)
    pad = np.zeros((1, s.shape[1])) if axis == 0 else np.zeros((s.shape[0], 1))
    steps = np.diff(np.concatenate([pad, s], axis=axis), axis=axis)
    return float(np.clip(steps, 0, None).sum() / (s.size * dx))


def label_buildings(hb, connectivity=4):
    """
    Groups touching building cells into buildings. Returns (labels, n) with
    labels 0 for no building and 1..n per building.
    connectivity 4: cells sharing a side; 8: also corners.
    """
    structure = ndimage.generate_binary_structure(2, 1 if connectivity == 4 else 2)
    labels, n = ndimage.label(hb > 0, structure=structure)
    return labels, n


def building_table(hb, labels, n, dx):
    """
    One row per building (dict of arrays): id, n_cells, area_m2, h_max, h_mean,
    i_center, j_center (cells), len_i, len_j (bounding box, cells), min_side (cells).
    """
    ids = np.arange(1, n + 1)
    n_cells = ndimage.sum_labels(np.ones_like(hb), labels, ids)
    h_max = ndimage.maximum(hb, labels, ids)
    h_mean = ndimage.mean(hb, labels, ids)
    centers = np.array(ndimage.center_of_mass(np.ones_like(hb), labels, ids)).reshape(-1, 2)
    slices = ndimage.find_objects(labels)
    len_j = np.array([s[0].stop - s[0].start for s in slices])
    len_i = np.array([s[1].stop - s[1].start for s in slices])
    return {
        "id": ids, "n_cells": n_cells.astype(int), "area_m2": n_cells * dx * dx,
        "h_max": np.asarray(h_max), "h_mean": np.asarray(h_mean),
        "i_center": centers[:, 1], "j_center": centers[:, 0],
        "len_i": len_i, "len_j": len_j, "min_side": np.minimum(len_i, len_j),
    }


def tile_stats(hb, hv, tile):
    """
    Statistics on tile x tile cell blocks (the last partial row/column of tiles
    is dropped). Returns dict of (ny_t, nx_t) arrays: lambda_p, h_mean (over
    building cells, NaN without buildings), h_max, h_av (area-weighted), tree_cover.
    """
    ny, nx = hb.shape
    nyt, nxt = ny // tile, nx // tile
    b = hb[:nyt * tile, :nxt * tile].reshape(nyt, tile, nxt, tile)
    v = hv[:nyt * tile, :nxt * tile].reshape(nyt, tile, nxt, tile)
    is_b = b > 0
    n_b = is_b.sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        h_mean = np.where(n_b > 0, b.sum(axis=(1, 3)) / n_b, np.nan)
    return {
        "lambda_p": is_b.mean(axis=(1, 3)),
        "h_mean": h_mean,
        "h_max": b.max(axis=(1, 3)),
        "h_av": b.mean(axis=(1, 3)),
        "tree_cover": ((v > 0) & ~is_b).mean(axis=(1, 3)),
    }


# =============================================================================
# Cut-out boxes (choosing a piece of the map to simulate)
# =============================================================================
# Cost model: the flat benchmark run 512 x 128 x 1024 cells took 0.068 s per
# step on one TSUBAME node_f (4 GPUs), dt = 0.008 s at 2 m cells (20261026_scalar2,
# 180005 steps in 3:24:37). Wall time is scaled linearly with the cell count [est].
BENCH_CELLS = 512 * 128 * 1024
BENCH_S_PER_STEP = 0.068
DT_2M = 0.008
ID_SOURCE_LIMIT = 214_748          # int32 particle IDs with ID_DIGIT 4: (2^31 - 1) // 10000


def blockage_by_column(hb, top_m, dx):
    """
    Share of each y-z cross-section (one per column i, wind along +i) that is
    building: sum over j of the building height x dx / (domain width x top).
    The periodic stand-in for the AIJ blockage ratio (Tominaga et al. 2008,
    sec. 3.1: < 3%), which in an inflow/outflow domain uses the frontal
    projection of all buildings. Heights above the top are cut at the top.
    """
    h = np.minimum(np.asarray(hb, dtype=float), top_m)
    return h.sum(axis=0) * dx / (h.shape[0] * dx * top_m)


def best_shift(counts, a0, a1, search):
    """
    Shift d in -search..search (kept inside the map) that minimises
    counts[a0 + d] + counts[a1 - 1 + d], i.e. the building cells on both edges
    of a periodic pair; ties go to the smallest |d|.
    """
    n = len(counts)
    shifts = np.arange(max(-search, -a0), min(search, n - a1) + 1)
    c = np.asarray(counts)
    cost = c[a0 + shifts] + c[a1 - 1 + shifts]
    return int(shifts[np.lexsort((np.abs(shifts), cost))[0]])


def box_summary(maps, box, dx=2.0, nz=None, run_s=3600.0, source_step=8,
                default_height=6.0, seam_search=16, min_cells=(10, 16)):
    """
    Numbers for one candidate cut-out box = (i0, i1, j0, j1), end exclusive,
    computed on the full-resolution map. Wind is taken along +i (map x).

    Returns a flat dict (see the keys) of:
    - size and position; lambda_p, H_av, building height stats, share of
      building cells at `default_height` (Jakarta: 6 m default in the OSM data);
    - tree cover, ground range;
    - periodic seams: building cells on each edge and the ground step across
      each seam, plus the same-size box shifted by up to +-seam_search cells
      whose seams cross the fewest building cells (street-aligned edges);
    - resolution: buildings (4-connected groups inside the box) narrower than
      each value in min_cells, by count and by volume (AIJ/COST >= 10 cells per
      side; professor >= 16);
    - with nz: domain top, top / H_max (AIJ >= 5), length / H_max (AIJ >= 10,
      COST 15), blockage max and mean, cells and wall-time estimate;
    - open ground (no building, no tree) and sources on a source_step grid.
    """
    i0, i1, j0, j1 = (int(v) for v in box)
    ny, nx = maps["topo"].shape
    if not (0 <= i0 < i1 <= nx and 0 <= j0 < j1 <= ny):
        raise ValueError(f"[ERROR] box {box} is outside the {nx} x {ny} map")
    hb_all, hv_all = object_heights(maps)
    hb, hv = hb_all[j0:j1, i0:i1], hv_all[j0:j1, i0:i1]
    topo = np.asarray(maps["topo"][j0:j1, i0:i1], dtype=float)
    is_b = hb > 0
    n_i, n_j = i1 - i0, j1 - j0
    h_max = float(hb.max())

    out = {"i0": i0, "i1": i1, "j0": j0, "j1": j1, "n_i": n_i, "n_j": n_j,
           "length_x_m": n_i * dx, "width_y_m": n_j * dx,
           "lambda_p": plan_area_fraction(hb), "H_av_m": area_weighted_height(hb),
           "lambda_f_x": frontal_area_index(hb, axis=1, dx=dx),
           "h_mean_m": float(hb[is_b].mean()) if is_b.any() else np.nan,
           "h_p50_m": float(np.median(hb[is_b])) if is_b.any() else np.nan,
           "h_max_m": h_max,
           "default_height_share": float((hb[is_b] == default_height).mean()) if is_b.any() else np.nan,
           "tree_cover": float(((hv > 0) & ~is_b).mean()),
           "ground_min_m": float(topo.min()), "ground_max_m": float(topo.max()),
           "ground_range_m": float(topo.max() - topo.min())}

    # periodic seams
    out.update({"edge_build_cells_i0": int(is_b[:, 0].sum()), "edge_build_cells_i1": int(is_b[:, -1].sum()),
                "edge_build_cells_j0": int(is_b[0, :].sum()), "edge_build_cells_j1": int(is_b[-1, :].sum()),
                "seam_step_x_mean_m": float(np.abs(topo[:, 0] - topo[:, -1]).mean()),
                "seam_step_x_max_m": float(np.abs(topo[:, 0] - topo[:, -1]).max()),
                "seam_step_y_mean_m": float(np.abs(topo[0, :] - topo[-1, :]).mean()),
                "seam_step_y_max_m": float(np.abs(topo[0, :] - topo[-1, :]).max())})
    # same-size box shifted by up to +-seam_search cells so that both seams of
    # each periodic pair cross the fewest building cells (keeps the cell counts
    # chosen for the GPU split)
    col_counts = (hb_all[j0:j1, :] > 0).sum(axis=0)       # building cells per column, box rows only
    row_counts = (hb_all[:, i0:i1] > 0).sum(axis=1)       # per row, box columns only
    di = best_shift(col_counts, i0, i1, seam_search)
    dj = best_shift(row_counts, j0, j1, seam_search)
    out.update({"shifted_box": f"{i0 + di} {i1 + di} {j0 + dj} {j1 + dj}",
                "shifted_edge_build_cells": int(col_counts[i0 + di] + col_counts[i1 - 1 + di]
                                                + row_counts[j0 + dj] + row_counts[j1 - 1 + dj])})

    # resolution of the buildings inside the box
    labels, n = label_buildings(hb)
    out["buildings"] = n
    if n:
        t = building_table(hb, labels, n, dx)
        vol = t["n_cells"] * t["h_mean"]
        out["one_cell_buildings_share"] = float((t["n_cells"] == 1).mean())
        for m in min_cells:
            narrow = t["min_side"] < m
            out[f"narrower_{m}_cells_share"] = float(narrow.mean())
            out[f"narrower_{m}_cells_volume_share"] = float(vol[narrow].sum() / vol.sum())
    else:
        out["one_cell_buildings_share"] = np.nan
        for m in min_cells:
            out[f"narrower_{m}_cells_share"] = np.nan
            out[f"narrower_{m}_cells_volume_share"] = np.nan

    # sources on open ground
    open_ground = ~is_b & ~(hv > 0)
    grid = open_ground[::source_step, ::source_step]
    out.update({"open_ground_share": float(open_ground.mean()), "source_step_cells": source_step,
                "sources": int(grid.sum()), "sources_vs_id_limit": float(grid.sum() / ID_SOURCE_LIMIT)})

    # domain and cost for a chosen nz
    if nz:
        top = nz * dx
        blk = blockage_by_column(hb, top, dx)
        cells = n_i * n_j * nz
        steps = int(round(run_s / DT_2M))
        hours = cells / BENCH_CELLS * BENCH_S_PER_STEP * steps / 3600
        out.update({"nz": int(nz), "top_m": top,
                    "top_over_hmax": top / h_max if h_max > 0 else np.inf,
                    "length_over_hmax": n_i * dx / h_max if h_max > 0 else np.inf,
                    "width_over_top": n_j * dx / top,
                    "blockage_max": float(blk.max()), "blockage_mean": float(blk.mean()),
                    "cells_million": cells / 1e6, "run_s": run_s, "wall_hours_4gpu_est": hours})
    return out


# =============================================================================
# Idealised arrays and morphometric roughness
# =============================================================================
KARMAN = 0.4


def cube_array(n_i, n_j, size, height, gap_i, gap_j, arrangement="aligned"):
    """
    Building heights (n_j, n_i) of a periodic array of square blocks, in cells:
    footprint size x size, height in m (any unit), gaps gap_i along i and
    gap_j along j. 'staggered' shifts every other row (along i) by half a
    pitch in j, as in Coceal et al. (2006); the array stays periodic when n_i
    is a multiple of 2 pitches and n_j of one pitch (checked).
    """
    p_i, p_j = size + gap_i, size + gap_j
    if arrangement not in ("aligned", "staggered"):
        raise ValueError(f"[ERROR] arrangement must be aligned or staggered, not {arrangement!r}")
    rows_period = 2 if arrangement == "staggered" else 1
    if n_i % (rows_period * p_i) or n_j % p_j:
        raise ValueError(f"[ERROR] {n_i} x {n_j} cells is not a whole number of pitches "
                         f"({rows_period} x {p_i} along i, {p_j} along j) for a periodic {arrangement} array")
    hb = np.zeros((n_j, n_i))
    for k, i0 in enumerate(range(0, n_i, p_i)):
        shift = (p_j // 2) if (arrangement == "staggered" and k % 2) else 0
        for j0 in range(0, n_j, p_j):
            jj = (np.arange(j0, j0 + size) + shift) % n_j
            hb[jj, i0:i0 + size] = height
    return hb


def mean_open_run(hb, axis, periodic=True):
    """
    Mean length (cells) of the open gaps between two buildings along an axis
    (axis=1: along i, axis=0: along j): the typical street or gap width W seen
    by a wind along that axis. Only lines that hold at least one building
    count; a line with no building is an open street parallel to the wind and
    has no W. periodic=True wraps each line (the gap across the seam counts);
    otherwise gaps touching the line ends are left out.
    """
    b = np.asarray(hb) > 0
    lines = b if axis == 1 else b.T
    lengths = []
    for row in lines:
        idx = np.nonzero(row)[0]
        if idx.size == 0:
            continue
        if periodic:
            gaps = np.diff(np.concatenate([idx, [idx[0] + row.size]])) - 1
        else:
            gaps = np.diff(idx) - 1
        lengths.append(gaps[gaps > 0])
    lengths = np.concatenate(lengths) if lengths else np.array([])
    return float(lengths.mean()) if lengths.size else np.nan


def macdonald_1998(lambda_p, lambda_f, height, arrangement="staggered", cd=1.2):
    """
    Displacement height d and roughness length z0 [same unit as height] from
    Macdonald, Griffiths & Hall (1998), Atmos. Environ. 32, 1857-1864, eqs. for
    d/H and z0/H with A = 4.43 / beta = 1.0 (staggered) or A = 3.59 / beta =
    0.55 (square, aligned); C_D = 1.2, kappa = 0.4 [U: coefficients to check
    against the paper].
    """
    a, beta = (4.43, 1.0) if arrangement == "staggered" else (3.59, 0.55)
    d_h = 1.0 + a ** (-lambda_p) * (lambda_p - 1.0)
    if lambda_f <= 0:
        return d_h * height, 0.0
    z0_h = (1.0 - d_h) * np.exp(-(0.5 * beta * cd / KARMAN ** 2 * (1.0 - d_h) * lambda_f) ** -0.5)
    return d_h * height, z0_h * height


def kanda_2013(lambda_p, lambda_f, h_mean, h_max, sigma_h, cd=1.2):
    """
    d and z0 corrected for height variety, Kanda, Inagaki, Miyamoto, Gryschka
    & Raasch (2013), Boundary-Layer Meteorol. 148, 357-377:
      d / H_max = c0 X^2 + (a0 lambda_p^b0 - c0) X,  X = (sigma_H + H_mean) / H_max
      z0 / z0_mac = b1 Y^2 + c1 Y + a1,             Y = lambda_p sigma_H / H_mean
    a0 1.29, b0 0.36, c0 -0.17, a1 0.71, b1 20.21, c1 -0.77; z0_mac from
    macdonald_1998 (staggered) with H = H_mean [U: coefficients and which
    Macdonald variant to check against the paper].
    """
    if h_max <= 0 or h_mean <= 0:
        return 0.0, 0.0
    x = (sigma_h + h_mean) / h_max
    c0, a0, b0 = -0.17, 1.29, 0.36
    d = h_max * (c0 * x ** 2 + (a0 * lambda_p ** b0 - c0) * x)
    _, z0_mac = macdonald_1998(lambda_p, lambda_f, h_mean, "staggered", cd)
    y = lambda_p * sigma_h / h_mean
    z0 = z0_mac * (20.21 * y ** 2 - 0.77 * y + 0.71)
    return d, z0


def morphology_parameters(hb, dx=2.0, arrangement="staggered", min_cells=(10, 16), periodic=True):
    """
    Standard urban morphology numbers of one map of building heights above
    ground (n_j, n_i), wind along +i. Heights in m; lengths in m.
    H_mean and sigma_H are over building cells (plan-area weighted).
    arrangement picks the Macdonald coefficients (real cities: staggered).
    """
    hb = np.asarray(hb, dtype=float)
    is_b = hb > 0
    h = hb[is_b]
    lam_p = plan_area_fraction(hb)
    lam_fx, lam_fy = frontal_area_index(hb, axis=1, dx=dx), frontal_area_index(hb, axis=0, dx=dx)
    h_mean = float(h.mean()) if h.size else 0.0
    h_max = float(h.max()) if h.size else 0.0
    sig = float(h.std()) if h.size else 0.0
    w_x, w_y = mean_open_run(hb, 1, periodic) * dx, mean_open_run(hb, 0, periodic) * dx
    out = {"n_i": hb.shape[1], "n_j": hb.shape[0], "length_x_m": hb.shape[1] * dx, "width_y_m": hb.shape[0] * dx,
           "lambda_p": lam_p, "lambda_f_x": lam_fx, "lambda_f_y": lam_fy,
           "H_av_m": area_weighted_height(hb), "H_mean_m": h_mean, "H_max_m": h_max,
           "sigma_H_m": sig, "sigma_H_over_H_mean": sig / h_mean if h_mean else np.nan,
           "H_max_over_H_mean": h_max / h_mean if h_mean else np.nan}
    if h.size:
        vals, counts = np.unique(h, return_counts=True)
        out["most_common_height_m"] = float(vals[np.argmax(counts)])
        out["most_common_height_share"] = float(counts.max() / h.size)
    labels, n = label_buildings(hb)
    out["buildings"] = n
    if n:
        t = building_table(hb, labels, n, dx)
        vol = t["n_cells"] * t["h_mean"]
        out["building_min_side_median_cells"] = float(np.median(t["min_side"]))
        for m in min_cells:
            narrow = t["min_side"] < m
            out[f"narrower_{m}_cells_share"] = float(narrow.mean())
            out[f"narrower_{m}_cells_volume_share"] = float(vol[narrow].sum() / vol.sum())
    out.update({"street_width_x_m": w_x, "street_width_y_m": w_y,
                "H_over_W_x": h_mean / w_x if w_x > 0 else np.nan, "H_over_W_y": h_mean / w_y if w_y > 0 else np.nan})
    d_m, z0_m = macdonald_1998(lam_p, lam_fx, h_mean, arrangement)
    d_k, z0_k = kanda_2013(lam_p, lam_fx, h_mean, h_max, sig)
    out.update({"d_macdonald_m": d_m, "z0_macdonald_m": z0_m,
                "d_kanda_m": d_k, "z0_kanda_m": z0_k,
                "d_macdonald_over_H": d_m / h_mean if h_mean else np.nan,
                "z0_macdonald_over_H": z0_m / h_mean if h_mean else np.nan,
                "d_kanda_over_H": d_k / h_mean if h_mean else np.nan,
                "z0_kanda_over_H": z0_k / h_mean if h_mean else np.nan})
    return out
