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

def virtual_tower(fields, x, dx=2.0, dz=2.0):
    """
    Vertical profiles at streamwise position x [m] from y-averaged XZ fields
    (load_xz_yav output, arrays indexed [z_idx, x_idx]).

    Returns a dict with "z" [m] (= z_idx * dz) and every available field as a column,
    plus "sigma_v" (needs vv, vm) and "u_star" (needs uw, um, wm).
    """
    any_field = next(iter(fields.values()))
    x_idx = min(int(x / dx), any_field.shape[1] - 1)
    profile = {"z": np.arange(any_field.shape[0]) * dz}
    for name, mat in fields.items():
        profile[name] = mat[:, x_idx]
    if "vv" in fields and "vm" in fields:
        profile["sigma_v"] = calc_sigma_v(profile["vv"], profile["vm"])
    if all(k in fields for k in ("uw", "um", "wm")):
        profile["u_star"] = calc_u_star(profile["uw"], profile["um"], profile["wm"])
    return profile


def mean_wind_profile(fields, x_min, dx=2.0, dz=2.0):
    """
    Eulerian mean and standard deviation of u, v, w against height, averaged over
    x >= x_min [m] from y-averaged XZ fields (load_xz_yav with um, vm, wm, uu, vv, ww;
    uu etc. are raw second moments, so variance = uu - um^2).

    Returns {"z": heights [m] (z_idx * dz), "u_mean", "v_mean", "w_mean", "u_std", "v_std", "w_std"}.
    *_mean is the x-average of the time/y mean; *_std is the square root of the x-average of the
    local variance (the spread of the mean across x is not included).
    Note: cells inside buildings are averaged in as they are stored in the file.
    """
    x0 = int(x_min / dx)
    profile = {"z": np.arange(fields["um"].shape[0]) * dz}
    for c in ("u", "v", "w"):
        mean = fields[f"{c}m"][:, x0:]
        second = fields[f"{c}{c}"][:, x0:]
        profile[f"{c}_mean"] = np.nanmean(mean, axis=1)
        profile[f"{c}_std"] = np.sqrt(np.nanmean(calc_reynolds_stress(second, mean), axis=1))
    return profile
