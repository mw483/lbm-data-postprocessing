"""
Resolved u, v, w of the particles that reached a sensor, against height, flat vs cube array.

Only each particle's records from release up to its arrival at the sensor are used, and only
x >= X_START (the measurement area; the approach blocks upstream are left out). Every record
(particle x output second) counts once. Optional: the Eulerian wind profile from the solver's
y-averaged XZ output, averaged over the same x range, as dotted lines.

Writes one figure and one CSV of the statistics per sensor.
"""
import polars as pl

from data_loaders.lbm_parsers import load_xz_yav
from data_loaders.local_paths import load_local_paths
from data_loaders.sensor_cache import load_sensor_subset
from physics_core.particle_analysis import compute_transit_times, until_arrival, velocity_stats_by_height
from physics_core.turbulence import mean_wind_profile
from plotting_core.velocity_analysis_plots import plot_velocity_profiles

# =============================================================================
# Settings
# =============================================================================
CASES = [
    # (label, particle run folder under particle_outputs, wind run folder under wind_outputs)
    ("Flat", "20260630_particle_flat_16mapproach", "20260630_output_flat_16mapproach"),
    ("Cube array", "20260803_particle_cube_16mapproach", "20260803_output_cube_16mapproach"),
]
SENSORS = {4: (3672.0, 256.0, 90.0)}   # sensor_id: centre; e.g. add 13: (3672, 256, 50), 22: (3672, 256, 20)
SENSOR_SIZE = (8.0, 8.0, 8.0)
C_REF = 100.0                          # -velocity_lbm 2.0 0.02 in the 16 m approach runs
DT_OUTPUT = 1.0
X_START = 3072.0                       # measurement area starts here [m]
Z_BIN = 4.0                            # height bin [m]
MIN_COUNT = 20                         # drop bins with fewer records than this
COMPONENTS = ("u_res", "v_res", "w_res")   # resolved velocity (total minus SGS)

OVERLAY_WIND = False                   # True: add the Eulerian profile (needs wind_outputs in local_paths.yaml)
WIND_STEP = 90000                      # xz_yav averaging window to use (step of its last output)
DX = DZ = 2.0


def main():
    paths = load_local_paths()
    out_dir = paths["figures"] / "presentation_2026-10-07" / "velocity_profiles"
    out_dir.mkdir(parents=True, exist_ok=True)

    wind_by_case = None
    if OVERLAY_WIND:
        if "wind_outputs" not in paths:
            raise KeyError("[ERROR] OVERLAY_WIND = True needs wind_outputs in local_paths.yaml")
        wind_by_case = {}
        for label, _, wind_run in CASES:
            fields = load_xz_yav(str(paths["wind_outputs"] / wind_run), WIND_STEP,
                                 variables=("um", "vm", "wm", "uu", "vv", "ww"))
            wind_by_case[label] = mean_wind_profile(fields, X_START, dx=DX, dz=DZ)

    for sensor_id, center in SENSORS.items():
        stats_by_case, tables = {}, []
        for label, run, _ in CASES:
            df, hits = load_sensor_subset(paths, run, sensor_id, c_ref=C_REF)
            transit = compute_transit_times(df, hits, SENSOR_SIZE, dt_output=DT_OUTPUT)
            path_df = until_arrival(df, transit).filter(pl.col("x") >= X_START)
            stats = velocity_stats_by_height(path_df, COMPONENTS, z_bin=Z_BIN, min_count=MIN_COUNT)
            print(f"{label}: {transit.height:,} particles, {path_df.height:,} records release->arrival at x >= {X_START:g}")
            stats_by_case[label] = stats
            tables.append(stats.with_columns(pl.lit(label).alias("case")))

        cx, cy, cz = (int(v) for v in center)
        tag = f"sensor_{sensor_id}_{cx}_{cy}_{cz}"
        pl.concat(tables).write_csv(out_dir / f"velocity_stats_{tag}.csv")
        print(f"[SUCCESS] Table saved to: {out_dir / f'velocity_stats_{tag}.csv'}")
        plot_velocity_profiles(
            stats_by_case, COMPONENTS, wind_by_case=wind_by_case,
            save_path=out_dir / f"velocity_profiles_{tag}{'_wind' if OVERLAY_WIND else ''}.png",
            title=f"Resolved velocity of particles reaching ({cx}, {cy}, {cz}) m, release to arrival, x >= {X_START:g} m",
        )


if __name__ == "__main__":
    main()
