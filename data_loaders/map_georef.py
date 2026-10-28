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
