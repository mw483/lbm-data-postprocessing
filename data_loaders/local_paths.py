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
OPTIONAL_KEYS = ("wind_outputs",)   # folder holding the solver Output folders (<date>_output_<case>)


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
