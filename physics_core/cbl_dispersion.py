"""
Dispersion in the convective boundary layer (CBL) in mixed-layer scaling, for comparing LBM particles with
the Willis & Deardorff water tank, Stull's summary of it and the Prairie Grass field data.

Scaling: Z = z / z_i, X = t w* / z_i (particle age) or X = x w* / (U z_i) (distance), and the
crosswind-integrated concentration as C_y U z_i / Q. For particles followed from their release,
C_y U z_i / Q at a given X is z_i times the probability density of z (Lagrangian form, x = U t).
"""
import numpy as np

WELL_MIXED_Z_MEAN = 0.5                 # mean height of a uniform distribution over 0..z_i, / z_i
WELL_MIXED_SIGMA_Z = 1.0 / np.sqrt(12)  # its standard deviation, / z_i (~0.29)


def stull_centreline(X, zs, wavelength=4.0):
    """Height of the concentration maximum / z_i for a source at zs = z_s / z_i (Stull, Practical
    Meteorology, Sec. 19.7, eq. 19.32, lambda = 4; read 2026-10-20, literature/notes/willis_deardorff_cbl_dispersion.md):
    Z_CL = 0.5 + 0.5 / (1 + 0.5 X^2) * cos(2 pi X / lambda + arccos(2 zs - 1))."""
    X = np.asarray(X, dtype=float)
    return 0.5 + 0.5 / (1.0 + 0.5 * X**2) * np.cos(2 * np.pi * X / wavelength + np.arccos(2 * zs - 1))


def lagrangian_cy(hist_z, z_edges, age_s, zi, wstar):
    """C_y U z_i / Q against (X = age w*/z_i, Z = z/z_i) from an age x z particle histogram [n_age, n_z].

    Each age row is normalised to a probability density in Z (integral 1); rows without particles are NaN.
    Returns (X [n_age], Z centres [n_z], density [n_age, n_z]).
    """
    hist_z = np.asarray(hist_z, dtype=float)
    dz = np.diff(z_edges) / zi
    n = hist_z.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        density = np.where(n > 0, hist_z / (n * dz[None, :]), np.nan)
    z_mid = 0.5 * (np.asarray(z_edges[1:]) + np.asarray(z_edges[:-1])) / zi
    return np.asarray(age_s) * wstar / zi, z_mid, density


def profile_moments_of_density(Z, density):
    """Mean height and standard deviation (both / z_i) of each row of a density on Z."""
    dz = np.gradient(Z)
    w = np.nan_to_num(density) * dz[None, :]
    total = w.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = (w * Z[None, :]).sum(axis=1) / total
        var = (w * Z[None, :] ** 2).sum(axis=1) / total - mean**2
    return np.where(total > 0, mean, np.nan), np.sqrt(np.clip(np.where(total > 0, var, np.nan), 0, None))


def lagrangian_cy_per_age(hist_z, z_edges, age_s, zi_age, wstar_age, Z_edges):
    """As lagrangian_cy, but each age is scaled by its own z_i and w* (arrays over the ages).

    Each row's cumulative distribution in z is interpolated at Z_edges * z_i(age) and differenced, so all
    rows share one Z grid. Returns (X [n_age], Z centres, density [n_age, n_Z]); rows without particles NaN.
    """
    hist_z = np.asarray(hist_z, dtype=float)
    z_edges = np.asarray(z_edges, dtype=float)
    Z_edges = np.asarray(Z_edges, dtype=float)
    zi_age, wstar_age = np.asarray(zi_age, dtype=float), np.asarray(wstar_age, dtype=float)
    n = hist_z.sum(axis=1)
    cdf = np.concatenate([np.zeros((hist_z.shape[0], 1)), np.cumsum(hist_z, axis=1)], axis=1)
    density = np.full((hist_z.shape[0], Z_edges.size - 1), np.nan)
    for i in np.nonzero(n > 0)[0]:
        c = np.interp(Z_edges * zi_age[i], z_edges, cdf[i] / n[i])
        density[i] = np.diff(c) / np.diff(Z_edges)
    X = np.asarray(age_s, dtype=float) * wstar_age / zi_age
    return X, 0.5 * (Z_edges[1:] + Z_edges[:-1]), density


def fraction_above(hist_z, z_edges, height):
    """Per age row, the fraction of particles above height [m] (a scalar or one value per row).

    Linear within the bin that contains the height. Rows without particles are NaN.
    """
    hist_z = np.asarray(hist_z, dtype=float)
    z_edges = np.asarray(z_edges, dtype=float)
    height = np.broadcast_to(np.asarray(height, dtype=float), (hist_z.shape[0],))
    n = hist_z.sum(axis=1)
    cdf = np.concatenate([np.zeros((hist_z.shape[0], 1)), np.cumsum(hist_z, axis=1)], axis=1)
    below = np.array([np.interp(h, z_edges, c) for h, c in zip(height, cdf)])
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, 1.0 - below / n, np.nan)


def scales_per_age(t_window, zi_window, wstar_window, age_s, t_release_first, t_last, n_sub=50):
    """z_i and w* for each particle age, from solver windows (centre times t_window [s]).

    Particles of age a are sampled at times t_release_first + a .. t_last (every release that reached that
    age within the outputs read), so each age gets the mean of z_i(t) and w*(t) over that interval, with
    z_i(t) linearly interpolated between window centres (held constant outside them). Ages that do not fit
    into the interval are NaN.
    """
    age_s = np.asarray(age_s, dtype=float)
    order = np.argsort(t_window)
    t_w = np.asarray(t_window, dtype=float)[order]
    zi_w, ws_w = np.asarray(zi_window, dtype=float)[order], np.asarray(wstar_window, dtype=float)[order]
    zi, ws = np.full(age_s.size, np.nan), np.full(age_s.size, np.nan)
    for i, a in enumerate(age_s):
        t0 = t_release_first + a
        if t0 > t_last:
            continue
        t = np.linspace(t0, t_last, n_sub)
        zi[i], ws[i] = np.interp(t, t_w, zi_w).mean(), np.interp(t, t_w, ws_w).mean()
    return zi, ws
