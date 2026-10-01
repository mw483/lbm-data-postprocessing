def apply_axis_zoom(ax, zoom_config):
    """Applies a camera zoom to the matplotlib axis without slicing underlying arrays."""
    if zoom_config and zoom_config.get("enabled", False):
        xc, yc = zoom_config["x_center"], zoom_config["y_center"]
        half_grid = zoom_config["grid_size"] // 2
        ax.set_xlim(xc - half_grid, xc + half_grid)
        ax.set_ylim(yc - half_grid, yc + half_grid)