# 3D viewer for LBM-city map sets (2026-10-16)

**Commits:** `08fdcab`, `6da5fe3`, `facb558`, `bb53352` (range `8542d4a..HEAD`, branch `analysis/scalar2-outputs`; the last two are described in the section "Follow-up: read maps from LBM-city cases" below)
**Goal:** Mikael wants to see LBM-city map sets (`topography.dat`, `building.dat`, `vegetation.dat`) in 3D, starting with the Jakarta map (8000 x 2560 cells at 2 m). He uses it to decide where to put particle sources in `particle_position.txt`. The Jakarta run is not approved yet; this is only for looking at the map.
**Result:** `pytest`: 47 passed, 1 failed. The failure (`tests/test_particle_io.py::test_streamed_trajectories_read_11_column_file`) also fails without these commits. It comes from polars 2.0.0 in the cloud test container, not from this change (same failure as in [2026-10-16_scalar2-output-reader.md](2026-10-16_scalar2-output-reader.md)). The script ran off-screen on the real Jakarta map set in the cloud container: whole map at stride 4 in about 38 s end to end, a 600 x 500 cell crop at stride 1 in a few seconds. It reported a building fraction of 28.8% and a tallest building of 383 m above ground, matching the earlier jakarta_sim review. The existing `add_voxel_buildings` path was checked with a synthetic cube map (bounds correct, clip works). **Not yet run interactively on Mikael's PC. The existing particle and density scenes were not re-run on real data.**

---

## Context

Options considered for the viewer: PyVista (already a dependency), ParaView, vedo / Open3D, Plotly / deck.gl, matplotlib 3D, and a 2D hillshade. PyVista was kept: the particle and density scenes already use it, it renders on the GPU, and it has point picking and PNG export.

The problem was not the library. It was the old `create_voxel_buildings`:

- It filled a dense boolean volume `nx x ny x max_height` (1 m steps in z) with a Python double loop, then thresholded it.
- For Jakarta that is about 7.9 billion voxels (about 7.9 GB) and a 20-million-step loop, so it could not run.
- It read one file only and treated any height > 0 as a building. This is wrong for map sets, where `building.dat` and `vegetation.dat` hold ABSOLUTE heights (ground + object).

## Commit `08fdcab`: map set reader and face-only building meshes

| File | Change | Why |
|---|---|---|
| [data_loaders/map_io.py](../data_loaders/map_io.py) | New `read_map_dat`: pandas C reader; falls back to fixed-width parsing when Fortran f5.1 values touch (for example `" 12.0386.0"`). Returns `(heights, nx, ny)`, shape `(ny, nx)`, indexed `[j, i]`. | `np.loadtxt` failed on files with touching values. The C reader is also faster on large maps. |
| [data_loaders/map_io.py](../data_loaders/map_io.py) | `load_lbm_map` now calls `read_map_dat`. Old return: float64. New return: float32. Shape and orientation are the same. | One reader for everything. |
| [data_loaders/map_io.py](../data_loaders/map_io.py) | New `load_map_set(folder)`: reads the three files, checks that the sizes match, raises if a file is missing. New `load_source_xyz(filepath)`: x, y, z columns of `particle_position.txt`. | Read a whole map set and the source list. |
| [data_loaders/map_io.py](../data_loaders/map_io.py) | `create_voxel_buildings` keeps its signature `(elevation_matrix, nx, ny, resolution=2.0)` but now calls `plotting_core.map_3d.blocky_columns`. Old return: thresholded `UnstructuredGrid`. New return: `PolyData`. Heights are no longer truncated to whole metres. | Same call for the existing scenes, without the dense volume. |
| [data_loaders/map_io.py](../data_loaders/map_io.py) | No `pyvista` import at module level (it is imported inside `create_voxel_buildings`). | Reading maps no longer needs PyVista. |
| [plotting_core/map_3d.py](../plotting_core/map_3d.py) (new) | `auto_stride` (target about 1.5 M columns, `TARGET_COLUMNS`), `crop_and_coarsen` (mean for ground, max for buildings and trees), `classify_cells`, `ground_surface` (smooth surface through cell centres), `blocky_columns` (top quad per column, wall where taller than the neighbour), `map_set_meshes`, `sources_in_box`. | Memory grows with map area, not area x height. |
| [tests/test_map_3d.py](../tests/test_map_3d.py) (new) | 9 tests. | Cover the new module. |

Notes on the design:

- Max for buildings and trees keeps tall buildings visible when coarsened. The cost is that footprints grow.
- Coordinates stay in global metres after cropping, so a picked point can go straight into `particle_position.txt`.

Behaviour change and how to revert: `create_voxel_buildings` now returns `PolyData` (visible faces only) instead of a thresholded grid, and `load_lbm_map` returns float32. Code that relied on the cell data `Building_Mask` or on float64 values would notice. The brief says the existing `add_voxel_buildings` path was checked with a synthetic cube map. To go back, revert `08fdcab`.

## Commit `6da5fe3`: 3D map viewer script

| File | Change | Why |
|---|---|---|
| [scripts/view_map_3d.py](../scripts/view_map_3d.py) (new) | CLI. Argument: a map folder path, or a subfolder of `maps` in `local_paths.yaml`. Options: `--crop i0 i1 j0 j1`, `--stride`, `--zscale`, `--sources`, `--max-sources`, `--no-trees`, `--tree-opacity`, `--save`. Key `p` picks a point and prints x, y, cell i, j and the heights. Key `s` saves a screenshot to `<figures>/map_3d/`. | Look at a map and choose source positions. |
| [README.md](../README.md) | New section "3D map viewer (2026-10-16)". | How to run it. |

## What was deliberately left alone

- ParaView `.vtp` export and a 2D hillshade view: optional in the plan, not done.
- `data_loaders/local_paths.py`: unchanged in `08fdcab` and `6da5fe3`, because another thread was editing this branch. Changed later in `facb558` (see the follow-up section).
- `plotting_core/pyvista_helpers.py`: unchanged.

## Not checked and open items

- Not run interactively on Mikael's PC (picking, screenshot key, window behaviour).
- The existing particle and density scenes were not re-run on real data.
- Coarsened views widen buildings and trees, so pick sources on a `--stride 1` crop (also stated in the README).

## How to check

```sh
git log --oneline 8542d4a..HEAD
git show --stat 08fdcab 6da5fe3
pytest tests/test_map_3d.py
python scripts/view_map_3d.py <folder> --crop 4300 4900 1000 1500 --stride 1
```

---

## Follow-up: read maps from LBM-city cases (`facb558`, `bb53352`, range `25ac921..HEAD`)

### Context

Mikael pointed out that the `maps` key in `local_paths.yaml` points at repo 1's map folder, which holds one `building.dat` per map. The newer LBM-city runs keep each case's map set at `cases/<case>/map` (topography, vegetation, building `.dat`), for example `/gs/bs/tga-lbmcity/mikael/LBM-city/cases/flat_512x128x1024/map` on TSUBAME. The generator setup command copies that folder into the solver's map folder. Mikael approved the plan before the change.

Checked on LBM-city branch `mikael/cases`: every case (`flat_128x128x1024`, `flat_512x128x1024`, `_check`, `_neutral`) has `map/` with the three files and `particle_position/particle_position.txt`.

### Decisions

- The new key `lbm_cases` is OPTIONAL, so existing `local_paths.yaml` files keep working.
- The old `maps` key is untouched, because repo 1 scripts still use it.
- The viewer no longer looks up a name as a subfolder of `maps`, because that folder holds repo 1's single-file maps, not map sets.
- A plain map folder still works (positional argument), for maps that are not a case yet, for example `jakarta_sim`.

### Commit `facb558`: optional `lbm_cases` path

| File | Change | Why |
|---|---|---|
| [data_loaders/local_paths.py](../data_loaders/local_paths.py) | `OPTIONAL_KEYS` gains `lbm_cases`. New `case_map_dir(paths, case)` returns `<lbm_cases>/<case>/map`. New `case_sources_file(paths, case)` returns `<lbm_cases>/<case>/particle_position/particle_position.txt`. Private `_case_folder` raises `KeyError` naming `lbm_cases` when the key is unset. | One place that knows the LBM-city case layout. |
| [local_paths.example.yaml](../local_paths.example.yaml) | Commented `lbm_cases` entry (lab PC: `C:/Users/Mikael Wijaya/Documents/GitHub/LBM-city/cases`; TSUBAME checkout through rclone: `Y:/cases`). Note on the `maps` entry that it is repo 1's folder with one `building.dat` per map. | Show how to set it; avoid confusing the two keys. |
| [tests/test_local_paths.py](../tests/test_local_paths.py) | 2 new tests: paths follow the LBM-city layout; `KeyError` matching `lbm_cases` when unset. | Cover the new helpers. |

### Commit `bb53352`: `--case` in the viewer

| File | Change | Why |
|---|---|---|
| [scripts/view_map_3d.py](../scripts/view_map_3d.py) | `resolve_map_set` replaced by `resolve_inputs(folder, case, sources)`. New `--case NAME` loads `<lbm_cases>/NAME/map`. `--sources` now takes an optional value: with no value it overlays the case's own `particle_position.txt`; without `--case` this exits with an error. The positional argument is now optional (`folder`); exactly one of folder or `--case` is required (`ap.error` otherwise). A missing map folder raises `FileNotFoundError`. The screenshot name and the "Map ..." line use the case name (or the folder name for a plain folder). Prints "Reading sources from ..." before loading sources. | Open a case by name and see its sources without typing paths. |
| [README.md](../README.md) | "3D map viewer" section: `--case` examples, the `lbm_cases` setting, and what a map folder is. | How to run it. |

The "Argument: a map folder path, or a subfolder of `maps`" line in the `6da5fe3` table above describes the earlier behaviour; the subfolder lookup was removed in `bb53352`.

### How it was checked

- `pytest`: 49 passed, 1 failed. The failure is the same pre-existing polars 2.0 failure, `test_streamed_trajectories_read_11_column_file`.
- Ran `--case flat_512x128x1024 --sources` off-screen against a clone of LBM-city `mikael/cases`. It read the three map files (all zero), found 2,816 sources (x 8-704 m, y 4-252 m, z 0.1 m) and showed all of them.
- Ran a plain Jakarta folder crop.
- Checked two error paths: `--sources` without `--case` exits with "[ERROR] --sources without a file needs --case", and giving both a folder and `--case` exits with "give either a map folder or --case, not both". The missing-folder path was not run.

### Not checked and open items

- Not run on Mikael's PC (real `lbm_cases` path, window, picking).
- `flat_128x128x1024`, `_check` and `_neutral` were not opened in the viewer; only their file layout was checked.
- Whether `Y:/cases` is the correct rclone path on the lab PC is not verified here; it is taken from the brief.

### How to check

```sh
git log --oneline 25ac921..HEAD
git diff 25ac921..HEAD
pytest tests/test_local_paths.py
python scripts/view_map_3d.py --case flat_512x128x1024 --sources
```
