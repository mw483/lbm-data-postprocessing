"""
3D view of an LBM-city map set: ground coloured by height, buildings as grey
columns (one per cell, as the solver sees them), trees as green columns, and
optionally the sources of a particle_position.txt as red points and the
road cells (rasterize_roads.py) as flat tiles coloured by road class.

The map set is either an LBM-city case (--case NAME reads
<lbm_cases>/NAME/map/ from local_paths.yaml) or any folder holding
topography.dat, building.dat and vegetation.dat (e.g. a map that is not a case yet).
Coordinates stay global (metres from the map origin) when cropping.

    python scripts/view_map_3d.py --case flat_512x128x1024                       # whole map, auto coarsened
    python scripts/view_map_3d.py --case flat_512x128x1024 --sources              # + the case's particle_position.txt
    python scripts/view_map_3d.py FOLDER --crop 4300 4900 1000 1500 --stride 1    # any map folder, cells i0 i1 j0 j1
    python scripts/view_map_3d.py FOLDER --sources path/to/particle_position.txt
    python scripts/view_map_3d.py --case NAME --save view.png                     # PNG, no window
    python scripts/view_map_3d.py FOLDER --box A --candidates candidates.yaml     # crop = candidate box A
                                                                                  #   (from explore_tiles.py)
    python scripts/view_map_3d.py F:/TSUBAME4_12m/map --box J1                    # with map.yaml: roads, name,
                                                                                  #   candidates, georef found
    python scripts/view_map_3d.py FOLDER --roads road_class.npy --georef georef.yaml   # same, by flags

map.yaml (optional, next to the .dat files; data_loaders/map_meta.py) names the
map and points to its georef, road raster and candidates. Flags override it;
--no-roads hides the roads. Maps without map.yaml look as before.

Saved images (key 's' or --save) are named <map>_<box>_NN.png (or
<map>_crop_i0-i1_j0-j1, or <map> for the whole map) and carry that name as a
title. With a georef, the image also shows the box's cells, metres, centre and
corners in lon/lat and which real direction x and y point to, and a
<image>.yaml next to it holds the same numbers in full (box_location in
data_loaders/map_georef.py). --save without a file name uses <figures>/map_3d/<name>.png.

Keys in the window: 'p' over a point prints x, y, cell i, j and the ground,
building and tree heights at that cell; 's' saves a numbered screenshot to
<figures>/map_3d/ (or the current folder without local_paths.yaml), plus the .yaml when georeferenced.
Coarsened views (stride > 1) widen buildings and trees; pick sources on a
--stride 1 crop.
"""
import argparse
from pathlib import Path

import numpy as np
import pyvista as pv

from data_loaders.local_paths import case_map_dir, case_sources_file, load_local_paths
from data_loaders.map_io import load_map_set, load_source_xyz
from data_loaders.map_meta import load_map_meta, load_road_raster, map_label
from plotting_core.map_3d import (auto_stride, classify_cells, crop_and_coarsen, crop_and_coarsen_codes,
                                  map_set_meshes, road_layers, sources_in_box)
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
# road class colours, as in scripts/jakarta-map-analysis/rasterize_roads.py
ROAD_COLORS = {"motorway": "#d62728", "arterial": "#ff7f0e", "collector": "#2ca02c",
               "local": "#1f77b4", "elevated": "#9467bd"}
ROAD_LIFT = 0.2             # m above the ground, so the tiles are not hidden in it
# with roads shown the ground gets a pale two-tone ramp, so it does not clash with the road colours
GROUND_CMAP_WITH_ROADS = ("#f5f2ea", "#a89f8c")


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
        label = None
    if not map_dir.is_dir():
        raise FileNotFoundError(f"[ERROR] map folder {map_dir} not found")
    return map_dir, label, sources


def view_name(label, box_name, crop, full_shape):
    """<map>_<box>, <map>_crop_i0-i1_j0-j1, or <map> for the whole map."""
    ny, nx = full_shape
    if box_name:
        return f"{label}_{box_name}"
    if crop and tuple(crop) != (0, nx, 0, ny):
        i0, i1, j0, j1 = crop
        return f"{label}_crop_{i0}-{i1}_{j0}-{j1}"
    return label


def location_text(loc):
    """Lines for the image: box in cells and metres, centre and corners in lon/lat, axis directions."""
    i0, i1, j0, j1 = loc["box_cells"]
    x0, x1, y0, y1 = loc["box_m"]
    c = loc["corners_lonlat"]
    fmt = lambda p: f"{p[1]:.5f}, {p[0]:.5f}"          # lat, lon
    return "\n".join([
        f"cells i {i0}-{i1}, j {j0}-{j1}   x {x0:g}-{x1:g} m, y {y0:g}-{y1:g} m ({loc['size_m'][0]:g} x {loc['size_m'][1]:g} m)",
        f"centre lat, lon {fmt(loc['centre_lonlat'])}",
        f"corner (i0, j0) {fmt(c['i0_j0'])}   (i1, j1) {fmt(c['i1_j1'])}",
        f"x points real {loc['x_points']}, y points real {loc['y_points']}",
    ])


def write_location(png_path, name, loc):
    """<png without extension>.yaml with the view name and box_location numbers."""
    import yaml
    path = Path(png_path).with_suffix(".yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"view": name, **loc}, f, sort_keys=False)
    print(f"Saved {path}")


def candidate_box(path, name):
    """[i0, i1, j0, j1] of the candidate called `name` in a candidates YAML."""
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        cands = (yaml.safe_load(f) or {}).get("candidates", [])
    for c in cands:
        if str(c["name"]) == name:
            return [int(v) for v in c["box"]]
    raise SystemExit(f"[ERROR] no candidate {name!r} in {path} (have: {', '.join(str(c['name']) for c in cands)})")


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
    ap.add_argument("--box", help="name of a candidate box in --candidates (instead of --crop)")
    ap.add_argument("--candidates", help="candidates YAML from scripts/jakarta-map-analysis/explore_tiles.py")
    ap.add_argument("--stride", type=int, default=0, help="coarsen by N x N cells (default: auto)")
    ap.add_argument("--zscale", type=float, default=1.0, help="vertical exaggeration")
    ap.add_argument("--sources", nargs="?", const=True,
                    help="particle_position.txt to overlay (x y z in m); no value = the case's own file")
    ap.add_argument("--max-sources", type=int, default=200_000)
    ap.add_argument("--no-trees", action="store_true")
    ap.add_argument("--tree-opacity", type=float, default=0.8)
    ap.add_argument("--roads", help="road_class.npy or road.dat (rasterize_roads.py); default from map.yaml")
    ap.add_argument("--no-roads", action="store_true", help="hide the roads even if map.yaml names them")
    ap.add_argument("--georef", help="georef.yaml, for the cut-out coordinates; default from map.yaml")
    ap.add_argument("--save", nargs="?", const=True,
                    help="write this PNG instead of opening a window; no value = <figures>/map_3d/<name>.png")
    args = ap.parse_args()

    if bool(args.folder) == bool(args.case):
        ap.error("give either a map folder or --case, not both")
    folder, label, sources = resolve_inputs(args.folder, args.case, args.sources)
    meta = load_map_meta(folder)
    label = label or map_label(folder, meta)
    if meta:
        print(f"map.yaml: {', '.join(f'{k}={v}' for k, v in meta.items())}")
    candidates = args.candidates or meta.get("candidates")
    if args.box:
        if args.crop or not candidates:
            ap.error("--box needs --candidates (or candidates in map.yaml) and replaces --crop")
        args.crop = candidate_box(candidates, args.box)
    roads_path = None if args.no_roads else (args.roads or meta.get("roads"))
    georef_path = args.georef or meta.get("georef")
    full = load_map_set(folder)
    describe(full, f"Map {label}")

    ny, nx = full["topo"].shape
    i0, i1, j0, j1 = args.crop or (0, nx, 0, ny)
    stride = args.stride or auto_stride((j1 - j0, i1 - i0))
    maps, (ci, cj) = crop_and_coarsen(full, args.crop, stride)
    name = view_name(label, args.box, args.crop, (ny, nx))
    describe(maps, f"Scene at {DX * stride:g} m (stride {stride})")
    origin = (ci * DX, cj * DX)
    meshes = map_set_meshes(maps, DX * stride, origin, args.zscale)

    pv.global_theme.allow_empty_mesh = True
    plotter = pv.Plotter(off_screen=bool(args.save), window_size=WINDOW_SIZE)
    zmax = max(1.0, float(maps["topo"].max()) * args.zscale)
    if roads_path:
        from matplotlib.colors import LinearSegmentedColormap
        ground_cmap = LinearSegmentedColormap.from_list("ground_pale", GROUND_CMAP_WITH_ROADS)
    else:
        ground_cmap = GROUND_CMAP
    plotter.add_mesh(meshes["ground"], scalars="ground_m", cmap=ground_cmap, clim=(0, zmax),
                     scalar_bar_args={"title": "Ground [m]" + (f" x{args.zscale:g}" if args.zscale != 1 else "")})
    if meshes["buildings"] is not None:
        plotter.add_mesh(meshes["buildings"], color=BUILDING_COLOR, label="Buildings")
    if meshes["trees"] is not None and not args.no_trees:
        plotter.add_mesh(meshes["trees"], color=TREE_COLOR, opacity=args.tree_opacity, label="Trees")
    if roads_path:
        codes = load_road_raster(roads_path)
        if codes.shape != (ny, nx):
            raise SystemExit(f"[ERROR] roads {roads_path} are {codes.shape}, map is {(ny, nx)}")
        layers = road_layers(crop_and_coarsen_codes(codes, args.crop, stride), maps["topo"],
                             DX * stride, origin, args.zscale, lift=ROAD_LIFT)
        print(f"Roads from {roads_path}: {', '.join(f'{k} {m.n_cells:,} cells' for k, m in layers.items()) or 'none in view'}")
        for road_class, mesh in layers.items():
            plotter.add_mesh(mesh, color=ROAD_COLORS[road_class], label=f"Road: {road_class}")
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
    plotter.add_text(name, position="upper_left", font_size=12)
    loc = None
    if georef_path:
        from data_loaders.map_georef import box_location, load_georef
        loc = box_location((i0, i1, j0, j1), load_georef(georef_path))
        plotter.add_text(location_text(loc), position="lower_left", font_size=9)
        print(location_text(loc))
    if roads_path:
        plotter.add_legend(bcolor=None, size=(0.15, 0.15), loc="upper right")

    if args.save:
        out = figures_dir() / f"{name}.png" if args.save is True else Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(str(out))
        print(f"Saved {out}")
        if loc:
            write_location(out, name, loc)
        return
    plotter.enable_point_picking(callback=pick_printer(full, DX), show_message="Press P to pick a point",
                                 show_point=True, use_picker=True)
    add_snapshot_key(plotter, str(figures_dir() / f"{name}.png"),
                     on_save=(lambda p: write_location(p, name, loc)) if loc else None)
    plotter.show()


if __name__ == "__main__":
    main()
