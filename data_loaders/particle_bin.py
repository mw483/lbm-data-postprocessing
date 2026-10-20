"""
Readers for the raw particle binaries written by the LBM solver
(result_particle_scatter_binary/, LSM output of Paraview_Particle.cu).

File layout, one file per rank group <r> and output number <n>:
    index<r>-<n>.bin     int32   particle ID
    position<r>-<n>.bin  float32 x, y, z [m]          (3 per particle)
    uvw<r>-<n>.bin       float32 u, v, w [lattice]    (3 per particle)
    uvw_sgs<r>-<n>.bin   float32 u, v, w SGS [m/s]    (3 per particle, flg_particle = 1 only)
    velocity<r>-<n>.bin  float32 speed [m/s]          (1 per particle)

Every file starts with one uint32 word: the payload size in bytes (fileLib::write_file).

Units, from the solver source:
    - uvw is NOT scaled: it is in lattice units. Multiply by c_ref (= velocity / cfl
      from the -velocity_lbm run argument, e.g. 2.0 / 0.02 = 100) to get m/s.
    - With flg_particle = 1, uvw is already resolved + SGS (u_tmp + u_sgs).
    - uvw_sgs and velocity are already multiplied by c_ref, so they are in m/s.

Particle ID = source_id * 10000 + release number (source IDs in particle_position.txt
are 10001, 20001, ...).
"""
import os
import re
import glob
import numpy as np

ID_BASE = 10000

# name -> (dtype, values per particle)
FIELDS = {
    "index":    (np.int32,   1),
    "position": (np.float32, 3),
    "uvw":      (np.float32, 3),
    "uvw_sgs":  (np.float32, 3),
    "velocity": (np.float32, 1),
}


def read_bin(path, dtype=np.float32, ncomp=1):
    """Read one solver .bin file, check its size header, return (N,) or (N, ncomp)."""
    with open(path, "rb") as f:
        size = int(np.fromfile(f, dtype=np.uint32, count=1)[0])
        data = np.fromfile(f, dtype=dtype)
    if data.nbytes != size:
        raise ValueError(f"{path}: header says {size} bytes, file holds {data.nbytes}")
    return data.reshape(-1, ncomp) if ncomp > 1 else data


def find_ranks(bin_dir, step, field="index"):
    """Rank-group numbers that have a <field><r>-<step>.bin file, sorted."""
    pattern = re.compile(rf"{field}(\d+)-{step}\.bin$")
    ranks = []
    for p in glob.glob(os.path.join(bin_dir, f"{field}*-{step}.bin")):
        m = pattern.search(os.path.basename(p))
        if m:
            ranks.append(int(m.group(1)))
    return sorted(ranks)


def load_step(bin_dir, step, fields=("index", "position"), ranks=None):
    """
    Load the given fields for one output step, concatenated over all rank groups.
    Returns {field: array}. Rows line up across fields.
    """
    if ranks is None:
        ranks = find_ranks(bin_dir, step)
    if not ranks:
        raise FileNotFoundError(f"No index*-{step}.bin files in {bin_dir}")

    out = {}
    for name in fields:
        dtype, ncomp = FIELDS[name]
        parts = [read_bin(os.path.join(bin_dir, f"{name}{r}-{step}.bin"), dtype, ncomp) for r in ranks]
        out[name] = np.concatenate(parts)
    return out


def particle_velocities(data, c_ref, flg_particle=1):
    """
    Physical velocities [m/s] from a load_step() result holding "uvw" (and "uvw_sgs").
    Returns {"total", "sgs", "resolved"}; "sgs" and "resolved" are None without uvw_sgs.
    With flg_particle = 1, total = resolved + SGS. Otherwise uvw is resolved only.
    """
    total = data["uvw"].astype(np.float64) * c_ref
    sgs = data.get("uvw_sgs")
    if sgs is None:
        return {"total": total, "sgs": None, "resolved": total if flg_particle != 1 else None}
    sgs = sgs.astype(np.float64)
    if flg_particle == 1:
        return {"total": total, "sgs": sgs, "resolved": total - sgs}
    return {"total": total + sgs, "sgs": sgs, "resolved": total}


def source_id(particle_ids):
    """Source number (1, 2, ...) from particle IDs."""
    return np.asarray(particle_ids) // ID_BASE


def release_number(particle_ids):
    """Release counter within its source (1 = first release)."""
    return np.asarray(particle_ids) % ID_BASE
