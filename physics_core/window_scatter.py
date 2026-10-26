"""
Run-to-run spread versus window-to-window change of the horizontal-mean profiles (prof*.csv windows).

Two runs that differ only in the random initial disturbance (std::random_device seed) are two samples
of the same flow. Their difference in one averaging window is sampling noise when it is about as large
as the change between consecutive windows of one run, which has the same sampling noise plus the slow
trend of the flow (z_i growth, wind decay). So the within-run change is an upper bound of the noise
of one window, and a run-to-run spread well above it points to a real difference between the runs.

Tables are DataFrames with the height z as index and one column per output step (window end).
"""
import numpy as np
import pandas as pd


def quantity_table(windows, quantity):
    """{step: (time, profile_moments DataFrame)} -> DataFrame of one quantity, index z, columns steps (sorted)."""
    cols = {step: df.set_index("z")[quantity] for step, (_, df) in sorted(windows.items())}
    return pd.DataFrame(cols)


def between_run_spread(tables):
    """
    {run: quantity_table} -> max - min over the runs, on the heights and steps that every run has.
    With two runs this is |run a - run b|.
    """
    tables = list(tables.values())
    steps = sorted(set.intersection(*(set(t.columns) for t in tables)))
    z = tables[0].index
    for t in tables[1:]:
        z = z.intersection(t.index)
    stack = np.stack([t.loc[z, steps].to_numpy(dtype=float) for t in tables])
    return pd.DataFrame(stack.max(axis=0) - stack.min(axis=0), index=z, columns=steps)


def within_run_change(table):
    """|Q(window k) - Q(window k-1)| of one run, labelled by the later window's step; the first window is dropped."""
    return table.diff(axis=1).abs().iloc[:, 1:]


def layer_mean(table, zband):
    """Mean over the heights zband[0] <= z <= zband[1] of every column (NaN levels skipped)."""
    z = table.index.to_numpy(dtype=float)
    return table.loc[(z >= zband[0]) & (z <= zband[1])].mean(axis=0)
