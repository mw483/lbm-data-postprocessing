"""
y-averaged x-z heatmaps (xz_yav_* files) of every averaging window, every run of a run set
(run_sets.yaml, --set NAME), plus animations.

Per variable and window it writes, in <figures>/<set>/xz_yav_heatmaps/<variable>/
  combined_step<step>.png   the cases side by side, one colorbar
  <case>_step<step>.png     each case alone
and from those frames combined.gif / <case>.gif (and .mp4 when imageio-ffmpeg is installed).
The colour scale of a variable is the same in every panel, case and window, so frames and slides compare
directly; it spans the min..max of all of them below ZMAX (symmetric around 0 for W).
"""
from data_loaders.lbm_output import list_steps, load_plane, read_header_txt
from data_loaders.local_paths import load_local_paths, wind_dir
from data_loaders.run_sets import parse_set_args, set_output_dir, write_manifest
from physics_core.moments import plane_moments
from plotting_core.heatmap_plots import frames_to_gif, frames_to_mp4, plot_xz_heatmaps, shared_norm

# =============================================================================
# Settings
# =============================================================================
VARIABLES = {
    # name in physics_core.moments.plane_moments: (colorbar label, colormap, centre of a diverging scale)
    "U": ("U [m/s]", "viridis", None),
    "W": ("W [m/s]", "RdBu_r", 0.0),
    "sigma_w": (r"$\sigma_w$ [m/s]", "magma", None),
    "tke": (r"resolved TKE [m$^2$/s$^2$]", "magma", None),
}
RAW = ("um", "vm", "wm", "uu", "vv", "ww")   # xz_yav files the variables above need
ZMAX = 1000.0      # top of the plots [m]
FPS = 1.0          # animation frames per second


def load_window(run_dir, step, header):
    """{variable: 2D array [z, x] below ZMAX}, the x and z axes, and the window end time [s]."""
    planes = {raw: load_plane(run_dir, f"xz_yav_{raw}", step, header) for raw in RAW}
    first = planes["um"]
    keep = first.coords["z"] <= ZMAX
    stats = plane_moments({raw: p.data[0][keep] for raw, p in planes.items()})
    return {v: stats[v] for v in VARIABLES}, first.coords["x"], first.coords["z"][keep], first.time


def main():
    set_name, run_names = parse_set_args(__doc__)
    paths = load_local_paths()
    out_root = set_output_dir(paths, set_name, "xz_yav_heatmaps")
    runs = {label: wind_dir(paths, run) for label, run in run_names.items()}
    headers = {label: read_header_txt(d) for label, d in runs.items()}
    steps = sorted(set.intersection(*(set(list_steps(d, "xz_yav_um")) for d in runs.values())))
    if not steps:
        raise FileNotFoundError("[ERROR] the cases share no xz_yav output step")
    t_ave = float(next(iter(headers.values()))["t_ave"])

    # data[step][case] = (fields, x, z, time); every window is held in memory (7 x 2 x 4 small arrays)
    data = {s: {c: load_window(runs[c], s, headers[c]) for c in runs} for s in steps}
    print(f"{len(steps)} windows, cases {list(runs)}")

    for var, (label, cmap, center) in VARIABLES.items():
        norm = shared_norm([data[s][c][0][var] for s in steps for c in runs], center=center)
        out_dir = out_root / var
        frames = {"combined": []} | {c: [] for c in runs}
        for s in steps:
            x, z, t_end = data[s][next(iter(runs))][1:]
            window = f"window {t_end - t_ave:.0f}-{t_end:.0f} s"
            panels = {c: data[s][c][0][var] for c in runs}
            save = out_dir / f"combined_step{s:08d}.png"
            plot_xz_heatmaps(panels, x, z, norm, cmap, label, save, title=f"y-averaged {label}, {window}", zmax=ZMAX)
            frames["combined"].append(save)
            for c, arr in panels.items():
                save = out_dir / f"{c}_step{s:08d}.png"
                plot_xz_heatmaps({c: arr}, x, z, norm, cmap, label, save, title=f"{window}", zmax=ZMAX)
                frames[c].append(save)
        for name, paths_ in frames.items():
            frames_to_gif(paths_, out_dir / f"{name}.gif", fps=FPS)
            has_mp4 = frames_to_mp4(paths_, out_dir / f"{name}.mp4", fps=FPS)
        print(f"[SUCCESS] {var}: {len(steps)} frames, GIF{' and MP4' if has_mp4 else ''} in {out_dir}"
              f" (scale {norm.vmin:.3g} to {norm.vmax:.3g})")
    write_manifest(out_root, set_name, run_names, inputs=runs)


if __name__ == "__main__":
    main()
