# lbm-data-postprocessing
Data postprocessing for Lattice Boltzmann Method (LBM) simulation results. Part of Master's Thesis work in Kanda Laboratory.

## Setup (once per machine)

```sh
cd lbm-data-postprocessing
python -m venv .venv            # or use an existing conda env
.venv\Scripts\activate          # Windows (source .venv/bin/activate on Linux)
pip install -e .[dev]
```

Then tell the scripts where the data is on this machine:

```sh
copy local_paths.example.yaml local_paths.yaml   # cp on Linux/macOS
```

Edit `local_paths.yaml` (git-ignored, one per machine): the particle post-processing outputs (lab PC: `D:/lbm_results/...`; laptop: the rclone mount of the TSUBAME folder), the map folder, a local cache folder and the figures folder.

`pip install -e .` makes `data_loaders`, `physics_core` and `plotting_core` importable from anywhere. The `-e` (editable) flag means edits to the library take effect immediately; there is no reinstall step.

## Layout

| Folder | Content |
|---|---|
| `data_loaders/` | Readers for LBM wind CSVs, C++ particle-postprocessing outputs, raw particle `.bin` files and maps |
| `physics_core/` | Calculations: turbulence statistics, footprints (Kljun FFP, Schmid), particle transit times |
| `plotting_core/` | Plotting functions (matplotlib, PyVista) |
| `scripts/` | One script per figure or analysis. Edit the settings at the top of `main()` and run it. |
| `tools/` | Small helpers, e.g. inspecting a particle `.bin` file |
| `tests/` | `pytest` checks for the loaders and calculations |
| `archive/` | Retired scripts and functions, kept for reference and no longer maintained |

## Running

### Run sets: which runs a comparison script reads (2026-10-26)

The comparison scripts below (`inventory_lbm_output`, `plot_profiles_by_window`, `plot_velocity_stress_profiles`, `plot_xz_yav_heatmaps`, `analyze_particle_density`, `plot_particle_bin_stats`, `animate_particles`) read the runs of a named set in `run_sets.yaml` (repo root, tracked). A set holds any number of runs as `label: <case>/<date>_<tag>`; the label is the name in legends and in the `case` column of the CSV files.

```sh
python -m scripts.plot_particle_bin_stats                       # set named "default" in run_sets.yaml
python -m scripts.plot_particle_bin_stats --set flat512_sgsfix  # another set
```

Output goes to `<figures>/<set>/<topic>/` (e.g. `figures/flat512_sgsfix/particle_bins/sgs_along_x.png`), so different sets never overwrite each other. Each output folder gets a `runs.yaml` with the set, its runs, the data folders read, the script, the date and the repo commit. To compare other runs, add a new set to `run_sets.yaml` rather than editing a set that already has figures. Reducer outputs are looked up in `<lbm_reduced>/<run>/particle_reduced` first (optional key in `local_paths.yaml`), then in `<lbm_results>/<run>/particle_reduced`.

### Presentation demo (2026-10-07)

```sh
pip install -e .[video]                                  # once, for the MP4 backup
python scripts/demo_presentation.py --record             # once before the talk: builds the cache, writes MP4/PNG backups
python scripts/demo_presentation.py                      # live: isopleths -> velocity lines -> TTD
```

Flat and cube array side by side, one shared camera. Close a window to go to the next stage. Settings are at the top of the script.

### 3D map viewer (2026-10-16)

```sh
python scripts/view_map_3d.py --case flat_512x128x1024                          # an LBM-city case, auto coarsened
python scripts/view_map_3d.py --case flat_512x128x1024 --sources                 # + the case's particle_position.txt
python scripts/view_map_3d.py <map folder> --crop 4300 4900 1000 1500 --stride 1 # any map folder; cells i0 i1 j0 j1, full 2 m
python scripts/view_map_3d.py <map folder> --sources <particle_position.txt>     # overlay a source file
```

`--case` reads `<lbm_cases>/<case>/map/` (set `lbm_cases` in `local_paths.yaml` to an LBM-city `cases` folder, branch `mikael/cases`). A map folder is any folder with `topography.dat`, `building.dat` and `vegetation.dat`, for maps that are not a case yet. Press `p` over a point to print x, y, cell i, j and the heights there; `s` saves a screenshot to `<figures>/map_3d/`. Coarsened views widen buildings and trees, so pick sources on a `--stride 1` crop. `--save view.png` writes a PNG without a window.

### Solver statistics, scalar2 and later (2026-10-16)

Set `lbm_results` in `local_paths.yaml` (lab PC: `D:/lbm_results`). Runs sit at `<lbm_results>/<case>/<date>_<tag>/output` (wind CSV) and `.../particle_postprocess` (post-processed particles). Put the runs, written `<case>/<date>_<tag>` (e.g. `flat_512x128x1024/20261011_scalar2`), in `CASES` at the top of each script, then:

```sh
python scripts/inventory_lbm_output.py      # which files, steps and ranks exist; stitch check of every plane
python scripts/plot_profiles_by_window.py   # mean, sigma_w, TKE, S_w, theta, w'theta' per 200 s window; cases compared
python scripts/plot_velocity_stress_profiles.py   # U, V, W and <u'u'>, <v'v'>, <w'w'>, <u'w'> per window, as is and / Ub (Chang et al. 2009 style)
python scripts/plot_xz_yav_heatmaps.py      # y-averaged x-z heatmaps of U, W, sigma_w, TKE per window; PNG frames, GIF, MP4
```

The heatmaps use one colour scale per variable, shared by both cases and every window, and plot 0 to 1000 m. Each variable gets `combined_step*.png` (cases side by side) and `<case>_step*.png` (one case each), plus `combined.gif` / `<case>.gif` at 1 frame per second. MP4 files need the video extra (`pip install -e .[video]`) and are skipped without it.

`data_loaders/lbm_output.py` reads every plane layout (xy, xy_ag, xz, yz, xz_yav), stitches the ranks and reads `prof*.csv` and `header.txt`. The files hold raw moments (`uu` = <u u>); `physics_core/moments.py` turns them into variances, covariances, TKE and skewness.

### Particle concentrations from the C++ basic pass (2026-10-19)

Run `run_basic.sh` (LBM-city `cases/<case>/`) once per window; each window lands in `particle_postprocess/<start>-<end>_basic/`. The script needs the whole release window, the steady window and its blocks (settings `FULL_WINDOW`, `STEADY_WINDOW`, `BLOCKS`), then:

```sh
python scripts/analyze_particle_density.py   # N(t), C(z), y-mean C(x) with block error bands, xz slab; CSV tables
```

The C++ density files are counts summed over all snapshots of a window. `data_loaders/particle_postprocess.py` reads them (plus `total_num.csv`, `profile.csv` and the settings and snapshot count in `log_analysis.txt`); `physics_core/particle_density.py` turns them into concentrations C = count / (snapshots x cell volume) [particles/m^3] and computes height statistics, spanwise and block spread, and residence time N / release rate. Output goes to `<figures>/<set>/particle_density/` (see Run sets).

### Raw particle binaries: Lagrangian statistics and animations (2026-10-20)

Step 1, on TSUBAME next to the binaries (Python 3.9 + numpy; `python3 -m pip install --user numpy` if missing):

```sh
python3 scripts/reduce_particle_bins.py --bin-dir <particle folder> \
    --sources <LBM-city>/cases/flat_512x128x1024/particle_position/particle_position.txt \
    --out <somewhere>/particle_reduced
```

It streams outputs 1200-1800 once and writes `reduced.npz` (age, height and x statistics) and `snapshots/snap_<n>.npz` (every 5th output, a fixed 1/8 of the particles with age). Copy the `particle_reduced` folder to `<lbm_results>/<case>/<date>_<tag>/particle_reduced` on the PC (rclone), or set `lbm_reduced` in `local_paths.yaml` to a root laid out as `<lbm_reduced>/<case>/<date>_<tag>/particle_reduced` (e.g. the TSUBAME mount `Z:/lbm_reduced`), then (add `--set NAME` for another run set):

```sh
python scripts/plot_particle_bin_stats.py           # height and sigma_z vs age, PDF(z | age), CBL scaling, particle vs Eulerian sigma_w, SGS along x
python scripts/animate_particles.py --mode xz       # side view of all particles, cases stacked; GIF + MP4
python scripts/animate_particles.py --mode xy --slab 0 10   # top view of the lowest 10 m
python scripts/animate_particles.py --mode 3d       # PyVista point cloud (off-screen)
```

Ages come from the particle ID (release number). Age statistics use only sources with x <= 104 m, so particles do not leave through the outflow (x = 1024 m) within the plotted ages. `sgs_along_x.png` shows the SGS velocity of near-ground particles along x, with the GPU rank boundaries marked.

```sh
python scripts/analyze_particle_statistics.py
pytest                      # run the checks
```
