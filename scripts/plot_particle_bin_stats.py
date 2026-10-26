"""
Lagrangian particle statistics from reduce_particle_bins.py output, every run of a run set (run_sets.yaml).

Reads <run>/particle_reduced/reduced.npz below lbm_reduced or lbm_results (copy of the folder written on
TSUBAME) and the solver profiles in <lbm_results>/<run>/output for the Eulerian comparison (a run without
that folder is left out of the Eulerian lines only). Writes to <figures>/<set>/particle_bins/:
  dispersion_vs_age.png       mean height, sigma_z, mean downwind travel, sigma_x against particle age
  dispersion_vs_age_cbl.png   runs with a convective scale, each scaled by its own z_i and w*
  z_pdf_vs_age.png            PDF of particle height at each age (log colour), mean height in white
  velocity_profiles.png       particle sigma_w and mean u (total and SGS part) against the Eulerian profiles
  sgs_along_x.png             SGS energy and mean height of near-ground particles along x, GPU rank edges dotted
  dispersion_vs_age.csv, velocity_profiles.csv, sgs_along_x.csv, runs.yaml

Usage:
  python -m scripts.plot_particle_bin_stats                       # default set of run_sets.yaml
  python -m scripts.plot_particle_bin_stats --set flat512_sgsfix
"""
import numpy as np
import pandas as pd

from data_loaders.lbm_output import domain_profile, load_prof
from data_loaders.local_paths import load_local_paths, particle_reduced_dir, wind_dir
from data_loaders.run_sets import parse_set_args, set_output_dir, write_manifest
from physics_core.moments import convective_scales, profile_moments
from physics_core.particle_bin_stats import age_histograms, age_stats, height_stats, load_reduced, x_stats
from plotting_core.particle_bin_plots import plot_age_pdf, plot_lines_grid, plot_profiles

# =============================================================================
# Settings
# =============================================================================
PROF_STEP = 175001          # solver profile window for the Eulerian comparison (200 s ending at 1400 s)
THETA0 = 300.0              # reference potential temperature [K] for w* (header out_ref)
MIN_COUNT = 2000            # age bins with fewer particle samples are not plotted
RANK_EDGES = (256.0, 512.0, 768.0)   # x of the GPU rank boundaries [m] (4 ranks over 1024 m)
ZMAX_PDF = 500.0            # top of the PDF figure [m]
ZMAX_PROFILE = 500.0        # top of the velocity profile figure [m]


def main():
    set_name, runs = parse_set_args(__doc__)
    paths = load_local_paths()
    out_dir = set_output_dir(paths, set_name, "particle_bins")

    data, meta, reduced = {}, {}, {}
    for case, run in runs.items():
        reduced[case] = particle_reduced_dir(paths, run)
        print(f"{case}: {reduced[case]}")
        meta[case], data[case] = load_reduced(reduced[case] / "reduced.npz")
        print(f"{case}: outputs {meta[case]['first_read']}-{meta[case]['last_read']} "
              f"({meta[case]['outputs_read']} read), {meta[case]['n_upstream_sources']} upstream sources")
    dt = {c: float(m["dt_output"]) for c, m in meta.items()}

    # Ages ------------------------------------------------------------------------------------
    stats, tables = {}, []
    for case, d in data.items():
        s = age_stats(d)
        age = np.arange(s["count"].size) * dt[case]
        keep = s["count"] >= MIN_COUNT
        stats[case] = {k: np.where(keep, v, np.nan) for k, v in s.items()}
        stats[case]["age"] = age
        tables.append(pd.DataFrame({"case": case, "age_s": age, **s}))
    pd.concat(tables).to_csv(out_dir / "dispersion_vs_age.csv", index=False)
    panels = [(label, {c: (s["age"], s[key]) for c, s in stats.items()}) for key, label in (
        ("z_mean", "mean height [m]"), ("sigma_z", r"$\sigma_z$ [m]"),
        ("dx_mean", r"mean $x - x_{source}$ [m]"), ("sigma_dx", r"$\sigma_x$ [m]"))]
    upstream = meta[next(iter(meta))]["upstream_xmax"]
    plot_lines_grid(panels, out_dir / "dispersion_vs_age.png", xlabel="particle age [s]",
                    title=f"Particles from sources with x <= {upstream:g} m")

    hists = {}
    for case, d in data.items():
        hz, _ = age_histograms(d)
        z_edges = d["age_z_edges"]
        hists[case] = hz
    z = 0.5 * (z_edges[1:] + z_edges[:-1])
    any_case = next(iter(stats))
    keep_age = np.isfinite(stats[any_case]["z_mean"])
    age_axis = stats[any_case]["age"][keep_age]
    plot_age_pdf({c: h[keep_age] for c, h in hists.items()}, age_axis, z, out_dir / "z_pdf_vs_age.png",
                 zmax=ZMAX_PDF, title="Particle height distribution against age",
                 overlay={c: (s["age"], s["z_mean"]) for c, s in stats.items()})

    # Eulerian profiles and convective scaling --------------------------------------------------
    euler = {}
    for case, run in runs.items():
        if not wind_dir(paths, run).is_dir():
            print(f"[WARNING] {case}: no {wind_dir(paths, run)}; left out of the Eulerian and CBL-scaled lines")
            continue
        euler[case] = profile_moments(domain_profile(load_prof(wind_dir(paths, run), PROF_STEP)))
    scaled = {}
    for case, m in euler.items():
        zi, wstar, flux = convective_scales(m, THETA0)
        print(f"{case}: surface heat flux {flux:.4f} K m/s, z_i {zi:.0f} m, w* {wstar:.3f} m/s")
        if np.isfinite(wstar):
            scaled[case] = (zi, wstar)
    if scaled:   # one figure, every run with a convective scale, each scaled by its own z_i and w*
        lines = {f"{c} (z_i {zi:.0f} m, w* {ws:.2f} m/s)": (stats[c]["age"] * ws / zi, c) for c, (zi, ws) in scaled.items()}
        plot_lines_grid(
            [(r"$\bar z / z_i$", {k: (t, stats[c]["z_mean"] / scaled[c][0]) for k, (t, c) in lines.items()}),
             (r"$\sigma_z / z_i$", {k: (t, stats[c]["sigma_z"] / scaled[c][0]) for k, (t, c) in lines.items()})],
            out_dir / "dispersion_vs_age_cbl.png", xlabel=r"$t\,w_* / z_i$",
            title=f"Convective scaling, profile step {PROF_STEP}")

    # Particle velocities against height ----------------------------------------------------------
    lines_w, lines_u, rows = {}, {}, []
    for i, (case, d) in enumerate(data.items()):
        h = height_stats(d)
        ok = h["count"] >= MIN_COUNT
        z_p = h["z"][ok]
        color = f"C{i}"
        rows.append(pd.DataFrame({"case": case, **h}))
        lines_w[f"{case} particle total"] = (h["sigma_w"][ok], z_p, {"color": color, "linewidth": 1.6})
        lines_w[f"{case} particle SGS"] = (h["sigma_ws"][ok], z_p, {"color": color, "linestyle": ":", "linewidth": 1.4})
        lines_u[f"{case} particle"] = (h["u_mean"][ok], z_p, {"color": color, "linewidth": 1.6})
        if case in euler:
            lines_w[f"{case} Eulerian resolved"] = (euler[case]["sigma_w"], euler[case]["z"],
                                                    {"color": color, "linestyle": "--", "linewidth": 1.0})
            lines_u[f"{case} Eulerian"] = (euler[case]["U"], euler[case]["z"],
                                           {"color": color, "linestyle": "--", "linewidth": 1.0})
    pd.concat(rows).to_csv(out_dir / "velocity_profiles.csv", index=False)
    plot_profiles([(r"$\sigma_w$ [m/s]", lines_w), ("mean u [m/s]", lines_u)], out_dir / "velocity_profiles.png",
                  zmax=ZMAX_PROFILE, title="Velocities seen by the particles vs the flow statistics")

    # SGS along x (rank-boundary check) -----------------------------------------------------------
    xs = {c: x_stats(d) for c, d in data.items()}
    ztop = float(data[any_case]["x_z_top"])
    plot_lines_grid(
        [(r"SGS energy $\frac{1}{2}\overline{u_s^2+v_s^2+w_s^2}$ [m$^2$/s$^2$]", {c: (s["x"], s["e_sgs"]) for c, s in xs.items()}),
         ("fraction with zero SGS velocity", {c: (s["x"], s["zero_fraction"]) for c, s in xs.items()}),
         ("mean height [m]", {c: (s["x"], s["z_mean"]) for c, s in xs.items()}),
         ("particle samples", {c: (s["x"], s["count"]) for c, s in xs.items()})],
        out_dir / "sgs_along_x.png", xlabel="x [m]", vlines=RANK_EDGES,
        title=f"Particles below {ztop:g} m; dotted = GPU rank boundaries")
    pd.concat([pd.DataFrame({"case": c, **s}) for c, s in xs.items()]).to_csv(out_dir / "sgs_along_x.csv", index=False)
    write_manifest(out_dir, set_name, runs, inputs=reduced)
    print(f"[SUCCESS] Outputs saved to: {out_dir}")


if __name__ == "__main__":
    main()
