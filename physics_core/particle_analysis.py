from pathlib import Path
from typing import Iterable, Optional, Union, Tuple
import numpy as np
import polars as pl

def compute_transit_times(csv_path: Union[str, Path], target_ids: Optional[Iterable[int]] = None, dt_output: float = 1.0, separator: str = ",") -> np.ndarray:
    """
    Computes travel time delta_t for all unique particle IDs using Polars.
    Reads only the first two columns (step and id) for fast ingestion.
    Filters by target_ids if a sensor hit list is provided.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"[ERROR] Trajectory CSV not found: {csv_path}")

    # Lazy scan of the CSV, extracting only the step and ID columns
    lazy_df = pl.scan_csv(
        csv_path,
        has_header=False,
        separator=separator,
        with_column_names=lambda cols: [f"col_{i}" for i in range(len(cols))]
    ).select([
        pl.col("col_0").cast(pl.Int32).alias("step"),
        pl.col("col_1").cast(pl.Int64).alias("id")
    ])

    # Filter to specific sensor hit IDs if provided
    if target_ids is not None:
        target_list = list(target_ids)
        if len(target_list) == 0:
            return np.array([], dtype=np.float64)
        lazy_df = lazy_df.filter(pl.col("id").is_in(target_list))

    # Aggregate min (release) and max (sensor arrival) step per particle
    transit_df = (
        lazy_df.group_by("id")
        .agg([
            pl.col("step").min().alias("t_spawn"),
            pl.col("step").max().alias("t_sensor")
        ])
        .with_columns(
                ((pl.col("t_sensor") - pl.col("t_spawn")) * dt_output).alias("delta_t")
        )
        .collect()
    )
    
    return transit_df["delta_t"].to_numpy()


def compute_depth_averaged_u(
    prof_csv_path: Union[str, Path],
    target_z: float
) -> float:
    """
    Computes depth-averaged wind speed U_bar(z) = (1/z) * integral(u(zeta) d_zeta)
    from ground up to target_z using trapezoidal integration.
    Assumes prof CSV contains [z, U] with a one-line comment header.
    """
    prof_path = Path(prof_csv_path)
    if not prof_path.exists():
        return 1.0  # Fallback scale if profile is missing

    data = np.loadtxt(prof_path, delimiter=",", skiprows=1)
    z_vals, u_vals = data[:, 0], data[:, 1]
    
    # Filter up to target_z
    mask = z_vals <= target_z
    if not np.any(mask):
        return float(u_vals[0])
    
    z_sub = np.insert(z_vals[mask], 0, 0.0)
    u_sub = np.insert(u_vals[mask], 0, 0.0)  # No-slip at ground
    
    u_bar = np.trapezoid(u_sub, z_sub) / target_z
    return float(u_bar)


def normalize_transit_distribution(
    delta_t: np.ndarray,
    method: str = "median",
    u_bar: Optional[float] = None,
    delta_x: float = 600.0,
    u_star: Optional[float] = None,
    sensor_z: Optional[float] = None
) -> Tuple[np.ndarray, str]:
    """
    Normalizes arrival times delta_t across different sensor heights.
    Methods: 'median', 'advective', 'eddy_turnover', or no normalization
    Returns: (scaled_time_array, axis_label)
    """
    if len(delta_t) == 0:
        return np.array([]), ""

    if method == "median":
        t50 = np.median(delta_t)
        scaled_t = delta_t / t50
        xlabel = r"Dimensionless Transit Time $\tilde{t} = \Delta t / t_{50}$"
    elif method == "advective":
        if u_bar is None or u_bar <= 0:
            raise ValueError("[ERROR] u_bar must be provided for advective scaling.")
        t_adv = delta_x / u_bar
        scaled_t = delta_t / t_adv
        xlabel = r"Advective Velocity Ratio $\theta = \Delta t \cdot \bar{U}_z / \Delta X$"
    elif method == "eddy_turnover":
        if u_star is None or sensor_z is None or sensor_z <= 0:
            raise ValueError("[ERROR] u_star and sensor_z must be provided for eddy turnover scaling.")
        tau_w = sensor_z / u_star
        scaled_t = delta_t / tau_w
        xlabel = r"Eddy Turnover Scale $t^* = \Delta t \cdot u_* / z_m$"
    elif method == "no_normalization":
        scaled_t = delta_t
        xlabel = r"$\Delta t$[s]"
    else:
        raise ValueError(f"Unknown normalization method: {method}")

    return scaled_t, xlabel