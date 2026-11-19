"""
Particle binaries (result_particle_scatter_binary/) -> one point cloud (.vtp) per output
step, plus particles.pvd for the time series.

Point fields written (one value per particle):
    particle_id         int32, = source_id * 10000 + release
    source_id, release  int32, from particle_id (data_loaders.particle_bin)
    velocity            m/s, 3 components, what moves the particle (resolved + SGS when flg_particle = 1)
    velocity_sgs        m/s, SGS part (only when uvw_sgs files exist)
    velocity_resolved   m/s, velocity - velocity_sgs (only when uvw_sgs files exist and flg_particle = 1)
    speed               m/s, |velocity|
Positions are the solver's x, y, z in metres.
"""
import re
from pathlib import Path

import numpy as np
import pyvista as pv

from data_loaders.particle_bin import (
    find_ranks, load_step, particle_velocities, release_number, source_id,
)

from .writer import save, write_pvd

_STEP = re.compile(r"^index\d+-(\d+)\.bin$")


def list_steps(bin_dir):
    """Output numbers that have at least one index<r>-<n>.bin file, sorted."""
    return sorted({int(m[1]) for p in Path(bin_dir).glob("index*-*.bin") if (m := _STEP.match(p.name))})


def step_cloud(bin_dir, step, c_ref, flg_particle=1, every=1, sources=None):
    """PolyData of one output step, or None when no particle is left after the selection."""
    ranks = find_ranks(bin_dir, step)
    fields = ["index", "position", "uvw"]
    if all((Path(bin_dir) / f"uvw_sgs{r}-{step}.bin").exists() for r in ranks):
        fields.append("uvw_sgs")
    data = load_step(bin_dir, step, fields=fields, ranks=ranks)

    keep = np.ones(len(data["index"]), dtype=bool)
    if sources is not None:
        keep &= np.isin(source_id(data["index"]), list(sources))
    if every > 1:
        keep &= (np.arange(len(keep)) % every) == 0   # same order every step, so mostly the same particles
    if not keep.any():
        return None
    data = {k: v[keep] for k, v in data.items()}

    vel = particle_velocities(data, c_ref, flg_particle)
    cloud = pv.PolyData(np.ascontiguousarray(data["position"], dtype=np.float32))
    ids = data["index"].astype(np.int32)
    cloud["particle_id"] = ids
    cloud["source_id"] = source_id(ids).astype(np.int32)
    cloud["release"] = release_number(ids).astype(np.int32)
    cloud["velocity"] = vel["total"].astype(np.float32)
    cloud["speed"] = np.linalg.norm(vel["total"], axis=1).astype(np.float32)
    if vel["sgs"] is not None:
        cloud["velocity_sgs"] = vel["sgs"].astype(np.float32)
    if vel["resolved"] is not None and vel["sgs"] is not None:
        cloud["velocity_resolved"] = vel["resolved"].astype(np.float32)
    return cloud


def convert(bin_dir, out_dir, c_ref, steps=None, dt_output=None, flg_particle=1, every=1, sources=None):
    """
    Write out_dir/particles_<n>.vtp for each step and out_dir/particles.pvd.
    Time in the .pvd: n * dt_output [s] when dt_output is given, else the output number n.
    Returns the list of written .vtp paths.
    """
    out_dir = Path(out_dir)
    steps = steps or list_steps(bin_dir)
    if not steps:
        raise FileNotFoundError(f"[ERROR] no index*-*.bin files in {bin_dir}")
    entries = []
    for n in steps:
        cloud = step_cloud(bin_dir, n, c_ref, flg_particle, every, sources)
        if cloud is None:
            print(f"[INFO] step {n}: no particles after the selection, skipped")
            continue
        path = save(cloud, out_dir / f"particles_{n:06d}.vtp")
        entries.append((n * dt_output if dt_output else n, path))
        print(f"step {n}: {cloud.n_points} particles -> {path.name}")
    if entries:
        write_pvd(entries, out_dir / "particles.pvd")
    return [p for _, p in entries]
