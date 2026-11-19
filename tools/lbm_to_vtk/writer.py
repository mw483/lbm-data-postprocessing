"""
The one place that writes files: VTK XML datasets (binary, zlib-compressed) and the
.pvd index that turns a list of them into a time series.
"""
from pathlib import Path
from xml.sax.saxutils import quoteattr


def save(mesh, path):
    """Write a pyvista dataset as binary VTK XML; the extension (.vti, .vtp) picks the type."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.save(path, binary=True)
    return path


def write_pvd(entries, path):
    """
    entries: list of (time, file path). Writes a ParaView collection with paths relative to
    the .pvd, so the folder can be copied elsewhere (e.g. to mdx) as a whole.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['<?xml version="1.0"?>',
             '<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">',
             "  <Collection>"]
    for time, file in sorted(entries, key=lambda e: e[0]):
        rel = Path(file).resolve().relative_to(path.parent.resolve()).as_posix()
        lines.append(f'    <DataSet timestep="{float(time):.9g}" part="0" file={quoteattr(rel)}/>')
    lines += ["  </Collection>", "</VTKFile>", ""]
    path.write_text("\n".join(lines))
    return path
