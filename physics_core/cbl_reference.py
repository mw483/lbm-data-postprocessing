"""
Reference curves of the convective boundary layer (CBL), for comparing LBM profiles in mixed-layer scaling.

Every height is zeta = z / z_i; velocities are scaled by w* and the heat flux by its surface value.
The citations were checked; the formulas marked [U] were not yet checked against the paper itself
(they are the forms commonly quoted from it) and must be confirmed before results are presented.
"""
import numpy as np


def sigma_w2_lenschow(zeta):
    """<w'w'> / w*^2 = 1.8 zeta^(2/3) (1 - 0.8 zeta)^2, for 0 <= zeta <= 1 (NaN outside).

    Lenschow, Wyngaard & Pennell 1980, J. Atmos. Sci. 37, 1313-1326,
    doi:10.1175/1520-0469(1980)037<1313:MFASMB>2.0.CO;2 (aircraft data, AMTEX). Formula [U].
    """
    zeta = np.asarray(zeta, dtype=float)
    out = 1.8 * np.cbrt(zeta) ** 2 * (1.0 - 0.8 * zeta) ** 2
    return np.where((zeta >= 0) & (zeta <= 1), out, np.nan)


def heat_flux_linear(zeta, entrainment_ratio=0.2):
    """<w'theta'> / surface flux = 1 - (1 + A) zeta, for 0 <= zeta <= 1 (NaN outside).

    Linear flux profile of a quasi-steady mixed layer; at z_i the flux is -A times the surface flux,
    with the entrainment ratio A ~ 0.2. Stull 1988, An Introduction to Boundary Layer Meteorology [U].
    """
    zeta = np.asarray(zeta, dtype=float)
    out = 1.0 - (1.0 + entrainment_ratio) * zeta
    return np.where((zeta >= 0) & (zeta <= 1), out, np.nan)


def zi_encroachment(t, zi0, surface_flux, gamma, entrainment_ratio=0.2):
    """Mixed-layer depth [m] at time t [s] growing into a stable layer of lapse rate gamma [K/m].

    Zero-order jump model: dz_i/dt = (1 + 2A) flux / (gamma z_i), so
    z_i^2 = zi0^2 + 2 (1 + 2A) flux t / gamma. A = 0 is pure encroachment (no entrainment).
    Tennekes 1973 / Stull 1988 [U]. Assumes a constant surface flux from t = 0 and a neutral layer up to zi0.
    """
    t = np.asarray(t, dtype=float)
    return np.sqrt(zi0**2 + 2.0 * (1.0 + 2.0 * entrainment_ratio) * surface_flux * t / gamma)
