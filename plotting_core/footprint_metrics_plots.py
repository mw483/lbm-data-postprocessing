import matplotlib.pyplot as plt
import numpy as np
import os

def plot_regression(x_data, y_data, xlabel, ylabel, title, save_path, fit_type='linear'):
    """
    Plots a scatter plot with an automated best-fit line.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Scatter points
    ax.scatter(x_data, y_data, color='blue', s=80, edgecolor='black', zorder=3)
    
    # Regression Fit
    if len(x_data) > 1:
        if fit_type == 'linear':
            # 1st degree polynomial
            m, b = np.polyfit(x_data, y_data, 1)
            x_line = np.linspace(min(x_data)*0.8, max(x_data)*1.1, 100)
            ax.plot(x_line, m*x_line + b, color='red', linestyle='--', label=f'Fit: y={m:.2f}x + {b:.2f}')
        elif fit_type == 'exponential':
            # Exponential fit: y = A * e^(B*x) -> ln(y) = ln(A) + B*x
            # We fit a line to the log of the Y data
            B, ln_A = np.polyfit(x_data, np.log(y_data), 1)
            A = np.exp(ln_A)
            x_line = np.linspace(min(x_data)*0.8, max(x_data)*1.1, 100)
            ax.plot(x_line, A * np.exp(B * x_line), color='red', linestyle='--', label=f'Fit: y={A:.2e} * e^({B:.3f}x)')
            
        ax.legend(fontsize=11)
        
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.grid(True, linestyle=':', alpha=0.6)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)