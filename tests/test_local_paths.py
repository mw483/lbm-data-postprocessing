import pytest

from data_loaders.local_paths import (
    REPO_ROOT, load_local_paths, particle_postprocess_dir, sensor_output_dir, wind_dir,
)


def test_example_file_loads_and_relative_paths_use_repo_root():
    paths = load_local_paths(REPO_ROOT / "local_paths.example.yaml")
    assert paths["cache"] == REPO_ROOT / "cache"
    assert sensor_output_dir(paths, "run1").parts[-3:] == ("run1", "sensor_8x8x8", "1200-1800_sensor_density")


def test_missing_key_is_reported(tmp_path):
    f = tmp_path / "local_paths.yaml"
    f.write_text("particle_outputs: /data\nmaps: /maps\n")
    with pytest.raises(KeyError, match="cache"):
        load_local_paths(f)


def test_run_folders_follow_case_date_tag_layout(tmp_path):
    f = tmp_path / "local_paths.yaml"
    f.write_text("particle_outputs: /data\nmaps: /maps\ncache: /c\nfigures: /f\nlbm_results: /lbm_results\n")
    paths = load_local_paths(f)
    run = "flat_512x128x1024/20261011_scalar2"
    assert wind_dir(paths, run).parts[-3:] == ("flat_512x128x1024", "20261011_scalar2", "output")
    assert particle_postprocess_dir(paths, run).parts[-1] == "particle_postprocess"


def test_run_folder_needs_lbm_results(tmp_path):
    f = tmp_path / "local_paths.yaml"
    f.write_text("particle_outputs: /data\nmaps: /maps\ncache: /c\nfigures: /f\n")
    with pytest.raises(KeyError, match="lbm_results"):
        wind_dir(load_local_paths(f), "a/b")
