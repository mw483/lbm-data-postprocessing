"""
Reader for the digitised Willis & Deardorff (1976) water-tank curves in validation_data/willis_deardorff_1976/.

fig2_mean_height.csv: mean particle height / z_i against X = t w*/z_i for the two tank cases
(l/z_i = 1.9 and 4.0) and Deardorff's (1972) numerical model (Fig. 2 of the paper). The file header
lists the case parameters and the digitising accuracy.
"""
import pandas as pd

from data_loaders.local_paths import REPO_ROOT

WD1976_DIR = REPO_ROOT / "validation_data" / "willis_deardorff_1976"
WD1976_MEAN_HEIGHT = WD1976_DIR / "fig2_mean_height.csv"


def read_wd1976_mean_height(path=WD1976_MEAN_HEIGHT):
    """{series: DataFrame(X, z_mean)} sorted by X; empty dict if the file is missing."""
    try:
        table = pd.read_csv(path, comment="#")
    except FileNotFoundError:
        return {}
    return {s: g.sort_values("X")[["X", "z_mean"]].reset_index(drop=True) for s, g in table.groupby("series")}
