from scipy.ndimage import gaussian_filter
from scipy.interpolate import RectBivariateSpline
import numpy as np

def merge_counts_with_positions(source_map, count_map, target_z=None):
    """
    Combines the coordinate map and count map.
    Optionally filters by z-height for future 3D sensitivity analysis.
    Returns lists of X, Y, Counts for plotting.
    """
    x_coords = []
    y_coords = []
    counts = []
    
    for source_id, count in count_map.items():
        if count > 0 and source_id in source_map:
            pos = source_map[source_id]
            
            # Future-proofing: filter by Z if requested
            if target_z is not None and not np.isclose(pos['z'], target_z):
                continue
                
            x_coords.append(pos['x'])
            y_coords.append(pos['y'])
            counts.append(count)
            
    return np.array(x_coords), np.array(y_coords), np.array(counts)


def points_to_grid(x_coords, y_coords, counts, dx, dy, x_bounds, y_bounds):
    """
    Converts scattered source points into a continuous 2D Eulerian grid.
    Returns the X grid, Y grid, and the normalized PDF matrix.
    """
    # Create the physical coordinate bins
    x_edges = np.arange(x_bounds[0], x_bounds[1] + dx, dx)
    y_edges = np.arange(y_bounds[0], y_bounds[1] + dy, dy)

    # 2D Histogram to sum particle counts into grid cells
    H, xedges, yedges = np.histogram2d(x_coords, y_coords, bins=(x_edges, y_edges), weights=counts)

    # H is returned as (nx, ny). We transpose to (nx, ny) to match standard X-Y plotting
    grid_counts = H.T

    # Normalzie to create a Probability Density Function (PDF) [m^-2]
    total_particles = np.sum(grid_counts)
    if total_particles > 0:
        pdf_grid = grid_counts / (total_particles * dx * dy)
    else:
        pdf_grid = grid_counts

    # Create meshgrid for plotting (using bin centers)
    X, Y = np.meshgrid(xedges[:-1] + dx/2, yedges[:-1] + dy/2)
    
    return X, Y, pdf_grid


def get_contour_thresholds(pdf_grid, dx, dy, levels=[0.5, 0.6, 0.7, 0.8, 0.9]):
    """
    Calculates the exact PDF values that correspond to the cumulative 
    contribution thresholds (e.g., the 50% source area boundary).
    """
    # Flatten and sort the grid from highest probability to lowest
    flat_pdf = pdf_grid.flatten()
    sorted_pdf = np.sort(flat_pdf)[::-1]
    
    # Calculate cumulative sum (multiplied by area to get total probability fraction)
    cumsum_pdf = np.cumsum(sorted_pdf) * (dx * dy)
    
    thresholds = []
    for lev in levels:
        # Find the index where the cumulative sum first exceeds the target level
        idx = np.argmax(cumsum_pdf >= lev)
        thresholds.append(sorted_pdf[idx])
        
    return thresholds


def extract_peak_metrics(X, Y, pdf_grid, sensor_x):
    """
    Finds the maximum contribution point and calculates its upwind distance.
    """
    # Find the 2D index of the maximum value
    max_idx = np.unravel_index(np.argmax(pdf_grid), pdf_grid.shape)
    
    peak_x = X[max_idx]
    peak_y = Y[max_idx]
    peak_val = pdf_grid[max_idx]
    
    # Upwind distance is Sensor X minus Peak X
    peak_distance = sensor_x - peak_x
    
    return peak_x, peak_y, peak_distance, peak_val

def smooth_footprint_grid(pdf_grid, dx, dy, sigma=1.0):
    """
    Applies a continuous 2D Gaussian filter to eliminate stochastic noise,
    jagged boundaries, and artificial inner holes in spread-out footprints.
    
    Args:
        pdf_grid (numpy.ndarray): The 2D binned footprint matrix.
        dx, dy (float): Grid cell resolution in meters.
        sigma (float): The standard deviation of the Gaussian kernel (in grid cells).
                       Higher values apply stronger smoothing over a wider area.
    """
    # Apply a true continuous 2D Gaussian blur
    # mode='constant' with cval=0.0 handles the boundaries outside the domain cleanly
    smoothed = gaussian_filter(pdf_grid, sigma=sigma, mode='constant', cval=0.0)
    
    # Re-normalize to ensure the total probability integral remains exactly 1.0
    total_integral = np.sum(smoothed) * dx * dy
    if total_integral > 0:
        smoothed = smoothed / total_integral
        
    return smoothed


def extract_cwif_metrics(X, pdf_grid, sensor_x, dx, dy, target_fraction=0.80):
    """
    Calculates the 1D Crosswind-Integrated Footprint (CWIF) to extract
    the peak location (x_max) and the target extent (e.g., x_80).
    """
    # 1. Integrate across the crosswind (Y) axis
    # pdf_grid shape is (ny, nx), so axis=0 sums across Y.
    cwif_1d = np.sum(pdf_grid, axis=0) * dy
    
    # Extract the 1D X-coordinates
    x_1d = X[0, :]
    
    # 2. Filter for upwind points only
    upwind_mask = x_1d <= sensor_x
    x_upwind = x_1d[upwind_mask]
    cwif_upwind = cwif_1d[upwind_mask]
    
    # Convert to "Distance from Sensor"
    dist = sensor_x - x_upwind
    
    # 3. Sort distances in ascending order (0m outwards to 600m)
    sort_idx = np.argsort(dist)
    dist_sorted = dist[sort_idx]
    cwif_sorted = cwif_upwind[sort_idx]
    
    # Extract x_max (Peak location of the 1D CWIF)
    x_max = dist_sorted[np.argmax(cwif_sorted)]
    
    # 4. Cumulative integration for x_80
    # cumsum * dx gives the cumulative fraction of the total footprint
    cum_cwif = np.cumsum(cwif_sorted) * dx
    
    # Find the exact distance where the cumulative sum crosses 0.80
    # argmax on a boolean array returns the first True index
    cross_idx = np.argmax(cum_cwif >= target_fraction)
    
    # Safety check if the domain is too short to capture 80%
    if cum_cwif[cross_idx] < target_fraction:
        x_80 = np.nan
        print(f"Warning: Footprint tail cut off. Max cumulative CWIF is {cum_cwif[-1]:.2f}")
    else:
        x_80 = dist_sorted[cross_idx]
        
    return x_max, x_80


def extract_shape_parameters(Y, pdf_grid, threshold, dx, dy):
    """
    Extracts the geometric area and maximum lateral half-width of a specific footprint contour.
    
    Args:
        Y (numpy.ndarray): 2D grid of Y coordinates.
        pdf_grid (numpy.ndarray): Smoothed 2D footprint probability density matrix.
        threshold (float): The specific PDF value bounding the contour (e.g., the 80% threshold).
        dx, dy (float): Grid resolution.
        
    Returns:
        area_m2 (float): Total area inside the contour.
        half_width_m (float): The maximum lateral distance from the centerline to the contour edge (d_c).
    """
    # Create a boolean mask of all cells inside the contour
    mask = pdf_grid >= threshold
    
    # 1. Calculate Area (Number of cells * area of one cell)
    area_m2 = np.sum(mask) * (dx * dy)
    
    # 2. Calculate Largest Lateral Half-Width (d_c)
    if np.any(mask):
        y_coords_inside = Y[mask]
        y_max = np.max(y_coords_inside)
        y_min = np.min(y_coords_inside)
        
        # Full crosswind span divided by 2 gives the half-width (d_c)
        half_width_m = (y_max - y_min) / 2.0
    else:
        half_width_m = 0.0
        
    return area_m2, half_width_m


def refine_footprint_grid(X_low, Y_low, pdf_low, x_bounds, y_bounds, target_res=1.0):
    """
    Fits a 2D cubic bivariate spline over a low-resolution grid and evaluates it
    onto a refined high-resolution grid to remove quantization plateaus.
    
    Args:
        X_low, Y_low (numpy.ndarray): Meshgrids from the original points_to_grid function.
        pdf_low (numpy.ndarray): The 2D smoothed PDF grid of shape (ny, nx).
        x_bounds, y_bounds (list): Global boundaries of the domain [min, max].
        target_res (float): New grid resolution in meters (e.g., 1.0m or 0.5m).
        
    Returns:
        X_fine, Y_fine, pdf_fine
    """
    # 1. Extract the unique 1D coordinate vectors from the input meshgrid
    x_low_1d = X_low[0, :]
    y_low_1d = Y_low[:, 0]
    
    # 2. Fit the cubic spline (kx=3, ky=3 sets cubic splines along both axes)
    # RectBivariateSpline expects Z to be oriented as (len(x), len(y)), so we pass the transpose
    spline = RectBivariateSpline(x_low_1d, y_low_1d, pdf_low.T, kx=3, ky=3)
    
    # 3. Define the new high-resolution coordinate arrays
    x_fine_1d = np.arange(x_bounds[0], x_bounds[1] + target_res, target_res)
    y_fine_1d = np.arange(y_bounds[0], y_bounds[1] + target_res, target_res)
    
    # 4. Evaluate the spline onto the high-resolution grid vectors
    pdf_fine_T = spline(x_fine_1d, y_fine_1d)
    pdf_fine = pdf_fine_T.T  # Transpose back to standard (ny, nx) shape
    
    # 5. Physics Guard: Clip any minor negative oscillations/overshoots to exactly 0.0
    pdf_fine = np.clip(pdf_fine, a_min=0.0, a_max=None)
    
    # Re-normalize to guarantee perfect integrated mass conservation (Sum = 1.0)
    total_integral = np.sum(pdf_fine) * (target_res * target_res)
    if total_integral > 0:
        pdf_fine = pdf_fine / total_integral
        
    # Generate high-resolution meshgrid for mapping/plotting downstream
    X_fine, Y_fine = np.meshgrid(x_fine_1d, y_fine_1d)
    
    return X_fine, Y_fine, pdf_fine