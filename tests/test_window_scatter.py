import numpy as np
import pandas as pd
import pytest

from physics_core.window_scatter import between_run_spread, layer_mean, quantity_table, within_run_change

Z = [1.0, 101.0, 201.0]


def windows(values):
    """{step: (time, moments)} with one quantity q; values[step index] = list over Z."""
    return {s: (200.0 * (i + 1), pd.DataFrame({"z": Z, "q": v}))
            for i, (s, v) in enumerate(zip((25001, 50001, 75001), values))}


def test_quantity_table_is_z_by_step():
    t = quantity_table(windows([[1, 2, 3], [4, 5, 6]]), "q")
    assert list(t.columns) == [25001, 50001] and list(t.index) == Z
    assert t.loc[101.0, 50001] == 5


def test_between_run_spread_uses_common_steps_and_any_number_of_runs():
    a = quantity_table(windows([[1, 2, 3], [4, 5, 6], [7, 8, 9]]), "q")
    b = quantity_table(windows([[1, 1, 1], [6, 5, 4]]), "q")
    c = quantity_table(windows([[0, 2, 5], [4, 9, 6]]), "q")
    s = between_run_spread({"a": a, "b": b, "c": c})
    assert list(s.columns) == [25001, 50001]
    np.testing.assert_allclose(s[25001], [1, 1, 4])
    np.testing.assert_allclose(s[50001], [2, 4, 2])


def test_within_run_change_drops_first_window():
    t = quantity_table(windows([[1, 2, 3], [4, 0, 3], [4, 1, 1]]), "q")
    w = within_run_change(t)
    assert list(w.columns) == [50001, 75001]
    np.testing.assert_allclose(w[50001], [3, 2, 0])
    np.testing.assert_allclose(w[75001], [0, 1, 2])


def test_layer_mean_limits_heights_and_skips_nan():
    t = pd.DataFrame({7: [10.0, np.nan, 4.0]}, index=Z)
    assert layer_mean(t, (100.0, 400.0))[7] == pytest.approx(4.0)
    assert layer_mean(t, (0.0, 400.0))[7] == pytest.approx(7.0)
