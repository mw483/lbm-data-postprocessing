import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy.ndimage import gaussian_filter
import os
import sys

# Ensure Python can find the modular packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 1. Import your newly implemented footprint smoothing function
# (Ensure your execution directory has physics_core in its python path)
from physics_core.footprint_processing import refine_footprint_grid, smooth_footprint_grid

# Domain constants
dx = 2.0  # Grid spacing resolution in meters
nx, ny = 512, 128

sensor_x = 600.0
sensor_y = 128.0
sensor_z = 90.0

target_blending_height = 40.0
delta_z = sensor_z - target_blending_height  # Vertical separation distance

output_dir = Path(f"../figures/blending_height/target_blending_{int(target_blending_height)}")
output_dir.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# STEP 1: Ingest Fast C++ Zero-Suppressed Counts
# ==============================================================================
df = pd.read_csv(
    rf"Y:\Particle_PostProcess_Outputs\20260612_particle_cube_3072\sensor_40x40x8"
    rf"\1200-1800_blend_foot\blending_footprint_z{int(target_blending_height)}"
    rf"_sensor_{int(sensor_x)}_{int(sensor_y)}_{int(sensor_z)}.csv"
)

# ==============================================================================
# STEP 2: Reconstruct Low-Res Grid Matrix
# ==============================================================================
grid_low = np.zeros((ny, nx))  # Shape: (128, 512)
grid_low[df['Y_Index'].values, df['X_Index'].values] = df['Count'].values

# ==============================================================================
# STEP 3: Apply Continuous 2D Gaussian Filter (Stochastic Denoising)
# ==============================================================================
# Dynamically scale sigma based on height above the blending layer.
# As delta_z grows, the physical turbulent length scales expand linearly.
target_sigma = 0.4 + (delta_z / 25.0)

# Pass your native dx into your custom smoothing tool
smoothed_grid_low = smooth_footprint_grid(grid_low, dx=dx, dy=dx, sigma=target_sigma)

# ==============================================================================
# STEP 4: Cubic Spline Upsampling (quantization plateau extraction)
# ==============================================================================
# Generate coordinates for low-res grid matching the domain layout
x_low_1d = np.arange(nx) * dx
y_low_1d = np.arange(ny) * dx
X_low, Y_low = np.meshgrid(x_low_1d, y_low_1d)

x_bounds = [0.0, nx * dx]
y_bounds = [0.0, ny * dx]

# Interpolate from 2.0m resolution to smooth 1.0m resolution vectors
X_fine, Y_fine, lbm_pdf_fine = refine_footprint_grid(
    X_low=X_low, 
    Y_low=Y_low, 
    pdf_low=smoothed_grid_low, 
    x_bounds=x_bounds, 
    y_bounds=y_bounds, 
    target_res=1.0
)

# ==============================================================================
# STEP 5: Render and Save Plot Assets
# ==============================================================================
file_path = output_dir / f"smooth_blending_footprint_target{int(target_blending_height)}_{int(sensor_x)}_{int(sensor_y)}_{int(sensor_z)}.png"

plt.figure(figsize=(12, 4))

# Layer 1: Continuous smoothed high-resolution footprint contour canvas
plt.imshow(
    lbm_pdf_fine, 
    origin='lower', 
    cmap='jet', 
    extent=[x_bounds[0], x_bounds[1], y_bounds[0], y_bounds[1]]
)
plt.colorbar(label='Normalized Mass Probability Density Function (PDF)')

# Layer 2: Visual sensor star placed explicitly on top using zorder vector stacking
plt.scatter(
    sensor_x, 
    sensor_y, 
    marker="*", 
    color="white", 
    s=250, 
    edgecolor="black", 
    linewidth=1.5,
    zorder=5
)

plt.title(f"Smoothed Virtual Footprint Plane at Blending Height (Z={target_blending_height}m)")
plt.xlabel("Streamwise Distance X (m)")
plt.ylabel("Spanwise Distance Y (m)")
plt.savefig(file_path, dpi=300, bbox_inches='tight')
plt.close()