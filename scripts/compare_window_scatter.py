"""
Is the difference between runs larger than the noise of one 200 s averaging window?

For every run of a run set (run_sets.yaml, --set NAME) this reads the prof<step>_<rank>.csv windows,
and for each quantity compares
  - the run-to-run spread in each window (max - min over the runs; |a - b| for two runs), with
  - the window-to-window change inside each run, |Q(window k) - Q(window k-1)|.
The second is the sampling noise of one window plus the slow trend of the flow, so it is an upper bound
of the noise; a run-to-run spread of the same size is what two random seeds of the same setup give.
With more than two runs the spread is a range, which grows with the number of runs, so compare it with
care (the pairwise check is the clean one).
See physics_core/window_scatter.py.

What it measures: how far apart the horizontal-mean profiles of the runs are, against how much one
  run's profile moves from one window to the next.
Why: the purpose is a code/run check. Runs 20261011 and 20261026 used the same build parameters but
  different random initial disturbances, and their upper-level <w'w'> and <u'w'> differ late in the run.
  Within-run scatter is the cheapest noise estimate from data we already have (a seed ensemble is the
  thorough alternative).
Reference expectation: none published for this domain. For orientation, sampling errors of CBL
  variances over averages shorter than a few large-eddy times are tens of percent (Lenschow, Mann &
  Kristensen 1994, J. Atmos. Ocean. Tech. 11, 661-673) [U].
Units and sample: the quantity's own units (m/s, m^2/s^2, K m/s), no normalisation; each window is a
  200 s time mean over the whole horizontal domain (ranks averaged); the layer means average the levels
  in ZBAND.

Writes to <figures>/<set>/window_scatter/:
  window_scatter_vs_time.png    layer mean (ZBAND) of the spread and of each run's change, per window
  window_scatter_step<step>.png profiles of the same at one window (default: the last common one)
  window_scatter.csv            all values: quantity, kind (between / within), run, step, time, z, value
  runs.yaml
"""
import argparse

import matplotlib.pyplot as plt
import pandas as pd

from data_loaders.lbm_output import domain_profile, list_steps, load_prof
from data_loaders.local_paths import load_local_paths, wind_dir
from data_loaders.run_sets import add_set_argument, get_run_set, set_output_dir, write_manifest
from physics_core.moments import profile_moments
from physics_core.window_scatter import between_run_spread, layer_mean, quantity_table, within_run_change
from plotting_core.profile_plots import plot_profile_panels

# =============================================================================
# Settings
# =============================================================================
QUANTITIES = [
    # (column of physics_core.moments.profile_moments, label)
    ("U", "U [m/s]"),
    ("var_u", r"$\langle u'u' \rangle$ [m$^2$/s$^2$]"),
    ("var_w", r"$\langle w'w' \rangle$ [m$^2$/s$^2$]"),
    ("cov_uw", r"$\langle u'w' \rangle$ [m$^2$/s$^2$]"),
    ("flux_wt", r"$\langle w'\theta' \rangle$ [K m/s]"),
]
ZBAND = (100.0, 400.0)  # layer for the time series [m]: above the surface layer, inside the mixed layer
ZMAX = 1000.0           # top of the profile plots [m]
BETWEEN = "between runs"


def window_profiles(run_dir):
    """{step: (time [s], central-moment DataFrame)} for every averaging window of one run."""
    out = {}
    for step in list_steps(run_dir, "prof"):
        dom = domain_profile(load_prof(run_dir, step))
        out[step] = (float(dom["time"].iloc[0]), profile_moments(dom))
    return out


def long_rows(table, quantity, kind, run, times):
    """Quantity table (index z, columns steps) -> long rows for the CSV."""
    df = table.rename_axis("z").reset_index().melt(id_vars="z", var_name="step", value_name="value")
    return df.assign(quantity=quantity, kind=kind, run=run, time=df["step"].map(times))


def main():
    p = add_set_argument(argparse.ArgumentParser(description=__doc__,
                                                 formatter_class=argparse.RawDescriptionHelpFormatter))
    p.add_argument("--step", type=int, help="window (output step) of the profile figure; default the last common one")
    args = p.parse_args()
    set_name, runs = get_run_set(args.run_set)
    if len(runs) < 2:
        raise ValueError(f"[ERROR] set {set_name} has {len(runs)} run; the spread needs at least 2")
    paths = load_local_paths()
    out_dir = set_output_dir(paths, set_name, "window_scatter")

    windows, times = {}, {}
    for label, folder in runs.items():
        windows[label] = window_profiles(wind_dir(paths, folder))
        if not windows[label]:
            raise FileNotFoundError(f"[ERROR] no prof*.csv in {folder}")
        times.update({s: t for s, (t, _) in windows[label].items()})
        print(f"{label}: {len(windows[label])} windows")

    colors = {BETWEEN: "black"}
    colors.update({label: f"C{i}" for i, label in enumerate(runs)})
    rows, between, within = [], {}, {}
    for q, _ in QUANTITIES:
        tables = {label: quantity_table(w, q) for label, w in windows.items()}
        between[q] = between_run_spread(tables)
        within[q] = {label: within_run_change(t) for label, t in tables.items()}
        rows.append(long_rows(between[q], q, "between", "all", times))
        rows += [long_rows(t, q, "within", label, times) for label, t in within[q].items()]
    pd.concat(rows, ignore_index=True)[["quantity", "kind", "run", "step", "time", "z", "value"]].to_csv(
        out_dir / "window_scatter.csv", index=False)

    # Time series of the layer means
    fig, axes = plt.subplots(1, len(QUANTITIES), figsize=(3.2 * len(QUANTITIES), 3.6), squeeze=False)
    for ax, (q, label) in zip(axes[0], QUANTITIES):
        s = layer_mean(between[q], ZBAND)
        ax.plot([times[k] for k in s.index], s.values, "o-", color="black", label=BETWEEN)
        for run, t in within[q].items():
            s = layer_mean(t, ZBAND)
            ax.plot([times[k] for k in s.index], s.values, "s--", color=colors[run], label=f"{run}: change from previous window")
        ax.set_xlabel("window end t [s]")
        ax.set_title(label, fontsize=9)
        ax.grid(True, linestyle=":", alpha=0.5)
    axes[0][0].set_ylabel(f"mean over {ZBAND[0]:.0f}-{ZBAND[1]:.0f} m")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False, bbox_to_anchor=(0.5, 1.08))
    fig.tight_layout()
    save = out_dir / "window_scatter_vs_time.png"
    fig.savefig(save, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[SUCCESS] Figure saved to: {save}")

    # Profiles at one window
    common = list(between[QUANTITIES[0][0]].columns)
    step = args.step if args.step is not None else common[-1]
    if step not in common:
        raise KeyError(f"[ERROR] step {step} is not a window of every run; common windows: {common}")
    lines = {BETWEEN: pd.DataFrame({"z": between[q].index for q, _ in QUANTITIES[:1]})}
    for q, _ in QUANTITIES:
        lines[BETWEEN][q] = between[q][step].to_numpy()
    for run in runs:
        df = pd.DataFrame({"z": within[QUANTITIES[0][0]][run].index})
        for q, _ in QUANTITIES:
            if step in within[q][run]:
                df[q] = within[q][run][step].to_numpy()
        lines[run] = df
    save = out_dir / f"window_scatter_step{step:08d}.png"
    plot_profile_panels(lines, QUANTITIES, save, zmax=ZMAX, colors=colors,
                        styles={run: "--" for run in runs},
                        title=f"Run-to-run spread (solid) vs change from the previous window (dashed), "
                              f"window ending t = {times[step]:.0f} s")
    print(f"[SUCCESS] Figure saved to: {save}")
    write_manifest(out_dir, set_name, runs, inputs={k: wind_dir(paths, r) for k, r in runs.items()})


if __name__ == "__main__":
    main()
