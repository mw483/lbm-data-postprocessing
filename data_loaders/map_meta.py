"""
Optional map.yaml next to a map set's .dat files: the map's name and where its
extra layers live, so viewers and scripts find them without flags.

    # F:/TSUBAME4_12m/map/map.yaml
    name: TSUBAME4_12m
    georef: C:/Users/Mikael Wijaya/Documents/GitHub/lbm-data-postprocessing/outputs/jakarta_map_analysis/TSUBAME4_12m/georef.yaml
    roads: C:/Users/Mikael Wijaya/Documents/GitHub/lbm-data-postprocessing/outputs/jakarta_map_analysis/TSUBAME4_12m/roads/road_class.npy
    candidates: C:/Users/Mikael Wijaya/Documents/GitHub/lbm-data-postprocessing/scripts/jakarta-map-analysis/candidates.yaml

Every key is optional. Paths are absolute or relative to the folder holding
map.yaml. A map without map.yaml (flat, cube maps) behaves as before. This is
the first piece of the map library proposal (planning/map_library_proposal_2026-11-12.md).
"""
from pathlib import Path

import numpy as np
import yaml

META_FILE = "map.yaml"
PATH_KEYS = ("georef", "roads", "candidates")


def load_map_meta(map_dir):
    """{name, georef, roads, candidates} from <map_dir>/map.yaml; path keys as Path; {} without the file."""
    path = Path(map_dir) / META_FILE
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}
    for key in PATH_KEYS:
        if meta.get(key):
            p = Path(str(meta[key])).expanduser()
            meta[key] = p if p.is_absolute() else path.parent / p
    return meta


def map_label(map_dir, meta=None):
    """Name of a map: map.yaml 'name', else the folder name, or its parent's when the folder is called 'map'."""
    if meta and meta.get("name"):
        return str(meta["name"])
    d = Path(map_dir).resolve()
    return d.parent.name if d.name == "map" else d.name


def load_road_raster(path):
    """(ny, nx) uint8 road class codes [j, i] from road_class.npy or road.dat (rasterize_roads.py)."""
    path = Path(path)
    if path.suffix == ".npy":
        return np.load(path).astype(np.uint8)
    from data_loaders.map_io import read_map_dat
    arr, _, _ = read_map_dat(path)
    return arr.astype(np.uint8)
