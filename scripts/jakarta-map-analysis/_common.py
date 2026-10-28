"""Shared command-line handling for the jakarta-map-analysis scripts (map input, output folder, land columns)."""
from pathlib import Path

from data_loaders.local_paths import case_map_dir, load_local_paths
from physics_core.urban_morphology import empty_edge_columns

DX = 2.0   # cell size [m]


def add_map_args(ap):
    ap.add_argument("folder", nargs="?", help="folder with topography.dat, building.dat, vegetation.dat")
    ap.add_argument("--case", help="LBM-city case name; reads <lbm_cases>/<case>/map")
    ap.add_argument("--land-columns", type=int, nargs=2, metavar=("I0", "I1"),
                    help="columns counted as land (end exclusive); default: drop the empty 0 m strips at both ends")
    ap.add_argument("--out", help="output folder (default <figures>/jakarta_map_analysis/<map name>)")


def resolve_map(ap, args):
    """(map folder, label)."""
    if bool(args.folder) == bool(args.case):
        ap.error("give either a map folder or --case, not both")
    if args.case:
        folder, label = case_map_dir(load_local_paths(), args.case), args.case
    else:
        folder = Path(args.folder)
        label = folder.resolve().name
        if label == "map":                      # e.g. F:/TSUBAME4_12m/map -> TSUBAME4_12m
            label = folder.resolve().parent.name
    if not folder.is_dir():
        raise FileNotFoundError(f"[ERROR] map folder {folder} not found")
    return folder, label


def out_dir(args, label):
    if args.out:
        d = Path(args.out)
    else:
        try:
            d = load_local_paths()["figures"] / "jakarta_map_analysis" / label
        except (FileNotFoundError, KeyError):
            d = Path.cwd() / "jakarta_map_analysis" / label
    d.mkdir(parents=True, exist_ok=True)
    return d


def land_columns(maps, args):
    """(i0, i1) of the land part, from --land-columns or the empty edge strips."""
    if args.land_columns:
        return tuple(args.land_columns)
    return empty_edge_columns(maps)
