"""
3D view of an LBM-city map set: ground coloured by height, buildings as grey
columns (one per cell, as the solver sees them), trees as green columns, and
optionally the sources of a particle_position.txt as red points.

The map set is either an LBM-city case (--case NAME reads
<lbm_cases>/NAME/map/ from local_paths.yaml) or any folder holding
topography.dat, building.dat and vegetation.dat (e.g. a map that is not a case yet).
Coordinates stay global (metres from the map origin) when cropping.

    python scripts/view_map_3d.py --case flat_512x128x1024                       # whole map, auto coarsened
    python scripts/view_map_3d.py --case flat_512x128x1024 --sources              # + the case's particle_position.txt
    python scripts/view_map_3d.py FOLDER --crop 4300 4900 1000 1500 --stride 1    # any map folder, cells i0 i1 j0 j1
    python scripts/view_map_3d.py FOLDER --sources path/to/particle_position.txt
    python scripts/view_map_3d.py --case NAME --save view.png                     # PNG, no window

Keys in the window: 'p' over a point prints x, y, cell i, j and the ground,
building and tree heights at that cell; 's' saves a numbered screenshot to
<figures>/map_3d/ (or the current folder without local_paths.yaml).
Coarsened views (stride > 1) widen buildings and trees; pick sources on a
--stride 1 crop.
"""
import argparse
from pathlib import Path

import numpy as np
import pyvista as pv

from data_loaders.local_paths import case_map_dir, case_sources_file, load_local_paths
from data_loaders.map_io import load_map_set, load_source_xyz
from plotting_core.map_3d import (auto_stride, classify_cells, crop_and_coarsen,
                                  map_set_meshes, sources_in_box)
from plotting_core.pyvista_helpers import add_snapshot_key, show_iso_grid

# =============================================================================
# Settings
# =============================================================================
DX = 2.0                    # cell size [m]
GROUND_CMAP = "terrain"
BUILDING_COLOR = "lightgray"
TREE_COLOR = "forestgreen"
SOURCE_COLOR = "red"
WINDOW_SIZE = (1600, 1000)


def resolve_inputs(folder, case, sources):
    """(map folder, label, sources file or None) from the command line."""
    if case:
        paths = load_local_paths()
        map_dir = case_map_dir(paths, case)
        if sources is True:
            sources = case_sources_file(paths, case)
        label = case
    else:
        map_dir = Path(folder)
        if sources is True:
            raise SystemExit("[ERROR] --sources without a file needs --case")
        label = map_dir.resolve().name
    if not map_dir.is_dir():
        raise FileNotFoundError(f"[ERROR] map folder {map_dir} not found")
    return map_dir, label, sources


def figures_dir():
    try:
        return load_local_paths()["figures"] / "map_3d"
    except (FileNotFoundError, KeyError):
        return Path.cwd()


def describe(maps, label):
    is_build, is_veg = classify_cells(maps)
    ny, nx = maps["topo"].shape
    print(f"{label}: {nx} x {ny} columns; buildings on {is_build.mean():.1%}, trees on {is_veg.mean():.1%}; "
          f"ground {maps['topo'].min():.0f}-{maps['topo'].max():.0f} m, "
          f"tallest building {np.max(maps['build'] - maps['topo']):.0f} m above ground "
          f"(top at {maps['build'].max():.0f} m)")


def pick_printer(full_maps, dx):
    ny, nx = full_maps["topo"].shape

    def on_pick(point):
        x, y = point[0], point[1]
        i, j = int(x // dx), int(y // dx)
        if not (0 <= i < nx and 0 <= j < ny):
            return
        g = full_maps["topo"][j, i]
        print(f"x={x:.1f} m  y={y:.1f} m  cell i={i} j={j}  ground={g:.1f} m  "
              f"building={full_maps['build'][j, i] - g:.1f} m  tree={full_maps['veg'][j, i] - g:.1f} m (above ground)")
    return on_pick


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", help="folder with topography.dat, building.dat, vegetation.dat")
    ap.add_argument("--case", help="LBM-city case name; reads <lbm_cases>/<case>/map")
    ap.add_argument("--crop", type=int, nargs=4, metavar=("I0", "I1", "J0", "J1"),
                    help="cell window, end exclusive")
    ap.add_argument("--stride", type=int, default=0, help="coarsen by N x N cells (default: auto)")
    ap.add_argument("--zscale", type=float, default=1.0, help="vertical exaggeration")
    ap.add_argument("--sources", nargs="?", const=True,
                    help="particle_position.txt to overlay (x y z in m); no value = the case's own file")
    ap.add_argument("--max-sources", type=int, default=200_000)
    ap.add_argument("--no-trees", action="store_true")
    ap.add_argument("--tree-opacity", type=float, default=0.8)
    ap.add_argument("--save", help="write this PNG instead of opening a window")
    args = ap.parse_args()

    if bool(args.folder) == bool(args.case):
        ap.error("give either a map folder or --case, not both")
    folder, label, sources = resolve_inputs(args.folder, args.case, args.sources)
    full = load_map_set(folder)
    describe(full, f"Map {label}")

    ny, nx = full["topo"].shape
    i0, i1, j0, j1 = args.crop or (0, nx, 0, ny)
    stride = args.stride or auto_stride((j1 - j0, i1 - i0))
    maps, (ci, cj) = crop_and_coarsen(full, args.crop, stride)
    describe(maps, f"Scene at {DX * stride:g} m (stride {stride})")
    origin = (ci * DX, cj * DX)
    meshes = map_set_meshes(maps, DX * stride, origin, args.zscale)

    pv.global_theme.allow_empty_mesh = True
    plotter = pv.Plotter(off_screen=bool(args.save), window_size=WINDOW_SIZE)
    zmax = max(1.0, float(maps["topo"].max()) * args.zscale)
    plotter.add_mesh(meshes["ground"], scalars="ground_m", cmap=GROUND_CMAP, clim=(0, zmax),
                     scalar_bar_args={"title": "Ground [m]" + (f" x{args.zscale:g}" if args.zscale != 1 else "")})
    if meshes["buildings"] is not None:
        plotter.add_mesh(meshes["buildings"], color=BUILDING_COLOR, label="Buildings")
    if meshes["trees"] is not None and not args.no_trees:
        plotter.add_mesh(meshes["trees"], color=TREE_COLOR, opacity=args.tree_opacity, label="Trees")
    if sources:
        print(f"Reading sources from {sources} ...")
        xyz = load_source_xyz(sources)
        print(f"Sources in file: {len(xyz):,}; x {xyz[:, 0].min():.1f}-{xyz[:, 0].max():.1f} m, "
              f"y {xyz[:, 1].min():.1f}-{xyz[:, 1].max():.1f} m, z {xyz[:, 2].min():.1f}-{xyz[:, 2].max():.1f} m")
        ny_s, nx_s = maps["topo"].shape
        bounds = (origin[0], origin[0] + nx_s * DX * stride, origin[1], origin[1] + ny_s * DX * stride)
        cloud = sources_in_box(xyz, bounds, args.max_sources)
        print(f"Sources shown: {0 if cloud is None else cloud.n_points:,}")
        if cloud is not None:
            cloud.points[:, 2] *= args.zscale
            plotter.add_mesh(cloud, color=SOURCE_COLOR, point_size=4, render_points_as_spheres=True,
                             label="Sources")
    show_iso_grid(plotter)

    if args.save:
        plotter.screenshot(args.save)
        print(f"Saved {args.save}")
        return
    plotter.enable_point_picking(callback=pick_printer(full, DX), show_message="Press P to pick a point",
                                 show_point=True, use_picker=True)
    add_snapshot_key(plotter, str(figures_dir() / f"{label}.png"))
    plotter.show()


if __name__ == "__main__":
    main()
