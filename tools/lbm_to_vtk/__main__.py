"""
Command line for the converters. From the repository root:

    python -m tools.lbm_to_vtk particles <bin_dir> <out_dir> --c-ref 100 [--dt-output 0.8] [--every 10] [--sources 1 2]
    python -m tools.lbm_to_vtk slices <run_output_dir> <out_dir> [--families xy_ xz_] [--variables um vm wm] [--steps 25001]
    python -m tools.lbm_to_vtk map <map_dir> <out_dir> [--dx 2] [--crop i0 i1 j0 j1] [--stride N]

See tools/lbm_to_vtk/README.md.
"""
import argparse

from . import maps, particles, slices


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tools.lbm_to_vtk", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("particles", help="particle .bin files -> .vtp per step + particles.pvd")
    p.add_argument("bin_dir"); p.add_argument("out_dir")
    p.add_argument("--c-ref", type=float, required=True,
                   help="lattice -> m/s factor for uvw (header.txt c_ref, = velocity_lbm / cfl)")
    p.add_argument("--steps", type=int, nargs="+", help="output numbers (default: all found)")
    p.add_argument("--dt-output", type=float, help="seconds per output number, for the .pvd time")
    p.add_argument("--flg-particle", type=int, default=1, help="1 (default): uvw already includes SGS")
    p.add_argument("--every", type=int, default=1, help="keep every N-th particle")
    p.add_argument("--sources", type=int, nargs="+", help="keep only these source IDs")

    s = sub.add_parser("slices", help="legacy CSV planes -> .vti per plane and step + .pvd per plane")
    s.add_argument("run_dir"); s.add_argument("out_dir")
    s.add_argument("--families", nargs="+", default=list(slices.DEFAULT_FAMILIES),
                   choices=list(slices.FAMILIES))
    s.add_argument("--variables", nargs="+", help="names without prefix, e.g. um vm wm (default: all)")
    s.add_argument("--steps", type=int, nargs="+", help="solver steps (default: all found)")

    m = sub.add_parser("map", help="map set .dat -> ground/buildings/trees .vtp")
    m.add_argument("map_dir"); m.add_argument("out_dir")
    m.add_argument("--dx", type=float, default=2.0, help="cell size [m] (default 2)")
    m.add_argument("--crop", type=int, nargs=4, metavar=("I0", "I1", "J0", "J1"))
    m.add_argument("--stride", type=int, help="N x N coarsening (default: auto)")

    a = ap.parse_args(argv)
    if a.cmd == "particles":
        particles.convert(a.bin_dir, a.out_dir, a.c_ref, a.steps, a.dt_output, a.flg_particle, a.every, a.sources)
    elif a.cmd == "slices":
        slices.convert(a.run_dir, a.out_dir, tuple(a.families), a.variables, a.steps)
    else:
        maps.convert(a.map_dir, a.out_dir, a.dx, tuple(a.crop) if a.crop else None, a.stride)


if __name__ == "__main__":
    main()
