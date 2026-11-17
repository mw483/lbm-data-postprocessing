import numpy as np

from data_loaders.willis_deardorff import read_wd1976_mean_height
from physics_core.cbl_dispersion import peak_height_of_density, profile_moments_of_density


def test_peak_height_finds_gaussian_maximum():
    Z = np.linspace(0, 1.5, 151)
    centres = np.array([0.1, 0.4, 0.7])
    density = np.exp(-0.5 * ((Z[None, :] - centres[:, None]) / 0.05) ** 2)
    assert np.allclose(peak_height_of_density(Z, density), centres, atol=0.011)


def test_peak_height_empty_row_is_nan_and_uniform_mean_is_half():
    Z = np.linspace(0.005, 0.995, 100)
    density = np.vstack([np.full(100, np.nan), np.ones(100)])
    peak = peak_height_of_density(Z, density)
    assert np.isnan(peak[0])
    mean, sd = profile_moments_of_density(Z, density)
    assert abs(mean[1] - 0.5) < 1e-6 and abs(sd[1] - 1 / np.sqrt(12)) < 0.01


def test_wd1976_file_has_three_sorted_series():
    ref = read_wd1976_mean_height()
    assert set(ref) == {"tank_l_zi_1.9", "tank_l_zi_4.0", "numerical_deardorff_1972"}
    for t in ref.values():
        assert np.all(np.diff(t["X"]) >= 0)
        assert t["z_mean"].between(0, 0.7).all()
