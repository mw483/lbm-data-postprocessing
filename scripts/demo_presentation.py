"""
Live demo for the 2026-10-07 progress talk: flat vs cube array, one sensor, side by side.

Stages, in talk order (close the window to go to the next one):
  1. isopleths      3D enclosed-mass shells of the particles that reached the sensor
  2. velocity       the same particles' paths coloured by vertical velocity w (shared colour range)
  3. ttd            transit-time distribution, raw counts

The two 3D views share one camera: rotate or zoom one and the other follows.
Keys in a 3D window: 's' saves a screenshot, 'r' resets the camera, 'q' closes it.

Usage:
  python scripts/demo_presentation.py                      # live, all stages
  python scripts/demo_presentation.py --stage velocity     # start at a later stage
  python scripts/demo_presentation.py --record             # MP4 orbit + PNG per stage, no windows (backup)
  python scripts/demo_presentation.py --rebuild-cache      # re-read the CSVs after new C++ outputs

The first run reads each target_trajectories.csv once and caches the sensor's particles
(see data_loaders/sensor_cache.py); later runs open in seconds. Run it once before the talk.
"""
import argparse

import numpy as np
import polars as pl
import pyvista as pv

from data_loaders.local_paths import load_local_paths
from data_loaders.sensor_cache import load_sensor_subset, trajectories_from_frame
from physics_core.particle_analysis import compute_transit_times
from plotting_core.particle_3d_plots import add_density_isopleths, add_particles_with_velocity
from plotting_core.pyvista_helpers import add_snapshot_key
from plotting_core.velocity_analysis_plots import plot_transit_time_distribution

# =============================================================================
# Settings
# =============================================================================
CASES = [
    # (label, run folder under particle_outputs, map file under maps)
    ("Flat", "20260630_particle_flat_16mapproach", "map_flat_16m_approach.dat"),
    ("Cube array", "20260803_particle_cube_16mapproach", "map_cube_16m_approach.dat"),
]
SENSOR_ID = 4                          # index in the C++ sensor list
SENSOR_CENTER = (3672.0, 256.0, 90.0)  # must match SENSOR_ID
SENSOR_SIZE = (8.0, 8.0, 8.0)
C_REF = 100.0                          # -velocity_lbm 2.0 0.02 in the 16 m approach runs
DT_OUTPUT = 1.0                        # seconds between particle .bin outputs
DX = 2.0
X_START = 3072.0                       # crop the approach fetch upstream of this x [m]

ISOPLETHS = dict(voxel_res=8.0, sigma=0.8, z_max=160.0, density_mode="concentration",
                 cumulative_levels=[0.50, 0.80, 0.95], shell_opacity=0.40)
VELOCITY = dict(scalar_field="w", display_mode="lines", stride=1)
TTD = dict(bin_width=4.0, max_time=600.0)

STAGES = ["isopleths", "velocity", "ttd"]
WINDOW_SIZE = (1800, 850)


def side_by_side(record):
    return pv.Plotter(shape=(1, len(CASES)), window_size=WINDOW_SIZE, off_screen=record, border=False)


def finish(plotter, out_dir, name, record):
    """Live: link the views and open the window. Record: write an orbit MP4 and a PNG."""
    plotter.link_views()
    if not record:
        add_snapshot_key(plotter, str(out_dir / f"{name}.png"))
        print(f"[{name}] Window open. Drag to rotate (both views follow), 's' = screenshot, close to continue.")
        plotter.show()
        return
    plotter.screenshot(str(out_dir / f"{name}.png"))
    movie = out_dir / f"{name}_orbit.mp4"
    plotter.open_movie(str(movie), framerate=30)
    orbit = plotter.generate_orbital_path(n_points=240, shift=plotter.length * 0.15, factor=2.0)
    plotter.orbit_on_path(orbit, write_frames=True, viewup=(0, 0, 1))
    plotter.close()
    print(f"[{name}] Saved {movie}")


def stage_isopleths(data, out_dir, record):
    plotter = side_by_side(record)
    for col, (label, df, _, map_path) in enumerate(data):
        plotter.subplot(0, col)
        add_density_isopleths(plotter, trajectories_from_frame(df), SENSOR_CENTER, SENSOR_SIZE,
                              map_filepath=map_path, dx=DX, crop_approach=True, x_start=X_START,
                              bar_title=f"{label}: particle density [pts/m^3]", **ISOPLETHS)
        plotter.add_text(label, font_size=14, color="black")
    finish(plotter, out_dir, "1_isopleths", record)


def stage_velocity(data, out_dir, record):
    # One colour range for both cases (2-98 % of |w| over the cropped paths), so colours compare
    field = {"w": "w_res", "w_total": "w"}.get(VELOCITY["scalar_field"])
    clim = None
    if field is not None:
        w = np.concatenate([df.filter(pl.col("x") >= X_START)[field].to_numpy() for _, df, _, _ in data])
        max_abs = max(abs(np.percentile(w, 2)), abs(np.percentile(w, 98)))
        clim = [-max_abs, max_abs]

    plotter = side_by_side(record)
    for col, (label, df, _, map_path) in enumerate(data):
        plotter.subplot(0, col)
        add_particles_with_velocity(plotter, df, SENSOR_CENTER, SENSOR_SIZE, map_filepath=map_path,
                                    dx=DX, crop_approach=True, x_start=X_START, clim=clim,
                                    bar_title=f"{label}: w [m/s]" if field else None, **VELOCITY)
        plotter.add_text(label, font_size=14, color="black")
    finish(plotter, out_dir, "2_velocity", record)


def stage_ttd(data, out_dir, record):
    transit = {}
    for label, df, hits, _ in data:
        tt = compute_transit_times(df, hits, SENSOR_SIZE, dt_output=DT_OUTPUT)
        transit[label] = tt["delta_t"].to_numpy()
    cx, cy, cz = (int(v) for v in SENSOR_CENTER)
    plot_transit_time_distribution(
        transit, save_path=(out_dir / "3_ttd.png") if record else None, density=False,
        title=f"Transit time to the sensor at x={cx}, y={cy}, z={cz} m", **TTD)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", choices=STAGES, default=STAGES[0], help="stage to start at")
    parser.add_argument("--only", action="store_true", help="show only the --stage stage")
    parser.add_argument("--record", action="store_true", help="write MP4/PNG files instead of opening windows")
    parser.add_argument("--rebuild-cache", action="store_true", help="re-read target_trajectories.csv")
    args = parser.parse_args()

    paths = load_local_paths()
    out_dir = paths["figures"] / "presentation_2026-10-07" / f"sensor_{SENSOR_ID}"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = []
    for label, run, map_file in CASES:
        df, hits = load_sensor_subset(paths, run, SENSOR_ID, c_ref=C_REF, rebuild=args.rebuild_cache)
        map_path = paths["maps"] / map_file
        if not map_path.exists():
            print(f"[WARNING] Map not found, drawing without buildings: {map_path}")
        data.append((label, df, hits, str(map_path)))

    stages = STAGES[STAGES.index(args.stage):]
    if args.only:
        stages = stages[:1]
    for stage in stages:
        {"isopleths": stage_isopleths, "velocity": stage_velocity, "ttd": stage_ttd}[stage](data, out_dir, args.record)


if __name__ == "__main__":
    main()
