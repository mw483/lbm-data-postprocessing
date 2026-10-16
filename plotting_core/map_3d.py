"""
3D scene pieces for LBM-city map sets (topography, buildings, trees).

Only visible faces are built: one top quad per column cell and a wall quad
wherever a column is higher than its neighbour. Memory therefore scales with
the map area, not with area x height as a voxel volume would.
Coordinates are global metres from the map origin, also after cropping, so a
point read off the scene can go straight into particle_position.txt.
"""
import numpy as np
import pyvista as pv

TARGET_COLUMNS = 1_500_000   # auto stride keeps a scene around this many columns


def auto_stride(shape, target=TARGET_COLUMNS):
    """Smallest N for which N x N coarsening brings `shape` cells to at most `target` columns."""
    return max(1, int(np.ceil(np.sqrt(shape[0] * shape[1] / target))))


def crop_and_coarsen(maps, crop=None, stride=1):
    """
    Crops a map set to cells [j0:j1, i0:i1] and coarsens it by stride x stride
    blocks: mean for the ground, max for buildings and trees (tall buildings
    stay visible, but footprints grow). The crop end is trimmed to a multiple
    of stride. Returns (maps, (i0, j0)).
    """
    ny, nx = maps["topo"].shape
    i0, i1, j0, j1 = crop if crop else (0, nx, 0, ny)
    if not (0 <= i0 < i1 and 0 <= j0 < j1):
        raise ValueError(f"[ERROR] bad crop {crop} for a {nx} x {ny} map")
    i1 = i0 + (min(i1, nx) - i0) // stride * stride
    j1 = j0 + (min(j1, ny) - j0) // stride * stride
    if i1 <= i0 or j1 <= j0:
        raise ValueError(f"[ERROR] crop {crop} is smaller than one {stride} x {stride} block")
    out = {}
    for key, arr in maps.items():
        a = arr[j0:j1, i0:i1]
        if stride > 1:
            b = a.reshape(a.shape[0] // stride, stride, a.shape[1] // stride, stride)
            a = b.mean(axis=(1, 3)) if key == "topo" else b.max(axis=(1, 3))
        out[key] = np.asarray(a, dtype=np.float32)
    return out, (i0, j0)


def classify_cells(maps):
    """Masks (is_building, is_tree) from absolute heights; a tree cell is never a building cell."""
    is_build = maps["build"] > maps["topo"]
    is_veg = (maps["veg"] > maps["topo"]) & ~is_build
    return is_build, is_veg


def ground_surface(topo, dx, origin=(0.0, 0.0)):
    """Smooth surface through the cell centres with point data 'ground_m'."""
    ny, nx = topo.shape
    x = origin[0] + (np.arange(nx) + 0.5) * dx
    y = origin[1] + (np.arange(ny) + 0.5) * dx
    X, Y = np.meshgrid(x, y)
    grid = pv.StructuredGrid(X, Y, topo)
    grid["ground_m"] = np.asarray(topo).ravel(order="F")
    return grid.extract_surface(algorithm="dataset_surface")


def blocky_columns(top, base, mask, dx, origin=(0.0, 0.0)):
    """
    PolyData of columns up to `top` on the cells where `mask` is set.
    `base` is the height a neighbour outside the mask stands at (the ground).
    Each column cell gets a top quad, plus a wall on every side where the
    neighbouring surface (its column top, or `base`) is lower; walls on the
    scene edge go down to the cell's own `base`. Point data 'height_m'.
    Returns None when the mask is empty.
    """
    top = np.asarray(top, dtype=np.float32)
    base = np.asarray(base, dtype=np.float32)
    ny, nx = top.shape
    jj, ii = np.nonzero(mask)
    if jj.size == 0:
        return None

    x0 = origin[0] + ii * dx
    y0 = origin[1] + jj * dx
    z = top[jj, ii]
    quads = [_quads((x0, y0, z), (x0 + dx, y0, z), (x0 + dx, y0 + dx, z), (x0, y0 + dx, z))]

    surf = np.where(mask, top, base)
    pad = np.pad(surf, 1, mode="constant", constant_values=np.nan)
    for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nb = pad[1 + dj:1 + dj + ny, 1 + di:1 + di + nx]
        nb_z = np.where(np.isnan(nb), base, nb)
        jj, ii = np.nonzero(mask & (top > nb_z))
        if jj.size == 0:
            continue
        zt, zb = top[jj, ii], nb_z[jj, ii]
        x0, y0 = origin[0] + ii * dx, origin[1] + jj * dx
        if di != 0:      # face at x = const
            xf = x0 + (dx if di == 1 else 0.0)
            quads.append(_quads((xf, y0, zb), (xf, y0 + dx, zb), (xf, y0 + dx, zt), (xf, y0, zt)))
        else:            # face at y = const
            yf = y0 + (dx if dj == 1 else 0.0)
            quads.append(_quads((x0, yf, zb), (x0 + dx, yf, zb), (x0 + dx, yf, zt), (x0, yf, zt)))

    pts = np.concatenate(quads).reshape(-1, 3)
    n = pts.shape[0] // 4
    faces = np.column_stack([np.full(n, 4), np.arange(4 * n).reshape(n, 4)]).ravel()
    mesh = pv.PolyData(pts, faces)
    mesh["height_m"] = pts[:, 2]
    return mesh


def _quads(*corners):
    """(n, 4, 3) float32 array from four (x, y, z) corners, each part an array or a scalar."""
    return np.stack([np.stack(np.broadcast_arrays(*c), -1) for c in corners], 1).astype(np.float32)


def map_set_meshes(maps, dx, origin=(0.0, 0.0), zscale=1.0):
    """
    Ground surface, building columns and tree columns of a (cropped, coarsened)
    map set. Returns {"ground", "buildings", "trees"}; empty layers are None.
    """
    topo, build, veg = (maps[k] * zscale for k in ("topo", "build", "veg"))
    is_build, is_veg = classify_cells(maps)
    return {
        "ground": ground_surface(topo, dx, origin),
        "buildings": blocky_columns(build, topo, is_build, dx, origin),
        "trees": blocky_columns(veg, np.where(is_build, build, topo), is_veg, dx, origin),
    }


def sources_in_box(xyz, bounds, max_points=200_000, seed=0):
    """
    Keeps the sources with xmin <= x <= xmax and ymin <= y <= ymax, then a
    random subsample of at most max_points (fixed seed). Returns PolyData or None.
    """
    xmin, xmax, ymin, ymax = bounds
    keep = (xyz[:, 0] >= xmin) & (xyz[:, 0] <= xmax) & (xyz[:, 1] >= ymin) & (xyz[:, 1] <= ymax)
    xyz = xyz[keep]
    if len(xyz) > max_points:
        xyz = xyz[np.random.default_rng(seed).choice(len(xyz), max_points, replace=False)]
    return pv.PolyData(np.ascontiguousarray(xyz)) if len(xyz) else None
