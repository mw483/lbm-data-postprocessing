"""
Animation of the particles that reached a sensor, in real simulation time, flat vs cube array.

Each frame is one output second of target_trajectories.csv (via the sensor cache): the
particles that exist at that second are drawn at their positions, coloured by the resolved
vertical velocity w (one colour range for both cases). Particles appear when they are
released and disappear when they leave the area or the post-processed window ends.

Usage:
  python scripts/animate_particles_to_sensor.py            # live: slider for time, space = play/pause
  python scripts/animate_particles_to_sensor.py --record   # MP4 (no window)
"""
import argparse

import numpy as np
import polars as pl
import pyvista as pv

from data_loaders.local_paths import load_local_paths
from data_loaders.map_io import load_lbm_map
from data_loaders.sensor_cache import load_sensor_subset
from physics_core.particle_analysis import compute_transit_times, until_arrival
from plotting_core.pyvista_helpers import add_ground_plane, add_sensor_box, add_snapshot_key, add_voxel_buildings

# =============================================================================
# Settings
# =============================================================================
CASES = [
    ("Flat", "20260630_particle_flat_16mapproach", "map_flat_16m_approach.dat"),
    ("Cube array", "20260803_particle_cube_16mapproach", "map_cube_16m_approach.dat"),
]
SENSOR_ID = 4
SENSOR_CENTER = (3672.0, 256.0, 90.0)
SENSOR_SIZE = (8.0, 8.0, 8.0)
C_REF = 100.0                  # -velocity_lbm 2.0 0.02 in the 16 m approach runs
DT_OUTPUT = 1.0                # seconds between particle outputs
DX = 2.0
X_START = 3072.0               # show only x >= X_START (the measurement area)
Z_TOP = 160.0                  # top of the shown box [m]
UNTIL_ARRIVAL = False          # True: hide each particle after it reaches the sensor
COLOR_BY = "w_res"             # None: one colour per case
FRAME_STRIDE = 1               # draw every n-th output second
FPS = 20                       # MP4 frame rate (600 s at stride 1 -> 30 s of video)
POINT_SIZE = 5.0
WINDOW_SIZE = (1800, 850)


def frames_by_step(df):
    """{step: (points (n, 3), colour values or None)}"""
    out = {}
    for (step,), part in df.partition_by("step", as_dict=True).items():
        pts = np.column_stack((part["x"].to_numpy(), part["y"].to_numpy(), part["z"].to_numpy()))
        out[int(step)] = (pts, part[COLOR_BY].to_numpy() if COLOR_BY else None)
    return out


def make_cloud(frame):
    pts, vals = frame if frame is not None else (np.empty((0, 3)), np.empty(0))
    cloud = pv.PolyData(pts)
    if COLOR_BY:
        cloud.point_data[COLOR_BY] = vals if vals is not None else np.empty(0)
    return cloud


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--record", action="store_true", help="write an MP4 instead of opening a window")
    args = parser.parse_args()
    pv.global_theme.allow_empty_mesh = True

    paths = load_local_paths()
    out_dir = paths["figures"] / "presentation_2026-10-07" / f"sensor_{SENSOR_ID}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = []
    for label, run, map_file in CASES:
        df, hits = load_sensor_subset(paths, run, SENSOR_ID, c_ref=C_REF)
        if UNTIL_ARRIVAL:
            df = until_arrival(df, compute_transit_times(df, hits, SENSOR_SIZE, dt_output=DT_OUTPUT))
        df = df.filter(pl.col("x") >= X_START)
        cases.append((label, df, frames_by_step(df), paths["maps"] / map_file))

    steps = sorted(set().union(*(fr.keys() for _, _, fr, _ in cases)))
    steps = list(range(steps[0], steps[-1] + 1, FRAME_STRIDE))
    clim = None
    if COLOR_BY:
        vals = np.concatenate([df[COLOR_BY].to_numpy() for _, df, _, _ in cases])
        m = max(abs(np.percentile(vals, 2)), abs(np.percentile(vals, 98)))
        clim = [-m, m]

    plotter = pv.Plotter(shape=(1, len(cases)), window_size=WINDOW_SIZE, off_screen=args.record, border=False)
    clouds = []
    for col, (label, df, frames, map_path) in enumerate(cases):
        plotter.subplot(0, col)
        plotter.set_background("white")
        x_max, y_max = df["x"].max() + 10.0, df["y"].max() + 10.0
        if map_path.exists():
            elev, nx_map, ny_map = load_lbm_map(str(map_path))
            x_max, y_max = nx_map * DX, ny_map * DX
            add_voxel_buildings(plotter, elev, nx_map, ny_map, DX, opacity=1.0, crop_approach=True, x_start=X_START)
        add_ground_plane(plotter, x_max, y_max, crop_approach=True, x_start=X_START, opacity=0.15)
        plotter.add_mesh(pv.Box(bounds=(X_START, x_max, 0.0, y_max, 0.0, Z_TOP)), style="wireframe",
                         color="lightgray", opacity=0.3)   # fixes the scene extent while points move
        add_sensor_box(plotter, SENSOR_CENTER, SENSOR_SIZE, surface_opacity=0.4, line_width=2.5)
        cloud = make_cloud(frames.get(steps[0]))
        kwargs = dict(scalars=COLOR_BY, cmap="coolwarm", clim=clim,
                      scalar_bar_args={"title": f"{label}: w [m/s]"}) if COLOR_BY else dict(color="tab:blue")
        plotter.add_mesh(cloud, render_points_as_spheres=True, point_size=POINT_SIZE, **kwargs)
        plotter.add_text(label, font_size=14, color="black")
        plotter.camera_position = "iso"
        clouds.append((cloud, frames))
    plotter.link_views()

    def show_step(step):
        for col, (cloud, frames) in enumerate(clouds):
            cloud.copy_from(make_cloud(frames.get(step)))
        plotter.subplot(0, 0)
        plotter.add_text(f"t = {step * DT_OUTPUT:.0f} s", position="lower_left", font_size=12,
                         color="black", name="time_label")

    if args.record:
        movie = out_dir / "4_particles_real_time.mp4"
        plotter.open_movie(str(movie), framerate=FPS)
        for step in steps:
            show_step(step)
            plotter.write_frame()
        plotter.close()
        print(f"[SUCCESS] Saved {movie} ({len(steps)} frames)")
        return

    show_step(steps[0])
    state = {"i": 0, "playing": False}
    slider = plotter.add_slider_widget(
        lambda v: (state.update(i=int(round((v - steps[0]) / FRAME_STRIDE))), show_step(steps[state["i"]])),
        [steps[0], steps[-1]], value=steps[0], title="output step", fmt="%.0f",
        pointa=(0.25, 0.92), pointb=(0.75, 0.92))

    def tick(_=None):
        if state["playing"] and state["i"] < len(steps) - 1:
            state["i"] += 1
            slider.GetRepresentation().SetValue(steps[state["i"]])
            show_step(steps[state["i"]])
            plotter.render()

    plotter.add_key_event("space", lambda: state.update(playing=not state["playing"]))
    plotter.add_timer_event(max_steps=10**7, duration=int(1000 / FPS), callback=tick)
    add_snapshot_key(plotter, str(out_dir / "4_particles_real_time.png"))
    print("Window open. Drag the slider or press space to play/pause; 's' = screenshot.")
    plotter.show()


if __name__ == "__main__":
    main()
