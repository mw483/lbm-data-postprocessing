"""
Named sets of runs (run_sets.yaml in the repo root) and the output folder of each set.

A comparison script takes --set NAME, reads the runs of that set and writes to <figures>/<NAME>/<topic>/,
so two comparisons (e.g. convective vs neutral, old vs new convective) never overwrite each other.
Every output folder gets a runs.yaml that records the set, its runs, the data folders that were read,
the script and the repo commit.
"""
import argparse
import datetime
import subprocess
import sys
from pathlib import Path

import yaml

from data_loaders.local_paths import REPO_ROOT

RUN_SETS_FILE = REPO_ROOT / "run_sets.yaml"
MANIFEST_NAME = "runs.yaml"


def load_run_sets(path=None):
    """(default set name, {set name: {"description": str, "runs": {label: run}}}) from run_sets.yaml."""
    path = Path(path or RUN_SETS_FILE)
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    sets = raw.get("sets") or {}
    for name, s in sets.items():
        runs = (s or {}).get("runs") or {}
        if not runs:
            raise ValueError(f"[ERROR] {path}: set {name} has no runs")
        if any(not isinstance(r, str) or not r for r in runs.values()):
            raise ValueError(f"[ERROR] {path}: set {name}: every run must be a '<case>/<date>_<tag>' string")
    default = raw.get("default")
    if default is not None and default not in sets:
        raise KeyError(f"[ERROR] {path}: default set {default} is not under sets")
    return default, {name: {"description": (s or {}).get("description", ""), "runs": dict(s["runs"])}
                     for name, s in sets.items()}


def get_run_set(name=None, path=None):
    """(set name, {label: run}) of one set; the default set when name is None."""
    default, sets = load_run_sets(path)
    name = name or default
    if name is None:
        raise KeyError("[ERROR] no --set given and run_sets.yaml has no default")
    if name not in sets:
        raise KeyError(f"[ERROR] unknown set {name}; sets in run_sets.yaml: {', '.join(sets)}")
    return name, sets[name]["runs"]


def add_set_argument(parser):
    """Add --set to an argparse parser."""
    parser.add_argument("--set", dest="run_set", metavar="NAME",
                        help="run set from run_sets.yaml (default: its 'default' entry)")
    return parser


def parse_set_args(description=None, argv=None):
    """For scripts with no other options: parse --set and return (set name, {label: run})."""
    p = add_set_argument(argparse.ArgumentParser(description=description,
                                                 formatter_class=argparse.RawDescriptionHelpFormatter))
    return get_run_set(p.parse_args(argv).run_set)


def set_output_dir(paths, set_name, *topic):
    """<figures>/<set name>/<topic...>, created."""
    out = Path(paths["figures"], set_name, *topic)
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_manifest(out_dir, set_name, runs, inputs=None, script=None):
    """
    Write <out_dir>/runs.yaml: set name, runs {label: run}, the folders read per label (inputs),
    the script, the date and the repo commit. Returns the file path.
    """
    manifest = {
        "set": set_name,
        "runs": dict(runs),
        "inputs": {k: str(v) for k, v in (inputs or {}).items()},
        "script": script or Path(sys.argv[0]).name,
        "written": datetime.datetime.now().isoformat(timespec="seconds"),
        "repo_commit": _git_commit(),
    }
    path = Path(out_dir) / MANIFEST_NAME
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, sort_keys=False, allow_unicode=True)
    return path


def _git_commit():
    """Short commit of this repo, with "+dirty" when files have uncommitted changes; "unknown" without git."""
    try:
        run = lambda *a: subprocess.run(["git", "-C", str(REPO_ROOT), *a], capture_output=True, text=True,
                                        check=True).stdout.strip()
        commit = run("rev-parse", "--short", "HEAD")
        return commit + ("+dirty" if run("status", "--porcelain", "--untracked-files=no") else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
