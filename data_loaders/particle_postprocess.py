"""
Reader for the C++ particle post-processing outputs (LBM-city Particle_PostProcessing_CPP, "basic" pass).

One run's particle_postprocess folder holds one subfolder per window, named "<start>-<end>_basic"
(outputs <start> to <end>, both included), each with
  log_analysis.txt                 console log: settings, one "Current processing :: <output>" line per snapshot
  total_num.csv                    2 rows: output index 0..end, particles in the domain at that output
  profile.csv                      per rank block: "Rank X:: i : Rank Y:: j", particles per z cell, fluid cells per z cell
  xy_number_density_<z>m.csv       ny rows x nx values      (slab z +- H_AVE/2)
  xz_number_density_<y>m.csv       nz rows x nx values      (slab y +- H_AVE/2)
  yz_number_density_<x>m.csv       nz rows x ny values      (slab x +- H_AVE/2)

Density files are raw integer counts summed over every snapshot of the window (density.cpp: one ++ per
particle per snapshot), on cells of dX; they are not normalised. Plane positions in the names are metres.
physics_core/particle_density.py turns them into concentrations.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW_DIR = re.compile(r"^(?P<start>\d+)-(?P<end>\d+)_basic$")
DENSITY_FILE = re.compile(r"^(?P<family>xy|xz|yz)_number_density_(?P<pos>\d+)m\.csv$")
# Array axes (rows, columns) of each density family, as written by density.cpp output_density.
DENSITY_AXES = {"xy": ("y", "x"), "xz": ("z", "x"), "yz": ("z", "y")}
_SETTING = re.compile(r"^(?P<key>[A-Za-z_]+)(\[\d+\])?\s*=\s*(?P<value>.*)$")


def list_windows(postprocess_dir):
    """{(start, end): folder} for every "<start>-<end>_basic" subfolder, sorted by start then end."""
    out = {}
    for p in Path(postprocess_dir).iterdir():
        m = WINDOW_DIR.match(p.name)
        if m and p.is_dir():
            out[(int(m["start"]), int(m["end"]))] = p
    return dict(sorted(out.items()))


def window_dir(postprocess_dir, start, end):
    p = Path(postprocess_dir) / f"{int(start)}-{int(end)}_basic"
    if not p.is_dir():
        raise FileNotFoundError(f"[ERROR] no window folder {p}")
    return p


def read_log_settings(window):
    """Settings block of log_analysis.txt -> dict, plus 'n_snapshots' (number of outputs processed).

    Numbers are converted; "[a b c]" lists become lists of floats. n_snapshots counts the
    "Current processing" lines, so it is the true divisor of the summed counts.
    """
    out, n_snap = {}, 0
    with open(Path(window) / "log_analysis.txt", "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("Current processing"):
                n_snap += 1
                continue
            m = _SETTING.match(line)
            if m and m["key"] not in out:
                out[m["key"]] = _parse_value(m["value"].strip())
    out["n_snapshots"] = n_snap
    return out


def _parse_value(text):
    if text.startswith("[") and text.endswith("]"):
        return [float(v) for v in text[1:-1].split()]
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def read_total_num(window):
    """total_num.csv -> DataFrame (output, n_particles), only the outputs of this window (count > 0 or inside it)."""
    rows = np.loadtxt(Path(window) / "total_num.csv", delimiter=",", ndmin=2)
    df = pd.DataFrame({"output": rows[0].astype(int), "n_particles": rows[1].astype(np.int64)})
    m = WINDOW_DIR.match(Path(window).name)
    if m:
        df = df[(df["output"] >= int(m["start"])) & (df["output"] <= int(m["end"]))]
    return df.reset_index(drop=True)


def read_profile(window, dx):
    """profile.csv -> DataFrame (z, count, fluid_cells), summed over the rank blocks.

    z is the cell centre (k + 0.5) dx; count is particles in that z cell summed over all snapshots;
    fluid_cells is the number of fluid cells of the domain at that height.
    """
    with open(Path(window) / "profile.csv", "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    counts, fluid = None, None
    i = 0
    while i < len(lines):
        if lines[i].startswith("Rank"):
            c = _int_row(lines[i + 1])
            g = _int_row(lines[i + 2])
            counts = c if counts is None else counts + c
            fluid = g if fluid is None else fluid + g
            i += 3
        else:
            i += 1
    if counts is None:
        raise ValueError(f"[ERROR] no rank block in {Path(window) / 'profile.csv'}")
    z = (np.arange(counts.size) + 0.5) * dx
    return pd.DataFrame({"z": z, "count": counts, "fluid_cells": fluid})


def _int_row(line):
    return np.array([int(v) for v in line.rstrip(",").split(",") if v != ""], dtype=np.int64)


def list_density(window, family):
    """Sorted plane positions [m] of one family ('xy', 'xz', 'yz') in a window folder."""
    out = []
    for p in Path(window).glob(f"{family}_number_density_*m.csv"):
        m = DENSITY_FILE.match(p.name)
        if m:
            out.append(int(m["pos"]))
    return sorted(out)


def read_density(window, family, position):
    """One density file -> 2D int array, axes DENSITY_AXES[family] (e.g. xy: [y, x])."""
    path = Path(window) / f"{family}_number_density_{int(position)}m.csv"
    if not path.exists():
        raise FileNotFoundError(f"[ERROR] no file {path}")
    return np.loadtxt(path, delimiter=",", dtype=np.int64, ndmin=2)


def read_xy_stack(window, heights=None):
    """xy slabs stacked bottom to top -> (heights [m], int array [n_heights, ny, nx]).

    heights: the slab heights to read; default every xy file in the folder.
    """
    heights = list_density(window, "xy") if heights is None else [int(h) for h in heights]
    if not heights:
        raise FileNotFoundError(f"[ERROR] no xy_number_density files in {window}")
    return np.array(heights, dtype=float), np.stack([read_density(window, "xy", h) for h in heights])


def cell_centres(n, dx):
    """Cell-centre positions [m] of n cells of size dx starting at 0 (density.cpp uses index = (int)(pos / dx))."""
    return (np.arange(n) + 0.5) * dx
