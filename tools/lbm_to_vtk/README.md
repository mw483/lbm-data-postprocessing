# lbm_to_vtk: LBM-city output → VTK (for vis_e2e and ParaView)

Converts LBM-city output into VTK XML files that vis_e2e on mdx can open (`.vtp`, `.vti`, `.pvd` are on its list of readable formats). Run from the repository root, with this repo installed (`pip install -e .`; needs numpy, pandas, pyvista).

```
python -m tools.lbm_to_vtk particles <bin_dir> <out_dir> --c-ref <c_ref> [--dt-output 0.8] [--every N] [--sources ID ...] [--steps n ...]
python -m tools.lbm_to_vtk slices    <output_dir> <out_dir> [--families xy_ xz_ yz_ xz_yav_ xy_ag_] [--variables um vm wm] [--steps s ...]
python -m tools.lbm_to_vtk map       <map_dir> <out_dir> [--dx 2] [--crop I0 I1 J0 J1] [--stride N]
```

| Subcommand | Reads | Writes |
|---|---|---|
| `particles` | `result_particle_scatter_binary/` (`index`, `position`, `uvw`, `uvw_sgs` `<r>-<n>.bin`; reader `data_loaders/particle_bin.py`) | `particles_<n>.vtp` per output number + `particles.pvd` |
| `slices` | legacy CSV planes in the run's `Output/` folder + `header.txt` (reader `data_loaders/lbm_output.py`) | `<family><axis><cell>/<...>_<step>.vti` per plane and step + one `.pvd` per plane |
| `map` | `topography.dat`, `building.dat`, `vegetation.dat` (reader `data_loaders/map_io.py`) | `ground.vtp`, `buildings.vtp`, `trees.vtp` |

Open the `.pvd` file in vis_e2e or ParaView to get the whole time series; open a single `.vtp`/`.vti` for one step.

## What is in the files

**Particles** (`particles.py`). Points at the solver's x, y, z [m], with:
- `particle_id` (= source × 10000 + release), `source_id`, `release`
- `velocity` [m/s]: `uvw × c_ref`. With `flg_particle = 1` this is resolved + SGS, i.e. what moves the particle.
- `velocity_sgs` [m/s] and `velocity_resolved` [m/s], when `uvw_sgs` files exist.
- `speed` [m/s] = |velocity|.

`--c-ref` is the lattice → m/s factor (`c_ref` in the run's `header.txt`, = velocity_lbm / cfl, e.g. 2.0 / 0.02 = 100). `--dt-output` sets the time in the `.pvd` to n × dt_output seconds; without it, the time is the output number n. `--every N` keeps every N-th particle (in file order), and `--sources` keeps chosen source IDs; both keep files small for the shared A100 (40 GB).

**Slices** (`slices.py`). One flat image per plane, placed at its real position, so xy, xz and yz planes line up in 3D. Fields are the variable names without the prefix (`xy_um` → `um`), the solver's window means of **raw moments** (`uu` = ⟨u u⟩, not a variance; see `physics_core/moments.py` for central moments). When `um`, `vm`, `wm` are all present, a vector `velocity_mean` is added for Glyph / Streamline filters.
- `xy_` at the label height z; `xz_` at the label y; `yz_` at the label x (one-based cell → cell centre).
- `xz_yav_` (averaged over y) is placed at y = 0.
- `xy_ag_` (above ground) is placed flat at its AGL height: exact only on flat terrain. Not converted unless asked for with `--families`.
- Instantaneous `xz_ins_` / `yz_ins_` files are not read (same limit as `lbm_output.py`).

**Map** (`maps.py`). Visible faces only (same meshes as `scripts/view_map_3d.py`), global metres from the map origin (cell (0, 0) starts at x = y = 0), also after `--crop`. `--stride` coarsens N × N cells (ground: mean, buildings and trees: max); by default a stride is chosen that keeps about 1.5 M columns, which matters for Jakarta-size maps.

## Using it with vis_e2e on mdx

1. Convert on the machine that has the data (lab PC, or TSUBAME for particle `.bin` files).
2. Copy the output folder to mdx, e.g. `scp -r vtk_out mdx:vis_work/` (or a folder under `/large` once agreed with the mentor).
3. On mdx: `cd ~/vis_work`, `module load vis_e2e`, then `vis_e2e ui --backend=visrtx --port=<your port> --files vtk_out/particles.pvd`. `--files` takes a path relative to the folder you start from. Or start without `--files` and use Data tab → BROWSE FILES.

## Not checked yet

- Only tested on small synthetic files (`tests/test_lbm_to_vtk.py`), not yet on a real run.
- Whether particles, slices and the map line up in space depends on the domain origin: slice positions use the CSV first line's `xg_min`/`yg_min`/`zg_min`, the map starts at 0, particles use the solver's positions. Check on a real run.
- How vis_e2e handles `.pvd` time series and large point clouds is untested.
- The new LBM-city binary slices (`src/sliceOutput.h` on main) are not handled yet; a reader can be added as one more module.
