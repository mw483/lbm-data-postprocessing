"""Streaming particle statistics (physics_core/particle_bin_stats.py) on small hand-made arrays."""
import numpy as np
import pytest

from physics_core.particle_bin_stats import (
    add_age, add_height, add_x, age_histograms, age_in_outputs, age_stats, decode_ids, height_stats,
    load_reduced, new_age_acc, new_height_acc, new_x_acc, sample_mask, save_reduced, x_stats,
)


def test_decode_ids_and_age():
    ids = np.array([10001, 10003, 28160001 + 5])           # source 1 release 0, source 1 release 2, source 2816 release 5
    k, n = decode_ids(ids)
    assert k.tolist() == [1, 1, 2816] and n.tolist() == [0, 2, 5]
    assert age_in_outputs(ids, 1210, release_start=1200).tolist() == [10, 8, 5]


def test_sample_mask_is_fixed_and_near_fraction():
    ids = np.arange(10001, 10001 + 100000)
    m = sample_mask(ids, 0.125)
    assert m.mean() == pytest.approx(0.125, abs=0.01)
    assert np.array_equal(m, sample_mask(ids, 0.125))
    assert sample_mask(ids[:3], 1.0).all()


def test_age_accumulator():
    acc = new_age_acc(3, np.arange(0.0, 11.0, 2.0), np.arange(-2.0, 7.0, 2.0))
    add_age(acc, age=[0, 0, 1, 5], z=[1.0, 3.0, 5.0, 1.0], dx=[0.0, 2.0, 4.0, 0.0])   # age 5 is outside
    s = age_stats(acc)
    assert s["count"].tolist() == [2, 1, 0]
    assert s["z_mean"][0] == pytest.approx(2.0) and s["sigma_z"][0] == pytest.approx(1.0)
    assert s["dx_mean"][1] == pytest.approx(4.0) and np.isnan(s["z_mean"][2])
    hz, hd = age_histograms(acc)
    assert hz.shape == (3, 5) and hz[0].tolist() == [1, 1, 0, 0, 0] and hz[1, 2] == 1
    assert hd[0].tolist() == [0, 1, 1, 0]


def test_height_and_x_accumulators(tmp_path):
    h = new_height_acc(np.arange(0.0, 5.0, 2.0))
    total = np.array([[1.0, 0.0, 1.0], [3.0, 0.0, -1.0], [2.0, 0.0, 0.0]])
    sgs = np.array([[0.0, 0.0, 0.5], [0.0, 0.0, -0.5], [0.0, 0.0, 0.0]])
    add_height(h, z=[1.0, 1.5, 3.0], total=total, sgs=sgs)
    s = height_stats(h)
    assert s["count"].tolist() == [2, 1]
    assert s["u_mean"][0] == pytest.approx(2.0) and s["sigma_w"][0] == pytest.approx(1.0)
    assert s["sigma_ws"][0] == pytest.approx(0.5) and s["cov_uw"][0] == pytest.approx(-1.0)

    x = new_x_acc(np.arange(0.0, 7.0, 2.0), z_top=2.0)
    add_x(x, x=[1.0, 1.0, 3.0, 5.0], z=[0.5, 1.5, 1.0, 3.0], sgs=np.array(
        [[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 2.0, 0.0], [1.0, 1.0, 1.0]]))
    xs = x_stats(x)
    assert xs["count"].tolist() == [2, 1, 0]                 # the particle at z = 3 is above z_top
    assert xs["zero_fraction"][0] == pytest.approx(0.5)
    assert xs["e_sgs"][0] == pytest.approx(0.25) and xs["e_sgs"][1] == pytest.approx(2.0)

    save_reduced(tmp_path / "r.npz", {"dt_output": 0.8}, h, x)
    meta, data = load_reduced(tmp_path / "r.npz")
    assert meta == {"dt_output": 0.8} and data["h_count"].tolist() == [2, 1]
