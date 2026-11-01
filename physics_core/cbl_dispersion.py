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
