"""
Streaming statistics over the raw particle binaries (data_loaders/particle_bin.py), one output at a time.

Kept to numpy and Python 3.9 so it runs on a TSUBAME interactive node next to the data.
Every accumulator is a dict of numpy arrays that np.bincount adds into, so memory does not grow with
the number of outputs; save_reduced / load_reduced write and read them as one .npz.

Particle IDs (src/Generate_Particle_GPU.cu): id = source_label + n, where source_label is the 8th column of
particle_position.txt (k * 10^ID_DIGIT + 1 for source line k) and n counts releases since the first one.
So source line k = id // 10^ID_DIGIT and release n = id % 10^ID_DIGIT - 1. Release n happens at output
release_start + n * release_every, which gives the particle age at any output.
"""
import json

import numpy as np

ID_BASE = 10000


# -----------------------------------------------------------------------------
# IDs, ages, sources
# -----------------------------------------------------------------------------
def decode_ids(ids, id_base=ID_BASE):
    """(source line k, 1-based; release number n, 0-based) from particle IDs."""
    ids = np.asarray(ids, dtype=np.int64)
    return ids // id_base, ids % id_base - 1


def age_in_outputs(ids, output, release_start, release_every=1, id_base=ID_BASE):
    """Particle age in outputs at this output number: output - (release_start + n * release_every)."""
    _, n = decode_ids(ids, id_base)
    return int(output) - (int(release_start) + n * int(release_every))


def read_sources(path):
    """particle_position.txt -> (x, y, z) arrays [m], indexed by source line k - 1."""
    a = np.loadtxt(path, ndmin=2)
    return a[:, 0], a[:, 1], a[:, 2]


def sample_mask(ids, fraction):
    """The same pseudo-random subset of particles at every output: keep an ID when its hash < fraction.

    Knuth's multiplicative hash spreads neighbouring IDs (same source, next release) over the range,
    so the subset is not striped by source or release.
    """
    if fraction >= 1.0:
        return np.ones(np.shape(ids), dtype=bool)
    h = (np.asarray(ids, dtype=np.uint64) * np.uint64(2654435761)) % np.uint64(2**32)
    return h < np.uint64(int(fraction * 2**32))


# -----------------------------------------------------------------------------
# Accumulators
# -----------------------------------------------------------------------------
def _bins(values, edges):
    """Bin index of each value for regular edges; -1 outside."""
    edges = np.asarray(edges, dtype=float)
    width = edges[1] - edges[0]
    idx = np.floor((np.asarray(values, dtype=float) - edges[0]) / width).astype(np.int64)
    idx[(idx < 0) | (idx >= edges.size - 1)] = -1
    return idx


def _add(acc, key, idx, weights=None, size=None):
    ok = idx >= 0
    w = None if weights is None else np.asarray(weights, dtype=float)[ok]
    acc[key] += np.bincount(idx[ok], weights=w, minlength=size if size is not None else acc[key].size)[: acc[key].size]


def new_age_acc(n_age, z_edges, dx_edges):
    """Statistics against age [outputs]: 2D histograms age x z and age x (x - x_source), plus z sums."""
    nz, nd = len(z_edges) - 1, len(dx_edges) - 1
    return {
        "age_z_edges": np.asarray(z_edges, dtype=float),
        "age_dx_edges": np.asarray(dx_edges, dtype=float),
        "age_count": np.zeros(n_age),
        "age_sum_z": np.zeros(n_age),
        "age_sum_z2": np.zeros(n_age),
        "age_sum_dx": np.zeros(n_age),
        "age_sum_dx2": np.zeros(n_age),
        "age_hist_z": np.zeros(n_age * nz),
        "age_hist_dx": np.zeros(n_age * nd),
    }


def add_age(acc, age, z, dx):
    """Add particles with age [outputs], height z [m] and downwind travel dx = x - x_source [m]."""
    n_age = acc["age_count"].size
    a = np.asarray(age, dtype=np.int64)
    a = np.where((a >= 0) & (a < n_age), a, -1)
    _add(acc, "age_count", a)
    _add(acc, "age_sum_z", a, z)
    _add(acc, "age_sum_z2", a, np.asarray(z, dtype=float) ** 2)
    _add(acc, "age_sum_dx", a, dx)
    _add(acc, "age_sum_dx2", a, np.asarray(dx, dtype=float) ** 2)
    for key, edges, v in (("age_hist_z", acc["age_z_edges"], z), ("age_hist_dx", acc["age_dx_edges"], dx)):
        b = _bins(v, edges)
        flat = np.where((a >= 0) & (b >= 0), a * (edges.size - 1) + b, -1)
        _add(acc, key, flat)


def new_height_acc(z_edges):
    """Particle velocity moments per height bin: total (resolved + SGS) and SGS parts."""
    n = len(z_edges) - 1
    acc = {"h_z_edges": np.asarray(z_edges, dtype=float), "h_count": np.zeros(n)}
    for c in ("u", "v", "w", "us", "vs", "ws"):
        acc[f"h_sum_{c}"] = np.zeros(n)
        acc[f"h_sum_{c}2"] = np.zeros(n)
    acc["h_sum_uw"] = np.zeros(n)
    return acc


def add_height(acc, z, total, sgs):
    """total, sgs: (N, 3) velocities [m/s] (particle_bin.particle_velocities)."""
    b = _bins(z, acc["h_z_edges"])
    _add(acc, "h_count", b)
    for i, c in enumerate("uvw"):
        _add(acc, f"h_sum_{c}", b, total[:, i])
        _add(acc, f"h_sum_{c}2", b, total[:, i] ** 2)
        _add(acc, f"h_sum_{c}s", b, sgs[:, i])
        _add(acc, f"h_sum_{c}s2", b, sgs[:, i] ** 2)
    _add(acc, "h_sum_uw", b, total[:, 0] * total[:, 2])


def new_x_acc(x_edges, z_top):
    """SGS velocity along x for particles below z_top: tests what happens at the GPU rank boundaries."""
    n = len(x_edges) - 1
    return {
        "x_edges": np.asarray(x_edges, dtype=float), "x_z_top": np.array(float(z_top)),
        "x_count": np.zeros(n), "x_sum_esgs": np.zeros(n), "x_sum_ws2": np.zeros(n), "x_zero_sgs": np.zeros(n),
        "x_sum_z": np.zeros(n),
    }


def add_x(acc, x, z, sgs):
    """Per x bin, particles below z_top: count, sum of u_s^2 + v_s^2 + w_s^2, sum of w_s^2, count with SGS = 0, sum z."""
    low = np.asarray(z) < float(acc["x_z_top"])
    b = np.where(low, _bins(x, acc["x_edges"]), -1)
    e = (sgs ** 2).sum(axis=1)
    _add(acc, "x_count", b)
    _add(acc, "x_sum_esgs", b, e)
    _add(acc, "x_sum_ws2", b, sgs[:, 2] ** 2)
    _add(acc, "x_zero_sgs", b, (e == 0.0).astype(float))
    _add(acc, "x_sum_z", b, z)


def new_plume_acc(dx_edges, z_edges):
    """Crosswind-integrated plume from all sources, measured from each particle's own source.

    One 2D histogram over (x - x_source, z), every particle weighted by 1 / (number of outputs read at which
    its age can occur); with that weight, every age counts once per release, so plume_concentration()
    turns the sum into the steady crosswind-integrated concentration of one continuous point source.
    """
    nd, nz = len(dx_edges) - 1, len(z_edges) - 1
    return {"plume_dx_edges": np.asarray(dx_edges, dtype=float), "plume_z_edges": np.asarray(z_edges, dtype=float),
            "plume_hist": np.zeros(nd * nz)}


def add_plume(acc, dx, z, weight):
    """Add particles with downwind distance dx = x - x_source [m], height z [m] and weight 1 / S(age)."""
    nz = acc["plume_z_edges"].size - 1
    bd, bz = _bins(dx, acc["plume_dx_edges"]), _bins(z, acc["plume_z_edges"])
    _add(acc, "plume_hist", np.where((bd >= 0) & (bz >= 0), bd * nz + bz, -1), weight)


def outputs_per_age(outputs, release_start, release_every, n_age):
    """S(a): how many of the outputs read can hold a particle of age a [outputs] (a = 0 .. n_age - 1).

    Age a occurs at output n when n - a is a release output: n - a >= release_start and
    (n - a - release_start) % release_every == 0.
    """
    s = np.zeros(n_age)
    for n in outputs:
        a = np.arange(n_age)
        released = n - a
        s += ((released >= release_start) & ((released - release_start) % release_every == 0)).astype(float)
    return s


# -----------------------------------------------------------------------------
# Derived statistics
# -----------------------------------------------------------------------------
def _div(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(b > 0, a / b, np.nan)


def age_stats(acc):
    """{"count", "z_mean", "sigma_z", "dx_mean", "sigma_dx"} per age bin."""
    n = acc["age_count"]
    zm = _div(acc["age_sum_z"], n)
    dm = _div(acc["age_sum_dx"], n)
    return {
        "count": n,
        "z_mean": zm,
        "sigma_z": np.sqrt(np.clip(_div(acc["age_sum_z2"], n) - zm ** 2, 0, None)),
        "dx_mean": dm,
        "sigma_dx": np.sqrt(np.clip(_div(acc["age_sum_dx2"], n) - dm ** 2, 0, None)),
    }


def age_histograms(acc):
    """(hist_z [n_age, nz], hist_dx [n_age, nd]) as counts."""
    n_age = acc["age_count"].size
    return (acc["age_hist_z"].reshape(n_age, -1), acc["age_hist_dx"].reshape(n_age, -1))


def height_stats(acc):
    """Mean and standard deviation of each velocity component per height bin, plus <u'w'> of the total."""
    n = acc["h_count"]
    out = {"z": 0.5 * (acc["h_z_edges"][1:] + acc["h_z_edges"][:-1]), "count": n}
    for c in ("u", "v", "w", "us", "vs", "ws"):
        m = _div(acc[f"h_sum_{c}"], n)
        out[f"{c}_mean"] = m
        out[f"sigma_{c}"] = np.sqrt(np.clip(_div(acc[f"h_sum_{c}2"], n) - m ** 2, 0, None))
    out["cov_uw"] = _div(acc["h_sum_uw"], n) - out["u_mean"] * out["w_mean"]
    return out


def x_stats(acc):
    """Per x bin: count, mean SGS energy 0.5 (u_s^2 + v_s^2 + w_s^2), rms w_s, fraction with zero SGS, mean z."""
    n = acc["x_count"]
    return {
        "x": 0.5 * (acc["x_edges"][1:] + acc["x_edges"][:-1]),
        "count": n,
        "e_sgs": 0.5 * _div(acc["x_sum_esgs"], n),
        "rms_ws": np.sqrt(_div(acc["x_sum_ws2"], n)),
        "zero_fraction": _div(acc["x_zero_sgs"], n),
        "z_mean": _div(acc["x_sum_z"], n),
    }


def plume_concentration(acc, n_sources, release_interval):
    """Steady crosswind-integrated concentration per unit release rate, C_y / Q [s/m^2], on (dx, z) bins.

    For a continuous point source C_y(x, z) / Q = integral over age of p(x, z | age); with one particle per
    source per release interval tau, the weighted histogram H gives C_y / Q = H tau / (n_sources dx dz).
    Returns (dx centres, z centres, array [n_dx, n_z]). Only complete for distances that particles reach
    within the oldest age read.
    """
    dx_e, z_e = acc["plume_dx_edges"], acc["plume_z_edges"]
    h = acc["plume_hist"].reshape(dx_e.size - 1, z_e.size - 1)
    cy = h * release_interval / (n_sources * np.diff(dx_e)[:, None] * np.diff(z_e)[None, :])
    return 0.5 * (dx_e[1:] + dx_e[:-1]), 0.5 * (z_e[1:] + z_e[:-1]), cy


# -----------------------------------------------------------------------------
# Files
# -----------------------------------------------------------------------------
def save_reduced(path, meta, *accs):
    """All accumulators in one .npz; meta (a JSON-able dict) is stored as the 'meta' entry."""
    arrays = {}
    for acc in accs:
        arrays.update(acc)
    np.savez_compressed(path, meta=np.array(json.dumps(meta)), **arrays)


def load_reduced(path):
    """(meta dict, {name: array}) from save_reduced."""
    with np.load(path) as f:
        data = {k: f[k] for k in f.files if k != "meta"}
        meta = json.loads(str(f["meta"]))
    return meta, data
