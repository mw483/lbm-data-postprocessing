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
    WELL_MIXED_SIGMA_Z, WELL_MIXED_Z_MEAN, lagrangian_cy, profile_moments_of_density, stull_centreline,
)
from physics_core.moments import cbl_scales, profile_moments
from physics_core.particle_bin_stats import age_histograms, load_reduced, plume_concentration
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
        rows.append({"step": step, "zi": s["zi_flux"], "wstar": s["wstar"], "u_ml": m.loc[ml, "U"].mean(),
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


def plot_vertical(X, Z, density, zs, title, cbar_label, save):
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
    a0.set(xlabel="X", ylabel="$z / z_i$", ylim=(0, Z_MAX), xlim=(0, X_MAX))
    a0.legend(fontsize=7, loc="upper right")
    a1.plot(X[keep], mean[keep], label=r"$\bar z / z_i$")
    a1.plot(X[keep], sd[keep], label=r"$\sigma_z / z_i$")
    a1.axhline(WELL_MIXED_Z_MEAN, color="C0", linestyle=":", label="well mixed, 0.5")
    a1.axhline(WELL_MIXED_SIGMA_Z, color="C1", linestyle=":", label="well mixed, 0.29")
    a1.set(xlabel="X", ylabel="/ $z_i$", xlim=(0, X_MAX), ylim=(0, 0.8))
    a1.grid(True, linestyle=":", alpha=0.5)
    a1.legend(fontsize=8)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(save, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_ground(model, pg, save):
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
    inputs, ground, scale_rows = {}, {}, []

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
        X, Z, dens = lagrangian_cy(hist_z, data["age_z_edges"], np.arange(hist_z.shape[0]) * dt, zi, ws)
        save = out_dir / f"dispersion_vertical_{case}.png"
        plot_vertical(X, Z, dens, SOURCE_HEIGHT / zi, f"{case}: particle height against age, X = t w*/z_i",
                      r"$C_y U z_i / Q$", save)
        print(f"[SUCCESS] Figure saved to: {save}")

        x, z, cy = plume_concentration(data, meta["n_upstream_sources"], meta["release_interval"])
        Xd = x * ws / (scales["u_ml"] * zi)
        save = out_dir / f"dispersion_distance_{case}.png"
        plot_vertical(Xd, z / zi, cy * scales["u_ml"] * zi, SOURCE_HEIGHT / zi,
                      f"{case}: steady plume against distance, X = x w*/(U_ml z_i)", r"$C_y U_{ml} z_i / Q$", save)
        print(f"[SUCCESS] Figure saved to: {save}")

        ground_cy = cy[:, :GROUND_DZ_BINS].mean(axis=1)
        ground[case] = pd.DataFrame({"x": x, "X": x * ws / (scales["u_ref"] * zi), "cy_over_q": ground_cy,
                                     "cy_scaled": ground_cy * scales["u_ref"] * zi})

    pg = prairie_grass_unstable()
    print(f"Prairie Grass: {pg['exp'].nunique()} unstable runs with z_i, {len(pg)} arcs")
    save = out_dir / "ground_level_concentration.png"
    plot_ground(ground, pg, save)
    print(f"[SUCCESS] Figure saved to: {save}")

    pg.to_csv(out_dir / "prairie_grass_unstable_arcs.csv", index=False)
    pd.concat([d.assign(case=c) for c, d in ground.items()]).to_csv(out_dir / "model_ground_level.csv", index=False)
    pd.concat(scale_rows).to_csv(out_dir / "cbl_scales_used.csv", index=False)
    print(f"[SUCCESS] Tables saved to: {out_dir}")
    write_manifest(out_dir, set_name, runs, inputs=inputs)


if __name__ == "__main__":
    main()
