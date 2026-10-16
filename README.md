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

### Presentation demo (2026-10-07)

```sh
pip install -e .[video]                                  # once, for the MP4 backup
python scripts/demo_presentation.py --record             # once before the talk: builds the cache, writes MP4/PNG backups
python scripts/demo_presentation.py                      # live: isopleths -> velocity lines -> TTD
```

Flat and cube array side by side, one shared camera. Close a window to go to the next stage. Settings are at the top of the script.

### Solver statistics, scalar2 and later (2026-10-16)

Set `lbm_results` in `local_paths.yaml` (lab PC: `D:/lbm_results`). Runs sit at `<lbm_results>/<case>/<date>_<tag>/output` (wind CSV) and `.../particle_postprocess` (post-processed particles). Put the runs, written `<case>/<date>_<tag>` (e.g. `flat_512x128x1024/20261011_scalar2`), in `CASES` at the top of each script, then:

```sh
python scripts/inventory_lbm_output.py      # which files, steps and ranks exist; stitch check of every plane
python scripts/plot_profiles_by_window.py   # mean, sigma_w, TKE, S_w, theta, w'theta' per 200 s window; cases compared
```

`data_loaders/lbm_output.py` reads every plane layout (xy, xy_ag, xz, yz, xz_yav), stitches the ranks and reads `prof*.csv` and `header.txt`. The files hold raw moments (`uu` = <u u>); `physics_core/moments.py` turns them into variances, covariances, TKE and skewness.

```sh
python scripts/analyze_particle_statistics.py
pytest                      # run the checks
```
