import numpy as np
from scipy.interpolate import RegularGridInterpolator

# Import Kljun's open-source module
from physics_core.calc_footprint_FFP_climatology import FFP_climatology

def calculate_kljun_ffp_grid(X_fine, Y_fine, sensor_x, sensor_y, zm, z0, umean, h, ol, sigmav, ustar, wind_dir):
    """
    Wraps Kljun's FFP (2015) model, mapping its relative output onto our absolute LBM grid.
    Highly optimized using RegularGridInterpolator.
    """
    
    # 2. Execute the Kljun FFP Model 
    FFP = FFP_climatology(zm=[zm], z0=[z0], umean=[umean], h=[h], ol=[ol], 
                          sigmav=[sigmav], ustar=[ustar], wind_dir=[wind_dir],
                          crop=False, fig=False, verbosity=0)
    
    if FFP is None:
        raise ValueError(f"FFP calculation failed for zm={zm}")

    # Extract Kljun's generated arrays
    x_rel = FFP['x_2d']
    y_rel = FFP['y_2d']
    f_2d = FFP['fclim_2d']
    
    # 3. Geometric Translation (Relative to Absolute)
    x_abs = x_rel + sensor_x
    y_abs = y_rel + sensor_y
    
    # =================================================================
    # 4. HIGH-SPEED INTERPOLATION (RegularGridInterpolator)
    # =================================================================
    # Extract the unique 1D axis arrays from Kljun's 2D meshgrid
    x_1d = x_abs[0, :]
    y_1d = y_abs[:, 0]
    
    # RegularGridInterpolator strictly requires ascending coordinates
    idx_x = np.argsort(x_1d)
    idx_y = np.argsort(y_1d)
    
    x_1d_sorted = x_1d[idx_x]
    y_1d_sorted = y_1d[idx_y]
    
    # Align the 2D probability matrix to match the sorted coordinates
    # (y is axis 0, x is axis 1)
    f_2d_sorted = f_2d[idx_y, :][:, idx_x]
    
    # Create the high-speed interpolator
    # bounds_error=False and fill_value=0.0 guarantee that if Kljun's grid is smaller 
    # than our 1024m domain, it cleanly fills the empty space with 0.0 probability.
    interp = RegularGridInterpolator((y_1d_sorted, x_1d_sorted), f_2d_sorted, 
                                     method='linear', bounds_error=False, fill_value=0.0)
    
    # Flatten our target fine grid into (N, 2) columns of [Y, X]
    points = np.column_stack((Y_fine.flatten(), X_fine.flatten()))
    
    # Evaluate and reshape back to 2D
    kljun_pdf_fine = interp(points).reshape(X_fine.shape)
    
    # 5. Domain Normalization (Sum inside the wind tunnel = 1.0)
    grid_res = X_fine[0,1] - X_fine[0,0] 
    total_mass = np.sum(kljun_pdf_fine) * (grid_res * grid_res)
    
    if total_mass > 0:
        kljun_pdf_fine = kljun_pdf_fine / total_mass
        
    return kljun_pdf_fine