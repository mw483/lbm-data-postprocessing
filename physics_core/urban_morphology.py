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


def frontal_area_index(hb, axis):
    """
    lambda_f for wind along +x (axis=1, along i) or +y (axis=0, along j):
    sum of the positive height steps met by the wind, times the cell width,
    over the total plan area. Walls in the lee of taller ones count only by the
    part that sticks out (raster definition). Inflow edge walls count in full.
    """
    s = np.asarray(hb, dtype=float)
    pad = np.zeros((1, s.shape[1])) if axis == 0 else np.zeros((s.shape[0], 1))
    steps = np.diff(np.concatenate([pad, s], axis=axis), axis=axis)
    # height x dx per wall, area dx^2 per cell: dx cancels
    return float(np.clip(steps, 0, None).sum() / s.size)


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
