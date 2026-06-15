import os
import sys

# Ensure Python can find the modular packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loaders.footprint_io import load_source_positions
from data_loaders.map_io import load_lbm_map
from plotting_core.map_plots import plot_birdseye_domain

def main():
    # 1. Paths
    flat_map_path = r"Z:\map\map_01_flat_plane.dat"
    cube_map_path = r"Z:\map\map_02_full_roughness.dat"
    
    flat_pos_path = r"Z:\particle_position\pos_flat_3072.txt"
    cube_pos_path = r"Z:\particle_position\pos_cube_3072.txt"
    
    output_dir = r"../figures/map_visualizations"
    
    # Sensor Coordinates & Grid Resolution
    sensor_x = 600.0
    sensor_y = 128.0
    dx = 2.0
    dy = 2.0

    # ==========================================
    # DOMAIN 1: FLAT PLANE
    # ==========================================
    print("Visualizing Flat Domain...")
    flat_matrix, _, _ = load_lbm_map(flat_map_path)
    flat_sources = load_source_positions(flat_pos_path)
    
    plot_birdseye_domain(
        elevation_matrix=flat_matrix, 
        source_map=flat_sources, 
        sensor_pos=(sensor_x, sensor_y), 
        title="Bird's-Eye View: Flat Domain Source Distribution", 
        save_path=os.path.join(output_dir, "domain_flat_plane.png"),
        dx=dx, dy=dy
    )

    # ==========================================
    # DOMAIN 2: CUBE ROUGHNESS
    # ==========================================
    print("Visualizing Cube Domain...")
    cube_matrix, _, _ = load_lbm_map(cube_map_path)
    cube_sources = load_source_positions(cube_pos_path)
    
    plot_birdseye_domain(
        elevation_matrix=cube_matrix, 
        source_map=cube_sources, 
        sensor_pos=(sensor_x, sensor_y), 
        title="Bird's-Eye View: Cube Canopy Source Distribution", 
        save_path=os.path.join(output_dir, "domain_cubes.png"),
        dx=dx, dy=dy
    )
    
    print(f"Visualizations generated successfully in {output_dir}")

if __name__ == "__main__":
    main()