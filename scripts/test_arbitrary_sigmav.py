import os
import sys
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_loaders.config_loader import load_json_config
from data_loaders.footprint_io import load_source_positions, load_footprint_counts
from data_loaders.lbm_parsers import XZMatrixParser
from physics_core.footprint_processing import smooth_footprint_grid, refine_footprint_grid, merge_counts_with_positions, points_to_grid
from physics_core.kljun_wrapper import calculate_kljun_ffp_grid
from plotting_core.experiment_plots import plot_arbitrary_sigmav_sweep

def main():
    base_dir = r"Z:\Particle_PostProcess_Outputs\20260527_particle_flat_3072\sensor_40x40x8"
    pos_file = r"Z:\particle_position\particle_position.txt"
    base_out = r"Z:\20260527_output_flat_3072"
    
    output_dir = r"../figures/flat_domain/sensor_40x40x8/sensitivity"
    os.makedirs(output_dir, exist_ok=True)
    
    sensor_x, sensor_y, sz = 600.0, 128.0, 40.0
    x_bounds, y_bounds = [0, 1024], [0, 256]
    dx_lbm, dz_lbm = 2.0, 2.0
    
    # The arbitrary array requested
    test_sigmas = [0.125, 0.250, 0.375, 0.500]
    
    params = load_json_config(r"../physics_core/metrics/schmid_params.json")
    u_star_global = params["u_star"]
    z0 = params["z0"]
    
    um_mat = XZMatrixParser.parse_file(os.path.join(base_out, "xz_yav_um00180000_0000.csv"))
    x_idx = min(int(sensor_x / dx_lbm), um_mat.shape[1] - 1)
    z_idx_local = min(int(sz / dz_lbm), um_mat.shape[0] - 1)
    
    u_local = um_mat[z_idx_local, x_idx]
    
    print(f"Executing Arbitrary Sigma_v Sweep at Z={sz}m (U_mean = {u_local:.2f} m/s)")

    # 1. Load LBM Truth Data
    source_map = load_source_positions(pos_file)
    csv_path = os.path.join(base_dir, "1200-1800_footprint", f"footprint_{int(sensor_x)}_{int(sensor_y)}_{int(sz)}.csv")
    count_map = load_footprint_counts(csv_path)
    x_pts, y_pts, counts = merge_counts_with_positions(source_map, count_map)
    X_low, Y_low, raw_pdf = points_to_grid(x_pts, y_pts, counts, dx=8.0, dy=8.0, x_bounds=x_bounds, y_bounds=y_bounds)
    
    target_sigma = 0.4 + (sz / 31.25)
    X_fine, Y_fine, lbm_pdf = refine_footprint_grid(X_low, Y_low, smooth_footprint_grid(raw_pdf, dx=8.0, dy=8.0, sigma=target_sigma), x_bounds=x_bounds, y_bounds=y_bounds, target_res=1.0)

    # 2. Run Kljun for each arbitrary sigma_v
    kljun_pdfs = []
    for sig_v in test_sigmas:
        print(f"  -> Calculating FFP for sigma_v = {sig_v:.3f} m/s...")
        k_pdf = calculate_kljun_ffp_grid(
            X_fine, Y_fine, sensor_x, sensor_y, 
            zm=sz, z0=z0, umean=u_local, h=160.0, ol=100000.0, 
            sigmav=sig_v, ustar=u_star_global, wind_dir=270.0
        )
        kljun_pdfs.append(k_pdf)
    
    # 3. Plot the Sweep
    save_path = os.path.join(output_dir, f"arbitrary_sigmav_sweep_z{sz}.png")
    plot_arbitrary_sigmav_sweep(X_fine, Y_fine, lbm_pdf, kljun_pdfs, test_sigmas, (sensor_x, sensor_y), save_path)
    print(f"\nSaved arbitrary sweep plot to {save_path}")

if __name__ == "__main__":
    main()