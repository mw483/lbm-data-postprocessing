from scipy.ndimage import gaussian_filter
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