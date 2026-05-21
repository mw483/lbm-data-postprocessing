import numpy as np

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