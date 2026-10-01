"""
Print what is in the particle .bin files of one output step: rank files found,
particle counts, and the first few rows of each field. Checks each file's size header.

Usage:
    python tools/inspect_bin.py <bin_dir> <step>
    python tools/inspect_bin.py Y:/LBM-city/20260929_particle_flat_512x128 1600
"""
import sys
import numpy as np

from data_loaders.particle_bin import FIELDS, find_ranks, load_step, source_id, release_number


def inspect(bin_dir, step, n_show=3):
    ranks = find_ranks(bin_dir, step)
    print(f"--- {bin_dir}, step {step} ---")
    print(f"Rank files: {ranks if ranks else 'none found'}")
    if not ranks:
        return

    for name in FIELDS:
        try:
            arr = load_step(bin_dir, step, fields=(name,), ranks=ranks)[name]
        except FileNotFoundError:
            print(f"\n[{name}] not written for this step")
            continue
        print(f"\n[{name}] {arr.dtype}, shape {arr.shape}")
        print(arr[:n_show])
        if name == "index":
            src = np.unique(source_id(arr))
            print(f"sources: {len(src)} ({src[:5]} ...), release numbers {release_number(arr).min()}..{release_number(arr).max()}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    inspect(sys.argv[1], int(sys.argv[2]))
