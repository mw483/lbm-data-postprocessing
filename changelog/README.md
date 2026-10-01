# Changelog

Notes on what changed in this repo and why. Each file covers one piece of work. Written so you can read it once and understand every change without opening the diffs.

## Index

| Date | File | What it covers | Commits |
|---|---|---|---|
| 2026-10-01 | [2026-10-01_cleanup-structure.md](2026-10-01_cleanup-structure.md) | Branch `cleanup/structure`: hygiene, installable library, archive, particle velocity-unit fix, shared wind and PyVista code, pytest checks | `5f32002` `1b48476` `575d2e8` `c6a3cfc` `20493e6` `2b7e95b` `37411b4` `87262d1` |

## Glossary

| Term | Meaning |
|---|---|
| LBM | Lattice Boltzmann Method, the solver in the LBM-city repo that produces the wind and particle data |
| Lattice units | The solver's internal units. A velocity of 0.02 is one CFL step. Multiply by `c_ref` to get m/s |
| `c_ref` | Velocity scale = `velocity / cfl` from the run argument `-velocity_lbm 2.0 0.02`, so 2.0 / 0.02 = 100 |
| SGS | Sub-grid scale. The turbulent velocity the particle model adds on top of the resolved (grid-scale) velocity |
| Resolved | Velocity interpolated from the LBM grid, without the SGS part |
| `flg_particle` | Solver switch in `Define_user.h`. 1 = Lagrangian stochastic model with SGS (writes `uvw_sgs*.bin`), 2 = resolved only |
| `.bin` files | Raw particle output of the solver: `index`, `position`, `uvw`, `uvw_sgs`, `velocity`, one file per rank group and output step |
| Particle ID | `source x 10000 + release number` |
| Virtual tower | A vertical wind profile read out of the y-averaged XZ plane at one x position |
| Footprint | Map of where particles that reach a sensor came from (source area) |
| Kljun / Schmid | Two analytical footprint models that the LBM footprints are compared with |
| Registry | Planned YAML file per simulation case (paths, dx, sensors, u*, z0). Designed, not implemented |
| Editable install | `pip install -e .`: Python imports the repo folders directly, so edits take effect without reinstalling |

## Inspecting the changes

```sh
cd lbm-data-postprocessing
git checkout cleanup/structure

git log --oneline main..cleanup/structure        # the 8 commits
git diff --stat main cleanup/structure           # files changed, whole branch
git diff main cleanup/structure -- data_loaders  # one folder only
git show <hash>                                  # one commit, message and diff
git show --stat <hash>                           # one commit, files only
git log -p main..cleanup/structure -- data_loaders/particle_io.py   # history of one file
git diff main cleanup/structure --find-renames --stat   # renames show up as moves
```
