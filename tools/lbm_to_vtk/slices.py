"""
Legacy CSV planes (Output/ of mikael/cases runs, read by data_loaders.lbm_output) -> one
flat image (.vti) per plane and output step, placed at its real position in metres, so xy,
xz and yz planes line up in 3D. One .pvd per plane gives the time series.

Each .vti holds every variable of that plane family found for the step, under the name
without the prefix (xy_um -> um). Values are what the solver wrote: window means of raw
moments in m/s units (uu = <u u>, not a variance). When um, vm and wm are all present a
3-component 'velocity_mean' is added, so Glyph and Streamline filters can use it.

Placement:
    xy_   plane at the label height z (one-based cell -> cell centre)
    xz_   plane at the label y;  yz_ plane at the label x
    xz_yav_ (averaged over y) at y = 0
    xy_ag_ (above ground) at the AGL height as a flat plane: exact only on flat terrain
"""
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyvista as pv

from data_loaders.lbm_output import load_plane, read_header_txt, scan_run

from .writer import save, write_pvd

FAMILIES = ("xz_yav_", "xy_ag_", "xy_", "xz_", "yz_")   # longest prefix first
DEFAULT_FAMILIES = ("xy_", "xz_", "yz_", "xz_yav_")
AXIS = {"x": 0, "y": 1, "z": 2}


def family_of(name):
    return next((f for f in FAMILIES if name.startswith(f)), None)


def plane_image(axes, coords, label_axis, position, fields, dx):
    """
    ImageData for one plane. axes: (rows axis, cols axis) of the 2D arrays; coords: centre
    positions per axis; label_axis/position: the third axis and where the plane sits on it.
    fields: {name: 2D array (rows, cols)}.
    """
    dims, origin = [1, 1, 1], [0.0, 0.0, 0.0]
    for ax in axes:
        dims[AXIS[ax]] = len(coords[ax])
        origin[AXIS[ax]] = float(coords[ax][0])
    origin[AXIS[label_axis]] = float(position)
    img = pv.ImageData(dimensions=dims, spacing=(dx, dx, dx), origin=origin)
    # VTK point order is x fastest, then y, then z: put the array axes in z, y, x order, then ravel.
    order = sorted(range(2), key=lambda k: AXIS[axes[k]], reverse=True)
    for name, arr in fields.items():
        img.point_data[name] = np.ascontiguousarray(np.transpose(arr, order)).ravel().astype(np.float32)
    if all(k in fields for k in ("um", "vm", "wm")):
        img.point_data["velocity_mean"] = np.column_stack(
            [img.point_data[k] for k in ("um", "vm", "wm")]).astype(np.float32)
    return img


def _third_axis(axes):
    return ({"x", "y", "z"} - set(axes)).pop()


def convert(run_dir, out_dir, families=DEFAULT_FAMILIES, variables=None, steps=None):
    """
    Write out_dir/<family>_<axis><cell>/<...>_<step>.vti and one .pvd per plane.
    variables: names without prefix (e.g. ['um', 'vm', 'wm']); None = all found.
    Returns {pvd path: number of steps}.
    """
    out_dir = Path(out_dir)
    header = read_header_txt(run_dir)
    dx = float(header["dx"])
    files = scan_run(run_dir)
    if files.empty:
        raise FileNotFoundError(f"[ERROR] no <name><step>_<rank>.csv files in {run_dir}")
    files["family"] = files["name"].map(family_of)
    files = files[files["family"].isin(families)]
    if variables:
        files = files[files.apply(lambda r: r["name"][len(r["family"]):] in variables, axis=1)]
    if steps:
        files = files[files["step"].isin(steps)]
    if files.empty:
        raise FileNotFoundError(f"[ERROR] nothing matches families={families}, variables={variables}, steps={steps}")

    series = defaultdict(list)   # pvd path -> [(time, vti path)]
    for (family, step), group in files.groupby(["family", "step"]):
        planes = {name[len(family):]: load_plane(run_dir, name, step, header)
                  for name in sorted(group["name"].unique())}
        first = next(iter(planes.values()))
        third = _third_axis(first.axes)
        for label in first.data:
            pos = first.labels_m.get(label, 0.0)      # xz_yav: no label, plane at y = 0
            tag = f"{family}{third}{label:04d}" if first.label_axis else family.rstrip("_")
            img = plane_image(first.axes, first.coords, third, pos,
                              {v: p.data[label] for v, p in planes.items() if label in p.data}, dx)
            path = save(img, out_dir / tag / f"{tag}_{step:08d}.vti")
            series[out_dir / f"{tag}.pvd"].append((first.time, path))
        print(f"{family} step {step}: {len(first.data)} plane(s), variables {', '.join(planes)}")
    for pvd, entries in series.items():
        write_pvd(entries, pvd)
    return {pvd: len(e) for pvd, e in series.items()}
