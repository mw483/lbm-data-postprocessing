import pytest

from data_loaders.local_paths import REPO_ROOT, load_local_paths, sensor_output_dir


def test_example_file_loads_and_relative_paths_use_repo_root():
    paths = load_local_paths(REPO_ROOT / "local_paths.example.yaml")
    assert paths["cache"] == REPO_ROOT / "cache"
    assert sensor_output_dir(paths, "run1").parts[-3:] == ("run1", "sensor_8x8x8", "1200-1800_sensor_density")


def test_missing_key_is_reported(tmp_path):
    f = tmp_path / "local_paths.yaml"
    f.write_text("particle_outputs: /data\nmaps: /maps\n")
    with pytest.raises(KeyError, match="cache"):
        load_local_paths(f)
