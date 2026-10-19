"""
Central moments from the raw time means the solver writes.

The solver's plane and profile files hold raw moments: a = <a>, ab = <a b>, aab = <a a b>, ...
Central (fluctuation) moments follow from them:
    <a'b'>    = ab  - a b
    <a'a'a'>  = aaa - 3 a aa + 2 a^3
    <a'a'b'>  = aab - 2 a ab - b aa + 2 a^2 b
Works on scalars, NumPy arrays and pandas Series alike. Unlike physics_core/turbulence.py,
nothing is clipped: a negative variance (round-off in 6-decimal plane files) is returned as it is,
and the derived sigma / skewness are NaN there, so the problem stays visible.
"""
import numpy as np
import pandas as pd


def covariance(ab, a, b):
    """<a'b'> from <ab>, <a>, <b>. With a == b this is the variance."""
    return ab - a * b


def third_moment(aaa, aa, a):
    """<a'^3> from <a^3>, <a^2>, <a>."""
    return aaa - 3.0 * a * aa + 2.0 * a**3


def mixed_third_moment(aab, aa, ab, a, b):
    """<a'a'b'> from <aab>, <aa>, <ab>, <a>, <b>."""
    return aab - 2.0 * a * ab - b * aa + 2.0 * a**2 * b


def sigma(var):
    """Standard deviation; NaN where the variance is negative."""
    return np.sqrt(np.where(var >= 0, var, np.nan))


def skewness(m3, var):
    """<a'^3> / var^1.5; NaN where the variance is not positive."""
    var = np.asarray(var, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(var > 0, np.asarray(m3, dtype=float) / var**1.5, np.nan)


def tke(var_u, var_v, var_w):
    """Resolved turbulent kinetic energy 0.5 (<u'u'> + <v'v'> + <w'w'>)."""
    return 0.5 * (var_u + var_v + var_w)


def profile_moments(prof):
    """Central moments from a solver profile table (prof*.csv columns, e.g. domain_profile output).

    Velocities [m/s]; theta columns are moments of (theta - out_ref) [K] as the solver writes them.
    The *_SGS columns are the solver's Laplacian-based estimate, copied unchanged (sgs_sum = uu+vv+ww).
    """
    p = prof
    out = pd.DataFrame({"z": p["z"], "U": p["U"], "V": p["V"], "W": p["W"], "T": p["T"]})
    for c in ("U", "V", "W"):
        out[f"var_{c.lower()}"] = covariance(p[c * 2], p[c], p[c])
    out["cov_uw"] = covariance(p["UW"], p["U"], p["W"])
    out["cov_vw"] = covariance(p["VW"], p["V"], p["W"])
    out["cov_uv"] = covariance(p["UV"], p["U"], p["V"])
    out["tke"] = tke(out["var_u"], out["var_v"], out["var_w"])
    for c in ("U", "V", "W"):
        m3 = third_moment(p[c * 3], p[c * 2], p[c])
        out[f"skew_{c.lower()}"] = skewness(m3, out[f"var_{c.lower()}"])
    out["sigma_w"] = sigma(out["var_w"])
    out["var_t"] = covariance(p["TT"], p["T"], p["T"])
    out["flux_wt"] = covariance(p["WT"], p["W"], p["T"])        # resolved <w'theta'> [K m/s]
    out["flux_wt_model"] = p["wt_MODEL"]                          # model SGS flux [K m/s]
    out["sgs_sum"] = p["uu_SGS"] + p["vv_SGS"] + p["ww_SGS"]
    return out


def plane_moments(fields):
    """Central moments from raw plane fields (e.g. load_plane arrays) keyed um, vm, wm, uu, vv, ww.

    Returns {"U", "V", "W", "var_u", "var_v", "var_w", "sigma_w", "tke"} for the keys that can be formed.
    """
    out = {k.upper()[0]: fields[k] for k in ("um", "vm", "wm") if k in fields}
    for c in "uvw":
        if f"{c}{c}" in fields and f"{c}m" in fields:
            out[f"var_{c}"] = covariance(fields[f"{c}{c}"], fields[f"{c}m"], fields[f"{c}m"])
    if "var_w" in out:
        out["sigma_w"] = sigma(out["var_w"])
    if all(f"var_{c}" in out for c in "uvw"):
        out["tke"] = tke(out["var_u"], out["var_v"], out["var_w"])
    return out
