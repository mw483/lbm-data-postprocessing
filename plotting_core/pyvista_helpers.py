"""
Small PyVista scene helpers shared by the 3D plotting modules.

Each helper reproduces a block that was previously copy-pasted across
particle_3d_plots.py and density_plots.py; colours, opacities and line
widths are passed in by the caller so every scene renders as before.
"""
import os

import pyvista as pv

from data_loaders.map_io import create_voxel_buildings


def add_snapshot_key(plotter, save_path, key='s'):
    """
    Creates the output directory and binds `key` to save numbered screenshots
    of the current view as `{base}_{NN:02d}{ext}` (starting at 01).
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    snap_counter = [1]

    def take_snap():
        base_name, ext = os.path.splitext(save_path)
        unique_save_path = f"{base_name}_{snap_counter[0]:02d}{ext}"
        plotter.screenshot(unique_save_path)
        print(f"--> SNAP! Saved view {snap_counter[0]} to: {unique_save_path}")
        snap_counter[0] += 1

    plotter.add_key_event(key, take_snap)


def show_iso_grid(plotter):
    """Isometric camera plus the labelled metre grid used by every 3D scene."""
    plotter.camera_position = 'iso'
    plotter.show_grid(
        font_size=10,
        fmt="%.0f",
        xtitle='X [m]', ytitle='Y [m]', ztitle='Z [m]'
    )


def add_sensor_box(plotter, sensor_center, sensor_size, surface_opacity,
                   line_width, wire_opacity=None):
    """
    Adds the sensor volume as a translucent magenta box with a red wireframe.
    `wire_opacity=None` leaves the wireframe at PyVista's default opacity.
    """
    cx, cy, cz = sensor_center
    sx, sy, sz = sensor_size
    bounds = [
        cx - sx / 2.0, cx + sx / 2.0,
        cy - sy / 2.0, cy + sy / 2.0,
        cz - sz / 2.0, cz + sz / 2.0
    ]
    sensor_box = pv.Box(bounds=bounds)
    plotter.add_mesh(sensor_box, color="magenta", opacity=surface_opacity,
                     style="surface", label="Sensor Volume")
    wire_kwargs = {} if wire_opacity is None else {"opacity": wire_opacity}
    plotter.add_mesh(sensor_box, color="red", style="wireframe",
                     line_width=line_width, **wire_kwargs)


def add_voxel_buildings(plotter, elevation_mat, nx_map, ny_map, dx, opacity=1.0,
                        crop_approach=False, x_start=None):
    """
    Builds the voxel building mesh, optionally clips away x < x_start, and adds
    it as light-grey with dark-grey edges. Returns the building mesh (None
    when the map has no buildings).
    """
    building_mesh = create_voxel_buildings(elevation_mat, nx_map, ny_map, resolution=dx)
    if building_mesh:
        if crop_approach:
            building_mesh = building_mesh.clip(normal='x', origin=(x_start, 0, 0), invert=False)
        plotter.add_mesh(
            building_mesh,
            color="lightgray",
            show_edges=True,
            edge_color="darkgray",
            opacity=opacity,
            label="Buildings"
        )
    return building_mesh


def add_ground_plane(plotter, x_domain_max, y_domain_max, crop_approach=False,
                     x_start=None, opacity=0.15):
    """
    Adds a dark-green ground plane covering the map, or only x >= x_start
    when crop_approach is set.
    """
    if crop_approach:
        x_len = x_domain_max - x_start
        ground = pv.Plane(
            center=(x_start + x_len / 2.0, y_domain_max / 2.0, 0.0),
            direction=(0, 0, 1),
            i_size=x_len,
            j_size=y_domain_max
        )
    else:
        ground = pv.Plane(
            center=(x_domain_max / 2.0, y_domain_max / 2.0, 0.0),
            direction=(0, 0, 1),
            i_size=x_domain_max,
            j_size=y_domain_max
        )
    plotter.add_mesh(ground, color="darkgreen", opacity=opacity)
