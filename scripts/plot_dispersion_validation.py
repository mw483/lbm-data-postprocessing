"""
Validation of the Lagrangian particles in a convective boundary layer (CBL), in mixed-layer scaling.

Every particle is measured from its own source and its own release (particle ID), so the area release of
many sources acts as an ensemble of repeated point releases, the ensemble the experiments average over.
Needs reduced.npz from scripts/reduce_particle_bins.py with the "plume" histogram (2026-11-01 and later)
and the run's wind output (prof*.csv) for z_i, w* and U.

Figures, each with: what it measures / why / reference / units and sample.
1. dispersion_vertical_<run>.png (left: contour, right: Z mean and sigma_z against X)
   What: how the particles spread in height as they age, in units of the CBL depth.
   Why: validation against the water-tank experiments, which first showed that near-ground releases in a
       CBL lift off and overshoot mid-layer before they mix (not Gaussian); a model with realistic
       updrafts / downdrafts must reproduce the lift-off, the timing and the well-mixed end state.
   Reference: Willis & Deardorff 1976 (Q. J. R. Meteorol. Soc. 102, doi:10.1002/qj.49710243212) as summarised
       in Stull, Practical Meteorology Sec. 19.7: centreline formula (eq. 19.32) and the well-mixed limits
       Z mean -> 0.5, sigma_z -> 0.29. The tank source was higher (z_s/z_i ~ 0.07 [U]) than ours (0.1 m).
   Units: X = t w*/z_i (age), Z = z/z_i; colour = C_y U z_i / Q = z_i p(z | age). Upstream sources only.
2. dispersion_distance_<run>.png: the same from the steady plume against distance, X = x w*/(U_ml z_i).
   Why: the experiments define X from distance; with a mean wind that changes with height, distance and
       age give different X, and this figure shows by how much (compare with figure 1).
   Units: colour = C_y U_ml z_i / Q, U_ml = mean wind over 0.1-1 z_i.
3. ground_level_concentration.png (left: scaled, right: dimensional)
   What: how fast the concentration at the ground falls off downwind of a near-ground source.
   Why: validation of the near-ground part of the model (resolved flow + SGS velocity), which the vertical
       spread does not test; Prairie Grass is the field case closest to our setup (near-ground release,
       flat open terrain, unstable daytime runs, samplers at 1.5 m).
   Reference: Prairie Grass 1956 arcs (Barad 1958; data https://www.harmo.org/jsirwin/PrairieGrassDiscussion.html),
       unstable runs with a daytime z_i, corrected for SO2 evaporation (Table 5.4). u*, L and the heat flux
       come from a Monin-Obukhov fit to the 0.5-8 m profiles (physics_core/surface_layer.py, [U]).
       Guide slope X^(-3/2): surface-layer similarity in free convection [U].
   Units: left C_y U8 z_i / Q against X = x w*/(U8 z_i), U8 = wind at 8 m for both model and data (the only
       height Prairie Grass has); right C_y / Q [s/m^2] against x [m]. Model = 0-2 m layer (first cell).

4. survival_<run>.png (three panels against X = t w*/z_i)
   What: (a) the share of released particles still in the domain at each age, (b) how far the plume front
       has travelled, (c) the share of particles above z_i (inside the inversion).
   Why: a check of the figures above, not a validation itself. Particles are deleted at the x and y edges
       (LBM-city boundary_flag_particle.cu) although the flow is periodic. y-edge losses do not bias the
       height statistics (the flow is uniform in y) but lower an all-release concentration; x-edge losses
       remove the fastest particles first and bias everything after the first exit, so the comparison
       with the experiments is only valid left of the "first exit" line. (c) tells how much of the
       overshoot of the mean height comes from particles stored in the inversion.
   Reference: none for (a) and (b). (c) The tank and LES show that near-ground plumes reach z_i at
       X ~ 1-2 and that little material is entrained above it [U]; there is no single published value.
   Units: (a) fraction; (b) x - x_source [m], 99 % and 100 % of the particles of that age, with the
       distances at which particles from the most downstream source (x = --upstream-xmax) and from x = 0
       leave; (c) fraction above z_i (and above 1.2 z_i). Upstream sources only, all outputs read.
5. near_wall_<run>.png
   What: the particle concentration in the lowest 40 m, cell by cell (2 m bins = LBM cells).
   Why: a code check. The contour plots show a thin bright layer a few cells above the ground; a
       Lagrangian model that is not well mixed (Thomson 1987 criterion) or a velocity interpolation
       problem near the wall can collect particles there. Physically, the concentration of an old,
       mixed plume should change smoothly with height near the ground, without a peak a few cells up.
   Reference: well-mixed value 1 (C_y U z_i/Q = z_i p(z) for a uniform distribution); no data set
       resolves the first cells of a CBL. Thomson 1987 (J. Fluid Mech. 180, doi:10.1017/S0022112087001940) [U].
   Units: left z_i p(z | age) for a few ages (Lagrangian, survivors); right C_y U_ml z_i / Q of the steady
       plume at a few distances (survivor-weighted when reduced.npz has it). Bins of --dx (2 m).

Per-age scaling (PER_AGE_SCALES): z_i grows during the particle period, so figure 1 and 4 scale each age
by the mean z_i and w* over the times at which particles of that age were sampled (release start + age
to the last output), interpolated between the 200 s solver windows. Figures 2, 3 and 5 (distance based)
use the period mean, because every distance mixes many ages.
Survivor normalisation: with reduced.npz from the survivor pass (reduce_particle_bins.py, 2026-11-01 and
later) figures 2, 3 and 5 also use the survivor-weighted plume (dashed curve in figure 3).

Runs = a run set (run_sets.yaml, --set NAME; each run needs particle_reduced and output);
output in <figures>/<set>/dispersion_validation/.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loaders.lbm_output import domain_profile, list_steps, load_prof, read_header_txt
from data_loaders.local_paths import REPO_ROOT, load_local_paths, particle_reduced_dir, wind_dir
from data_loaders.prairie_grass import crosswind_integrated, read_arcs, read_corrections, read_profiles, read_zi
from data_loaders.run_sets import parse_set_args, set_output_dir, write_manifest
from physics_core.cbl_dispersion import (
    WELL_MIXED_SIGMA_Z, WELL_MIXED_Z_MEAN, fraction_above, lagrangian_cy, lagrangian_cy_per_age,
    profile_moments_of_density, scales_per_age, stull_centreline,
)
from physics_core.moments import cbl_scales, profile_moments
from physics_core.particle_bin_stats import (
    age_histograms, leading_edge, load_reduced, outputs_per_age, plume_concentration, survival_by_age,
)
from physics_core.surface_layer import fit_profiles, surface_heat_flux

# =============================================================================
# Settings
# =============================================================================
PRAIRIE_GRASS = REPO_ROOT / "validation_data" / "prairie_grass"
PG_Z0 = 0.006           # Prairie Grass roughness length [m] (PGrassTTUU.txt header)
PG_FIT_ZMIN = 0.5       # lowest profile level used in the Monin-Obukhov fit [m]
U_REF_HEIGHT = 8.0      # height of the reference wind for the ground-level figure [m]
SOURCE_HEIGHT = 0.1     # particle release height [m] (LBM-city cases/defaults.yaml sources.z)
X_MAX = 4.0             # right end of the X axes
Z_MAX = 1.5             # top of the Z axes [z / z_i]
MIN_COUNT = 2000        # ages with fewer particle samples are left out (as in plot_particle_bin_stats)
GROUND_DZ_BINS = 1      # model ground-level value = the lowest z bins of the plume histogram (1 bin = 0-2 m)
PER_AGE_SCALES = True   # figures 1 and 4: scale each age by its own z_i and w* (False = period mean)
Z_GRID_STEP = 0.01      # Z bin of the per-age scaled figure 1 [z / z_i]
NEAR_WALL_TOP = 40.0    # top of the near-wall figure [m]
NEAR_WALL_AGES = (20, 60, 120, 300, 600)        # ages shown in the near-wall figure [s]
NEAR_WALL_DISTANCES = (100, 300, 1000, 2000)    # distances shown in the near-wall figure [m]


def run_scales(run_dir, t_first, t_last):
    """z_i, w*, mixed-layer U and U at U_REF_HEIGHT averaged over the solver windows overlapping [t_first, t_last]."""
    header = read_header_txt(run_dir)
    theta0, t_ave, dt = float(header.get("out_ref", 300.0)), float(header["t_ave"]), float(header["dt_real"])
    rows = []
    for step in list_steps(run_dir, "prof"):
        t_end = step * dt
        if t_end <= t_first or t_end - t_ave >= t_last:
            continue
        m = profile_moments(domain_profile(load_prof(run_dir, step)))
        s = cbl_scales(m, theta0)
        ml = (m["z"] >= 0.1 * s["zi_flux"]) & (m["z"] <= s["zi_flux"])
        rows.append({"step": step, "t_mid": t_end - 0.5 * t_ave, "zi": s["zi_flux"], "wstar": s["wstar"], "u_ml": m.loc[ml, "U"].mean(),
                     "u_ref": float(np.interp(U_REF_HEIGHT, m["z"], m["U"]))})
    if not rows:
        raise ValueError(f"[ERROR] no prof window of {run_dir} overlaps the particle period {t_first:.0f}-{t_last:.0f} s")
    table = pd.DataFrame(rows)
    return table.mean(numeric_only=True).to_dict(), table


def prairie_grass_unstable():
    """Ground-level C_y / Q per unstable Prairie Grass run and arc, with u*, L, heat flux, w*, z_i and U8."""
    arcs = read_arcs(PRAIRIE_GRASS)
    arcs = arcs[arcs["release_height"] < 1.0]                       # Exp 63-68 released at 1.5 m
    cy = crosswind_integrated(arcs)
    corr = read_corrections(PRAIRIE_GRASS)
    cy = cy.merge(corr, on=["exp", "distance"], how="left")
    cy["cy_over_q"] *= cy["factor"].fillna(1.0)                    # evaporation loss correction
    met = []
    for exp, g in read_profiles(PRAIRIE_GRASS).groupby("exp"):
        g = g[g["z"] >= PG_FIT_ZMIN]
        ustar, tstar, L = fit_profiles(g["z"], g["wind"], g["temp"] + 273.15, PG_Z0)
        u8 = g.loc[g["z"] == U_REF_HEIGHT, "wind"]
        met.append({"exp": exp, "ustar": ustar, "L": L, "flux": surface_heat_flux(ustar, tstar),
                    "t_k": g["temp"].mean() + 273.15, "u_ref": u8.iloc[0] if len(u8) else np.nan})
    met = pd.DataFrame(met).merge(read_zi(PRAIRIE_GRASS), on="exp", how="left")
    met["wstar"] = np.cbrt(9.81 / met["t_k"] * met["flux"].clip(lower=0) * met["zi"])
    unstable = met[(met["L"] < 0) & (met["flux"] > 0) & met["zi"].notna() & met["u_ref"].notna()]
    out = cy.merge(unstable, on="exp", how="inner")
    out["X"] = out["distance"] * out["wstar"] / (out["u_ref"] * out["zi"])
    out["cy_scaled"] = out["cy_over_q"] * out["u_ref"] * out["zi"]
    return out


def mark_exit(ax, x_exit):
    """Grey area right of the first exit through the outflow, where the particle statistics are biased."""
    if x_exit is not None and np.isfinite(x_exit):
        ax.axvspan(x_exit, X_MAX, color="0.6", alpha=0.25, zorder=0)
        ax.axvline(x_exit, color="0.3", linestyle="-.", linewidth=1, label=f"first exit, X = {x_exit:.2f}")


def plot_vertical(X, Z, density, zs, title, cbar_label, save, x_exit=None):
    """Contour of the scaled concentration with the centreline formula, and Z mean / sigma_z against X."""
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 4.8))
    keep = X <= X_MAX
    mesh = a0.pcolormesh(X[keep], Z, density[keep].T, shading="nearest", cmap="viridis",
                         vmin=0, vmax=np.nanpercentile(density[keep], 99))
    fig.colorbar(mesh, ax=a0, label=cbar_label)
    xr = np.linspace(0, X_MAX, 200)
    a0.plot(xr, stull_centreline(xr, zs), "--", color="orange", label=f"Stull eq. 19.32, $z_s/z_i$ = {zs:.4f}")
    mean, sd = profile_moments_of_density(Z, density)
    a0.plot(X[keep], mean[keep], "r-", linewidth=1, label="model mean height")
    if x_exit is not None and np.isfinite(x_exit):
        a0.axvline(x_exit, color="w", linestyle="-.", linewidth=1, label=f"first exit, X = {x_exit:.2f}")
    a0.set(xlabel="X", ylabel="$z / z_i$", ylim=(0, Z_MAX), xlim=(0, X_MAX))
    a0.legend(fontsize=7, loc="upper right")
    a1.plot(X[keep], mean[keep], label=r"$\bar z / z_i$")
    a1.plot(X[keep], sd[keep], label=r"$\sigma_z / z_i$")
    a1.axhline(WELL_MIXED_Z_MEAN, color="C0", linestyle=":", label="well mixed, 0.5")
    a1.axhline(WELL_MIXED_SIGMA_Z, color="C1", linestyle=":", label="well mixed, 0.29")
    mark_exit(a1, x_exit)
    a1.set(xlabel="X", ylabel="/ $z_i$", xlim=(0, X_MAX), ylim=(0, 0.8))
    a1.grid(True, linestyle=":", alpha=0.5)
    a1.legend(fontsize=8)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(save, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_survival(X, surv, edge99, edge_max, above, above12, x_exit, lx, x_src_max, title, save):
    """Survival fraction, plume front and fraction above z_i against X (figure 4)."""
    fig, (a0, a1, a2) = plt.subplots(1, 3, figsize=(16, 4.6))
    keep = np.isfinite(X) & (X <= X_MAX)
    a0.plot(X[keep], surv[keep], "k-")
    a0.set(ylabel="particles in the domain / released", ylim=(0, 1.05), title="(a) survival")
    a1.plot(X[keep], edge99[keep], label="99 % of particles within")
    a1.plot(X[keep], edge_max[keep], label="front (furthest particle)")
    a1.axhline(lx - x_src_max, color="0.3", linestyle=":", label=f"exit of the source at x = {x_src_max:g} m")
    a1.axhline(lx, color="0.3", linestyle="--", label="exit of a source at x = 0")
    a1.set(ylabel="x - x_source [m]", title="(b) plume front")
    a2.plot(X[keep], above[keep], label="above $z_i$")
    a2.plot(X[keep], above12[keep], label="above 1.2 $z_i$")
    a2.set(ylabel="fraction of particles", ylim=(0, None), title="(c) particles in the inversion")
    for ax in (a0, a1, a2):
        mark_exit(ax, x_exit)
        ax.set(xlabel="X = t w*/z_i", xlim=(0, X_MAX))
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.legend(fontsize=7)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(save, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_near_wall(z_mid, lagr, plume_z, plume, title, save):
    """Lowest NEAR_WALL_TOP metres: z_i p(z | age) per age (left) and the steady plume per distance (right)."""
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    for label, prof in lagr.items():
        a0.plot(prof, z_mid, marker=".", label=label)
    for label, prof in plume.items():
        a1.plot(prof, plume_z, marker=".", label=label)
    a0.set(xlabel=r"$z_i\, p(z\,|\,\mathrm{age})$", ylabel="z [m]", title="particles of one age")
    a1.set(xlabel=r"$C_y U_{ml} z_i / Q$", title="steady plume at one distance")
    for ax in (a0, a1):
        ax.axvline(1.0, color="k", linestyle=":", label="well mixed, 1")
        ax.set_xscale("log")
        ax.xaxis.set_minor_formatter(plt.NullFormatter())
        ax.set_ylim(0, NEAR_WALL_TOP)
        ax.set_yticks(np.arange(0, NEAR_WALL_TOP + 1, 4))
        ax.grid(True, axis="y", linestyle=":", alpha=0.6)
        ax.legend(fontsize=7)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(save, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_ground(model, pg, save, x_exit_m=None):
    """Ground-level C_y: scaled against X (left) and dimensional against distance (right)."""
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 5))
    sc = a0.scatter(pg["X"], pg["cy_scaled"], c=-pg["zi"] / pg["L"], cmap="plasma", norm="log", s=18,
                    label="Prairie Grass, unstable runs")
    fig.colorbar(sc, ax=a0, label="$-z_i / L$ (Prairie Grass)")
    a1.scatter(pg["distance"], pg["cy_over_q"], c="0.5", s=12, label="Prairie Grass, unstable runs")
    for i, (case, d) in enumerate(model.items()):
        ok = d["x"] > 0
        a0.plot(d["X"][ok], d["cy_scaled"][ok], color=f"C{i}", linewidth=2, label=f"{case} (0-2 m layer)")
        a1.plot(d["x"][ok], d["cy_over_q"][ok], color=f"C{i}", linewidth=2, label=f"{case} (0-2 m layer)")
        if "cy_scaled_surv" in d:
            a0.plot(d["X"][ok], d["cy_scaled_surv"][ok], color=f"C{i}", linewidth=1.5, linestyle="--",
                    label=f"{case}, survivors only")
            a1.plot(d["x"][ok], d["cy_over_q_surv"][ok], color=f"C{i}", linewidth=1.5, linestyle="--",
                    label=f"{case}, survivors only")
        if x_exit_m is not None and case in x_exit_m and np.isfinite(x_exit_m[case]):
            a1.axvline(x_exit_m[case], color=f"C{i}", linestyle="-.", linewidth=1,
                       label=f"{case}: beyond this, sources lose particles at the outflow")
    xg = np.array([0.01, 0.3])     # guide line through the median Prairie Grass value at 0.03 < X < 0.08
    near = pg.loc[pg["X"].between(0.03, 0.08), "cy_scaled"]
    anchor = near.median() if len(near) else 1.0
    a0.plot(xg, anchor * (xg / 0.05) ** -1.5, "k--", label=r"slope $X^{-3/2}$ [U], through the data at X = 0.05")
    for ax in (a0, a1):
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.grid(True, which="both", linestyle=":", alpha=0.4)
        ax.legend(fontsize=7)
    a0.set(xlabel=r"$X = x\,w_* / (U_8\, z_i)$", ylabel=r"$C_y\, U_8\, z_i / Q$")
    a1.set(xlabel="x [m]", ylabel=r"$C_y / Q$ [s/m$^2$]")
    fig.suptitle("Ground-level crosswind-integrated concentration of a near-ground source")
    fig.tight_layout()
    fig.savefig(save, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    set_name, runs = parse_set_args(__doc__)
    paths = load_local_paths()
    out_dir = set_output_dir(paths, set_name, "dispersion_validation")
    inputs, ground, scale_rows, exit_x_m = {}, {}, [], {}

    for case, run in runs.items():
        red_dir, run_dir = particle_reduced_dir(paths, run), wind_dir(paths, run)
        inputs[case] = {"particle_reduced": red_dir, "output": run_dir}
        meta, data = load_reduced(red_dir / "reduced.npz")
        if "plume_hist" not in data:
            raise KeyError(f"[ERROR] {red_dir}/reduced.npz has no plume histogram; rerun reduce_particle_bins.py")
        dt = float(meta["dt_output"])
        scales, table = run_scales(run_dir, meta["first_read"] * dt, meta["last_read"] * dt)
        scale_rows.append(table.assign(case=case))
        zi, ws = scales["zi"], scales["wstar"]
        print(f"{case}: z_i {zi:.0f} m, w* {ws:.3f} m/s, U_ml {scales['u_ml']:.2f} m/s, "
              f"U({U_REF_HEIGHT:g} m) {scales['u_ref']:.2f} m/s over windows {table['step'].tolist()}")

        hist_z, _ = age_histograms(data)
        hist_z = np.where(data["age_count"][:, None] >= MIN_COUNT, hist_z, 0)
        age_s = np.arange(hist_z.shape[0]) * dt
        if PER_AGE_SCALES:
            zi_a, ws_a = scales_per_age(table["t_mid"], table["zi"], table["wstar"], age_s,
                                        meta["release_start"] * dt, meta["last_read"] * dt)
        else:
            zi_a, ws_a = np.full(age_s.size, zi), np.full(age_s.size, ws)
        X_age = age_s * ws_a / zi_a

        # survival, plume front, particles in the inversion (figure 4)
        n_up, lx, x_up = meta["n_upstream_sources"], float(meta["lx"]), float(meta["upstream_xmax"])
        if "plume_outputs_per_age" in data:
            per_age = data["plume_outputs_per_age"]
        else:
            print(f"[WARNING] {case}: reduced.npz has no plume_outputs_per_age, assumed every output "
                  f"{meta['first_read']}-{meta['last_read']} was read")
            per_age = outputs_per_age(range(meta["first_read"], meta["last_read"] + 1), meta["release_start"],
                                      meta["release_every"], data["age_count"].size)
        surv = survival_by_age(data, n_up, per_age)
        edge99, edge_max = leading_edge(data, 0.99)
        exits = np.nonzero(edge_max >= lx - x_up - float(np.diff(data["age_dx_edges"][:2])[0]))[0]
        exit_age = age_s[exits[0]] if exits.size else np.nan
        x_exit = X_age[exits[0]] if exits.size else np.nan
        all_z, _ = age_histograms(data)
        above = fraction_above(all_z, data["age_z_edges"], zi_a)
        above12 = fraction_above(all_z, data["age_z_edges"], 1.2 * zi_a)
        print(f"{case}: first exit through x at age {exit_age:.0f} s (X = {x_exit:.2f}); "
              f"survival there {np.interp(exit_age, age_s, surv) if exits.size else np.nan:.2f}")
        save = out_dir / f"survival_{case}.png"
        plot_survival(X_age, surv, edge99, edge_max, above, above12, x_exit, lx, x_up,
                      f"{case}: particle survival, plume front and particles above $z_i$", save)
        print(f"[SUCCESS] Figure saved to: {save}")
        pd.DataFrame({"age_s": age_s, "X": X_age, "zi": zi_a, "wstar": ws_a, "count": data["age_count"],
                      "survival": surv, "dx_99": edge99, "dx_front": edge_max, "frac_above_zi": above,
                      "frac_above_1p2zi": above12}).to_csv(out_dir / f"survival_{case}.csv", index=False)

        # figure 1
        if PER_AGE_SCALES:
            X, Z, dens = lagrangian_cy_per_age(hist_z, data["age_z_edges"], age_s, zi_a, ws_a,
                                               np.arange(0.0, Z_MAX + Z_GRID_STEP, Z_GRID_STEP))
            scaling = "each age scaled by its own z_i, w*"
        else:
            X, Z, dens = lagrangian_cy(hist_z, data["age_z_edges"], age_s, zi, ws)
            scaling = "period-mean z_i, w*"
        save = out_dir / f"dispersion_vertical_{case}.png"
        plot_vertical(X, Z, dens, SOURCE_HEIGHT / zi, f"{case}: particle height against age, X = t w*/z_i "
                      f"({scaling})", r"$C_y U z_i / Q$", save, x_exit=x_exit)
        print(f"[SUCCESS] Figure saved to: {save}")

        # figure 2 (survivor-weighted plume when available)
        surv_key = "plume_surv_hist" if "plume_surv_hist" in data else None
        if surv_key is None:
            print(f"[WARNING] {case}: reduced.npz has no survivor-weighted plume; rerun reduce_particle_bins.py "
                  "for the survivor curves")
        x, z, cy = plume_concentration(data, n_up, meta["release_interval"])
        cy_main = plume_concentration(data, n_up, meta["release_interval"], key=surv_key)[2] if surv_key else cy
        Xd = x * ws / (scales["u_ml"] * zi)
        x_exit_d = (lx - x_up) * ws / (scales["u_ml"] * zi)
        save = out_dir / f"dispersion_distance_{case}.png"
        plot_vertical(Xd, z / zi, cy_main * scales["u_ml"] * zi, SOURCE_HEIGHT / zi,
                      f"{case}: steady plume against distance, X = x w*/(U_ml z_i)"
                      + (" (survivors)" if surv_key else " (all released)"), r"$C_y U_{ml} z_i / Q$", save,
                      x_exit=x_exit_d)
        print(f"[SUCCESS] Figure saved to: {save}")

        # figure 3
        ground_cy = cy[:, :GROUND_DZ_BINS].mean(axis=1)
        ground[case] = pd.DataFrame({"x": x, "X": x * ws / (scales["u_ref"] * zi), "cy_over_q": ground_cy,
                                     "cy_scaled": ground_cy * scales["u_ref"] * zi})
        if surv_key:
            g = cy_main[:, :GROUND_DZ_BINS].mean(axis=1)
            ground[case]["cy_over_q_surv"] = g
            ground[case]["cy_scaled_surv"] = g * scales["u_ref"] * zi
        exit_x_m[case] = lx - x_up

        # figure 5
        zl = 0.5 * (data["age_z_edges"][1:] + data["age_z_edges"][:-1])
        low = zl <= NEAR_WALL_TOP
        X1, _, dens1 = lagrangian_cy(hist_z, data["age_z_edges"], age_s, zi, ws)
        lagr = {}
        for a in NEAR_WALL_AGES:
            i = int(round(a / dt))
            if i < dens1.shape[0] and np.isfinite(dens1[i]).any():
                lagr[f"age {a} s (X = {X1[i]:.2f})"] = dens1[i, low]
        zlow = z <= NEAR_WALL_TOP
        plume = {}
        for d in NEAR_WALL_DISTANCES:
            j = int(np.argmin(np.abs(x - d)))
            plume[f"x = {x[j]:.0f} m (X = {Xd[j]:.2f})"] = cy_main[j, zlow] * scales["u_ml"] * zi
        save = out_dir / f"near_wall_{case}.png"
        plot_near_wall(zl[low], lagr, z[zlow], plume, f"{case}: lowest {NEAR_WALL_TOP:g} m, one point per 2 m bin", save)
        print(f"[SUCCESS] Figure saved to: {save}")

    pg = prairie_grass_unstable()
    print(f"Prairie Grass: {pg['exp'].nunique()} unstable runs with z_i, {len(pg)} arcs")
    save = out_dir / "ground_level_concentration.png"
    plot_ground(ground, pg, save, exit_x_m)
    print(f"[SUCCESS] Figure saved to: {save}")

    pg.to_csv(out_dir / "prairie_grass_unstable_arcs.csv", index=False)
    pd.concat([d.assign(case=c) for c, d in ground.items()]).to_csv(out_dir / "model_ground_level.csv", index=False)
    pd.concat(scale_rows).to_csv(out_dir / "cbl_scales_used.csv", index=False)
    print(f"[SUCCESS] Tables saved to: {out_dir}")
    write_manifest(out_dir, set_name, runs, inputs=inputs)


if __name__ == "__main__":
    main()
