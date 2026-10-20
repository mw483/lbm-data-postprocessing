"""
Readers for LBM-city map files and source lists.

Map .dat convention (LBM-city read_map): line 1 "nx ny", then ny rows of nx
values; row index = y (first row is j = 0), column index = x, heights in m.
A map set is the three files one case needs: topography.dat, building.dat and
vegetation.dat. In a map set, building.dat and vegetation.dat hold ABSOLUTE
heights (ground + object); the flat and cube maps have no ground, so there
the building height is the object height.
"""
import os

import numpy as np
import pandas as pd

MAP_SET_FILES = {"topo": "topography.dat", "build": "building.dat", "veg": "vegetation.dat"}


def read_map_dat(filepath):
    """
    Reads one map .dat file. Returns (heights, nx, ny) with heights a float32
    array of shape (ny, nx), indexed [j, i].
    Uses the fast whitespace reader, and falls back to fixed-width parsing
    when Fortran-formatted values touch (e.g. " 12.0386.0" from f5.1).
    """
    with open(filepath, "r") as f:
        nx, ny = (int(v) for v in f.readline().split()[:2])
    try:
        data = pd.read_csv(filepath, sep=r"\s+", header=None, skiprows=1,
                           dtype=np.float32, engine="c").to_numpy()
    except (ValueError, pd.errors.ParserError):
        data = None
    if data is None or data.shape != (ny, nx) or np.isnan(data).any():
        data = _read_fixed_width(filepath, nx, ny)
    return data, nx, ny


def _read_fixed_width(filepath, nx, ny):
    """Slow path: every row is nx fields of equal width."""
    print(f"[INFO] {os.path.basename(str(filepath))}: values touch, reading as fixed width")
    out = np.empty((ny, nx), dtype=np.float32)
    with open(filepath, "r") as f:
        f.readline()
        for j in range(ny):
            line = f.readline().rstrip("\r\n")
            w = len(line) // nx
            if w == 0 or len(line) != w * nx:
                raise ValueError(f"{filepath}: row {j + 1} is {len(line)} characters, "
                                 f"not {nx} fields of equal width")
            out[j] = [float(line[k * w:(k + 1) * w]) for k in range(nx)]
    return out


def load_lbm_map(filepath):
    """
    Loads one LBM .dat map file. Returns (elevation_matrix, nx, ny), with the
    matrix of shape (ny, nx): rows = y, columns = x.
    """
    return read_map_dat(filepath)


def load_map_set(folder):
    """
    Loads topography.dat, building.dat and vegetation.dat from one folder.
    Returns {"topo", "build", "veg": (ny, nx) float32 arrays}. Raises if a file
    is missing or the sizes differ.
    """
    maps = {}
    for key, name in MAP_SET_FILES.items():
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"[ERROR] {path} not found (a map set needs {', '.join(MAP_SET_FILES.values())})")
        print(f"Reading {path} ...")
        maps[key], _, _ = read_map_dat(path)
    shapes = {key: arr.shape for key, arr in maps.items()}
    if len(set(shapes.values())) != 1:
        raise ValueError(f"[ERROR] map sizes differ in {folder}: {shapes}")
    return maps


def load_source_xyz(filepath):
    """x, y, z columns of a particle_position.txt (x y z u v w group id) as an (n, 3) float32 array."""
    return pd.read_csv(filepath, sep=r"\s+", header=None, usecols=[0, 1, 2],
                       dtype=np.float32, engine="c").to_numpy()


def create_voxel_buildings(elevation_matrix, nx, ny, resolution=2.0):
    """
    Building mesh for PyVista from a map of object heights (flat and cube maps:
    no ground). X/Y are in cells (scaled by `resolution`), heights in metres.
    Returns None when the map has no buildings.
    Kept for the existing scenes; now builds only the visible faces
    (plotting_core.map_3d.blocky_columns) instead of a dense voxel volume.
    """
    from plotting_core.map_3d import blocky_columns

    elev = np.asarray(elevation_matrix, dtype=np.float32).reshape(ny, nx)
    return blocky_columns(elev, np.zeros_like(elev), elev > 0, resolution)
