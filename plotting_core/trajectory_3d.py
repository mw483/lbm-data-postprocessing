import pyvista as pv
import numpy as np
import os

def plot_trajectories_with_sensor(trajectories, sensor_center, sensor_size, save_path):
    """
    Renders 3D trajectories and a transparent sensor volume using PyVista.
    """
    if not trajectories:
        print("No trajectories to plot!")
        return

    # 1. Format the trajectory data for PyVista (PolyData lines)
    points = []
    lines = []
    for p_id, coords in trajectories.items():
        if len(coords) < 2:  # Need at least 2 points to draw a line
            continue
            
        start_idx = len(points)
        points.extend(coords)
        
        # PyVista line format: [number_of_points, index1, index2, ...]
        lines.append(len(coords))
        lines.extend(range(start_idx, start_idx + len(coords)))

    poly = pv.PolyData(points)
    poly.lines = lines

    # 2. Define the Sensor Box bounds
    cx, cy, cz = sensor_center
    dx, dy, dz = sensor_size
    bounds = [
        cx - dx/2, cx + dx/2,  # X min, X max
        cy - dy/2, cy + dy/2,  # Y min, Y max
        cz - dz/2, cz + dz/2   # Z min, Z max
    ]
    sensor_box = pv.Box(bounds=bounds)

    # 3. Setup the PyVista Plotter (off_screen=True prevents X11 server crashes on TSUBAME)
    plotter = pv.Plotter(off_screen=False)
    
    # Add elements to the scene
    plotter.add_mesh(poly, color="cyan", line_width=0.5, opacity=0.5, label="Particle Trajectories")
    plotter.add_mesh(sensor_box, color="magenta", opacity=0.3, style="surface", label="Sensor Volume")
    plotter.add_mesh(sensor_box, color="red", style="wireframe", line_width=2) # Box outline

    # Add a simple ground plane for reference (adjust to your domain size)
    ground = pv.Plane(center=(512, 128, 0), direction=(0, 0, 1), i_size=1024, j_size=256)
    plotter.add_mesh(ground, color="darkgreen", opacity=0.2)

    # Configure Camera and Lighting, as well as Plot Font Sizes
    plotter.camera_position = 'iso'
    plotter.show_grid(
        font_size=10, 
        fmt="%.0f", 
        xtitle='X [m]', ytitle='Y [m]', ztitle='Z [m]'
    )
    plotter.add_legend()

    # Save the output safely
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    # Use plotter.screenshot if just want to save picture, plotter.show if want to view and move the camera around
    print(f"Interactive window opened.")
    print(f"Rotate to the desired angle, then press 'q' on your keyboard to save and close.")

    plotter.show(screenshot=save_path, auto_close=False)
    # plotter.screenshot(save_path)
    plotter.close()