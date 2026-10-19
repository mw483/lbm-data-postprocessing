# Velocity and Reynolds stress profiles, xz_yav heatmaps and animations (2026-10-19)

**Commits:** `0abeba0`, `70483dd`, `bf0f9a7` (range `285fdb2..bf0f9a7`, branch `analysis/scalar2-outputs`)
**Goal:** Two analysis scripts for the flat runs `flat_512x128x1024/20261011_scalar2` (convective) and `flat_512x128x1024/20261017_neutral`: (1) Chang et al. (2009)-style time-averaged velocity and Reynolds stress profiles, (2) heatmaps and animations of the y-averaged x-z files (`xz_yav_*`).
**Result:** Both scripts ran in the cloud on copies of the real output files (`header.txt`, `prof`, `xz_yav` um/vm/wm/uu/vv/ww, 7 windows, steps 25001-175001, 4 ranks). Figures were inspected: the convective boundary layer reaches about 400-450 m, sigma_w up to 0.89 m/s; the neutral case has turbulence only below about 100 m. pytest: 51 passed, 1 failed (the known `tests/test_particle_io.py::test_streamed_trajectories_read_11_column_file`, polars version, unrelated, see [2026-10-16_scalar2-output-reader.md](2026-10-16_scalar2-output-reader.md)). **Not run on the lab PC itself.**

---

## Context

Mikael asked on 2026-10-19 for two scripts. Builds on the reader and moments module from [2026-10-16_scalar2-output-reader.md](2026-10-16_scalar2-output-reader.md).

Confirmed with Mikael:

- Profiles: U, V, W plus <u'u'>, <v'v'>, <w'w'> and <u'w'>; every 200 s averaging window; z 0-1000 m. Two figures per window: as is, and normalised by the inflow velocity Ub = 5 m/s.
- Chang et al. used several y-positions around blocks. The domain here is flat, so the domain-mean `prof*.csv` profile is used instead.
- Heatmaps: U, W, sigma_w, plus TKE (added by Mikael); 0-1000 m (Mikael saw that the statistics are constant above 1000 m); every output window; pictures and animations at 1 frame per second; two layouts (cases side by side in one figure, and one figure per case).

## Commit `0abeba0`: plane moments, profile grid and heatmap helpers

| File | Change | Why |
|---|---|---|
| [physics_core/moments.py](../physics_core/moments.py) | New `plane_moments(fields)`. Input: raw plane arrays keyed `um, vm, wm, uu, vv, ww`. Output keys `U, V, W, var_u, var_v, var_w, sigma_w, tke`, only those that can be formed. Variance = `covariance(uu, um, um)`. | Central moments from the raw `xz_yav` fields, same maths as the profile path. |
| [plotting_core/heatmap_plots.py](../plotting_core/heatmap_plots.py) (new) | `shared_norm(arrays, center=None)`: one `Normalize` over all arrays (NaN ignored). With `center`, a `TwoSlopeNorm` symmetric around it (half range = largest distance of min or max from the centre). `plot_xz_heatmaps`: panels side by side, one colorbar, fixed figure size (`layout="constrained"`, `savefig(dpi=150)` without tight bbox), equal aspect. `frames_to_gif` (Pillow). `frames_to_mp4` (imageio, imageio-ffmpeg, libx264; returns `False` if not installed; drops a last row or column to get even size). | Frames of an animation must have the same pixel size and the same colour scale. |
| [plotting_core/profile_plots.py](../plotting_core/profile_plots.py) | New `plot_profile_grid(profiles, rows, ...)`: panels in rows, a `None` entry hides that panel. `plot_profile_panels` now calls it with one row. Title offset is `y=1.04` for several rows, `1.06` for one. | The stress figure needs two rows (3 velocities, 4 stresses). |
| [tests/test_lbm_output.py](../tests/test_lbm_output.py) | `test_plane_moments_central`, `test_shared_norm_same_scale_and_centred`. | Cover the two new helpers. |

Behaviour of `plot_profile_panels` is unchanged (one row, same output); it was only moved onto the new function. To undo: revert `0abeba0`, which also removes the helpers the two scripts need.

TKE here is resolved TKE from the plane variances, 0.5 (var_u + var_v + var_w). There is no SGS part.

## Commit `70483dd`: velocity and Reynolds stress profile script

| File | Change | Why |
|---|---|---|
| [scripts/plot_velocity_stress_profiles.py](../scripts/plot_velocity_stress_profiles.py) (new) | `CASES` = convective `flat_512x128x1024/20261011_scalar2`, neutral `flat_512x128x1024/20261017_neutral`. Settings `UB = 5.0` [m/s], `ZMAX = 1000.0` [m]. Uses the steps both cases share. Per step: `domain_profile(load_prof(...))`, then `profile_moments`. Row 1: U, V, W. Row 2: `var_u`, `var_v`, `var_w`, `cov_uw`. Writes `velocity_stress_step<step>.png` and `..._normalised.png`, plus `velocity_stress_profiles.csv` with all values (columns `case`, `step`, `time` added). Output in `<figures>/scalar2_outputs/velocity_stress_profiles/`. | Chang et al. (2009) style profiles for the flat runs. |

Normalised figure: velocities divided by Ub, stresses divided by Ub squared (axis labels `U / $U_b$`, `<u'u'> / $U_b^2$`). The window label is `t_end - t_ave` to `t_end`, with `t_ave` from `header.txt`.

## Commit `bf0f9a7`: xz_yav heatmap script and README

| File | Change | Why |
|---|---|---|
| [scripts/plot_xz_yav_heatmaps.py](../scripts/plot_xz_yav_heatmaps.py) (new) | Loads `xz_yav_um/vm/wm/uu/vv/ww` for every shared step, cuts at `ZMAX = 1000.0`, calls `plane_moments`. Variables: U (`viridis`), W (`RdBu_r`, centre 0), sigma_w (`magma`), tke (`magma`). Per variable: `combined_step<step>.png`, `<case>_step<step>.png`, `combined.gif` and `<case>.gif`, and `.mp4` when the video extra is installed. `FPS = 1.0`. Output in `<figures>/scalar2_outputs/xz_yav_heatmaps/<variable>/`. | Show how the x-z structure develops window by window, both cases comparable. |
| [README.md](../README.md) | Two lines for the new scripts and a paragraph on colour scale, height range, file names and the MP4 extra. | How to run them. |

Design choices (from the brief):

- One colour scale per variable, shared over both cases and all windows, so animation frames can be compared. The cost: a window with small values looks pale next to a strong one.
- W uses a diverging map centred at 0 (symmetric limits).
- Fixed figure size, no tight bbox, so GIF and MP4 frames all match.
- GIF needs only Pillow. MP4 needs the existing optional `video` extra (imageio, imageio-ffmpeg) and is silently skipped without it (the script prints "GIF" instead of "GIF and MP4").
- All windows are held in memory (7 windows x 2 cases x 4 small arrays).

## What was deliberately left alone

- Figures are not committed. Mikael commits figures himself from the lab PC.
- No SGS part in TKE.
- Only the domain-mean profile is used for the stress figures (no per-y positions as in Chang et al.).
- The reader and the older scripts were not changed.

## Not checked and open items

- Not run on the lab PC itself.
- The first window's W map is nearly blank on the shared scale. Expected: the flow is still spinning up.
- Domain-mean W in the profile figure is about 1e-4 m/s noise, so the W panel shows noise on its own axis.
- Both new scripts use the neutral folder `20261017_neutral` that Mikael set in `plot_profiles_by_window.py` in `285fdb2` (a placeholder in the 2026-10-16 entry).

## How to check

```sh
git log --oneline 285fdb2..bf0f9a7
git show --stat 0abeba0 70483dd bf0f9a7
git diff -w 285fdb2 bf0f9a7 -- plotting_core physics_core
pip install -e .[dev]          # add .[video] for MP4
pytest tests/test_lbm_output.py
# lbm_results must be set in local_paths.yaml
python scripts/plot_velocity_stress_profiles.py
python scripts/plot_xz_yav_heatmaps.py
```
