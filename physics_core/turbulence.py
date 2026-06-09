import numpy as np
from scipy.optimize import curve_fit

def calc_reynolds_stress(variance, mean_vel):
    """Calculates normal stress and clips negative machine precision errors."""
    stress = variance - (mean_vel**2)
    return np.maximum(0, stress)

def calc_tke(uu, vv, ww, um, vm, wm):
    """Calculates Turbulent Kinetic Energy."""
    uu_stress = calc_reynolds_stress(uu, um)
    vv_stress = calc_reynolds_stress(vv, vm)
    ww_stress = calc_reynolds_stress(ww, wm)
    return 0.5 * (uu_stress + vv_stress + ww_stress)

def calc_sigma_v(vv, vm):
    """Calculates lateral wind speed fluctuation."""
    vv_stress = calc_reynolds_stress(vv, vm)
    return np.sqrt(vv_stress)

def calc_u_star(uw, um, wm):
    """Calculates friction velocity u*."""
    cov_uw = uw - (um * wm)
    return np.sqrt(np.abs(cov_uw))

# --- Future-Proofing Normalization ---
def normalize_data(data, ref_value):
    """Generic normalizer for velocity (U_H) or heights (H)."""
    return data / ref_value

def log_law_profile(z, u_star, z0):
    """
    Theoretical logarithmic wind profile equation.
    kappa (von Karman constant) is standardly taken as 0.40.
    """
    # In the LBM code, the friction velocity u_tau is calculated in lbm_gpu.cu line 628, under the if condition for flg_wallFunction
    #     if(user_init::z0 > 0.0){ // loglaw
    #     u_tau = 0.4 * U_neighbor / log(dx*0.5/user_init::z0); // friction velocity
    # }else{ // Spalding law
    #     u_tau = U_neighbor / 30.0;
    #     for(int c=0; c<30; c++){
    #         u_tau = u_tau - wall_func(u_tau, U_neighbor, dx*0.5) / d_wall_func_dut(u_tau, U_neighbor, dx*0.5);
    #     }
    # }
    kappa = 0.40
    return (u_star / kappa) * np.log(z / z0)

def fit_boundary_layer_profile(z_array, u_array, max_fit_height=40.0):
    """
    Fits the log-law equation to a vertical velocity profile to extract
    friction velocity (u*) and aerodynamic roughness (z0).
    
    Args:
        z_array (np.ndarray): 1D array of physical heights [m].
        u_array (np.ndarray): 1D array of mean wind speeds [m/s].
        max_fit_height (float): Upper limit of the constant flux layer [m].
                                (Only fit the curve to the bottom portion of the domain).
    """
    # Filter arrays to only include the constant flux layer (near-wall region)
    mask = z_array <= max_fit_height
    z_fit = z_array[mask]
    u_fit = u_array[mask]
    
    # p0 provides initial logical guesses: u_star=0.5 m/s, z0=0.01 m
    # bounds enforce physical reality (u* > 0, z0 > 0)
    popt, _ = curve_fit(log_law_profile, z_fit, u_fit, 
                        p0=[0.5, 0.01], 
                        bounds=([0.001, 0.0001], [5.0, 2.0]))
    
    u_star, z0 = popt
    return u_star, z0