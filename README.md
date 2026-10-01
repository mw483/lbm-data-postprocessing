# lbm-data-postprocessing
Data postprocessing for Lattice Boltzmann Method (LBM) simulation results. Part of Master's Thesis work in Kanda Laboratory.

## Setup (once per machine)

```sh
cd lbm-data-postprocessing
python -m venv .venv            # or use an existing conda env
.venv\Scripts\activate          # Windows (source .venv/bin/activate on Linux)
pip install -e .[dev]
```

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

```sh
python scripts/analyze_particle_statistics.py
pytest                      # run the checks
```
