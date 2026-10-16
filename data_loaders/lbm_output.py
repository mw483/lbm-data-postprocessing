"""
Reader for the solver's CSV statistics (LBM-city src/output_user_def.cu, refactor/scalar2 and later).

One run folder holds, per rank (_0000, _0001, ...) and per output step:
  xy_<var>, xy_ag_<var>   horizontal planes; one block per level: a label line, then ny rows x nx values
  xz_<var>                xz slice at y = jout; a label line, then nz rows x nx values
  yz_<var>                yz slice at x = iout; a label line, then ny rows x nz values
  xz_yav_<var>            xz plane averaged over y; no label line, nz rows x nx values
  prof<step>_<rank>.csv   profiles averaged over the rank's xy area, one row per z, named columns
and once: header.txt (geometry, dt, c_ref, plane lists).

Every file starts with the line "rank, rank_x, rank_y, rank_z, step, time, xg_min, yg_min, zg_min".
xg/yg/zg_min are the GLOBAL domain minimum (the same on every rank); a rank's place in the domain comes
from rank_x/y/z. Plane labels are one-based global cells. Plane values are time means of raw moments
(uu = <u u>, not a variance) in m/s units; see physics_core/moments.py for central moments.

Files with an extra plane suffix (xz_ins_u<step>_<rank>_<plane>.csv, yz_ins_...) are not read here yet.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# File prefix -> layout. Longest prefix first, so "xz_yav_" wins over "xz_".
# axes: the meaning of (rows, columns); labelled: blocks start with a plane-label line;
# label_axis: what the label counts ("agl" = cells above ground).
LAYOUTS = {
    "xz_yav_": {"axes": ("z", "x"), "labelled": False, "label_axis": None},
    "xy_ag_":  {"axes": ("y", "x"), "labelled": True, "label_axis": "agl"},
    "xy_":     {"axes": ("y", "x"), "labelled": True, "label_axis": "z"},
    "xz_":     {"axes": ("z", "x"), "labelled": True, "label_axis": "y"},
    "yz_":     {"axes": ("y", "z"), "labelled": True, "label_axis": "x"},
}
RANK_KEY = {"x": "rank_x", "y": "rank_y", "z": "rank_z"}
MIN_KEY = {"x": "xg_min", "y": "yg_min", "z": "zg_min"}
FIRST_LINE_KEYS = ("rank", "rank_x", "rank_y", "rank_z", "step", "time", "xg_min", "yg_min", "zg_min")
UNLABELLED = 0   # key of the single block in files without plane labels


@dataclass
class Plane:
    """A stitched plane variable at one output step.

    data:   {label: 2D array (rows, cols) = axes}; NaN where no rank wrote a value.
    coords: {axis: 1D cell-centre positions [m]} for both axes of the arrays.
    labels_m: {label: position of the plane [m]} along label_axis (height above ground for "agl").
    """
    name: str
    step: int
    time: float
    axes: tuple
    label_axis: str | None
    data: dict
    coords: dict
    labels_m: dict = field(default_factory=dict)


def layout_of(name):
    """Layout dict for a file name stem such as 'xy_um' or 'xz_yav_uu'."""
    for prefix, layout in LAYOUTS.items():
        if name.startswith(prefix):
            return layout
    raise ValueError(f"[ERROR] unknown plane family for '{name}' (known prefixes: {', '.join(LAYOUTS)})")


def read_header_txt(run_dir):
    """header.txt -> dict. Integers and floats are converted; comma lists become lists."""
    out = {}
    with open(Path(run_dir) / "header.txt", "r", encoding="utf-8") as f:
        for line in f:
            if "=" not in line:
                continue
            key, value = (s.strip() for s in line.split("=", 1))
            out[key] = _parse_value(value)
    return out


def _parse_value(text):
    parts = [p.strip() for p in text.split(",") if p.strip()]
    values = [_number(p) for p in parts]
    return values if "," in text else (values[0] if values else "")


def _number(text):
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def _parse_first_line(line):
    values = [v for v in line.strip().split(",") if v != ""]
    return {k: _number(v) for k, v in zip(FIRST_LINE_KEYS, values)}


def _rows_to_array(rows):
    return np.array([r.rstrip().rstrip(",").split(",") for r in rows], dtype=float)


def read_plane_file(path, labelled):
    """One rank's file -> (first-line dict, {label: 2D array}). 'nan' entries become NaN."""
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip()]
    meta = _parse_first_line(lines[0])
    if not labelled:
        return meta, {UNLABELLED: _rows_to_array(lines[1:])}
    blocks, label, rows = {}, None, []
    for ln in lines[1:]:
        if "," not in ln:                       # plane-label line
            if label is not None:
                blocks[label] = _rows_to_array(rows)
            label, rows = int(ln), []
        else:
            rows.append(ln)
    if label is not None:
        blocks[label] = _rows_to_array(rows)
    return meta, blocks


_RANK_FILE = re.compile(r"^(?P<name>.+?)(?P<step>\d{8})_(?P<rank>\d{4})\.csv$")


def scan_run(run_dir):
    """DataFrame of every '<name><step>_<rank>.csv' in the folder: columns name, step, rank, path."""
    rows = []
    for p in Path(run_dir).glob("*.csv"):
        m = _RANK_FILE.match(p.name)
        if m:
            rows.append({"name": m["name"], "step": int(m["step"]), "rank": int(m["rank"]), "path": p})
    return pd.DataFrame(rows, columns=["name", "step", "rank", "path"])


def list_steps(run_dir, name):
    """Sorted output steps available for one variable, e.g. list_steps(run, 'xy_um')."""
    files = scan_run(run_dir)
    return sorted(files.loc[files["name"] == name, "step"].unique().tolist())


def plane_path(run_dir, name, step, rank):
    return Path(run_dir) / f"{name}{int(step):08d}_{int(rank):04d}.csv"


def load_plane(run_dir, name, step, header=None):
    """Read every rank of one plane variable at one step and stitch them into global arrays.

    name: file stem without step/rank, e.g. 'xy_um', 'xy_ag_ww', 'xz_uw', 'yz_vv', 'xz_yav_um'.
    header: read_header_txt(run_dir); read here when not given (dx comes from it).
    """
    layout = layout_of(name)
    header = header or read_header_txt(run_dir)
    dx = float(header["dx"])
    paths = sorted(Path(run_dir).glob(f"{name}{int(step):08d}_[0-9][0-9][0-9][0-9].csv"))
    if not paths:
        raise FileNotFoundError(f"[ERROR] no files {name}{int(step):08d}_*.csv in {run_dir}")

    pieces, meta0 = [], None
    for p in paths:
        meta, blocks = read_plane_file(p, layout["labelled"])
        meta0 = meta0 or meta
        pieces.extend((meta, label, arr) for label, arr in blocks.items())

    rows_ax, cols_ax = layout["axes"]
    if not layout["labelled"]:
        _check_unsplit(pieces, layout)
    block_shape = pieces[0][2].shape
    n_rows = block_shape[0] * (1 + max(m[RANK_KEY[rows_ax]] for m, _, _ in pieces))
    n_cols = block_shape[1] * (1 + max(m[RANK_KEY[cols_ax]] for m, _, _ in pieces))

    data = {}
    for meta, label, arr in pieces:
        if arr.shape != block_shape:
            raise ValueError(f"[ERROR] {name} step {step}: rank {meta['rank']} block {arr.shape}, expected {block_shape}")
        out = data.setdefault(label, np.full((n_rows, n_cols), np.nan))
        r0 = meta[RANK_KEY[rows_ax]] * block_shape[0]
        c0 = meta[RANK_KEY[cols_ax]] * block_shape[1]
        target = out[r0:r0 + block_shape[0], c0:c0 + block_shape[1]]
        # Fill only empty cells: xy_ag files print nan where another z-rank owns the level.
        np.copyto(target, arr, where=np.isnan(target))

    coords = {
        rows_ax: meta0[MIN_KEY[rows_ax]] + (np.arange(n_rows) + 0.5) * dx,
        cols_ax: meta0[MIN_KEY[cols_ax]] + (np.arange(n_cols) + 0.5) * dx,
    }
    return Plane(
        name=name, step=int(meta0["step"]), time=float(meta0["time"]),
        axes=layout["axes"], label_axis=layout["label_axis"],
        data=dict(sorted(data.items())), coords=coords,
        labels_m=_label_positions(data, layout["label_axis"], meta0, dx),
    )


def _check_unsplit(pieces, layout):
    """Unlabelled files (xz_yav) are averages over the axis that is not in the array; with several
    ranks along that axis each rank wrote its own partial average, which this reader does not combine."""
    missing = ({"x", "y", "z"} - set(layout["axes"])).pop()
    if any(m[RANK_KEY[missing]] != 0 for m, _, _ in pieces):
        raise NotImplementedError(f"[ERROR] ranks split along {missing}: combining partial averages is not implemented")


def _label_positions(data, label_axis, meta, dx):
    """Cell-centre position of each plane label. Labels are one-based cells; 'agl' is above ground."""
    if label_axis is None:
        return {}
    origin = 0.0 if label_axis == "agl" else meta[MIN_KEY[label_axis]]
    return {label: origin + (label - 0.5) * dx for label in data}


def load_prof(run_dir, step):
    """All ranks' prof<step>_<rank>.csv -> one DataFrame with a 'rank' column (+ rank_x/y/z, time)."""
    paths = sorted(Path(run_dir).glob(f"prof{int(step):08d}_[0-9][0-9][0-9][0-9].csv"))
    if not paths:
        raise FileNotFoundError(f"[ERROR] no files prof{int(step):08d}_*.csv in {run_dir}")
    frames = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            meta = _parse_first_line(f.readline())
        df = pd.read_csv(p, skiprows=1)
        df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
        for key in ("rank", "rank_x", "rank_y", "rank_z", "time"):
            df[key] = meta[key]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def domain_profile(prof):
    """Average the ranks' profiles at each z (load_prof output) -> one row per z.

    Each rank's profile is a mean over its own xy area. A plain mean over ranks is the domain mean
    when every rank has the same number of fluid cells at that height (true for flat cases with
    equal rank sizes; not for building cases, where it is only approximate).
    """
    value_cols = [c for c in prof.columns if c not in ("rank", "rank_x", "rank_y", "rank_z")]
    return prof[value_cols].groupby("z", as_index=False).mean()
