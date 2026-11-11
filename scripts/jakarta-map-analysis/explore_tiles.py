"""
Explore a map set tile by tile and mark candidate cut-out boxes for a simulation.

    python scripts/jakarta-map-analysis/explore_tiles.py MAP_FOLDER [--georef georef.yaml] [--nz 256]
    python scripts/jakarta-map-analysis/explore_tiles.py MAP_FOLDER --candidates candidates.yaml --save candidates.png

Window (matplotlib):
- top: building height above ground, seen from above (log colours; the map is
  drawn in map axes, x = column i = wind direction, y = row j);
- middle: one 500 m tile statistic (keys 1-4: plan area fraction, mean building
  height, max building height, tree cover);
- right: the numbers of the current box.
Mouse: drag a box on either map (free, any cells); a click without dragging
selects the tile under the mouse.
Keys: 1-4 tile statistic | t snap boxes to whole tiles on/off | a add the box as
a candidate (saved to the candidates file at once) | x remove the last
candidate | v open the box in the 3D viewer (view_map_3d.py) | w write
the figure (PNG) and candidates.csv | q quit.
The full numbers of every box are printed in the terminal.

With --save no window opens: the candidates are drawn on both maps, the figure
is written to the given PNG and candidates.csv (one row per candidate, all
numbers) next to it. This is the page to show which areas were picked and why.

Figure (and candidates.csv) explained:
1. What: where each candidate box sits in the city, over maps of how built-up,
   how tall and how green each 500 m tile is; the CSV gives each box's own numbers.
2. Why: to choose and justify a piece of the map to simulate. The box numbers
   test the AIJ CFD guideline (Tominaga et al. 2008, J. Wind Eng. Ind.
   Aerodyn. 96, 1749-1761): domain top >= 5 x tallest building, blockage < 3%,
   >= 10 H downstream (COST: 15 H_max), >= 10 cells per building side
   (professor: 16); and the periodic set-up: buildings cut at the seams,
   ground step across the seams, width compared with the domain depth.
3. Reference: the AIJ/COST numbers above; plan area fraction and heights
   compare with GHSL (see compare_reference.py). Wall time is scaled from one
   benchmark run [est].
4. Units: cells of 2 m (map x = column i, y = row j), heights in m above ground,
   fractions 0-1; tiles start at the first land column (the same tiles as
   tiles_500m.csv from map_statistics.py).
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DX, add_map_args, land_columns, out_dir, resolve_map   # noqa: E402

from data_loaders.map_io import load_map_set                                  # noqa: E402
from physics_core.urban_morphology import box_summary, object_heights, tile_stats   # noqa: E402

# =============================================================================
# Settings
# =============================================================================
TILE_M = 500.0
DISPLAY_CELLS = 2000            # the building map is max-pooled to about this many pixels across
CLICK_CELLS = 3                 # a drag shorter than this is a click
STATS = {"1": ("lambda_p", "plan area fraction λp [-]", "Greys", (0, 0.7)),
         "2": ("h_mean", "mean building height [m]", "viridis", (0, 50)),
         "3": ("h_max", "max building height [m]", "magma", (0, 300)),
         "4": ("tree_cover", "tree cover [-]", "Greens", (0, 0.5))}
BOX_COLOR = "#2f6db5"
CAND_COLOR = "#c0392b"
VIEWER = Path(__file__).resolve().parents[1] / "view_map_3d.py"

# lines shown in the side panel: (key, label, format)
PANEL = [("size", "size", None),
         ("lambda_p", "λp", "{:.2f}"), ("H_av_m", "H_av [m]", "{:.1f}"),
         ("h_mean_m", "mean height [m]", "{:.1f}"), ("h_max_m", "max height [m]", "{:.0f}"),
         ("default_height_share", "share at 6 m", "{:.0%}"), ("tree_cover", "tree cover", "{:.0%}"),
         ("ground_range_m", "ground range [m]", "{:.0f}"),
         ("narrower_10_cells_volume_share", "volume < 10 cells", "{:.0%}"),
         ("narrower_16_cells_volume_share", "volume < 16 cells", "{:.0%}"),
         ("edge_build_cells_i0", "bldg cells on edge i0", "{:d}"), ("edge_build_cells_i1", "  on edge i1", "{:d}"),
         ("edge_build_cells_j0", "  on edge j0", "{:d}"), ("edge_build_cells_j1", "  on edge j1", "{:d}"),
         ("shifted_box", "street-aligned box", "{}"),
         ("top_m", "top [m]", "{:.0f}"), ("top_over_hmax", "top / H_max (AIJ ≥ 5)", "{:.1f}"),
         ("length_over_hmax", "length / H_max (≥ 10)", "{:.1f}"),
         ("blockage_max", "blockage max (AIJ < 3%)", "{:.1%}"),
         ("width_over_top", "width / top", "{:.1f}"),
         ("sources", "sources", "{:,}"), ("cells_million", "cells [M]", "{:.0f}"),
         ("wall_hours_4gpu_est", "wall time 4 GPU [h, est]", "{:.1f}")]


# =============================================================================
# Candidates file
# =============================================================================
def load_candidates(path):
    if path is None or not Path(path).exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out = []
    for c in data.get("candidates", []):
        out.append({"name": str(c["name"]), "box": [int(v) for v in c["box"]],
                    "nz": int(c["nz"]) if c.get("nz") else None, "note": c.get("note", "")})
    return out


def save_candidates(path, cands):
    data = {"about": "Candidate cut-out boxes: box = [i0, i1, j0, j1] in map cells, end exclusive; "
                     "nz = vertical cells (2 m); wind along +i (map x).",
            "candidates": [{"name": c["name"], "box": list(c["box"]), "nz": c["nz"], "note": c["note"]}
                           for c in cands]}
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    print(f"Saved {len(cands)} candidates to {path}")


def next_name(cands):
    used = {c["name"] for c in cands}
    for k in range(1000):
        name = chr(ord("A") + k) if k < 26 else f"box{k}"
        if name not in used:
            return name


# =============================================================================
# Numbers
# =============================================================================
def lonlat(box, geo):
    if geo is None:
        return {}
    from data_loaders.map_georef import cell_to_lonlat
    try:
        lon, lat = cell_to_lonlat((box[0] + box[1]) / 2 - 0.5, (box[2] + box[3]) / 2 - 0.5, geo)
    except ImportError:
        return {}
    return {"lon_centre": round(float(lon), 5), "lat_centre": round(float(lat), 5)}


def summarise(maps, box, nz, args, geo):
    s = box_summary(maps, box, dx=DX, nz=nz, run_s=args.run_seconds, source_step=args.source_step)
    s.update(lonlat(box, geo))
    return s


def print_summary(title, s):
    print(f"\n=== {title} ===")
    for k, v in s.items():
        print(f"  {k:32s} {v:.4g}" if isinstance(v, float) else f"  {k:32s} {v}")


def panel_text(title, s):
    lines = [title]
    for key, label, fmt in PANEL:
        if key == "size":
            lines.append(f"{s['n_i']} x {s['n_j']} cells = {s['length_x_m']:.0f} x {s['width_y_m']:.0f} m")
            lines.append(f"cells i {s['i0']}-{s['i1']}, j {s['j0']}-{s['j1']}")
            if "lon_centre" in s:
                lines.append(f"centre {s['lon_centre']:.4f} E, {-s['lat_centre']:.4f} S")
            continue
        if key not in s:
            continue
        v = s[key]
        try:
            txt = fmt.format(v) if not (isinstance(v, float) and np.isnan(v)) else "-"
        except (ValueError, TypeError):
            txt = str(v)
        lines.append(f"{label}: {txt}")
    return "\n".join(lines)


# =============================================================================
# Drawing
# =============================================================================
def building_image(hb, n_display):
    """Block max of the building heights, so tall buildings stay visible; 0 -> NaN (white)."""
    ny, nx = hb.shape
    f = max(1, int(np.ceil(nx / n_display)))
    a = hb[:ny // f * f, :nx // f * f].reshape(ny // f, f, nx // f, f).max(axis=(1, 3))
    a = np.where(a > 0, a, np.nan)
    return a, (0, nx // f * f, 0, ny // f * f)


def tile_grid(hb, hv, land, tile_cells):
    st = tile_stats(hb[:, land[0]:land[1]], hv[:, land[0]:land[1]], tile_cells)
    nyt, nxt = st["lambda_p"].shape
    extent = (land[0], land[0] + nxt * tile_cells, 0, nyt * tile_cells)
    return st, extent


def draw_box(ax, box, color, label=None, ls="-"):
    from matplotlib.patches import Rectangle
    i0, i1, j0, j1 = box
    artists = [ax.add_patch(Rectangle((i0, j0), i1 - i0, j1 - j0, fill=False, ec=color, lw=1.6, ls=ls))]
    if label:
        artists.append(ax.text(i0, j1, f" {label}", color=color, fontsize=9, fontweight="bold",
                               va="bottom", ha="left"))
    return artists


def axis_names(geo):
    if geo is None:
        return "map x, column i (wind direction)", "map y, row j"
    names = {"N": "north", "S": "south", "E": "east", "W": "west"}
    i_dir, j_dir = (p.split(":")[1] for p in geo["orientation"].split(","))
    return (f"map x, column i (towards {names[i_dir]}; wind direction)", f"map y, row j (towards {names[j_dir]})")


class Explorer:
    def __init__(self, fig, axes, maps, hb, hv, land, tile_cells, folder, args, geo, cand_path):
        self.fig, (self.ax_b, self.ax_t, self.ax_txt) = fig, axes
        self.maps, self.hb, self.hv, self.land, self.tile = maps, hb, hv, land, tile_cells
        self.folder, self.args, self.geo, self.cand_path = folder, args, geo, cand_path
        self.cands = load_candidates(cand_path)
        self.box, self.box_artists, self.cand_artists = None, [], []
        self.snap = False
        self.stats, self.tile_extent = tile_grid(hb, hv, land, tile_cells)
        self.stat_key = "1"
        self.tile_im = None
        self.draw_tiles()
        self.draw_candidates()

    # --- drawing -----------------------------------------------------------
    def draw_tiles(self):
        name, label, cmap, clim = STATS[self.stat_key]
        if self.tile_im is not None:
            self.tile_im.colorbar.remove()
            self.tile_im.remove()
        self.tile_im = self.ax_t.imshow(self.stats[name], origin="lower", extent=self.tile_extent, cmap=cmap,
                                        vmin=clim[0], vmax=clim[1], aspect="equal", interpolation="nearest")
        self.fig.colorbar(self.tile_im, ax=self.ax_t, label=label, shrink=0.8, pad=0.01)
        self.ax_t.set_title(f"{self.args.tile:g} m tiles: {label}  (keys 1-4 switch)", fontsize=9, loc="left")
        ny, nx = self.hb.shape
        self.ax_t.set_xlim(0, nx)            # imshow rescales the shared axes to the tiles
        self.ax_t.set_ylim(0, ny)

    def draw_candidates(self):
        for a in self.cand_artists:
            a.remove()
        self.cand_artists = []
        for c in self.cands:
            for ax in (self.ax_b, self.ax_t):
                self.cand_artists += draw_box(ax, c["box"], CAND_COLOR, c["name"])

    def show_box(self, box, title):
        for a in self.box_artists:
            a.remove()
        self.box_artists = []
        self.box = box
        for ax in (self.ax_b, self.ax_t):
            self.box_artists += draw_box(ax, box, BOX_COLOR, ls="--")
        s = summarise(self.maps, box, self.args.nz, self.args, self.geo)
        print_summary(title, s)
        self.ax_txt.clear()
        self.ax_txt.axis("off")
        self.ax_txt.text(0, 1, panel_text(title, s), va="top", ha="left", fontsize=8, family="monospace",
                         transform=self.ax_txt.transAxes)
        self.fig.canvas.draw_idle()

    # --- events --------------------------------------------------------------
    def tile_box_at(self, x, y):
        t = self.tile
        ti, tj = int((x - self.land[0]) // t), int(y // t)
        nyt, nxt = self.stats["lambda_p"].shape
        if not (0 <= ti < nxt and 0 <= tj < nyt):
            return None, None
        i0 = self.land[0] + ti * t
        return (i0, i0 + t, tj * t, tj * t + t), f"tile i={ti} j={tj}"

    def snap_box(self, box):
        t, L = self.tile, self.land[0]
        i0 = L + int(np.floor((box[0] - L) / t)) * t
        i1 = L + int(np.ceil((box[1] - L) / t)) * t
        return (i0, i1, int(np.floor(box[2] / t)) * t, int(np.ceil(box[3] / t)) * t)

    def clip(self, box):
        ny, nx = self.hb.shape
        i0, i1, j0, j1 = box
        return (max(0, i0), min(nx, i1), max(0, j0), min(ny, j1))

    # mouse: own rubber band (works the same on every matplotlib version)
    def busy(self, event):
        tb = getattr(self.fig.canvas, "toolbar", None)
        return (event.inaxes not in (self.ax_b, self.ax_t) or event.button != 1
                or (tb is not None and getattr(tb, "mode", "")))

    def on_press(self, event):
        if self.busy(event) or event.xdata is None:
            self.press = None
            return
        from matplotlib.patches import Rectangle
        self.press = (event.xdata, event.ydata)
        self.band = [ax.add_patch(Rectangle(self.press, 0, 0, fill=False, ec=BOX_COLOR, lw=1.0))
                     for ax in (self.ax_b, self.ax_t)]

    def on_motion(self, event):
        if getattr(self, "press", None) is None or event.xdata is None or event.inaxes not in (self.ax_b, self.ax_t):
            return
        x0, y0 = self.press
        for r in self.band:
            r.set_bounds(min(x0, event.xdata), min(y0, event.ydata), abs(event.xdata - x0), abs(event.ydata - y0))
        self.fig.canvas.draw_idle()

    def on_release(self, event):
        if getattr(self, "press", None) is None:
            return
        for r in self.band:
            r.remove()
        start, self.press = self.press, None
        if event.xdata is None or event.inaxes not in (self.ax_b, self.ax_t):
            self.fig.canvas.draw_idle()
            return
        self.on_select(start, (event.xdata, event.ydata))

    def on_select(self, p0, p1):
        x0, x1 = sorted((p0[0], p1[0]))
        y0, y1 = sorted((p0[1], p1[1]))
        if x1 - x0 < CLICK_CELLS and y1 - y0 < CLICK_CELLS:
            box, title = self.tile_box_at(x0, y0)
            if box is None:
                return
        else:
            box = (int(round(x0)), int(round(x1)), int(round(y0)), int(round(y1)))
            if self.snap:
                box = self.snap_box(box)
            title = "box"
        box = self.clip(box)
        if box[1] - box[0] < 1 or box[3] - box[2] < 1:
            return
        self.show_box(box, title)

    def on_key(self, event):
        k = event.key
        if k in STATS:
            self.stat_key = k
            self.draw_tiles()
            self.fig.canvas.draw_idle()
        elif k == "t":
            self.snap = not self.snap
            print(f"Snap to tiles: {'on' if self.snap else 'off'}")
        elif k == "a" and self.box:
            name = next_name(self.cands)
            self.cands.append({"name": name, "box": list(self.box), "nz": self.args.nz, "note": ""})
            save_candidates(self.cand_path, self.cands)
            self.draw_candidates()
            self.fig.canvas.draw_idle()
            print(f"Added candidate {name} {self.box}; write the reason under 'note' in {self.cand_path}")
        elif k == "x" and self.cands:
            gone = self.cands.pop()
            save_candidates(self.cand_path, self.cands)
            self.draw_candidates()
            self.fig.canvas.draw_idle()
            print(f"Removed candidate {gone['name']}")
        elif k == "v" and self.box:
            i0, i1, j0, j1 = self.box
            src = ["--case", self.args.case] if self.args.case else [str(self.folder)]
            cmd = [sys.executable, str(VIEWER), *src, "--crop", str(i0), str(i1), str(j0), str(j1)]
            print("Opening 3D view:", " ".join(cmd))
            subprocess.Popen(cmd)
        elif k == "w":
            write_outputs(self.fig, self.cands, self.maps, self.args, self.geo, self.cand_path.parent / "candidates.png")


def write_outputs(fig, cands, maps, args, geo, png):
    fig.savefig(png, dpi=200, bbox_inches="tight")
    print(f"Saved {png}")
    if not cands:
        return
    rows = []
    for c in cands:
        s = summarise(maps, c["box"], c["nz"] or args.nz, args, geo)
        rows.append({"name": c["name"], "note": c["note"], **s})
    csv = Path(png).with_name("candidates.csv")
    pd.DataFrame(rows).to_csv(csv, index=False)
    print(f"Saved {csv}")


# =============================================================================
# Main
# =============================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_map_args(ap)
    ap.add_argument("--georef", help="georef.yaml (from fit_map_location.py): compass labels and lon/lat")
    ap.add_argument("--candidates", help="candidates YAML to read and write (default <out>/candidates.yaml)")
    ap.add_argument("--nz", type=int, default=256, help="vertical cells for the domain top and cost (default 256 = 512 m)")
    ap.add_argument("--run-seconds", type=float, default=3600.0, help="simulated time for the wall-time estimate")
    ap.add_argument("--source-step", type=int, default=8, help="one source every N cells on open ground (default 8)")
    ap.add_argument("--tile", type=float, default=TILE_M, help="tile size in m (default 500)")
    ap.add_argument("--save", help="write this PNG (and candidates.csv beside it) without opening a window")
    args = ap.parse_args()

    import matplotlib
    if args.save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    for k in ("keymap.forward", "keymap.back", "keymap.save", "keymap.xscale", "keymap.yscale", "keymap.grid"):
        plt.rcParams[k] = [v for v in plt.rcParams[k] if v not in ("v", "x", "a", "t", "w", "1", "2", "3", "4")]

    folder, label = resolve_map(ap, args)
    out = out_dir(args, label)
    cand_path = Path(args.candidates) if args.candidates else out / "candidates.yaml"
    geo = None
    if args.georef:
        from data_loaders.map_georef import load_georef
        geo = load_georef(args.georef)

    maps = load_map_set(folder)
    land = land_columns(maps, args)
    hb, hv = object_heights(maps)
    tile_cells = int(round(args.tile / DX))

    fig = plt.figure(figsize=(17, 9))
    gs = fig.add_gridspec(2, 2, width_ratios=[4.2, 1], wspace=0.05, hspace=0.25)
    ax_b = fig.add_subplot(gs[0, 0])
    ax_t = fig.add_subplot(gs[1, 0], sharex=ax_b, sharey=ax_b)
    ax_txt = fig.add_subplot(gs[:, 1])
    ax_txt.axis("off")
    img, ext = building_image(hb, DISPLAY_CELLS)
    im = ax_b.imshow(img, origin="lower", extent=ext, cmap="viridis", interpolation="nearest",
                     norm=LogNorm(vmin=1, vmax=max(2.0, float(np.nanmax(img)))), aspect="equal")
    fig.colorbar(im, ax=ax_b, label="building height above ground [m]", shrink=0.8, pad=0.01)
    ax_b.set_title(f"{label}: buildings from above (white = no building)", fontsize=9, loc="left")
    xl, yl = axis_names(geo)
    ax_t.set_xlabel(xl)
    for ax in (ax_b, ax_t):
        ax.set_ylabel(yl)
        ax.axvline(land[0], color="0.5", lw=0.6, ls=":")
        ax.axvline(land[1], color="0.5", lw=0.6, ls=":")
    ex = Explorer(fig, (ax_b, ax_t, ax_txt), maps, hb, hv, land, tile_cells, folder, args, geo, cand_path)

    if args.save:
        if not ex.cands:
            print(f"[WARN] no candidates in {cand_path}")
        lines = []
        for c in ex.cands:
            s = summarise(maps, c["box"], c["nz"] or args.nz, args, geo)
            lines.append(f"{c['name']}: {s['length_x_m']:.0f} x {s['width_y_m']:.0f} x {s['top_m']:.0f} m\n"
                         f"   λp {s['lambda_p']:.2f}, height mean {s['h_mean_m']:.1f} / max {s['h_max_m']:.0f} m\n"
                         f"   top/H_max {s['top_over_hmax']:.1f}, blockage max {s['blockage_max']:.1%}\n"
                         f"   building volume < 10 cells {s['narrower_10_cells_volume_share']:.0%}\n"
                         f"   {s['sources']:,} sources, ~{s['wall_hours_4gpu_est']:.1f} h on 4 GPUs"
                         + (f"\n   {c['note']}" if c["note"] else ""))
        ax_txt.text(0, 1, "Candidates\n\n" + "\n\n".join(lines), va="top", ha="left", fontsize=8,
                    family="monospace", transform=ax_txt.transAxes, wrap=True)
        write_outputs(fig, ex.cands, maps, args, geo, Path(args.save))
        return

    ax_txt.text(0, 1, "Drag a box, or click a tile.\nKeys: 1-4 tile statistic, t snap to tiles,\n"
                      "a add candidate, x remove last,\nv 3D view, w write PNG + CSV, q quit",
                va="top", ha="left", fontsize=8, family="monospace", transform=ax_txt.transAxes)
    fig.canvas.mpl_connect("button_press_event", ex.on_press)
    fig.canvas.mpl_connect("motion_notify_event", ex.on_motion)
    fig.canvas.mpl_connect("button_release_event", ex.on_release)
    fig.canvas.mpl_connect("key_press_event", ex.on_key)
    plt.show()


if __name__ == "__main__":
    main()
