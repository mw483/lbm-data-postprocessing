import numpy as np
import pytest

from data_loaders.particle_bin import (
    read_bin, find_ranks, load_step, particle_velocities, source_id, release_number,
)
from conftest import write_solver_bin


def test_find_ranks(bin_dir):
    assert find_ranks(bin_dir, 1600) == [0, 1]
    assert find_ranks(bin_dir, 9999) == []


def test_load_step_concatenates_ranks(bin_dir):
    d = load_step(bin_dir, 1600, fields=("index", "position"))
    assert d["index"].tolist() == [10001, 20003, 30002]
    assert d["position"].shape == (3, 3)
    assert d["position"][2].tolist() == [7, 8, 9]


def test_missing_step_raises(bin_dir):
    with pytest.raises(FileNotFoundError):
        load_step(bin_dir, 1234)


def test_header_mismatch_detected(tmp_path):
    p = tmp_path / "bad.bin"
    with open(p, "wb") as f:
        np.array([999], np.uint32).tofile(f)
        np.zeros(3, np.float32).tofile(f)
    with pytest.raises(ValueError):
        read_bin(p)


def test_velocities_in_m_per_s_without_double_count(bin_dir):
    d = load_step(bin_dir, 1600, fields=("uvw", "uvw_sgs"))
    vel = particle_velocities(d, c_ref=100.0, flg_particle=1)
    np.testing.assert_allclose(vel["sgs"][0], [0.1, 0.2, 0.3], atol=1e-6)
    np.testing.assert_allclose(vel["resolved"][0], [2.0, 0.0, 0.0], atol=1e-4)
    np.testing.assert_allclose(vel["total"][0], [2.1, 0.2, 0.3], atol=1e-4)


def test_id_decoding():
    ids = np.array([10001, 10600, 20001, 54561234])
    assert source_id(ids).tolist() == [1, 1, 2, 5456]
    assert release_number(ids).tolist() == [1, 600, 1, 1234]
