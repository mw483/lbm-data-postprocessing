# Particle statistics, TTD table and real-time animation (2026-10-06)

**Commits:** `771df9f`, `b96f838`, `c3bc27d` (range `1c69f84..c3bc27d`, branch `analysis/presentation-oct`)
**Goal:** More post-analysis for the 2026-10-07 talk. Extends [2026-10-05_presentation-scripts.md](2026-10-05_presentation-scripts.md).
**Result:** 26 pytest tests pass (new file `tests/test_particle_stats.py`). The velocity script, the table script and `animate_particles_to_sensor.py --record` ran on synthetic data under Xvfb. The live animation window opened without errors (not interacted with). **Nothing was run on real data.**

---

## Context

kaka (2026-10-06) asked for two things:

1. An animation of the particles moving from source to sensor. The isopleths and density clouds pool the whole 600 s window, so they do not show the motion.
2. More statistics on the TTD and on the particle velocities, for example mean, median and variance of u, v, w against height. Until now only the wind was looked at.

## Decisions (kaka)

- Animation in real simulation time, simply following `target_trajectories.csv` by time.
- Resolved velocity only (total minus SGS). kaka is unsure how much SGS contributes. The LSM is a TKE-scaled stochastic model, and kaka only has 2D plane wind output (a choice in `Define_user.h`), so there is no 3D TKE to judge it with.
- Only the release-to-sensor part of each path is used for the velocity statistics.
- Only x >= 3072 m. The upstream blocks only induce turbulence.
- Eulerian wind overlay: wanted, but kaka is not confident in its accuracy (only 2D planes). It is therefore a toggle, `OVERLAY_WIND`, default `False`.
- The 4 m height bin and the TTD table columns were part of the plan kaka approved.

## Commit `771df9f`: particle velocity statistics vs height

| File | Change | Why |
|---|---|---|
| [physics_core/particle_analysis.py](../physics_core/particle_analysis.py) `until_arrival` | Keeps each particle's records from its first record up to and including its arrival step at one sensor. Particles without an arrival are dropped. | Release-to-sensor part only. |
| same, `velocity_stats_by_height` | Per height bin (`z_bin=4.0` default) writes `n` and, for each component, `_mean`, `_median`, `_std`, `_var`, `_p10`, `_p90`. Bins with fewer than `min_count` records are dropped. Every record (particle x output second) counts once. | mean/median/variance of u, v, w vs height. |
| same, `transit_time_summary` | Added here, used by the next commit (see below). | |
| [physics_core/turbulence.py](../physics_core/turbulence.py) `mean_wind_profile` | Eulerian mean and std of u, v, w vs height from the y-averaged XZ output, averaged over x >= `x_min`. Variance = uu - um^2 (`calc_reynolds_stress`). The std is the root of the x-average of the local variance, so the spread of the mean across x is not included. Building cells are averaged in as stored. | Optional overlay. |
| [plotting_core/velocity_analysis_plots.py](../plotting_core/velocity_analysis_plots.py) `plot_velocity_profiles` | Two rows, one column per component, height on y. Row 1: mean, median, 10-90 % band. Row 2: std. Flat vs cube. Optional dotted Eulerian lines. | Figure for the talk. |
| [scripts/plot_particle_velocity_profiles.py](../scripts/plot_particle_velocity_profiles.py) | New. Settings: `SENSORS = {4: (3672, 256, 90)}`, `X_START = 3072`, `Z_BIN = 4`, `MIN_COUNT = 20`, `COMPONENTS = u_res, v_res, w_res`, `OVERLAY_WIND = False`, `WIND_STEP = 90000`. Writes one PNG and one CSV per sensor into `figures/presentation_2026-10-07/velocity_profiles/`. | |
| [data_loaders/local_paths.py](../data_loaders/local_paths.py), [local_paths.example.yaml](../local_paths.example.yaml) | New optional key `wind_outputs` (`OPTIONAL_KEYS`): folder with the solver `<date>_output_<case>` folders. Only read when set. | Needed only for the overlay. Existing configs keep working. |
| [tests/test_particle_stats.py](../tests/test_particle_stats.py) | Tests for `until_arrival`, `velocity_stats_by_height`, `transit_time_summary`, `mean_wind_profile` (4 tests). | |

## Commit `b96f838`: transit-time statistics table

| File | Change | Why |
|---|---|---|
| [scripts/table_transit_time_stats.py](../scripts/table_transit_time_stats.py) | New. One CSV (`ttd_stats.csv`, flat vs cube): per sensor (`scope = sensor`) and per spanwise line at each height (`scope = line`, one value per particle at its earliest arrival, as in `plot_ensemble_ttd.py`). Columns: `case, scope, sensor_id, x, y, z, n, mean_s, median_s, std_s, p10_s, p90_s, min_s, max_s`. | TTD statistics for the talk. |

## Commit `c3bc27d`: real-time animation

| File | Change | Why |
|---|---|---|
| [scripts/animate_particles_to_sensor.py](../scripts/animate_particles_to_sensor.py) | New. One frame per output second of `target_trajectories.csv` (via the sensor cache). Flat and cube side by side, linked camera, points coloured by resolved `w_res` with one shared range (2nd to 98th percentile, symmetric). Only x >= 3072 m. Live mode: time slider, space plays and pauses, `s` screenshot. `--record` writes `4_particles_real_time.mp4` (no window). `UNTIL_ARRIVAL` (default `False`) hides a particle after it reaches the sensor. Sensor 4 at (3672, 256, 90). | Show the motion that the pooled clouds hide. |

No physics, solver or existing-script behaviour changed. Nothing here needs a revert beyond removing the new files.

## What was deliberately left alone

- Total velocity (resolved + SGS) and any SGS statistics.
- Parts of the path after sensor arrival and x < 3072 m.
- Sensors other than 4 (the velocity script lists 13 and 22 in a comment as examples).

## Not checked and open items

- **`WIND_STEP = 90000`** as the xz_yav window that matches the particle window 1200-1800 s is inferred (dt 0.02 s, 600 s windows every 30000 steps). kaka needs to confirm it.
- The wind folder names `20260630_output_flat_16mapproach` and `20260803_output_cube_16mapproach` are inferred from the particle folder names.
- The Eulerian mean includes building cells as stored.
- Particle statistics are weighted by residence time (each record counts once). This differs from the Eulerian time average, so the dotted lines and the particle lines are not the same kind of average.
- Nothing was run on real data. The live animation was not interacted with.

## How to check

```sh
git log --oneline 1c69f84..c3bc27d
git diff -w --stat 1c69f84 c3bc27d
pytest tests/test_particle_stats.py     # 4 new tests; whole suite: 26
python scripts/plot_particle_velocity_profiles.py
python scripts/table_transit_time_stats.py
python scripts/animate_particles_to_sensor.py [--record]
```
