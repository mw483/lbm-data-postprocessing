"""
Concentrations and simple statistics from the C++ particle counts (data_loaders/particle_postprocess.py).

Conventions
- Counts are summed over n_snapshots outputs. The mean number of particles in a cell per snapshot is
  count / n_snapshots; divided by the cell volume this is a number concentration C [particles / m^3].
- A density slab cell is dx x dx x h_ave (h_ave = slab thickness, H_AVE in the log).
- A profile.csv z cell spans the whole domain: its volume is fluid_cells x dx^3.
- Release rate q [particles / s] = particles released per output / output interval [s].
  A steady particle number N in the domain then gives a mean residence time N / q.
"""
import numpy as np
import pandas as pd


def concentration(counts, n_snapshots, cell_volume):
    """Number concentration [1/m^3] from counts summed over n_snapshots: counts / (n_snapshots * cell_volume)."""
    return np.asarray(counts, dtype=float) / (float(n_snapshots) * float(cell_volume))


def slab_cell_volume(dx, h_ave):
    """Volume [m^3] of one density-slab cell: dx * dx * h_ave."""
    return float(dx) * float(dx) * float(h_ave)


def profile_concentration(profile, n_snapshots, dx):
    """Horizontal-mean concentration [1/m^3] per z cell from read_profile output (NaN where no fluid cells)."""
    volume = profile["fluid_cells"].to_numpy(dtype=float) * float(dx) ** 3
    with np.errstate(divide="ignore", invalid="ignore"):
        c = profile["count"].to_numpy(dtype=float) / (float(n_snapshots) * volume)
    return np.where(volume > 0, c, np.nan)


def vertical_stats(z, count, quantiles=(0.5, 0.9, 0.99)):
    """Moments of the particle height distribution from counts per z cell.

    Returns {"z_mean", "sigma_z", "z_max", "z_q50", ...}: mean height, standard deviation, highest
    occupied cell centre, and the heights below which the given fractions of particles lie
    (cell centre of the first cell where the cumulative fraction reaches the quantile).
    """
    z = np.asarray(z, dtype=float)
    w = np.asarray(count, dtype=float)
    total = w.sum()
    if total <= 0:
        return {"z_mean": np.nan, "sigma_z": np.nan, "z_max": np.nan, **{_qkey(q): np.nan for q in quantiles}}
    mean = (w * z).sum() / total
    out = {
        "z_mean": mean,
        "sigma_z": np.sqrt((w * (z - mean) ** 2).sum() / total),
        "z_max": z[np.nonzero(w)[0].max()],
    }
    cum = np.cumsum(w) / total
    for q in quantiles:
        out[_qkey(q)] = z[min(np.searchsorted(cum, q), z.size - 1)]
    return out


def _qkey(q):
    return f"z_q{round(q * 100):d}"


def spanwise_stats(plane, axis=0):
    """Mean, standard deviation and coefficient of variation across one axis (default rows = y of an xy plane).

    In a case that is homogeneous in y the y-mean is the best estimate along x, and the spread across y
    is a first measure of sampling variability.
    """
    a = np.asarray(plane, dtype=float)
    mean = a.mean(axis=axis)
    std = a.std(axis=axis, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = np.where(mean > 0, std / mean, np.nan)
    return mean, std, cv


def block_stats(blocks):
    """Statistics across time blocks of equal length (same-shape arrays, e.g. one per block window).

    Returns {"mean", "std", "sem", "cv"}: block mean, sample standard deviation (ddof = 1), standard
    error of the mean std / sqrt(n_blocks), and std / mean. The standard error assumes the blocks are
    independent, which holds only when a block is much longer than the correlation time of the signal.
    """
    a = np.stack([np.asarray(b, dtype=float) for b in blocks])
    n = a.shape[0]
    if n < 2:
        raise ValueError("[ERROR] block_stats needs at least two blocks")
    mean = a.mean(axis=0)
    std = a.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = np.where(mean > 0, std / mean, np.nan)
    return {"mean": mean, "std": std, "sem": std / np.sqrt(n), "cv": cv}


def release_rate(per_output, dt_output):
    """Particles released per second: particles released each output / output interval [s]."""
    return float(per_output) / float(dt_output)


def residence_time(n_particles, rate):
    """Mean residence time [s] of a steady particle number N with release rate q: N / q."""
    return float(n_particles) / float(rate)


def count_summary(total_num, dt_output, rate):
    """Particle-number statistics over a window from read_total_num output (one row of numbers)."""
    n = total_num["n_particles"].to_numpy(dtype=float)
    t = total_num["output"].to_numpy(dtype=float) * float(dt_output)
    slope = np.polyfit(t, n, 1)[0] if n.size > 1 else np.nan
    return pd.Series({
        "n_mean": n.mean(),
        "n_min": n.min(),
        "n_max": n.max(),
        "trend_per_s": slope,            # linear trend of N [particles / s]; near 0 when the plume is steady
        "trend_vs_rate": slope / rate,   # trend as a fraction of the release rate
        "residence_time_s": residence_time(n.mean(), rate),
    })
