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
    plotter.add_mesh(sensor_box, color="red", opacity=0.3, style="wireframe", line_width=2) # Box outline

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
    # Define a function to take a screenshot of the resulting 3d interactive plot
    # Use a list for the counter so it can be modified inside the nested function
    snap_counter = [1] 

    # Create a custom function to take the screenshot with an incrementing name
    def take_snap():
        # Split the path to insert the number before the ".png"
        base_name, ext = os.path.splitext(save_path)
        
        # Format the new path (e.g., "...peak_source_2129_steps_1200-1500_01.png")
        unique_save_path = f"{base_name}_{snap_counter[0]:02d}{ext}"
        
        # Take the screenshot
        plotter.screenshot(unique_save_path)
        print(f"--> SNAP! Saved view {snap_counter[0]} to: {unique_save_path}")
        
        # Increment the counter for the next picture
        snap_counter[0] += 1

    # Bind that function to the 's' key
    plotter.add_key_event('s', take_snap)

    print("Interactive window opened.")
    print("Press 's' on your keyboard at any time to take a screenshot.")
    print("Close the window or press 'q' when you are done.")
    
    # Show the plot
    plotter.show()