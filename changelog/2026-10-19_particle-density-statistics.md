# Particle concentration statistics from the C++ basic pass (2026-10-19)

**Commits:** `e7260ed`, `a50be0f` (range `4286f57..HEAD`, branch `analysis/scalar2-outputs`)
**Goal:** Basic statistical analysis of the C++ particle post-processing outputs (`total_num.csv`, `profile.csv`, `xy/xz/yz_number_density_*.csv`) for the runs `flat_512x128x1024/20261011_scalar2` (convective) and `flat_512x128x1024/20261017_neutral`.
**Result:** A reader, a statistics module, a plotting module and one script (`analyze_particle_density.py`). pytest on tiny files: 8 passed. The script ran in the cloud on copies of both runs' real files (staged from the lab PC). **Not run on the lab PC itself. No C++ changes.**

---

## Context

Mikael asked on 2026-10-19 for a basic statistical analysis of the C++ particle outputs of the two flat runs. He approved "density-related code only for now"; sensor analysis is deferred.

Facts checked before coding (LBM-city `mikael/cases`: `Particle_PostProcessing_CPP/src/density.cpp`, `cases/flat_512x128x1024/case_resolved.yaml`, and the runs' `total_num.csv`):

- `density.cpp` adds 1 per particle per snapshot. The CSVs are therefore raw counts summed over all snapshots of the window, not concentrations.
- The window 1200-1800 is in outputs of 0.8 s (dt 0.008 s x pout 100). Release runs from t = 960 s to 1440 s.
- The convective particle number reaches a plateau from about output 1500. The neutral one is still rising at 1800, and the neutral flow itself is still developing. Mikael chose to report neutral as developing.
- About a third of the snapshots in 1200-1800 come from the filling stage.

Because of this, Mikael reran `run_basic.sh` for the steady window 1500-1800 and for the blocks 1500-1600, 1600-1700, 1700-1800. Folders are named `<start>-<end>_basic`. Both ends are included, so neighbouring blocks share one output.

## Decisions

- **Normalisation (Mikael):** particles per m^3 per snapshot, C = count / (n_snapshots x dx x dx x H_AVE). `n_snapshots` is counted from the "Current processing" lines of `log_analysis.txt`, because that is the true divisor. The script warns if it differs from end - start + 1.
- **Release rate:** Mikael said 2816 per second. The case releases 2816 particles (one per source) every output = 0.8 s (generate_step = pout = 100; `total_num` rises by 2816 per output). The script therefore uses 3520 particles/s, from settings `RELEASE_PER_OUTPUT = 2816`, `DT_OUTPUT = 0.8`, `RELEASE_EVERY = 1`. **Point to confirm with Mikael.**
- **Block statistics:** the standard error assumes independent blocks. Spanwise (y) CV uses the y-homogeneity of the flat case. Both are assumptions, not tested.
- **Left out on purpose:** C++ changes, sensor/footprint analysis, y-integrated xz density (a possible later C++ addition).

## Commit `e7260ed`: reader and statistics

| File | Change | Why |
|---|---|---|
| `data_loaders/particle_postprocess.py:list_windows`, `window_dir` | Find `<start>-<end>_basic` folders, keyed by `(start, end)` | The windows are separate folders per run |
| `:read_log_settings` | Reads the settings block of `log_analysis.txt` (numbers, `[a b c]` lists) and adds `n_snapshots` from the "Current processing" lines | The summed counts need the true snapshot count as divisor |
| `:read_total_num` | `total_num.csv` (2 rows) to a DataFrame, cut to the outputs of the window named by the folder | The file holds output 0..end; only the window is wanted |
| `:read_profile` | `profile.csv` rank blocks summed to count and fluid cells per z cell; z = cell centre | Profile is stored per rank block |
| `:list_density`, `read_density`, `read_xy_stack`, `cell_centres` | List and read `xy/xz/yz_number_density_<pos>m.csv` as int arrays; stack xy slabs | Density files are counts on cells of dX |
| `physics_core/particle_density.py:concentration`, `slab_cell_volume`, `profile_concentration` | Counts to C [1/m^3]; slab cell volume dx x dx x H_AVE; profile cell volume fluid_cells x dx^3 (NaN where no fluid) | Normalisation decided above |
| `:vertical_stats` | Mean height, sigma_z, z_max, 50/90/99 % heights from counts per z cell | Height distribution of the plume |
| `:spanwise_stats`, `block_stats` | Mean, std (ddof 1), CV across y; mean, std, sem, CV across time blocks (needs at least 2 blocks) | Sampling variability |
| `:release_rate`, `residence_time`, `count_summary` | Rate = per output / output interval; N mean/min/max, linear trend of N and trend / rate, residence time = mean N / rate | Plateau check and residence time |
| `tests/test_particle_density.py` | 8 tests on tiny files in the C++ formats | Check reader and formulas |

## Commit `a50be0f`: script, figures, README

| File | Change | Why |
|---|---|---|
| `scripts/analyze_particle_density.py` | Settings block (`CASES`, `FULL_WINDOW = (1200, 1800)`, `STEADY_WINDOW = (1500, 1800)`, `BLOCKS`, release settings, `HEIGHTS = (2, 10, 20, 50)`). Stops with a clear error if a window folder is missing. Writes to `<figures>/particle_density/`: `particle_count.png`, `concentration_profiles.png`, `concentration_along_x.png`, `xz_slab_<y>m_steady.png`, `count_summary.csv`, `vertical_stats.csv`, `along_x.csv`. Prints the tables and median block CV and spanwise CV | Compare the two cases over the full release window, the steady window and its blocks |
| `plotting_core/particle_density_plots.py:plot_particle_count`, `plot_concentration_profiles`, `plot_along_x` | N(t) with shaded windows; C(z) per case on a log axis; y-mean C(x) per height with block min..max band and the whole-window curve dashed, source area marked | Figures for the script. The xz slab reuses the existing `plot_xz_heatmaps` |
| `README.md` | New section "Particle concentrations from the C++ basic pass" | How to run and what the numbers mean |
| `local_paths.example.yaml` | Comment: `lbm_results` is also needed by `analyze_particle_density.py` | Documentation only |

## How it was checked

- `python -m pytest tests/test_particle_density.py`: 8 passed (tiny files).
- The script ran on copies of both runs' real files in the cloud session. Numbers from that run: steady-window residence time about 158 s (convective) and 237 s (neutral); mean particle height 22.3 m (convective) vs 10.0 m (neutral); block CV of the y-mean C at 2 m about 0.03 in both cases. The figures were inspected.
- **Not checked:** the lab PC run; the full pytest suite beyond the new file; the release rate with Mikael (see above); independence of the blocks.

## Known issue seen in the results

Near the ground (2 m), the y-mean concentration jumps up by about 24 % at x = 256 m and 14-17 % at x = 512 m, in both runs. These x positions are the GPU rank boundaries. LBM-city `src/ParamParticle_MPI.cu` sends only x, y, z, vel, state and source index between ranks, not the SGS velocity. A likely cause is that the SGS velocity is reset when a particle crosses a rank boundary. The MPI datatype was read in `ParamParticle_MPI.cu` (`MPI_Type_create_struct`, six fields). That it causes the jump is **inferred, not proven**. Nothing was changed here.

## Open items and known limits

- Confirm the release rate of 3520 particles/s (2816 per 0.8 s) against Mikael's "2816 per second".
- The neutral run is still developing; its steady-window numbers (residence time, profiles) are not steady-state values.
- The residence time N / q uses the window mean of N; in the neutral case N is still rising.
- Rank-boundary jump above: needs a check in the particle code.
- Possible later C++ addition: y-integrated xz density. Sensor/footprint analysis is deferred.

## How to see the change

```sh
git log --oneline 4286f57..HEAD
git diff --stat 4286f57 HEAD
git show e7260ed
git show a50be0f
python -m pytest tests/test_particle_density.py
python scripts/analyze_particle_density.py     # needs lbm_results in local_paths.yaml
```
