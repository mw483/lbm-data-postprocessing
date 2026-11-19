# LBM output to VTK converters for vis_e2e (2026-11-19)

**Commits**: `3404736`, `8226c87` (range `a29da91..8226c87`, branch `feature/lbm-to-vtk`)

**Goal**: Mikael is interning at Prometech. Their browser-based viewer vis_e2e (on the mdx cloud) opens only VTK files (`.vtu`, `.vti`, `.vtp`, `.vtm`, `.pvd`, `.vtkhdf`). LBM-city writes CSV planes, particle `.bin` files and map `.dat` files, so a converter was needed. Prometech asked Mikael to write it himself. He asked for a package with subcommands under `tools/`. His main interest is seeing how his Lagrangian particles look in vis_e2e, so `particles` came first. He has no runs yet with LBM-city's new binary slice format, so `slices` reads the legacy CSV planes.

**Result**: `tests/test_lbm_to_vtk.py` (8 tests on small synthetic files) passes. Full suite: 151 passed, 3 failed, 3 skipped. The 3 failures are old ones in `test_road_network` and `test_urban_morphology` (optional GIS modules not installed) and are unrelated. **Not yet tested on real run data**, and not yet opened in vis_e2e.

## Commit 3404736: add the `lbm_to_vtk` package

Run from the repo root with `python -m tools.lbm_to_vtk <subcommand>`.

| File | Change | Why |
|---|---|---|
| [tools/lbm_to_vtk/\_\_init\_\_.py](../tools/lbm_to_vtk/__init__.py) | New, one line. | Makes `tools/lbm_to_vtk` a package. |
| [tools/lbm_to_vtk/\_\_main\_\_.py](../tools/lbm_to_vtk/__main__.py) | New. `argparse` with three subcommands. `particles`: `bin_dir out_dir --c-ref` (required) `[--steps] [--dt-output] [--flg-particle 1] [--every N] [--sources ...]`. `slices`: `run_dir out_dir [--families] [--variables] [--steps]`, default families `xy_ xz_ yz_ xz_yav_`. `map`: `map_dir out_dir [--dx 2] [--crop I0 I1 J0 J1] [--stride N]`. | One entry point, one subcommand per data type, as Mikael asked. |
| [tools/lbm_to_vtk/particles.py](../tools/lbm_to_vtk/particles.py) | New. Reads `index*-<n>.bin` with `data_loaders.particle_bin`; writes `particles_<n>.vtp` (6-digit step) per output number and `particles.pvd`. Point fields: `particle_id`, `source_id`, `release` (int32; ID = source x 10000 + release), `velocity` (m/s = `uvw` x `c_ref`), `velocity_sgs` and `velocity_resolved` (only when `uvw_sgs` files exist; resolved only for `flg_particle = 1`), `speed` = abs(velocity). Positions are the solver's x, y, z in metres. `--every N` keeps every N-th particle in file order; `--sources` keeps chosen source IDs. `.pvd` time is `n * dt_output` seconds, or the output number `n` when `--dt-output` is not given. | Particles are Mikael's main interest. Velocity in m/s needs `c_ref` (`velocity_lbm / cfl`, e.g. 2.0 / 0.02 = 100); same unit rule as the earlier particle velocity fix in [2026-10-01_cleanup-structure.md](2026-10-01_cleanup-structure.md). SGS and resolved parts let him colour by either. `--every` and `--sources` keep files small for the shared A100 (40 GB). |
| [tools/lbm_to_vtk/slices.py](../tools/lbm_to_vtk/slices.py) | New. Reads legacy CSV planes with `data_loaders.lbm_output` (`read_header_txt`, `scan_run`, `load_plane`); writes one `.vti` per plane and step in `<tag>/<tag>_<step:08d>.vti` and one `<tag>.pvd` per plane. Planes sit at their real position in metres, with spacing `dx` from `header.txt`. Placement: `xy_` at the label height z, `xz_` at label y, `yz_` at label x (one-based cell to cell centre); `xz_yav_` at y = 0. `xy_ag_` is placed flat at its above-ground height, exact on flat terrain only, and is not converted unless asked for with `--families`. Variable names lose their prefix (`xy_um` becomes `um`). When `um`, `vm`, `wm` all exist, a 3-component `velocity_mean` is added. Values are the raw window means as written (`uu` = mean of u u, not a variance). `xz_ins_` / `yz_ins_` are not read. | No binary slice output exists yet for his runs, so CSV is the only source. Real positions make xy, xz and yz planes line up in 3D. `velocity_mean` lets vis_e2e's Glyph and Streamline filters use the mean wind. Raw moments are kept as written; central moments are in `physics_core/moments.py`. |
| [tools/lbm_to_vtk/maps.py](../tools/lbm_to_vtk/maps.py) | New. `load_map_set` then `plotting_core.map_3d` (`crop_and_coarsen`, `auto_stride`, `map_set_meshes`); writes `ground.vtp`, `buildings.vtp`, `trees.vtp` (empty layers skipped). Coordinates are global metres from the map origin (cell (0, 0) starts at x = y = 0), also after `--crop`. Point fields `height_m` (buildings, trees) and `ground_m` (ground). `--stride` coarsens N x N; default is chosen by `auto_stride`. | Gives context for the particles and planes. Reusing `map_3d` means the same visible-face-only meshes as `scripts/view_map_3d.py` (see [2026-10-16_map-3d-viewer.md](2026-10-16_map-3d-viewer.md)), so memory follows the map area and Jakarta-size maps stay usable. |
| [tools/lbm_to_vtk/writer.py](../tools/lbm_to_vtk/writer.py) | New. `save(mesh, path)` writes binary VTK XML (extension picks `.vti` or `.vtp`); `write_pvd(entries, path)` writes a ParaView collection sorted by time, with file paths relative to the `.pvd`. | One module writes every file. Relative paths mean the whole output folder can be copied to mdx. |
| [tests/test_lbm_to_vtk.py](../tests/test_lbm_to_vtk.py) | New, 8 tests on small synthetic files: particle units, fields and filters; plane placement and axis order; map bounds in metres; `.pvd` relative paths. | Checks the parts where a silent mistake would put data in the wrong place or unit. |

Design: readers are the existing `data_loaders` modules (`particle_bin`, `lbm_output`, `map_io`). Only `writer.py` writes files. When LBM-city's new binary slice format is used, only one new reader module is needed.

## Commit 8226c87: documentation

| File | Change | Why |
|---|---|---|
| [tools/lbm_to_vtk/README.md](../tools/lbm_to_vtk/README.md) | New. Usage of the three subcommands, what is in each file (fields and units), steps for vis_e2e on mdx (copy with `scp -r`, `module load vis_e2e`, `vis_e2e ui --backend=visrtx --port=<port> --files vtk_out/particles.pvd`), and a "Not checked yet" list. | Mikael and colleagues need the commands and the open points in one place. |
| [README.md](../README.md) | `tools/` row now names `inspect_bin.py` and `lbm_to_vtk/`. | Index of the repo. |

## What is not checked yet

- No real run data has been converted. Only synthetic files.
- Alignment in space is open: slice positions use the CSV first line `xg_min`/`yg_min`/`zg_min`, the map starts at 0, particles use the solver's positions. These origins may not agree on a real run.
- How vis_e2e handles `.pvd` time series and large point clouds is untested.
- Slice output in the new LBM-city binary format (`src/sliceOutput.h` on main) is not handled yet.

## What was deliberately left alone

- No reader for the new binary slice format (no runs with it yet).
- `xy_ag_` on terrain: only flat placement. Instantaneous `xz_ins_` / `yz_ins_` planes not read.
- No existing loader or plotting code was changed; the package only imports from them.

## How to check

```sh
python -m pytest tests/test_lbm_to_vtk.py
python -m tools.lbm_to_vtk particles <bin_dir> vtk_out/particles --c-ref 100 --dt-output 0.8 --every 10
python -m tools.lbm_to_vtk slices <run_output_dir> vtk_out/slices --variables um vm wm
python -m tools.lbm_to_vtk map <map_dir> vtk_out/map
```
