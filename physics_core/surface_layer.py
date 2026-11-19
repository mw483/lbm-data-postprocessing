"""
Monin-Obukhov surface-layer profiles, to estimate u*, theta* and the Obukhov length L from measured
wind and temperature profiles (used for the Prairie Grass experiments, which give profiles but no fluxes).

Profile relations [U: the standard forms, as quoted in Stull 1988 Ch. 9; not yet checked in the source]:
    U(z)             = u*/k     [ln(z/z0) - psi_m(z/L)]
    T(z) - T(z_ref)  = theta*/k [ln(z/z_ref) - psi_h(z/L) + psi_h(z_ref/L)]
    L                = u*^2 T / (k g theta*)          (theta* = -<w'theta'>_s / u*)
Unstable psi (Businger-Dyer, Paulson 1970): x = (1 - 16 z/L)^(1/4),
    psi_m = 2 ln((1+x)/2) + ln((1+x^2)/2) - 2 atan(x) + pi/2,  psi_h = 2 ln((1+x^2)/2).
Stable: psi_m = psi_h = -5 z/L.
"""
import numpy as np

KARMAN = 0.4
G = 9.81


def psi_m(zeta):
    zeta = np.asarray(zeta, dtype=float)
    x = np.power(np.clip(1.0 - 16.0 * zeta, 1.0, None), 0.25)
    unstable = 2 * np.log((1 + x) / 2) + np.log((1 + x**2) / 2) - 2 * np.arctan(x) + np.pi / 2
    return np.where(zeta < 0, unstable, -5.0 * zeta)


def psi_h(zeta):
    zeta = np.asarray(zeta, dtype=float)
    x = np.power(np.clip(1.0 - 16.0 * zeta, 1.0, None), 0.25)
    return np.where(zeta < 0, 2 * np.log((1 + x**2) / 2), -5.0 * zeta)


def fit_profiles(z, wind, temp_k, z0, n_iter=50):
    """u*, theta*, L from wind [m/s] and temperature [K] at heights z [m] (NaN levels dropped).

    Iterates L: for a given L, u* and theta* are least-squares slopes of the profile relations above
    (wind through the origin at z0; temperature relative to its lowest level), then L is updated.
    Returns (u*, theta*, L); L = inf for a neutral profile, NaN when fewer than 2 usable levels.
    """
    z, wind, temp_k = (np.asarray(a, dtype=float) for a in (z, wind, temp_k))
    ok_u = np.isfinite(wind) & (z > z0)
    ok_t = np.isfinite(temp_k)
    if ok_u.sum() < 2 or ok_t.sum() < 2:
        return np.nan, np.nan, np.nan
    zu, u = z[ok_u], wind[ok_u]
    zt, t = z[ok_t], temp_k[ok_t]
    zr, tr = zt[0], t[0]
    t_mean = float(np.mean(t))
    inv_l = 0.0
    for _ in range(n_iter):
        fm = (np.log(zu / z0) - psi_m(zu * inv_l)) / KARMAN
        fh = (np.log(zt / zr) - psi_h(zt * inv_l) + psi_h(zr * inv_l)) / KARMAN
        ustar = float(np.sum(fm * u) / np.sum(fm * fm))
        tstar = float(np.sum(fh[1:] * (t[1:] - tr)) / np.sum(fh[1:] ** 2))
        new = KARMAN * G * tstar / (ustar**2 * t_mean)
        new = float(np.clip(new, -10.0, 10.0))        # |L| >= 0.1 m keeps the iteration bounded
        if abs(new - inv_l) < 1e-6:
            inv_l = new
            break
        inv_l = 0.5 * (inv_l + new)                    # damped update
    return ustar, tstar, (1.0 / inv_l if inv_l != 0 else np.inf)


def surface_heat_flux(ustar, tstar):
    """Kinematic surface heat flux <w'theta'>_s = -u* theta* [K m/s]."""
    return -ustar * tstar
