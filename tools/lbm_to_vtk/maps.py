"""
LBM-city map set (topography.dat, building.dat, vegetation.dat) -> surfaces for context:
ground.vtp, buildings.vtp, trees.vtp (empty layers are skipped). Built with
plotting_core.map_3d, the same meshes as scripts/view_map_3d.py: only visible faces, so
memory follows the map area. Coordinates are global metres from the map origin (cell
(0, 0) starts at x = y = 0), also after cropping. Point field 'height_m' (buildings, trees)
and 'ground_m' (ground).
"""
from pathlib import Path

from data_loaders.map_io import load_map_set
from plotting_core.map_3d import auto_stride, crop_and_coarsen, map_set_meshes

from .writer import save


def convert(map_dir, out_dir, dx=2.0, crop=None, stride=None):
    """
    crop: (i0, i1, j0, j1) in cells; stride: N x N coarsening (None = auto, keeps the scene
    near plotting_core.map_3d.TARGET_COLUMNS columns). Returns the written paths.
    """
    maps = load_map_set(map_dir)
    if crop:
        maps, origin_cells = crop_and_coarsen(maps, crop, 1)
    else:
        origin_cells = (0, 0)
    stride = stride or auto_stride(maps["topo"].shape)
    maps, _ = crop_and_coarsen(maps, None, stride)
    origin = (origin_cells[0] * dx, origin_cells[1] * dx)
    meshes = map_set_meshes(maps, dx * stride, origin)
    written = []
    for name, mesh in meshes.items():
        if mesh is not None:
            written.append(save(mesh, Path(out_dir) / f"{name}.vtp"))
            print(f"{name}: {mesh.n_cells} faces -> {written[-1].name}")
    print(f"stride {stride} (cell size {dx * stride:g} m), origin {origin} m")
    return written
