"""
Time-averaged velocities and Reynolds stresses against height, after the profile figures of Chang et al. (2009):
x direction (U, <u'u'>), y direction (V, <v'v'>), z direction (W, <w'w'>), plus the shear stress <u'w'>.

Domain-mean profiles from prof<step>_<rank>.csv (full precision; ranks averaged, raw moments turned into
central moments). One figure per averaging window that all cases share, cases overlaid, written twice:
as is [m/s, m^2/s^2] and normalised by the inflow velocity Ub (U/Ub, stress/Ub^2).
"""
import pandas as pd

from data_loaders.lbm_output import domain_profile, list_steps, load_prof, read_header_txt
from data_loaders.local_paths import load_local_paths, wind_dir
from physics_core.moments import profile_moments
from plotting_core.profile_plots import plot_profile_grid

# =============================================================================
# Settings
# =============================================================================
CASES = {
    # label: run as "<case>/<date>_<tag>"; its wind CSV are in <lbm_results>/<run>/output (local_paths.yaml)
    "convective": "flat_512x128x1024/20261011_scalar2",
    "neutral": "flat_512x128x1024/20261017_neutral",
}
UB = 5.0                # inflow (initial) velocity [m/s] used for the normalised figure
ZMAX = 1000.0           # top of the plots [m]
# Panels: (column of profile_moments, axis label, power of Ub it is divided by in the normalised figure)
ROWS = [
    [("U", "U", 1), ("V", "V", 1), ("W", "W", 1), None],
    [("var_u", r"$\langle u'u' \rangle$", 2), ("var_v", r"$\langle v'v' \rangle$", 2),
     ("var_w", r"$\langle w'w' \rangle$", 2), ("cov_uw", r"$\langle u'w' \rangle$", 2)],
]
UNITS = {1: "[m/s]", 2: r"[m$^2$/s$^2$]"}


def scaled(df, ub):
    """Copy of a profile_moments table with every plotted column divided by ub^power."""
    out = df.copy()
    for row in ROWS:
        for spec in filter(None, row):
            col, _, power = spec
            out[col] = df[col] / ub**power
    return out


def panel_rows(normalised):
    """ROWS as (column, axis label) for plot_profile_grid, with units or the Ub normalisation."""
    def label(name, power):
        return f"{name} / $U_b^{power}$" if normalised else f"{name} {UNITS[power]}"
    return [[None if s is None else (s[0], label(s[1], s[2]).replace("$U_b^1$", "$U_b$")) for s in row]
            for row in ROWS]


def main():
    paths = load_local_paths()
    out_dir = paths["figures"] / "scalar2_outputs" / "velocity_stress_profiles"
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = {label: wind_dir(paths, run) for label, run in CASES.items()}
    steps = sorted(set.intersection(*(set(list_steps(d, "prof")) for d in runs.values())))
    if not steps:
        raise FileNotFoundError("[ERROR] the cases share no prof*.csv output step")
    t_ave = float(read_header_txt(next(iter(runs.values())))["t_ave"])

    tables = []
    for step in steps:
        domain = {label: domain_profile(load_prof(d, step)) for label, d in runs.items()}
        profiles = {label: profile_moments(df) for label, df in domain.items()}
        t_end = float(next(iter(domain.values()))["time"].iloc[0])
        window = f"window {t_end - t_ave:.0f}-{t_end:.0f} s"
        for normalised, suffix in ((False, ""), (True, "_normalised")):
            lines = {k: scaled(v, UB) if normalised else v for k, v in profiles.items()}
            save = out_dir / f"velocity_stress_step{step:08d}{suffix}.png"
            title = f"Time-averaged velocities and Reynolds stresses, {window}"
            title += f", normalised by $U_b$ = {UB:g} m/s" if normalised else ""
            plot_profile_grid(lines, panel_rows(normalised), save, title=title, zmax=ZMAX)
            print(f"[SUCCESS] Figure saved to: {save}")
        tables += [df.assign(case=k, step=step, time=t_end) for k, df in profiles.items()]

    save = out_dir / "velocity_stress_profiles.csv"
    pd.concat(tables, ignore_index=True).to_csv(save, index=False)
    print(f"[SUCCESS] Table saved to: {save}")


if __name__ == "__main__":
    main()
