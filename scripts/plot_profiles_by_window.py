"""
Horizontal-mean profiles for every 200 s averaging window, convective vs neutral.

Reads prof<step>_<rank>.csv (full precision, already averaged over each rank's xy area and over the
window), averages the ranks, converts raw moments to central moments (physics_core/moments.py) and
plots:
  1. per case, one line per window (darker = later), to see when the profiles stop changing;
  2. the last common window of all cases on top of each other.
Writes the per-window statistics as CSV next to the figures.
"""

import matplotlib.pyplot as plt
import pandas as pd

from data_loaders.lbm_output import domain_profile, list_steps, load_prof
from data_loaders.local_paths import load_local_paths, wind_dir
from physics_core.moments import profile_moments
from plotting_core.profile_plots import plot_profile_panels

# =============================================================================
# Settings
# =============================================================================
CASES = {
    # label: run as "<case>/<date>_<tag>"; its wind CSV are in <lbm_results>/<run>/output (local_paths.yaml)
    "convective": "flat_512x128x1024/20261011_scalar2",
    # "neutral": "flat_512x128x1024/<date>_neutral",
}
QUANTITIES = [
    # (column of physics_core.moments.profile_moments, axis label)
    ("U", "U [m/s]"),
    ("sigma_w", r"$\sigma_w$ [m/s]"),
    ("tke", "resolved TKE [m$^2$/s$^2$]"),
    ("skew_w", r"$S_w$ [-]"),
    ("T", r"$\theta - \theta_{ref}$ [K]"),
    ("flux_wt", r"$\langle w'\theta' \rangle$ [K m/s]"),
]
ZMAX = 2048.0           # top of the plots [m]
WINDOW_CMAP = "Blues"   # one hue, light = early window, dark = late window


def window_profiles(run_dir):
    """{step: (time [s], central-moment DataFrame)} for every averaging window of one run."""
    out = {}
    for step in list_steps(run_dir, "prof"):
        dom = domain_profile(load_prof(run_dir, step))
        out[step] = (float(dom["time"].iloc[0]), profile_moments(dom))
    return out


def main():
    paths = load_local_paths()
    out_dir = paths["figures"] / "scalar2_outputs" / "profiles"
    out_dir.mkdir(parents=True, exist_ok=True)

    by_case = {}
    for label, folder in CASES.items():
        windows = window_profiles(wind_dir(paths, folder))
        if not windows:
            raise FileNotFoundError(f"[ERROR] no prof*.csv in {folder}")
        by_case[label] = windows
        print(f"{label}: {len(windows)} windows, t = {[round(t) for t, _ in windows.values()]} s")

        table = pd.concat([df.assign(step=s, time=t) for s, (t, df) in windows.items()], ignore_index=True)
        table.to_csv(out_dir / f"profiles_by_window_{label}.csv", index=False)

        cmap = plt.get_cmap(WINDOW_CMAP)
        n = len(windows)
        lines = {f"t = {t:.0f} s": df for t, df in windows.values()}
        colors = {k: cmap(0.3 + 0.7 * i / max(n - 1, 1)) for i, k in enumerate(lines)}
        plot_profile_panels(lines, QUANTITIES, out_dir / f"profiles_by_window_{label}.png",
                            title=f"{label}: horizontal means per averaging window", zmax=ZMAX, colors=colors)
        print(f"[SUCCESS] Figure saved to: {out_dir / f'profiles_by_window_{label}.png'}")

    common = set.intersection(*(set(w) for w in by_case.values()))
    if len(by_case) > 1 and common:
        step = max(common)
        lines = {label: w[step][1] for label, w in by_case.items()}
        save = out_dir / f"profiles_cases_step{step:08d}.png"
        t = next(iter(by_case.values()))[step][0]
        plot_profile_panels(lines, QUANTITIES, save, title=f"Cases compared, window ending t = {t:.0f} s", zmax=ZMAX)
        print(f"[SUCCESS] Figure saved to: {save}")
    elif len(by_case) > 1:
        print("[WARN] the cases share no output step; no comparison figure")


if __name__ == "__main__":
    main()
