# Tile explorer: choosing a cut-out of the Jakarta map (2026-11-11)

**Commits**: `5dd6a7a`, `4553092` (range `53b32ef..4553092`, branch `analysis/scalar2-outputs`)

**Goal**: Mikael (kaka) wants to choose a small piece (a "cut-out") of the Jakarta map for a first neutral LBM simulation, and to justify the choice to the professor. The professor's rule: write a simulation plan (size, boundaries, heat, map) and show it before running. The plans are in `planning/jakarta_cutout_neutral_plan_2026-11-09.md` and `planning/tile_explorer_plan_2026-11-09.md`. kaka approved the explorer plan on 2026-11-11. He chose a 2D matplotlib window over a 3D one, and free boxes, with snapping to tiles as an option. This builds on the tile statistics of [2026-10-28_jakarta-map-analysis.md](2026-10-28_jakarta-map-analysis.md).

**Result**: `pytest tests/`: 109 passed, 2 failed. Both failures were there before these commits and are unrelated: `test_streamed_trajectories` (polars 2.0) and `test_image_transform` (needs the optional `affine` package).
- `explore_tiles.py` was run on a synthetic 2000 x 640 map. The `--save` output was checked by eye.
- The window's mouse and key handlers were driven with synthetic events under the Agg backend. Drag, add (`a`), tile click, snap (`t`), `v`, `w` and `x` all worked.
- **Not run on the real Jakarta map** (it lives on the lab PC). The interactive window and the 3D view were **not opened on a real display**.

## Commit 5dd6a7a: box_summary for candidate cut-out boxes

| File | Change | Why |
|---|---|---|
| [physics_core/urban_morphology.py](../physics_core/urban_morphology.py) | New `box_summary(maps, box, dx=2.0, nz=None, run_s=3600.0, source_step=8, default_height=6.0, seam_search=16, min_cells=(10, 16))`. Takes `box = (i0, i1, j0, j1)`, end exclusive, and computes a flat dict of numbers from the full 2 m map (not from tile averages). Wind is along +i. Raises `ValueError` if the box is outside the map. | The professor needs numbers for the exact box, not for the 500 m tiles around it. |
| same | `box_summary` basic numbers: size, lambda_p, H_av, lambda_f (x), building height mean / median / max, tree cover, ground min / max / range. | Describe the piece. |
| same | `box_summary` share of building cells at the default height (`default_height_share`, 6 m). | 73 % of the Jakarta map's building cells are 6 m, probably a default height. The share shows how much of a box is default height. |
| same | `box_summary` periodic seams: building cells on each of the four edges (`edge_build_cells_*`), ground step across each seam (`seam_step_*_mean_m`, `_max_m`), and `shifted_box` / `shifted_edge_build_cells`. | The domain is periodic, so the left edge meets the right edge. Buildings cut by a seam and a ground step there disturb the flow. |
| same | New `best_shift(counts, a0, a1, search)`: picks the shift d in -search..search (kept inside the map) that minimises `counts[a0+d] + counts[a1-1+d]`; ties go to the smallest abs(d). `box_summary` uses it for i and j with `seam_search=16`. | Finds the same-size box moved by at most 16 cells whose seams fall on streets. Same size is kept because the cell counts are chosen to split over the GPUs. An earlier draft moved each edge independently and so changed the size; it was dropped. |
| same | `box_summary` resolution: 4-connected building groups inside the box narrower than 10 and 16 cells, as share by count and by volume (`narrower_10_cells_share`, `narrower_16_cells_volume_share`, ...), plus `one_cell_buildings_share`. | AIJ / COST ask for at least 10 cells per building side (Tominaga et al. 2008, JWEIA 96, 1749-1761). The professor's rule is 16. |
| same | `box_summary` sources: open ground (no building, no tree) share, sources on a grid of `source_step` cells (default 8), and `sources_vs_id_limit` against the new constant `ID_SOURCE_LIMIT = 214_748`. | Particle IDs are int32 with `ID_DIGIT` 4 (ID = source x 10000 + release number), so at most (2^31 - 1) // 10000 = 214,748 sources. |
| same | `box_summary` with `nz`: domain top (`nz * dx`), `top_over_hmax`, `length_over_hmax`, `width_over_top`, `blockage_max`, `blockage_mean`, cells in millions, and `wall_hours_4gpu_est`. | The AIJ checks (see below) and the cost. |
| same | New `blockage_by_column(hb, top_m, dx)`: for each column i, the building share of the y-z cross-section = sum over j of (height cut at top) x dx / (domain width x top). | AIJ blockage is below 3 %, defined from the frontal projection of all buildings for an inflow/outflow domain. The domain here is periodic, so it has no direct meaning. The per-cross-section share is the stand-in. |
| same | New constants `BENCH_CELLS = 512*128*1024`, `BENCH_S_PER_STEP = 0.068`, `DT_2M = 0.008`. Wall time = cells / `BENCH_CELLS` x 0.068 s x steps / 3600, with steps = `run_s` / 0.008. | Linear scaling of the 512 x 128 x 1024 benchmark (0.068 s per step on one TSUBAME node, 4 GPUs, dt 0.008 s at 2 m cells; run 20261026_scalar2). **Estimate only**: GPU memory and non-linear scaling are not checked. |
| [tests/test_urban_morphology.py](../tests/test_urban_morphology.py) | 57 new lines: tests on small synthetic maps. | Check the new functions without the real map. |

### Checks used, and where they come from

| Check | Threshold | Source |
|---|---|---|
| Domain top / H_max | at least 5 | AIJ guideline (Tominaga et al. 2008), brought by kaka on 2026-11-11 |
| Blockage | below 3 % | same |
| Length / H_max downstream | at least 10 (COST uses 15 H_max) | same / COST |
| Cells per building side | at least 10 (professor: 16) | same / professor |

Thresholds checked against the paper text (Tominaga et al. 2008, sections 3.1 and 4.2; COST values as quoted there from Franke 2006).

## Commit 4553092: explore_tiles.py and the 3D viewer short form

| File | Change | Why |
|---|---|---|
| [scripts/jakarta-map-analysis/explore_tiles.py](../scripts/jakarta-map-analysis/explore_tiles.py) | New (457 lines). Matplotlib window: buildings seen from above, plus one 500 m tile statistic (keys 1-4). Drag a box, or click a tile, to see the `box_summary` numbers. Keys: `a` add candidate, `x` remove, `v` open [view_map_3d.py](../scripts/view_map_3d.py) on the box, `w` write PNG + `candidates.csv`, `t` snap to tiles. | One place to look at the map, pick a box and see the numbers the professor asked for. Free boxes with optional snapping, as kaka chose. |
| same | Options: `--georef`, `--candidates` (default `<out>/candidates.yaml`), `--nz` (default 256, i.e. 512 m top), `--run-seconds` (default 3600), `--source-step` (default 8), `--tile` (default 500 m), `--save PNG`. | `--save` draws the candidates without a window and writes `candidates.csv` beside the PNG, for the figure to show the professor. |
| same | Own rubber-band mouse handling instead of matplotlib `RectangleSelector`. | A plain click (select tile) then behaves the same on all matplotlib versions. |
| same | Candidates YAML: `name`, `box` = `[i0, i1, j0, j1]` (end exclusive), `nz`, `note`. | Saved boxes can be reloaded and reused by the 3D viewer. |
| [scripts/view_map_3d.py](../scripts/view_map_3d.py) | New `candidate_box(path, name)`, and options `--box NAME` and `--candidates FILE`. `--box` replaces `--crop` (error if both are given, or if `--candidates` is missing; error lists the names found if NAME is unknown). | Short form of `--crop` for a saved candidate. Without the new options the viewer behaves as before. |
| [scripts/jakarta-map-analysis/README.md](../scripts/jakarta-map-analysis/README.md) | New command block, table row for `explore_tiles.py`, library line mentions cut-out box numbers, two caveats (blockage definition, wall-time scaling). | Make the script findable and state its limits. |

## What was deliberately left alone

- Writing the cut-out `.dat` map files and the particle sources. That is a later step.
- No new dependencies.

## How to check

```sh
pytest tests/test_urban_morphology.py
M=<map folder>
python scripts/jakarta-map-analysis/explore_tiles.py $M --georef <out>/georef.yaml --nz 256     # window
python scripts/jakarta-map-analysis/explore_tiles.py $M --georef <out>/georef.yaml \
    --candidates <out>/candidates.yaml --save <out>/candidates.png                              # PNG + candidates.csv
python scripts/view_map_3d.py $M --box A --candidates <out>/candidates.yaml                    # one box in 3D
```

Still to do on the lab PC: run on the real Jakarta map, open the window and the 3D view on a real display.
