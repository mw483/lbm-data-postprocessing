"""
Particle concentration statistics from the C++ "basic" post-processing, every run of a run set
(run_sets.yaml, --set NAME).

Reads <lbm_results>/<run>/particle_postprocess/<start>-<end>_basic/ (one folder per window) and turns the
summed counts into number concentrations C = count / (snapshots x cell volume) [particles / m^3].

Windows (outputs, 0.8 s each; release starts at output 1200 = 960 s):
  FULL_WINDOW    the whole release window, includes the stage where the plume still fills the domain
  STEADY_WINDOW  after the convective plume has reached a steady particle number
  BLOCKS         equal sub-windows of STEADY_WINDOW; their spread gives error bars

Writes to <figures>/<set>/particle_density/ (with runs.yaml):
  particle_count.png                N(t) of both cases, windows shaded
  concentration_profiles.png        horizontal-mean C(z) per case: full, steady and block windows
  concentration_along_x.png         y-mean C(x) at HEIGHTS: steady window with block min..max band, full dashed
  xz_slab_<y>m_steady.png           C on the xz slab (log colour scale shared by the cases)
  count_summary.csv                 N statistics, trend and residence time per case and window
  vertical_stats.csv                mean height, sigma_z, 50/90/99 % heights per case and window
  along_x.csv                       the along-x curves with block std / sem and spanwise CV
"""
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd

from data_loaders.local_paths import load_local_paths, particle_postprocess_dir
from data_loaders.run_sets import parse_set_args, set_output_dir, write_manifest
from data_loaders.particle_postprocess import (
    cell_centres, list_density, list_windows, read_density, read_log_settings, read_profile, read_total_num,
)
from physics_core.particle_density import (
    block_stats, concentration, count_summary, profile_concentration, release_rate, slab_cell_volume,
    spanwise_stats, vertical_stats,
)
from plotting_core.heatmap_plots import plot_xz_heatmaps
from plotting_core.particle_density_plots import plot_along_x, plot_concentration_profiles, plot_particle_count

# =============================================================================
# Settings
# =============================================================================
FULL_WINDOW = (1200, 1800)
STEADY_WINDOW = (1500, 1800)
BLOCKS = [(1500, 1600), (1600, 1700), (1700, 1800)]   # as run; neighbours share their end output
RELEASE_PER_OUTPUT = 2816   # sources, one particle each per release (case.yaml sources grid)
RELEASE_EVERY = 1           # releases every this many outputs (generate_step / pout = 100 / 100)
DT_OUTPUT = 0.8             # s per output (dt 0.008 s x pout 100, case_resolved.yaml)
SOURCE_X = (8.0, 704.0)     # x range of the source grid [m], marked on the along-x figure
HEIGHTS = (2, 10, 20, 50)   # xy slabs for the along-x figure [m]
PROFILE_ZMAX = 400.0        # top of the profile figure [m]
XZ_ZMAX = 300.0             # top of the xz slab figure [m]


def label(window):
    return f"{window[0]}-{window[1]} ({window[0] * DT_OUTPUT:.0f}-{window[1] * DT_OUTPUT:.0f} s)"


def load_case(pp_dir):
    """{window: (folder, settings)} for the windows the script needs; stops if one is missing."""
    found = list_windows(pp_dir)
    need = [FULL_WINDOW, STEADY_WINDOW, *BLOCKS]
    missing = [w for w in need if w not in found]
    if missing:
        raise FileNotFoundError(f"[ERROR] {pp_dir} has no window folder for {missing}; found {list(found)}")
    return {w: (found[w], read_log_settings(found[w])) for w in need}


def check_snapshots(case, windows):
    for w, (_, s) in windows.items():
        expected = w[1] - w[0] + 1
        if s["n_snapshots"] != expected:
            print(f"[WARNING] {case} {w}: log lists {s['n_snapshots']} snapshots, window spans {expected}")


def count_part(cases, rate, out_dir):
    series, rows = {}, []
    for case, windows in cases.items():
        full_dir = windows[FULL_WINDOW][0]
        tn = read_total_num(full_dir)
        series[case] = (tn["output"] * DT_OUTPUT, tn["n_particles"])
        for w, (folder, _) in windows.items():
            rows.append(count_summary(read_total_num(folder), DT_OUTPUT, rate).rename(None)
                        .to_frame().T.assign(case=case, window=label(w)))
    plot_particle_count(
        series, out_dir / "particle_count.png",
        spans=[(STEADY_WINDOW[0] * DT_OUTPUT, STEADY_WINDOW[1] * DT_OUTPUT, "steady window")],
        lines=[(FULL_WINDOW[0] * DT_OUTPUT, "release starts")],
        title=f"Particles in the domain (release {rate:.0f} particles/s)",
    )
    table = pd.concat(rows, ignore_index=True)
    table.to_csv(out_dir / "count_summary.csv", index=False)
    return table


def profile_part(cases, out_dir):
    panels, rows = {}, []
    styles = {FULL_WINDOW: {"color": "0.3", "linestyle": "--", "linewidth": 1.2},
              STEADY_WINDOW: {"color": "C0", "linewidth": 1.8}}
    for case, windows in cases.items():
        lines = {}
        for i, (w, (folder, s)) in enumerate(windows.items()):
            prof = read_profile(folder, s["dX"])
            c = profile_concentration(prof, s["n_snapshots"], s["dX"])
            style = styles.get(w, {"color": f"C{i}", "linewidth": 0.8, "alpha": 0.8})
            lines[label(w)] = (prof["z"], c, style)
            rows.append({"case": case, "window": label(w), **vertical_stats(prof["z"], prof["count"])})
        panels[case] = lines
    plot_concentration_profiles(panels, out_dir / "concentration_profiles.png", zmax=PROFILE_ZMAX,
                                title="Horizontal-mean particle concentration")
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "vertical_stats.csv", index=False)
    return table


def slab_concentration(folder, settings, family, position):
    vol = slab_cell_volume(settings["dX"], settings["H_AVE"])
    return concentration(read_density(folder, family, position), settings["n_snapshots"], vol)


def along_x_part(cases, out_dir):
    heights = [h for h in HEIGHTS
               if all(h in list_density(ws[w][0], "xy") for ws in cases.values() for w in ws)]
    if not heights:
        print("[WARNING] no xy slab of HEIGHTS is in every window; along-x part skipped")
        return None
    panels, rows = {}, []
    for h in heights:
        panel = {}
        for case, windows in cases.items():
            planes = {w: slab_concentration(folder, s, "xy", h) for w, (folder, s) in windows.items()}
            x = cell_centres(planes[STEADY_WINDOW].shape[1], windows[STEADY_WINDOW][1]["dX"])
            steady, _, span_cv = spanwise_stats(planes[STEADY_WINDOW])
            full = planes[FULL_WINDOW].mean(axis=0)
            block_means = [planes[b].mean(axis=0) for b in BLOCKS]
            bs = block_stats(block_means)
            panel[case] = {"x": x, "steady": steady, "full": full,
                           "lo": np.min(block_means, axis=0), "hi": np.max(block_means, axis=0)}
            rows.append(pd.DataFrame({
                "case": case, "z": h, "x": x, "C_full": full, "C_steady": steady,
                "C_block_mean": bs["mean"], "C_block_std": bs["std"], "C_block_sem": bs["sem"],
                "block_cv": bs["cv"], "spanwise_cv_steady": span_cv,
            }))
        panels[f"z = {h} m"] = panel
    plot_along_x(panels, out_dir / "concentration_along_x.png", source_x=SOURCE_X,
                 title=f"y-mean concentration; band = block min..max of {len(BLOCKS)} blocks")
    table = pd.concat(rows, ignore_index=True)
    table.to_csv(out_dir / "along_x.csv", index=False)
    return table


def xz_part(cases, out_dir):
    positions = set.intersection(*(set(list_density(ws[STEADY_WINDOW][0], "xz")) for ws in cases.values()))
    for y in sorted(positions):
        panels = {}
        for case, windows in cases.items():
            folder, s = windows[STEADY_WINDOW]
            c = slab_concentration(folder, s, "xz", y)
            panels[case] = np.where(c > 0, c, np.nan)
        any_case = next(iter(cases.values()))[STEADY_WINDOW][1]
        nz, nx = next(iter(panels.values())).shape
        x, z = cell_centres(nx, any_case["dX"]), cell_centres(nz, any_case["dX"])
        keep = z <= XZ_ZMAX
        panels = {k: v[keep] for k, v in panels.items()}
        positive = np.concatenate([v[np.isfinite(v)] for v in panels.values()])
        norm = LogNorm(vmin=positive.min(), vmax=positive.max())
        plot_xz_heatmaps(panels, x, z[keep], norm, "viridis", r"C [m$^{-3}$]",
                         out_dir / f"xz_slab_{y}m_steady.png",
                         title=f"Concentration on the xz slab y = {y} m, {label(STEADY_WINDOW)}",
                         panel_size=(7.0, 3.0))


def main():
    set_name, runs = parse_set_args(__doc__)
    paths = load_local_paths()
    out_dir = set_output_dir(paths, set_name, "particle_density")
    rate = release_rate(RELEASE_PER_OUTPUT, DT_OUTPUT * RELEASE_EVERY)

    cases = {case: load_case(particle_postprocess_dir(paths, run)) for case, run in runs.items()}
    for case, windows in cases.items():
        check_snapshots(case, windows)

    counts = count_part(cases, rate, out_dir)
    vertical = profile_part(cases, out_dir)
    along = along_x_part(cases, out_dir)
    xz_part(cases, out_dir)

    pd.set_option("display.width", 160)
    print(f"Release rate {rate:.0f} particles/s ({RELEASE_PER_OUTPUT} every {DT_OUTPUT * RELEASE_EVERY:g} s)")
    print(counts[["case", "window", "n_mean", "trend_vs_rate", "residence_time_s"]].round(4).to_string(index=False))
    print(vertical.round(1).to_string(index=False))
    if along is not None:
        print("Median block CV and spanwise CV of y-mean C over x (steady window):")
        print(along.groupby(["case", "z"])[["block_cv", "spanwise_cv_steady"]].median().round(3).to_string())
    write_manifest(out_dir, set_name, runs, inputs={k: particle_postprocess_dir(paths, r) for k, r in runs.items()})
    print(f"[SUCCESS] Outputs saved to: {out_dir}")


if __name__ == "__main__":
    main()
