"""
Per-machine data folders, read from local_paths.yaml in the repo root.

local_paths.yaml is git-ignored, so each machine (lab PC, laptop) keeps its own copy.
Start from local_paths.example.yaml. Set LBM_LOCAL_PATHS to use a file elsewhere.
"""
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
KEYS = ("particle_outputs", "maps", "cache", "figures")
OPTIONAL_KEYS = (
    "wind_outputs",   # old layout: folder holding the solver Output folders (<date>_output_<case>)
    "lbm_results",    # new layout: <case>/<date>_<tag>/{output,particle_postprocess} below this folder
    "lbm_cases",      # an LBM-city cases/ folder: <case>/map/*.dat, <case>/particle_position/particle_position.txt
    "lbm_reduced",    # reducer outputs kept apart from lbm_results: <case>/<date>_<tag>/particle_reduced below it
)


def load_local_paths(path=None):
    """
    Returns {key: Path} for the keys in KEYS, plus any OPTIONAL_KEYS that are set.
    Relative entries are taken from the repo root.
    """
    path = Path(path or os.environ.get("LBM_LOCAL_PATHS") or REPO_ROOT / "local_paths.yaml")
    if not path.exists():
        raise FileNotFoundError(
            f"[ERROR] {path} not found. Copy local_paths.example.yaml to local_paths.yaml "
            "and set the folders for this machine."
        )
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    missing = [k for k in KEYS if not raw.get(k)]
    if missing:
        raise KeyError(f"[ERROR] {path} has no entry for: {', '.join(missing)}")

    paths = {}
    for key in KEYS + tuple(k for k in OPTIONAL_KEYS if raw.get(k)):
        p = Path(os.path.expanduser(str(raw[key])))
        paths[key] = p if p.is_absolute() else REPO_ROOT / p
    return paths


def sensor_output_dir(paths, run, sensor_folder="sensor_8x8x8", window="1200-1800_sensor_density"):
    """Folder with sensor_hit_ids.txt and target_trajectories.csv for one C++ post-processing run."""
    return paths["particle_outputs"] / run / sensor_folder / window


def wind_dir(paths, run):
    """Folder with the solver's wind CSV files of one run, e.g. run = "flat_512x128x1024/20261011_scalar2"."""
    return _run_subfolder(paths, run, "output")


def particle_postprocess_dir(paths, run):
    """Folder with the post-processed particle files (e.g. density CSV) of one run (same run name as wind_dir)."""
    return _run_subfolder(paths, run, "particle_postprocess")


def particle_reduced_dir(paths, run):
    """
    Folder with the output of scripts/reduce_particle_bins.py for one run (reduced.npz, snapshots/).

    Looks in <lbm_reduced>/<run>/particle_reduced first (when lbm_reduced is set), then in
    <lbm_results>/<run>/particle_reduced, and returns the first that exists.
    """
    roots = [k for k in ("lbm_reduced", "lbm_results") if k in paths]
    if not roots:
        raise KeyError("[ERROR] set lbm_reduced or lbm_results in local_paths.yaml")
    candidates = [paths[k] / run / "particle_reduced" for k in roots]
    for c in candidates:
        if c.is_dir():
            return c
    raise FileNotFoundError(f"[ERROR] no particle_reduced folder for {run}; looked in: "
                            + ", ".join(str(c) for c in candidates))


def case_map_dir(paths, case):
    """Map set folder (topography, building, vegetation .dat) of an LBM-city case, e.g. case = "flat_512x128x1024"."""
    return _case_folder(paths, case) / "map"


def case_sources_file(paths, case):
    """particle_position.txt of an LBM-city case."""
    return _case_folder(paths, case) / "particle_position" / "particle_position.txt"


def _case_folder(paths, case):
    if "lbm_cases" not in paths:
        raise KeyError("[ERROR] set lbm_cases in local_paths.yaml (an LBM-city cases/ folder)")
    return paths["lbm_cases"] / case


def _run_subfolder(paths, run, sub):
    if "lbm_results" not in paths:
        raise KeyError("[ERROR] set lbm_results in local_paths.yaml (folder holding <case>/<date>_<tag>/output ...)")
    return paths["lbm_results"] / run / sub
