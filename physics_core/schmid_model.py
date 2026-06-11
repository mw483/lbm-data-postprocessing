import numpy as np

def calculate_analytical_footprint(X, Y, sensor_x, sensor_y, zm, u_star, z0, sigma_v):
    """
    Generates the true Schmid (1994) SAM footprint using Van Ulden (1978) 
    vertical dispersion physics (s=1.5).
    """
    # 1. Van Ulden & Atmospheric Constants
    kappa = 0.35
    s = 1.5
    A = 0.73
    B = 0.66
    p = 1.55 # Van Ulden 1978
    gamma = 0.66 # Horst & Weil (1992), Van Ulden (1978), Chatwin (1968)

    # Chatwin (1968)
    # s = 1.0
    # A = 1.0
    # B = 1.0
    # p = 0.562 # Horst & Weil (1992), Chatwin (1968)
    
    # 2. Upwind Distance from sensor
    x_dist = np.maximum(sensor_x - X, 0.001) 
    
    # =================================================================
    # 3. SOLVE MEAN PLUME HEIGHT (z_bar) FOR EVERY GRID CELL
    # =================================================================
    # Create a theoretical 1D array of z_bar from the ground up to 10x the sensor height
    z_bar_theory = np.linspace(z0/p + 0.001, zm * 10, 5000)
    
    # Calculate the theoretical fetch (x) required to reach each z_bar
    # Derived from integrating: dx = (0.74/kappa^2) * ln(p*z_bar/z0) d(z_bar)
    phi_h_neutral = 0.74  # Turbulent Prandtl Number for neutral passive scalars

    x_theory = phi_h_neutral * ( (z_bar_theory / kappa**2) * (np.log(p * z_bar_theory / z0) - 1) + (z0 / (p * kappa**2)) )
    
    # Use ultra-fast 1D interpolation to map the theoretical z_bar onto our actual 2D grid
    z_bar_grid = np.interp(x_dist, x_theory, z_bar_theory)
    
    # =================================================================
    # 4. SCHMID (1994) CONCENTRATION FOOTPRINT EQUATIONS
    # =================================================================
    # Effective Advection Velocity U_e(x) evaluated at height p * z_bar
    U_e = (u_star / kappa) * np.log(np.exp(-gamma) * z_bar_grid / z0)
    
    # Vertical Concentration Distribution D_z(x, zm)
    Dz = (A / z_bar_grid) * np.exp(- (B * zm / z_bar_grid)**s)
    
    # 1D Crosswind-Integrated Footprint fy(x) = Dz / U_e
    fy = Dz / U_e
    fy[X >= sensor_x] = 0.0  # Zero out anything downwind of the sensor
    
    # Crosswind Spread (sigma_y) based on effective advection time
    sigma_y = sigma_v * (x_dist / U_e)
    
    # 2D Gaussian Crosswind Distribution D_y(x, y)
    y_dist = Y - sensor_y
    Dy = (1.0 / (np.sqrt(2 * np.pi) * sigma_y)) * np.exp(-0.5 * (y_dist / sigma_y)**2)
    
    # Final 2D Footprint (Source Weight Function)
    f_xy = fy * Dy
    f_xy = np.nan_to_num(f_xy, 0.0)
    
    return f_xy