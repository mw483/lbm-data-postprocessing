"""
Profiles in mixed-layer scaling (z/z_i, velocities / w*, heat flux / surface flux) next to standard CBL curves.

What it measures: the shape of the turbulence and the heat flux through the convective layer, with
    height counted in units of the layer depth and velocities in units of the thermal velocity w*.
Why: validation against theory and observations. If the LBM turbulence has the standard CBL shape, the
    particles are carried by a realistic convective flow. Mixed-layer scaling removes the depth and
    strength of each window, so windows and runs can be compared on one plot, and with field data.
Reference: <w'w'>/w*^2 = 1.8 (z/z_i)^(2/3) (1 - 0.8 z/z_i)^2 (Lenschow, Wyngaard & Pennell 1980,
    J. Atmos. Sci. 37, 1313-1326; formula [U]); <w'theta'>/flux = 1 - 1.2 z/z_i (linear flux, entrainment
    ratio 0.2, Stull 1988 [U]). <u'u'>, <v'v'> / w*^2 roughly constant (~0.3) in the mixed layer and
    positive w skewness: no curve drawn [U], reference to be found.
Units and sample: dimensionless. z_i (heat-flux minimum) and w* of the same window and run
    (physics_core.moments.cbl_scales). Domain-mean prof*.csv, one 200 s solver window per figure; one figure
    per run with every window overlaid. Runs without a positive surface heat flux (neutral) are skipped.
    S_w is hidden where <w'w'>/w*^2 < MIN_VAR_W: a ratio of two near-zero moments above the CBL.

Runs = a run set (run_sets.yaml, --set NAME); output in <figures>/<set>/cbl_normalised_profiles/.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loaders.lbm_output import domain_profile, list_steps, load_prof, read_header_txt
from data_loaders.local_paths import load_local_paths, wind_dir
from data_loaders.run_sets import parse_set_args, set_output_dir, write_manifest
from physics_core.cbl_reference import heat_flux_linear, sigma_w2_lenschow
from physics_core.moments import cbl_scales, profile_moments
from plotting_core.profile_plots import plot_profile_grid

# =============================================================================
# Settings
# =============================================================================
ZETA_MAX = 1.5          # top of the plots [z / z_i]
MIN_VAR_W = 0.01        # S_w is hidden where <w'w'>/w*^2 is below this (above the CBL it is noise / ~0)
ROWS = [[("var_w_n", r"$\langle w'w' \rangle / w_*^2$"), ("var_u_n", r"$\langle u'u' \rangle / w_*^2$"),
         ("var_v_n", r"$\langle v'v' \rangle / w_*^2$")],
        [("flux_n", r"$\langle w'\theta' \rangle / \overline{w'\theta'}_s$"), ("skew_w", "$S_w$"), None]]
ZETA_REF = np.linspace(0.0, 1.0, 101)
REFERENCES = {"var_w_n": (sigma_w2_lenschow(ZETA_REF), ZETA_REF, "Lenschow et al. 1980 [U]"),
              "flux_n": (heat_flux_linear(ZETA_REF), ZETA_REF, "linear flux, A = 0.2 [U]")}


def normalised(m, scales):
    """profile_moments table in mixed-layer scaling; "z" becomes z / z_i."""
    zi, ws, flux = scales["zi_flux"], scales["wstar"], scales["surface_flux"]
    return pd.DataFrame({"z": m["z"] / zi, "var_w_n": m["var_w"] / ws**2, "var_u_n": m["var_u"] / ws**2,
                         "var_v_n": m["var_v"] / ws**2, "flux_n": (m["flux_wt"] + m["flux_wt_model"]) / flux,
                         "skew_w": np.where(m["var_w"] / ws**2 >= MIN_VAR_W, m["skew_w"], np.nan)})


def main():
    set_name, run_names = parse_set_args(__doc__)
    paths = load_local_paths()
    out_dir = set_output_dir(paths, set_name, "cbl_normalised_profiles")
    inputs, by_step, tables = {}, {}, []
    for case, run in run_names.items():
        run_dir = inputs[case] = wind_dir(paths, run)
        header = read_header_txt(run_dir)
        theta0, t_ave = float(header.get("out_ref", 300.0)), float(header["t_ave"])
        per_window = {}
        for step in list_steps(run_dir, "prof"):
            domain = domain_profile(load_prof(run_dir, step))
            m = profile_moments(domain)
            scales = cbl_scales(m, theta0)
            if not np.isfinite(scales["wstar"]):
                print(f"[SKIP] {case} step {step}: no positive surface heat flux")
                continue
            time = float(domain["time"].iloc[0])
            n = normalised(m, scales)
            window = f"{time - t_ave:.0f}-{time:.0f} s (z_i {scales['zi_flux']:.0f} m, w* {scales['wstar']:.2f} m/s)"
            per_window[window] = n
            by_step.setdefault(step, {})[f"{case}, {window}"] = n
            tables.append(n.assign(case=case, step=step, time=time, zi=scales["zi_flux"], wstar=scales["wstar"]))
        if per_window:
            colors = dict(zip(per_window, plt.cm.viridis(np.linspace(0, 0.9, len(per_window)))))
            save = out_dir / f"cbl_normalised_all_windows_{case}.png"
            plot_profile_grid(per_window, ROWS, save, zmax=ZETA_MAX, colors=colors, ylabel="$z / z_i$",
                              references=REFERENCES, title=f"{case}: mixed-layer scaling, every window")
            print(f"[SUCCESS] Figure saved to: {save}")

    for step, profiles in sorted(by_step.items()):
        save = out_dir / f"cbl_normalised_step{step:08d}.png"
        plot_profile_grid(profiles, ROWS, save, zmax=ZETA_MAX, ylabel="$z / z_i$", references=REFERENCES,
                          title="Mixed-layer scaling against standard CBL curves")
        print(f"[SUCCESS] Figure saved to: {save}")

    if tables:
        save = out_dir / "cbl_normalised_profiles.csv"
        pd.concat(tables, ignore_index=True).to_csv(save, index=False)
        print(f"[SUCCESS] Table saved to: {save}")
    write_manifest(out_dir, set_name, run_names, inputs=inputs)


if __name__ == "__main__":
    main()
