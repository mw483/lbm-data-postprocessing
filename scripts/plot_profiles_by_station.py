"""
Profiles of U, sigma_u, sigma_v, sigma_w and <u'w'> at several x stations along the domain, per averaging window.

What it measures: how the wind and its fluctuations change with height at a few positions along the
    domain, next to the domain mean.
Why: a code and sampling check. On a flat, periodic domain every station should give the same profile,
    so the spread between stations shows how noisy one 200 s window is (convective cells are a few
    hundred metres wide, the domain only 256 m in y). That spread is the error bar for the domain-mean
    profiles and the CBL scales; a spread well above it points to a real change along x (wind decay,
    sponge, boundaries).
Reference: horizontal homogeneity (all stations equal); there is no published value for the spread.
Units and sample: m/s and m^2/s^2, not normalised. Each station = the y-averaged plane (xz_yav_*)
    averaged over +-HALF_WIDTH in x (raw moments averaged first, then central moments formed, so the
    station is one sampling region). Domain mean = prof*.csv (all x and y). One 200 s solver window per figure.

Stations default to the yz output planes of the run (iout in header.txt). As a reader check the script
also compares the y-average of each yz plane with the xz_yav column at the same x and prints the
largest difference (both are written with 6 decimals, so it should be ~1e-6).

Runs = a run set (run_sets.yaml, --set NAME); output in <figures>/<set>/station_profiles/<run label>/.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loaders.lbm_output import domain_profile, list_steps, load_plane, load_prof, read_header_txt
from data_loaders.local_paths import load_local_paths, wind_dir
from data_loaders.run_sets import parse_set_args, set_output_dir, write_manifest
from physics_core.moments import plane_moments, profile_moments, sigma
from plotting_core.profile_plots import plot_profile_grid

# =============================================================================
# Settings
# =============================================================================
HALF_WIDTH = 64.0       # half width [m] of the x band averaged around each station
STATIONS_M = None       # station x positions [m]; None = the yz planes of the run (iout in header.txt)
ZMAX = 1000.0           # top of the plots [m]
RAW = ("um", "vm", "wm", "uu", "vv", "ww")
RAW_OPTIONAL = ("uw",)  # <u'w'> panel stays empty when the run has no xz_yav_uw files
PANELS = [("U", "U [m/s]"), ("sigma_u", r"$\sigma_u$ [m/s]"), ("sigma_v", r"$\sigma_v$ [m/s]"),
          ("sigma_w", r"$\sigma_w$ [m/s]"), ("cov_uw", r"$\langle u'w' \rangle$ [m$^2$/s$^2$]")]
DOMAIN = "domain mean (prof)"


def station_positions(header):
    """x [m] of the yz output planes: cell centres of the one-based global cells in iout."""
    iout = header["iout"] if isinstance(header["iout"], list) else [header["iout"]]
    return [float(header["xg_min"]) + (i - 0.5) * float(header["dx"]) for i in iout]


def station_table(fields, x, z, xs, half_width):
    """Profile at station xs: raw moments averaged over |x - xs| <= half_width, then central moments."""
    band = np.abs(x - xs) <= half_width
    raw = {k: np.nanmean(v[:, band], axis=1) for k, v in fields.items()}
    m = plane_moments(raw)
    return pd.DataFrame({"z": z, "U": m["U"], "sigma_u": sigma(m["var_u"]), "sigma_v": sigma(m["var_v"]),
                         "sigma_w": m["sigma_w"], "cov_uw": m.get("cov_uw", np.full(len(z), np.nan))})


def yz_check(run_dir, step, header, fields, x):
    """Largest |y-average of yz_um - xz_yav_um column| over the yz planes of this step (None if no yz files)."""
    if step not in list_steps(run_dir, "yz_um"):
        return None
    yz = load_plane(run_dir, "yz_um", step, header)
    diffs = []
    for label, arr in yz.data.items():
        col = int(np.argmin(np.abs(x - yz.labels_m[label])))
        n = min(arr.shape[1], fields["um"].shape[0])
        diffs.append(np.nanmax(np.abs(np.nanmean(arr, axis=0)[:n] - fields["um"][:n, col])))
    return max(diffs)


def main():
    set_name, run_names = parse_set_args(__doc__)
    paths = load_local_paths()
    out_root = set_output_dir(paths, set_name, "station_profiles")
    inputs, tables = {}, []

    for label, run in run_names.items():
        run_dir = inputs[label] = wind_dir(paths, run)
        header = read_header_txt(run_dir)
        stations = STATIONS_M or station_positions(header)
        t_ave = float(header["t_ave"])
        out_dir = out_root / label
        steps = sorted(set(list_steps(run_dir, "xz_yav_um")) & set(list_steps(run_dir, "prof")))
        spread = {}
        for step in steps:
            names = RAW + tuple(k for k in RAW_OPTIONAL if step in list_steps(run_dir, f"xz_yav_{k}"))
            planes = {k: load_plane(run_dir, f"xz_yav_{k}", step, header) for k in names}
            first = planes["um"]
            x, z = first.coords["x"], first.coords["z"]
            fields = {k: p.data[0] for k, p in planes.items()}
            window = f"window {first.time - t_ave:.0f}-{first.time:.0f} s"

            profiles = {f"x = {xs:.0f} m": station_table(fields, x, z, xs, HALF_WIDTH) for xs in stations}
            profiles[DOMAIN] = profile_moments(domain_profile(load_prof(run_dir, step))).assign(
                sigma_u=lambda d: sigma(d["var_u"]), sigma_v=lambda d: sigma(d["var_v"]))
            save = out_dir / f"station_profiles_step{step:08d}.png"
            plot_profile_grid(profiles, [PANELS], save, zmax=ZMAX, colors={DOMAIN: "k"}, styles={DOMAIN: "--"},
                              title=f"{label}: profiles at x stations (+-{HALF_WIDTH:g} m), {window}")
            print(f"[SUCCESS] Figure saved to: {save}")

            stack = pd.concat([d.assign(station=k) for k, d in profiles.items() if k != DOMAIN])
            spread[f"{first.time - t_ave:.0f}-{first.time:.0f} s"] = (
                stack.groupby("z")[[c for c, _ in PANELS]].std().reset_index())
            tables.append(pd.concat([d.assign(station=k) for k, d in profiles.items()])
                          [["station", "z"] + [c for c, _ in PANELS]].assign(case=label, step=step, time=first.time))
            diff = yz_check(run_dir, step, header, fields, x)
            if diff is not None:
                print(f"[CHECK] {label} step {step}: max |mean_y(yz_um) - xz_yav_um| = {diff:.2e} m/s")

        save = out_dir / "station_spread.png"
        rows = [[(c, f"std over stations of {lab}") for c, lab in PANELS]]
        colors = dict(zip(spread, plt.cm.viridis(np.linspace(0, 0.9, len(spread)))))
        plot_profile_grid(spread, rows, save, zmax=ZMAX, colors=colors,
                          title=f"{label}: spread between the {len(stations)} stations, per window")
        print(f"[SUCCESS] Figure saved to: {save}")

    save = out_root / "station_profiles.csv"
    pd.concat(tables, ignore_index=True).to_csv(save, index=False)
    print(f"[SUCCESS] Table saved to: {save}")
    write_manifest(out_root, set_name, run_names, inputs=inputs)


if __name__ == "__main__":
    main()
