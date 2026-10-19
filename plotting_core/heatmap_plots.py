"""
x-z heatmaps with one colour scale shared by every panel and frame, and GIF / MP4 assembly from frames.
"""
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize, TwoSlopeNorm


def shared_norm(arrays, center=None):
    """One colour scale for all arrays (NaN ignored). With center, the scale is symmetric around it."""
    lo = min(float(np.nanmin(a)) for a in arrays)
    hi = max(float(np.nanmax(a)) for a in arrays)
    if center is None:
        return Normalize(vmin=lo, vmax=hi)
    half = max(abs(lo - center), abs(hi - center)) or 1.0
    return TwoSlopeNorm(vcenter=center, vmin=center - half, vmax=center + half)


def plot_xz_heatmaps(panels, x, z, norm, cmap, cbar_label, save_path, title="", zmax=None,
                     panel_size=(5.0, 5.0)):
    """
    Heatmaps side by side with one colorbar.

    panels: {panel title: 2D array [z, x]}; x, z: 1D cell-centre positions [m].
    The figure size is fixed (no tight bbox), so frames of an animation all have the same pixel size.
    """
    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(panel_size[0] * n + 1.2, panel_size[1]), sharey=True,
                             squeeze=False, layout="constrained")
    axes = axes[0]
    for ax, (name, arr) in zip(axes, panels.items()):
        mesh = ax.pcolormesh(x, z, arr, norm=norm, cmap=cmap, shading="nearest", rasterized=True)
        ax.set_title(name)
        ax.set_xlabel("x [m]")
        ax.set_aspect("equal")
        if zmax is not None:
            ax.set_ylim(0, zmax)
    axes[0].set_ylabel("z [m]")
    fig.colorbar(mesh, ax=list(axes), label=cbar_label, shrink=0.9)
    if title:
        fig.suptitle(title)
    os.makedirs(os.path.dirname(str(save_path)), exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def frames_to_gif(frame_paths, save_path, fps=1.0):
    """Animated GIF from PNG frames (Pillow, which matplotlib already needs)."""
    from PIL import Image
    images = [Image.open(p).convert("RGB") for p in frame_paths]
    images[0].save(save_path, save_all=True, append_images=images[1:],
                   duration=int(1000 / fps), loop=0)


def frames_to_mp4(frame_paths, save_path, fps=1.0):
    """MP4 from PNG frames. Needs imageio + imageio-ffmpeg (pip install -e .[video]); returns False without them."""
    try:
        import imageio.v2 as imageio
        import imageio_ffmpeg  # noqa: F401  (only to check it is installed)
    except ImportError:
        return False
    with imageio.get_writer(save_path, fps=fps, codec="libx264", macro_block_size=1) as writer:
        for p in frame_paths:
            writer.append_data(_even_size(imageio.imread(p)[..., :3]))
    return True


def _even_size(img):
    """H.264 needs even width and height: drop a last row / column if needed."""
    return img[: img.shape[0] - img.shape[0] % 2, : img.shape[1] - img.shape[1] % 2]

