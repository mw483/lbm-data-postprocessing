import numpy as np

def calculate_analytical_footprint(X, Y, sensor_x, sensor_y, zm, u_star, z0, sigma_v):
    """
    Generates a 2D analytical footprint based on Schmid (1994) / Schuepp (1990) theory.
    
    Args:
        X, Y: 2D meshgrids of coordinates [m]
        sensor_x, sensor_y: Location of the sensor [m]
        zm: Measurement height [m]
        u_star: Friction velocity [m/s]
        z0: Aerodynamic roughness length [m]
        sigma_v: Crosswind standard deviation [m/s]
        
    Returns:
        pdf_grid: 2D array of footprint probabilities [m^-2]
    """
    kappa = 0.40
    
    # 1. Calculate the mean wind speed at the sensor height using our log-law
    U_mean = (u_star / kappa) * np.log(zm / z0)
    
    # 2. Calculate Upwind Distance from the sensor
    # We use np.maximum to prevent divide-by-zero exactly at the sensor location
    x_dist = np.maximum(sensor_x - X, 0.001) 
    
    # 3. The 1D Crosswind-Integrated Footprint (CWIF)
    # Based on the analytical advection-diffusion solution
    numerator = U_mean * zm
    denominator = kappa * u_star * (x_dist**2)
    exponent = - (U_mean * zm) / (kappa * u_star * x_dist)
    
    # fy(x) is the 1D probability density [m^-1]
    fy = (numerator / denominator) * np.exp(exponent)
    
    # Zero out any values that are downwind of the sensor (x_dist < 0)
    fy[X >= sensor_x] = 0.0
    
    # 4. The Crosswind Dispersion (Lateral Spread)
    # The plume width (sigma_y) grows linearly with time/distance
    sigma_y = sigma_v * (x_dist / U_mean)
    
    # 5. The 2D Gaussian Crosswind Distribution
    y_dist = Y - sensor_y
    
    # Dy(x,y) distributes the 1D fy(x) mass laterally across the Y-axis [m^-1]
    Dy = (1.0 / (np.sqrt(2 * np.pi) * sigma_y)) * np.exp(- (y_dist**2) / (2 * sigma_y**2))
    
    # 6. The Final 2D Footprint [m^-2]
    f_xy = fy * Dy
    
    # Clean up any potential NaNs from the zero-distance clipping
    f_xy = np.nan_to_num(f_xy, 0.0)
    
    return f_xy