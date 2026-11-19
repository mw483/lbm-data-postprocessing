"""
Convective boundary-layer (CBL) scales per averaging window: mixed-layer depth z_i, Deardorff velocity w*
and turnover time t*, with the theta and heat-flux profiles they come from.

What it measures: how deep the convective layer is and how fast its thermals move, window by window,
    for the whole domain and for each GPU segment (rank) along x.
Why: validation and readiness check. Particle statistics are scaled by z_i and w* (X = t w*/z_i), so we
    must know when they settle and how much they drift; the growth of z_i can be compared with theory
    before any particle is looked at. z_i is taken as the height of the heat-flux minimum (the standard
    definition) and, as a robustness check, as the height of the largest theta gradient (less noisy).
Reference: w* = (g/theta0 * flux * z_i)^(1/3) and t* = z_i/w* (Deardorff 1970; Stull 1988 Sec. 4.2,
    eqs. 4.2a/b, checked by kaka). z_i growth: zero-order jump model, z_i^2 = zi0^2 + 2 (1 + 2A) flux t / gamma,
    drawn for A = 0 (encroachment) and A = 0.2 [U] (physics_core/cbl_reference.py).
Units and sample: z_i [m], w* [m/s], t* [s]. Total heat flux = resolved <w'theta'> + model SGS flux [K m/s].
    theta0 = out_ref of header.txt. Domain = all ranks' prof*.csv averaged; segments = each rank's own
    prof*.csv (1024 m of x on the long run, 4 ranks). One point per 200 s solver window, at the window end.

Runs = a run set (run_sets.yaml, --set NAME); output in <figures>/<set>/cbl_scales/.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loaders.lbm_output import domain_profile, list_steps, load_prof, read_header_txt
from data_loaders.local_paths import load_local_paths, wind_dir
from data_loaders.run_sets import parse_set_args, set_output_dir, write_manifest
from physics_core.cbl_reference import zi_encroachment
from physics_core.moments import cbl_scales, profile_moments

# =============================================================================
# Settings (initial state and forcing of the runs, LBM-city src/Define_user.h:116-140)
# =============================================================================
ZI0 = 300.0             # top of the initial neutral layer [m] (zhigh)
GAMMA = 0.01            # lapse rate above it [K/m] (dsdz_high)
FLUX_IN = 0.1           # prescribed surface heat flux [K m/s] (flux_const)
ENTRAINMENT = (0.0, 0.2)
ZMAX = 1000.0           # top of the profile plots [m]
SCALE_COLUMNS = ["zi_flux", "zi_grad", "surface_flux", "wstar", "tstar"]
RANK_COLUMNS = ["rank", "rank_x", "rank_y", "rank_z"]


def scales_of_step(run_dir, step, theta0):
    """Rows (segment, scales) for the domain and every rank at one step, plus the domain moments table."""
    prof = load_prof(run_dir, step)
    domain = profile_moments(domain_profile(prof))
    rows = [{"segment": "domain", **cbl_scales(domain, theta0)}]
    for rank, part in prof.groupby("rank"):
        m = profile_moments(part.drop(columns=RANK_COLUMNS).sort_values("z").reset_index(drop=True))
        rows.append({"segment": f"rank {rank}", **cbl_scales(m, theta0)})
    return rows, domain, float(prof["time"].iloc[0])


def plot_scales(table, save):
    """z_i, w* and t* against time, one colour per run; domain as markers, rank segments as a min-max band."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    t_ref = np.linspace(0.0, table["time"].max(), 200)
    for i, (case, g) in enumerate(table.groupby("case", sort=False)):
        color = f"C{i}"
        dom = g[g["segment"] == "domain"]
        seg = g[g["segment"] != "domain"].groupby("time")
        for ax, col in zip(axes, ("zi_flux", "wstar", "tstar")):
            ax.plot(dom["time"], dom[col], "o-", color=color, label=f"{case}")
            ax.fill_between(seg[col].min().index, seg[col].min(), seg[col].max(), color=color, alpha=0.2,
                            label=f"{case}, rank segments (min-max)")
        axes[0].plot(dom["time"], dom["zi_grad"], "s:", color=color, label=f"{case}, max dtheta/dz")
    for a, style in zip(ENTRAINMENT, ("--", "-.")):
        axes[0].plot(t_ref, zi_encroachment(t_ref, ZI0, FLUX_IN, GAMMA, a), style, color="k",
                     label=f"jump model, A = {a:g} [U]")
    for ax, ylabel in zip(axes, ("$z_i$ [m]", "$w_*$ [m/s]", "$t_* = z_i / w_*$ [s]")):
        ax.set_xlabel("window end [s]")
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle=":", alpha=0.5)
    axes[0].legend(fontsize=7)
    axes[1].legend(fontsize=7)
    fig.suptitle("CBL scales per 200 s window: z_i from the heat-flux minimum (and the largest theta gradient)")
    fig.tight_layout()
    fig.savefig(save, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_theta_flux(profiles, case, save):
    """theta and total heat flux against z, one line per window coloured by time."""
    fig, axes = plt.subplots(1, 2, figsize=(9, 5), sharey=True)
    colors = plt.cm.viridis(np.linspace(0, 0.9, len(profiles)))
    for color, (window, m) in zip(colors, profiles.items()):
        axes[0].plot(m["T"], m["z"], color=color, label=window)
        axes[1].plot(m["flux_wt"] + m["flux_wt_model"], m["z"], color=color)
    axes[0].set_xlabel(r"$\theta - \theta_0$ [K]")
    axes[1].set_xlabel(r"total $\langle w'\theta' \rangle$ [K m/s]")
    axes[1].axvline(0.0, color="0.6", linewidth=0.8)
    axes[0].set_ylabel("z [m]")
    axes[0].set_ylim(0, ZMAX)
    for ax in axes:
        ax.grid(True, linestyle=":", alpha=0.5)
    axes[0].legend(fontsize=7, title="window")
    fig.suptitle(f"{case}: domain-mean theta and heat flux per window")
    fig.tight_layout()
    fig.savefig(save, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    set_name, run_names = parse_set_args(__doc__)
    paths = load_local_paths()
    out_dir = set_output_dir(paths, set_name, "cbl_scales")
    inputs, rows = {}, []
    for case, run in run_names.items():
        run_dir = inputs[case] = wind_dir(paths, run)
        header = read_header_txt(run_dir)
        theta0, t_ave = float(header.get("out_ref", 300.0)), float(header["t_ave"])
        profiles = {}
        for step in list_steps(run_dir, "prof"):
            step_rows, domain, time = scales_of_step(run_dir, step, theta0)
            rows += [dict(r, case=case, step=step, time=time) for r in step_rows]
            profiles[f"{time - t_ave:.0f}-{time:.0f} s"] = domain
        save = out_dir / f"theta_flux_profiles_{case}.png"
        plot_theta_flux(profiles, case, save)
        print(f"[SUCCESS] Figure saved to: {save}")

    table = pd.DataFrame(rows)[["case", "step", "time", "segment"] + SCALE_COLUMNS]
    save = out_dir / "cbl_scales.csv"
    table.to_csv(save, index=False)
    print(f"[SUCCESS] Table saved to: {save}")
    for case, g in table[table["segment"] == "domain"].groupby("case", sort=False):
        last = g.iloc[-1]
        print(f"{case}: last window z_i {last.zi_flux:.0f} m (grad {last.zi_grad:.0f} m), "
              f"w* {last.wstar:.3f} m/s, t* {last.tstar:.0f} s, surface flux {last.surface_flux:.4f} K m/s")
    save = out_dir / "cbl_scales_vs_time.png"
    plot_scales(table, save)
    print(f"[SUCCESS] Figure saved to: {save}")
    write_manifest(out_dir, set_name, run_names, inputs=inputs)


if __name__ == "__main__":
    main()
