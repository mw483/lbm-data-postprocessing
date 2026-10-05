from pathlib import Path
from typing import Optional, Union, Tuple
import numpy as np
import polars as pl

TRAJECTORY_COLUMNS = ["step", "id", "x", "y", "z", "u", "v", "w", "u_sgs", "v_sgs", "w_sgs"]


def scan_trajectories(csv_path: Union[str, Path], separator: str = ",") -> pl.LazyFrame:
    """Lazy scan of the C++ target_trajectories.csv (no header, 5 or 11 columns)."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"[ERROR] Trajectory CSV not found: {csv_path}")
    return pl.scan_csv(
        csv_path,
        has_header=False,
        separator=separator,
        with_column_names=lambda cols: TRAJECTORY_COLUMNS[:len(cols)],
    )


def compute_transit_times(
    trajectories: Union[str, Path, pl.LazyFrame, pl.DataFrame],
    hits: pl.DataFrame,
    sensor_size: Tuple[float, float, float],
    dt_output: float = 1.0,
) -> pl.DataFrame:
    """
    Transit time from release to the FIRST arrival inside the sensor box, one row per
    (sensor, particle) pair in `hits` (a table from data_loaders.particle_io.load_hit_table,
    already filtered to the sensors wanted).

    target_trajectories.csv keeps every output step of a hit particle, also after it has
    passed the sensor (sensor_density.cpp, stream_trajectories), so the arrival is found
    from the positions: the first step with centre - size/2 <= (x, y, z) <= centre + size/2,
    the same inclusive box test as harvest_ids in the C++ suite.

    Release step = the particle's first record in the file. This is the true release only
    when the particles were released inside the post-processed window (the 16 m approach
    runs: pstart = FILE_START = 1200).

    Returns columns: sensor_id, id, step_release, step_arrival, delta_t [s].
    Pairs with no in-box record are dropped with a warning.
    """
    if isinstance(trajectories, (str, Path)):
        lazy = scan_trajectories(trajectories)
    else:
        lazy = trajectories.lazy()

    hits = hits.select(["sensor_id", "sx", "sy", "sz", "id"])
    if hits.height == 0:
        return pl.DataFrame(schema={"sensor_id": pl.Int64, "id": pl.Int64, "step_release": pl.Int64,
                                    "step_arrival": pl.Int64, "delta_t": pl.Float64})

    hx, hy, hz = (s / 2.0 for s in sensor_size)
    target_ids = hits["id"].unique().to_list()
    lazy = lazy.select(["step", "id", "x", "y", "z"]).filter(pl.col("id").is_in(target_ids))

    release = lazy.group_by("id").agg(pl.col("step").min().alias("step_release"))

    arrival = (
        lazy.join(hits.lazy(), on="id", how="inner")
        .filter(
            pl.col("x").is_between(pl.col("sx") - hx, pl.col("sx") + hx)
            & pl.col("y").is_between(pl.col("sy") - hy, pl.col("sy") + hy)
            & pl.col("z").is_between(pl.col("sz") - hz, pl.col("sz") + hz)
        )
        .group_by(["sensor_id", "id"])
        .agg(pl.col("step").min().alias("step_arrival"))
    )

    result = (
        arrival.join(release, on="id", how="inner")
        .with_columns(((pl.col("step_arrival") - pl.col("step_release")) * dt_output).alias("delta_t"))
        .select(["sensor_id", "id", "step_release", "step_arrival", "delta_t"])
        .sort(["sensor_id", "id"])
        .collect()
    )

    n_missing = hits.height - result.height
    if n_missing > 0:
        print(f"[WARNING] {n_missing:,} of {hits.height:,} hits have no record inside the sensor box; dropped.")
    return result


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