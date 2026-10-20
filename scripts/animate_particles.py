"""
Animation of all particles (a fixed subset) from the snapshots of reduce_particle_bins.py, cases side by side.

Python port of the old MATLAB particle_visual.m: the same three views, now for several cases at once.
  --mode xz   side view, every particle projected on x-z (or only a slab with --slab y0 y1)
  --mode xy   top view, projected on x-y (or a height slab with --slab z0 z1)
  --mode 3d   PyVista point cloud, one row per case
Particles are coloured by age [s] (or height with --color z); one colour scale for all frames and cases.

Reads <lbm_results>/<run>/particle_reduced/snapshots/snap_<n>.npz and writes to
<figures>/particle_animation/<mode>/: frame_<n>.png, animation.gif, animation.mp4 (needs the video extra).

Usage:
  python scripts/animate_particles.py --mode xz
  python scripts/animate_particles.py --mode xy --slab 0 10 --every 2
  python scripts/animate_particles.py --mode 3d --zmax 400
"""
import argparse

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize

from data_loaders.local_paths import load_local_paths, particle_reduced_dir
from plotting_core.heatmap_plots import frames_to_gif, frames_to_mp4

# =============================================================================
# Settings
# =============================================================================
CASES = {
    "convective": "flat_512x128x1024/20261011_scalar2",
    "neutral": "flat_512x128x1024/20261017_neutral",
}
DOMAIN = (1024.0, 256.0)    # x, y extent [m]
FPS = 10                    # animation frames per second
POINT_SIZE = 0.4            # matplotlib marker size (points^2)
BACKGROUND = "black"        # "black" like the MATLAB figures, or "white"
CMAP = "turbo"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=("xz", "xy", "3d"), default="xz")
    p.add_argument("--slab", nargs=2, type=float, metavar=("LO", "HI"),
                   help="keep particles with y (xz mode) or z (xy mode) in [LO, HI) [m]")
    p.add_argument("--color", choices=("age", "z"), default="age", help="colour by age [s] or height [m]")
    p.add_argument("--zmax", type=float, default=300.0, help="top of the xz and 3d views [m]")
    p.add_argument("--every", type=int, default=1, help="use every n-th snapshot")
    p.add_argument("--vmax", type=float, help="top of the colour scale (default: max over all frames)")
    return p.parse_args()


def snapshot_files(folder):
    """{output number: path} of snap_<n>.npz files."""
    return {int(p.stem.split("_")[1]): p for p in sorted(folder.glob("snap_*.npz"))}


def load_snapshot(path, mode, slab):
    with np.load(path) as f:
        d = {k: f[k] for k in ("x", "y", "z", "age")}
        d["time"] = float(f["time"])
    if slab is not None:
        key = "y" if mode == "xz" else "z"
        keep = (d[key] >= slab[0]) & (d[key] < slab[1])
        d.update({k: d[k][keep] for k in ("x", "y", "z", "age")})
    return d


def draw_2d(snaps, mode, color, norm, zmax, title, save_path):
    n = len(snaps)
    height = 2.6 if mode == "xz" else 2.2
    fig, axes = plt.subplots(n, 1, figsize=(11.0, height * n + 0.8), squeeze=False, facecolor=BACKGROUND,
                             layout="constrained")
    fg = "w" if BACKGROUND == "black" else "k"
    for ax, (case, d) in zip(axes[:, 0], snaps.items()):
        vert = d["z"] if mode == "xz" else d["y"]
        sc = ax.scatter(d["x"], vert, c=d[color], s=POINT_SIZE, cmap=CMAP, norm=norm, linewidths=0, rasterized=True)
        ax.set_xlim(0, DOMAIN[0])
        ax.set_ylim(0, zmax if mode == "xz" else DOMAIN[1])
        ax.set_aspect("equal")
        ax.set_facecolor(BACKGROUND)
        ax.set_title(f"{case}: {d['x'].size} particles shown", color=fg, fontsize=10)
        ax.set_ylabel("z [m]" if mode == "xz" else "y [m]", color=fg)
        ax.tick_params(colors=fg)
        for s in ax.spines.values():
            s.set_color(fg)
    axes[-1, 0].set_xlabel("x [m]", color=fg)
    cb = fig.colorbar(sc, ax=list(axes[:, 0]), shrink=0.9)
    cb.set_label("age [s]" if color == "age" else "z [m]", color=fg)
    cb.ax.tick_params(colors=fg)
    fig.suptitle(title, color=fg)
    fig.savefig(save_path, dpi=130, facecolor=BACKGROUND)
    plt.close(fig)


def draw_3d(snaps, color, norm, zmax, title, save_path):
    import pyvista as pv
    n = len(snaps)
    pl = pv.Plotter(off_screen=True, shape=(n, 1), window_size=(1400, 520 * n), border=False)
    for i, (case, d) in enumerate(snaps.items()):
        pl.subplot(i, 0)
        pl.set_background(BACKGROUND)
        keep = d["z"] <= zmax
        cloud = pv.PolyData(np.column_stack([d["x"][keep], d["y"][keep], d["z"][keep]]))
        cloud[color] = d[color][keep]
        pl.add_mesh(cloud, scalars=color, cmap=CMAP, clim=(norm.vmin, norm.vmax), point_size=2,
                    render_points_as_spheres=False, show_scalar_bar=(i == 0),
                    scalar_bar_args={"title": "age [s]" if color == "age" else "z [m]", "n_labels": 5,
                                     "color": "w" if BACKGROUND == "black" else "k"})
        pl.add_mesh(pv.Box(bounds=(0, DOMAIN[0], 0, DOMAIN[1], 0, zmax)), style="wireframe", color="gray")
        pl.add_text(f"{case}" + (f"   {title}" if i == 0 else ""), font_size=10,
                    color="w" if BACKGROUND == "black" else "k")
        pl.camera_position = [(-350.0, -900.0, 650.0), (DOMAIN[0] / 2, DOMAIN[1] / 2, 40.0), (0, 0, 1)]
    pl.screenshot(str(save_path))
    pl.close()


def main():
    a = parse_args()
    paths = load_local_paths()
    folders = {c: particle_reduced_dir(paths, r) / "snapshots" for c, r in CASES.items()}
    files = {c: snapshot_files(f) for c, f in folders.items()}
    outputs = sorted(set.intersection(*(set(f) for f in files.values())))[:: a.every]
    if not outputs:
        raise FileNotFoundError(f"[ERROR] the cases share no snapshot; folders {list(folders.values())}")
    slab = tuple(a.slab) if a.slab else None
    tag = a.mode + (f"_slab{a.slab[0]:g}-{a.slab[1]:g}" if slab else "") + f"_{a.color}"
    out_dir = paths["figures"] / "particle_animation" / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    vmax = a.vmax
    if vmax is None:   # colour scale from the last snapshot, where ages and heights are largest
        last = {c: load_snapshot(files[c][outputs[-1]], a.mode, slab) for c in CASES}
        vmax = max(float(d[a.color].max()) for d in last.values() if d[a.color].size)
    norm = Normalize(vmin=0.0, vmax=vmax)

    frames = []
    for n in outputs:
        snaps = {c: load_snapshot(files[c][n], a.mode, slab) for c in CASES}
        t = next(iter(snaps.values()))["time"]
        title = f"output {n}, t = {t:.1f} s"
        if slab:
            title += f", {'y' if a.mode == 'xz' else 'z'} in [{a.slab[0]:g}, {a.slab[1]:g}) m"
        save = out_dir / f"frame_{n:05d}.png"
        if a.mode == "3d":
            draw_3d(snaps, a.color, norm, a.zmax, title, save)
        else:
            draw_2d(snaps, a.mode, a.color, norm, a.zmax, title, save)
        frames.append(save)
    frames_to_gif(frames, out_dir / "animation.gif", fps=FPS)
    if frames_to_mp4(frames, out_dir / "animation.mp4", fps=FPS):
        print(f"[SUCCESS] MP4 saved to: {out_dir / 'animation.mp4'}")
    print(f"[SUCCESS] {len(frames)} frames and GIF saved to: {out_dir}")


if __name__ == "__main__":
    main()
