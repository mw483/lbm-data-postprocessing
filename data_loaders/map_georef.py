"""
Where an LBM-city map grid sits on the globe.

The location is stored in a small YAML file written by
scripts/jakarta-map-analysis/fit_map_location.py:

    crs: EPSG:23834          # metric CRS of the reference data
    cell_size: 2.0           # m, map cell = CRS units
    orientation: "i:S,j:W"   # compass direction in which map i and j increase
    nx: 8000
    ny: 2560
    e_topleft: ...           # CRS easting / northing of the north-west corner
    n_topleft: ...           #   of the map drawn north-up
    fit: {...}               # how well the fit matched, for the record

Only axis-aligned orientations are supported (i along one compass direction,
j along a perpendicular one).
"""
import numpy as np
import yaml

ORIENTATIONS = ("i:S,j:W", "i:S,j:E", "i:N,j:W", "i:N,j:E",
                "i:E,j:S", "i:E,j:N", "i:W,j:S", "i:W,j:N")


def north_up(arr, orientation):
    """
    The (ny, nx) map array [j, i] redrawn as a north-up image: rows run north
    to south, columns west to east.
    """
    i_dir, j_dir = (p.split(":")[1] for p in orientation.split(","))
    a = arr.T if i_dir in "NS" else arr          # rows along i when i runs N-S
    row_dir, col_dir = (i_dir, j_dir) if i_dir in "NS" else (j_dir, i_dir)
    if row_dir == "N":
        a = a[::-1, :]
    if col_dir == "W":
        a = a[:, ::-1]
    return a


def image_index(i, j, geo):
    """(row, col) in the north-up image of map cell (i, j)."""
    i_dir, j_dir = (p.split(":")[1] for p in geo["orientation"].split(","))
    i, j = np.asarray(i, dtype=float), np.asarray(j, dtype=float)
    ni, nj = geo["nx"], geo["ny"]
    if i_dir in "NS":
        row = i if i_dir == "S" else ni - 1 - i
        col = j if j_dir == "E" else nj - 1 - j
    else:
        row = j if j_dir == "S" else nj - 1 - j
        col = i if i_dir == "E" else ni - 1 - i
    return row, col


def cell_to_crs(i, j, geo):
    """(easting, northing) in geo['crs'] of the centre of map cell (i, j); i, j may be fractional."""
    row, col = image_index(i, j, geo)
    d = geo["cell_size"]
    return geo["e_topleft"] + (col + 0.5) * d, geo["n_topleft"] - (row + 0.5) * d


def cell_to_lonlat(i, j, geo):
    """(lon, lat) in degrees of the centre of map cell (i, j). Needs pyproj."""
    from pyproj import Transformer
    e, n = cell_to_crs(i, j, geo)
    return Transformer.from_crs(geo["crs"], "EPSG:4326", always_xy=True).transform(e, n)


def load_georef(path):
    with open(path, "r", encoding="utf-8") as f:
        geo = yaml.safe_load(f)
    if geo.get("orientation") not in ORIENTATIONS:
        raise ValueError(f"[ERROR] {path}: orientation must be one of {ORIENTATIONS}")
    return geo


def save_georef(path, geo):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(geo, f, sort_keys=False)


def image_transform(geo):
    """Affine transform (rasterio) of the north-up map image, for warping other rasters onto it."""
    from affine import Affine
    d = geo["cell_size"]
    return Affine(d, 0.0, geo["e_topleft"], 0.0, -d, geo["n_topleft"])


def image_shape(geo):
    """(rows, cols) of the north-up map image."""
    i_dir = geo["orientation"].split(",")[0].split(":")[1]
    return (geo["nx"], geo["ny"]) if i_dir in "NS" else (geo["ny"], geo["nx"])


def warp_to_map(path, geo, resampling="bilinear", src_crs=None, band=1, use_nodata=True):
    """
    A raster file resampled onto the north-up map image grid (float, NaN where
    it has no data). src_crs is for files without a CRS tag. use_nodata=False
    keeps the file's nodata value as data (e.g. 0 = no building). Needs rasterio.
    """
    import rasterio
    from rasterio.warp import Resampling, reproject
    out = np.full(image_shape(geo), np.nan, dtype=np.float32)
    with rasterio.open(path) as src:
        crs = src.crs or src_crs
        if crs is None:
            raise ValueError(f"[ERROR] {path} has no CRS; pass src_crs")
        data = src.read(band).astype(np.float32)
        nodata = src.nodata if use_nodata and src.nodata is not None else -3.0e38   # -3e38: never in the data
        reproject(source=data, destination=out, src_transform=src.transform, src_crs=crs, src_nodata=nodata,
                  dst_transform=image_transform(geo), dst_crs=geo["crs"], dst_nodata=np.nan,
                  resampling=getattr(Resampling, resampling))
    return out


AXIS_WORDS = {"N": "north", "S": "south", "E": "east", "W": "west"}


def box_location(box, geo):
    """
    Where a cell box [i0, i1, j0, j1] (end exclusive) lies: cell edges in map metres,
    corners in geo['crs'] and lon/lat, its centre, and which real direction map x and y
    point to. Plain floats and lists, ready for YAML. Needs pyproj for lon/lat.
    """
    from pyproj import Transformer
    i0, i1, j0, j1 = (int(v) for v in box)
    d = geo["cell_size"]
    # cell_to_crs gives the centre of (fractional) cell i, so the edge at i is cell i - 0.5
    corners = {"i0_j0": (i0, j0), "i1_j0": (i1, j0), "i0_j1": (i0, j1), "i1_j1": (i1, j1)}
    to_ll = Transformer.from_crs(geo["crs"], "EPSG:4326", always_xy=True)
    crs_c, ll_c = {}, {}
    for k, (i, j) in corners.items():
        e, n = cell_to_crs(i - 0.5, j - 0.5, geo)
        lon, lat = to_ll.transform(float(e), float(n))
        crs_c[k] = [round(float(e), 2), round(float(n), 2)]
        ll_c[k] = [round(lon, 6), round(lat, 6)]
    ec, nc = cell_to_crs((i0 + i1) / 2 - 0.5, (j0 + j1) / 2 - 0.5, geo)
    lonc, latc = to_ll.transform(float(ec), float(nc))
    i_dir, j_dir = (p.split(":")[1] for p in geo["orientation"].split(","))
    return {
        "box_cells": [i0, i1, j0, j1],
        "box_m": [i0 * d, i1 * d, j0 * d, j1 * d],
        "size_m": [(i1 - i0) * d, (j1 - j0) * d],
        "crs": geo["crs"],
        "corners_crs": crs_c,
        "corners_lonlat": ll_c,
        "centre_crs": [round(float(ec), 2), round(float(nc), 2)],
        "centre_lonlat": [round(lonc, 6), round(latc, 6)],
        "x_points": AXIS_WORDS[i_dir],
        "y_points": AXIS_WORDS[j_dir],
    }
