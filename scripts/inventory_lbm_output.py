"""
What is in each solver output folder, and is anything missing.

For every case: lists each variable (file stem such as xy_um, xz_yav_uu, prof), its output steps
with times, and how many rank files each step has against ncpu in header.txt. For the newest
step it reads every plane variable once and checks that all ranks stitched to the expected
domain size. Prints a summary and writes inventory_<case>.csv to <figures>/<set>/inventory/.
Cases = the runs of a run set (run_sets.yaml, --set NAME).

Files with an extra plane suffix (xz_ins_*, yz_ins_*) are counted by the folder listing only.
"""

import pandas as pd

from data_loaders.lbm_output import LAYOUTS, load_plane, read_header_txt, scan_run
from data_loaders.local_paths import load_local_paths, wind_dir
from data_loaders.run_sets import parse_set_args, set_output_dir, write_manifest

# =============================================================================
# Settings
# =============================================================================
SKIP_PREFIXES = ("xy_ag_",)    # terrain-following planes repeat the xy planes on flat ground
CHECK_SHAPES = True            # read the newest step of every plane variable (slower)


def expected_sizes(header):
    """Global physical cells per axis from header.txt (nx etc. are per rank and include halos)."""
    halo = header["halo"]
    return {ax: (header[f"n{ax}"] - 2 * halo) * header[f"ncpu_{ax}"] for ax in ("x", "y", "z")}


def summarise(run_dir):
    header = read_header_txt(run_dir)
    files = scan_run(run_dir)
    files = files[~files["name"].str.startswith(SKIP_PREFIXES)]
    per_step = files.groupby(["name", "step"])["rank"].nunique().rename("n_ranks").reset_index()
    rows = []
    for name, grp in per_step.groupby("name"):
        rows.append({
            "name": name,
            "n_steps": len(grp),
            "first_step": grp["step"].min(),
            "last_step": grp["step"].max(),
            "ranks_min": grp["n_ranks"].min(),
            "ranks_max": grp["n_ranks"].max(),
        })
    table = pd.DataFrame(rows)
    table["complete"] = (table["ranks_min"] == header["ncpu"]) & (table["ranks_max"] == header["ncpu"])
    if CHECK_SHAPES:
        table["shape_check"] = [shape_check(run_dir, header, r["name"], r["last_step"]) for _, r in table.iterrows()]
    return header, table


def shape_check(run_dir, header, name, step):
    if not name.startswith(tuple(LAYOUTS)):
        return ""
    try:
        plane = load_plane(run_dir, name, step, header)
    except (ValueError, NotImplementedError, FileNotFoundError) as err:
        return f"FAIL: {err}"
    want = expected_sizes(header)
    got = next(iter(plane.data.values())).shape
    expect = tuple(want[ax] for ax in plane.axes)
    n_nan = sum(int(pd.isna(a).sum()) for a in plane.data.values())
    status = "ok" if got == expect else f"FAIL: {got} != {expect}"
    return f"{status}; {len(plane.data)} planes; {n_nan} NaN"


def main():
    set_name, runs = parse_set_args(__doc__)
    paths = load_local_paths()
    out_dir = set_output_dir(paths, set_name, "inventory")

    for label, folder in runs.items():
        run_dir = wind_dir(paths, folder)
        header, table = summarise(run_dir)
        prof_steps = sorted(int(s) for s in scan_run(run_dir).query("name == 'prof'")["step"].unique())
        print(f"\n=== {label}: {run_dir}")
        print(f"grid {expected_sizes(header)} cells, dx = {header['dx']} m, ncpu = {header['ncpu']} "
              f"({header['ncpu_x']} x {header['ncpu_y']} x {header['ncpu_z']}), t_ave = {header['t_ave']} s")
        print(f"averaging windows (prof steps): {prof_steps}")
        with pd.option_context("display.max_rows", None, "display.width", 200, "display.max_colwidth", 60):
            print(table.to_string(index=False))
        incomplete = table.loc[~table["complete"], "name"].tolist()
        print(f"[{'WARN' if incomplete else 'OK'}] variables with missing rank files: {incomplete or 'none'}")
        save = out_dir / f"inventory_{label}.csv"
        table.to_csv(save, index=False)
        print(f"[SUCCESS] Table saved to: {save}")
    write_manifest(out_dir, set_name, runs, inputs={k: wind_dir(paths, r) for k, r in runs.items()})


if __name__ == "__main__":
    main()
