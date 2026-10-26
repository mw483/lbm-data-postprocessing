import pytest
import yaml

from data_loaders.local_paths import load_local_paths, particle_reduced_dir
from data_loaders.run_sets import (
    RUN_SETS_FILE, get_run_set, load_run_sets, parse_set_args, set_output_dir, write_manifest,
)

SETS = """
default: a_vs_b
sets:
  a_vs_b:
    description: two runs
    runs:
      a: case/20261011_a
      b: case/20261017_b
  three:
    runs:
      x: case/1
      y: case/2
      z: case/3
"""


@pytest.fixture
def sets_file(tmp_path):
    f = tmp_path / "run_sets.yaml"
    f.write_text(SETS)
    return f


def test_repo_run_sets_file_loads():
    default, sets = load_run_sets(RUN_SETS_FILE)
    assert default in sets
    assert all(s["runs"] for s in sets.values())


def test_default_set_and_named_set_keep_order(sets_file):
    assert get_run_set(None, sets_file) == ("a_vs_b", {"a": "case/20261011_a", "b": "case/20261017_b"})
    name, runs = get_run_set("three", sets_file)
    assert name == "three" and list(runs) == ["x", "y", "z"]


def test_unknown_set_lists_the_known_ones(sets_file):
    with pytest.raises(KeyError, match="a_vs_b, three"):
        get_run_set("nope", sets_file)


def test_set_without_runs_is_refused(tmp_path):
    f = tmp_path / "run_sets.yaml"
    f.write_text("sets:\n  empty:\n    runs: {}\n")
    with pytest.raises(ValueError, match="empty"):
        load_run_sets(f)


def test_default_must_name_a_set(tmp_path):
    f = tmp_path / "run_sets.yaml"
    f.write_text("default: gone\nsets:\n  s:\n    runs:\n      a: c/r\n")
    with pytest.raises(KeyError, match="gone"):
        load_run_sets(f)


def test_parse_set_args_reads_the_repo_file():
    name, runs = parse_set_args(argv=["--set", "flat512_sgsfix"])
    assert name == "flat512_sgsfix" and len(runs) == 2


def test_output_dir_is_per_set_and_manifest_records_runs(tmp_path):
    paths = {"figures": tmp_path / "figures"}
    out_a = set_output_dir(paths, "set_a", "particle_bins")
    out_b = set_output_dir(paths, "set_b", "particle_bins")
    assert out_a != out_b and out_a.is_dir() and out_a.parts[-2:] == ("set_a", "particle_bins")
    f = write_manifest(out_a, "set_a", {"old": "c/r1", "new": "c/r2"}, inputs={"old": tmp_path / "in"}, script="t.py")
    m = yaml.safe_load(f.read_text())
    assert m["set"] == "set_a" and list(m["runs"]) == ["old", "new"]
    assert m["inputs"]["old"] == str(tmp_path / "in") and m["script"] == "t.py" and m["repo_commit"]


def _paths(tmp_path, extra):
    f = tmp_path / "local_paths.yaml"
    f.write_text("particle_outputs: /d\nmaps: /m\ncache: /c\nfigures: /f\n" + extra)
    return load_local_paths(f)


def test_reduced_dir_prefers_lbm_reduced_then_lbm_results(tmp_path):
    run = "flat/20261026_scalar2"
    red, res = tmp_path / "reduced", tmp_path / "results"
    paths = _paths(tmp_path, f"lbm_reduced: {red}\nlbm_results: {res}\n")
    (res / run / "particle_reduced").mkdir(parents=True)
    assert particle_reduced_dir(paths, run) == res / run / "particle_reduced"
    (red / run / "particle_reduced").mkdir(parents=True)
    assert particle_reduced_dir(paths, run) == red / run / "particle_reduced"


def test_missing_reduced_dir_names_every_place_looked(tmp_path):
    paths = _paths(tmp_path, f"lbm_reduced: {tmp_path / 'r1'}\nlbm_results: {tmp_path / 'r2'}\n")
    with pytest.raises(FileNotFoundError, match="r1.*r2"):
        particle_reduced_dir(paths, "c/run")
