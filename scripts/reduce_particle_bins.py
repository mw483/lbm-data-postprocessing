"""
Reduce the raw particle binaries of one run to small files that can be copied to a PC.

Runs where the binaries are (TSUBAME interactive node); needs only Python 3.9 and numpy:
  cd lbm-data-postprocessing
  python3 -m scripts.reduce_particle_bins --bin-dir <..._particle_..._scalar2> \
      --sources <LBM-city>/cases/flat_512x128x1024/particle_position/particle_position.txt \
      --out <folder>/particle_reduced_scalar2

Reads index, position (every output) and uvw, uvw_sgs (every --vel-stride outputs) between --first and --last,
and writes into --out:
  reduced.npz             accumulators of physics_core/particle_bin_stats.py:
                            age:    z and downwind travel against particle age (sources with x <= --upstream-xmax,
                                    so particles are not lost through the outflow before --max-age)
                            height: particle velocity moments per 2 m height bin (total and SGS)
                            x:      SGS velocity per 2 m x bin below --sgs-ztop (rank-boundary check)
  snapshots/snap_<n>.npz  every --snap-every outputs: x, y, z, age [s], id of a fixed --snap-fraction of particles
Copy the --out folder to <lbm_results>/<case>/<date>_<tag>/particle_reduced on the PC for
plot_particle_bin_stats.py and animate_particles.py.
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_loaders.particle_bin import find_ranks, load_step, particle_velocities  # noqa: E402
from physics_core.particle_bin_stats import (  # noqa: E402
    add_age, add_height, add_x, age_in_outputs, decode_ids, new_age_acc, new_height_acc, new_x_acc,
    read_sources, sample_mask, save_reduced,
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bin-dir", required=True, help="folder with index<r>-<n>.bin, position<r>-<n>.bin, ...")
    p.add_argument("--sources", required=True, help="particle_position.txt of the case")
    p.add_argument("--out", required=True, help="output folder")
    p.add_argument("--first", type=int, default=1200, help="first output (default 1200)")
    p.add_argument("--last", type=int, default=1800, help="last output, included (default 1800)")
    p.add_argument("--release-start", type=int, default=1200, help="output of the first release (read_particle_box)")
    p.add_argument("--release-every", type=int, default=1, help="outputs between releases (generate_step / pout)")
    p.add_argument("--dt-output", type=float, default=0.8, help="seconds per output (dt x pout)")
    p.add_argument("--c-ref", type=float, default=250.0, help="c_ref = velocity / cfl, converts uvw to m/s")
    p.add_argument("--dx", type=float, default=2.0, help="cell size [m], bin width of the height and x statistics")
    p.add_argument("--lx", type=float, default=1024.0, help="domain length in x [m]")
    p.add_argument("--lz", type=float, default=2048.0, help="domain height [m]")
    p.add_argument("--upstream-xmax", type=float, default=104.0,
                   help="age statistics only for sources with x <= this [m] (default 104)")
    p.add_argument("--max-age", type=int, default=600, help="age bins in outputs (default 600)")
    p.add_argument("--vel-stride", type=int, default=5, help="read uvw, uvw_sgs every this many outputs (default 5)")
    p.add_argument("--sgs-ztop", type=float, default=10.0, help="x statistics for particles below this height [m]")
    p.add_argument("--snap-every", type=int, default=5, help="snapshot every this many outputs, 0 = none (default 5)")
    p.add_argument("--snap-fraction", type=float, default=0.125, help="fraction of particles in snapshots")
    return p.parse_args()


def main():
    a = parse_args()
    os.makedirs(a.out, exist_ok=True)
    snap_dir = os.path.join(a.out, "snapshots")
    if a.snap_every > 0:
        os.makedirs(snap_dir, exist_ok=True)

    sx, sy, sz = read_sources(a.sources)
    upstream = np.zeros(sx.size + 2, dtype=bool)          # indexed by source line k (1-based)
    upstream[1:sx.size + 1] = sx <= a.upstream_xmax
    src_x = np.concatenate([[np.nan], sx, [np.nan]])

    age_acc = new_age_acc(a.max_age, np.arange(0.0, a.lz + a.dx, a.dx), np.arange(-100.0, a.lx + a.dx, a.dx))
    height_acc = new_height_acc(np.arange(0.0, a.lz + a.dx, a.dx))
    x_acc = new_x_acc(np.arange(0.0, a.lx + a.dx, a.dx), a.sgs_ztop)

    t0, used = time.time(), []
    for n in range(a.first, a.last + 1):
        ranks = find_ranks(a.bin_dir, n)
        if not ranks:
            print(f"[WARNING] output {n}: no index*-{n}.bin, skipped")
            continue
        with_vel = (n - a.first) % a.vel_stride == 0
        fields = ("index", "position", "uvw", "uvw_sgs") if with_vel else ("index", "position")
        d = load_step(a.bin_dir, n, fields=fields, ranks=ranks)
        ids, pos = d["index"], d["position"].astype(np.float64)
        k, _ = decode_ids(ids)
        k = np.clip(k, 0, sx.size + 1)
        age = age_in_outputs(ids, n, a.release_start, a.release_every)
        up = upstream[k]
        add_age(age_acc, age[up], pos[up, 2], pos[up, 0] - src_x[k[up]])
        if with_vel:
            v = particle_velocities(d, a.c_ref, flg_particle=1)
            add_height(height_acc, pos[:, 2], v["total"], v["sgs"])
            add_x(x_acc, pos[:, 0], pos[:, 2], v["sgs"])
        if a.snap_every > 0 and (n - a.first) % a.snap_every == 0:
            m = sample_mask(ids, a.snap_fraction)
            np.savez_compressed(
                os.path.join(snap_dir, f"snap_{n:05d}.npz"),
                x=pos[m, 0].astype(np.float32), y=pos[m, 1].astype(np.float32), z=pos[m, 2].astype(np.float32),
                age=(age[m] * a.dt_output).astype(np.float32), id=ids[m].astype(np.int32),
                output=np.array(n), time=np.array(n * a.dt_output), n_total=np.array(ids.size),
            )
        used.append(n)
        if len(used) % 50 == 1:
            print(f"output {n}: {ids.size} particles, {time.time() - t0:.0f} s elapsed", flush=True)

    if not used:
        sys.exit(f"[ERROR] no output between {a.first} and {a.last} in {a.bin_dir}")
    meta = {k: getattr(a, k) for k in vars(a)}
    meta.update({"outputs_read": len(used), "first_read": used[0], "last_read": used[-1],
                 "n_upstream_sources": int(upstream.sum())})
    save_reduced(os.path.join(a.out, "reduced.npz"), meta, age_acc, height_acc, x_acc)
    print(f"[SUCCESS] {len(used)} outputs reduced in {time.time() - t0:.0f} s -> {a.out}")


if __name__ == "__main__":
    main()
