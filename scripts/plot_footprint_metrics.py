import os
import sys
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from plotting_core.footprint_metrics_plots import plot_regression

def main():
    # File paths
    metrics_csv = r"../figures/20260527_flat_footprints/contour_analysis/peak_distance_metrics.csv"
    output_dir = r"../figures/20260527_flat_footprints/metrics"
    
    print(f"Loading metrics from {metrics_csv}...")
    try:
        df = pd.read_csv(metrics_csv)
    except FileNotFoundError:
        print("CSV not found. Run 02_plot_lbm_contours.py first!")
        return

    # Extract columns
    zm = df['Sensor_Z'].values
    peak_dist = df['Peak_Distance_m'].values
    peak_den = df['Peak_Density_m2'].values
    x_max_cwif = df['X_Max_CWIF'].values
    x_80 = df['X_80_Extent'].values
    area_80 = df['Area_80_m2'].values
    d_80 = df['HalfWidth_80_m'].values
    
    # 1. Plot Zm vs Peak Distance (Linear)
    plot_regression(
        zm, peak_dist, 
        xlabel="Measurement Height, $z_m$ [m]", 
        ylabel="2D Peak Distance, $x_{max}$ [m]",
        title="Effect of Sensor Height on Footprint Peak Distance",
        save_path=os.path.join(output_dir, "zm_vs_peak_distance.png"),
        fit_type='linear'
    )
    
    # 2. Plot Zm vs Peak Density (Exponential)
    plot_regression(
        zm, peak_den, 
        xlabel="Measurement Height, $z_m$ [m]", 
        ylabel="Peak Source Density [m$^{-2}$]",
        title="Exponential Decay of Footprint Peak Density",
        save_path=os.path.join(output_dir, "zm_vs_peak_density.png"),
        fit_type='exponential'
    )

    # 3. Schmid Validation: Area vs Zm

    plot_regression(
        zm, area_80, 
        xlabel="Measurement Height, $z_m$ [m]", 
        ylabel="Isopleth Area, $A_{80}$ [m$^2$]",
        title="Effect of Sensor Height on Isopleth Area",
        save_path=os.path.join(output_dir, "zm_vs_area_80.png"),
        fit_type='linear'
    )

    # 4. Schmid Validation: Lateral extent (d) vs Zm

    plot_regression(
        zm, d_80, 
        xlabel="Measurement Height, $z_m$ [m]", 
        ylabel="Lateral Extent, $d$ [m]",
        title="Effect of Sensor Height on Isopleth Lateral Extent",
        save_path=os.path.join(output_dir, "zm_vs_lateral_extent_80.png"),
        fit_type='linear'
    )

    # 5. Kljun Validation: x_max vs x_80 (Linear)
    # We drop any NaN values in case x_80 got cut off by the domain boundary
    valid_mask = ~np.isnan(x_80)
    
    plot_regression(
        x_max_cwif[valid_mask], x_80[valid_mask], 
        xlabel="Peak Location, $x_{max}$ [m]", 
        ylabel="80% Extent, $x_{80}$ [m]",
        title="LBM Validation of Kljun (2015) Linear Scaling",
        save_path=os.path.join(output_dir, "kljun_xmax_vs_x80.png"),
        fit_type='linear'
    )
    
    print(f"Saved metric plots to {output_dir}")

if __name__ == "__main__":
    main()