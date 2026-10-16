"""
What is in each solver output folder, and is anything missing.

For every case: lists each variable (file stem such as xy_um, xz_yav_uu, prof), its output steps
with times, and how many rank files each step has against ncpu in header.txt. For the newest
step it reads every plane variable once and checks that all ranks stitched to the expected
domain size. Prints a summary and writes inventory_<case>.csv.

Files with an extra plane suffix (xz_ins_*, yz_ins_*) are counted by the folder listing only.
"""
from pathlib import Path

import pandas as pd

from data_loaders.lbm_output import LAYOUTS, load_plane, read_header_txt, scan_run
from data_loaders.local_paths import load_local_paths

# =============================================================================
# Settings
# =============================================================================
CASES = {
    # label: run folder under wind_outputs in local_paths.yaml (the folder holding the CSV files)
    "convective": "20261011_output_flat_512x128x1024_scalar2",
    # "neutral": "<date>_output_flat_512x128x1024_neutral",
}
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
    paths = load_local_paths()
    if "wind_outputs" not in paths:
        raise KeyError("[ERROR] set wind_outputs in local_paths.yaml (folder holding the run output folders)")
    out_dir = paths["figures"] / "scalar2_outputs" / "inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    for label, folder in CASES.items():
        run_dir = Path(paths["wind_outputs"]) / folder
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


if __name__ == "__main__":
    main()
