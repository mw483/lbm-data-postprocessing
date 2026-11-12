# Urban parameter comparison: cube arrays vs Jakarta cut-outs, and a lambda_f bug fix (2026-11-12)

**Commits**: `1b7addf`, `e68fef9`, `345ecf1` (range `146b2e6..345ecf1`, branch `analysis/scalar2-outputs`)

**Goal**: kaka asked (2026-11-11/12) for a general script that compares the urban building parameters of the idealised cube arrays (regular: aligned and staggered) with the chosen Jakarta cut-outs, and for a Jakarta strip of 512 x 128 cells that meets the domain criteria. The cube case is the small neutral domain 512 x 128 x 160 cells, with 16 x 16 x 16 cell cubes and 16-cell gaps. The plan is `planning/urban_parameter_comparison_plan_2026-11-11.md` (a project file, not in this repo). kaka approved it with three answers: default cubes 16 x 16 x 16 with 16-cell gaps; include both Macdonald 1998 and Kanda 2013; pick the Jakarta strip that fills 512 x 128 x 160 while meeting the criteria. This builds on [2026-11-11_tile-explorer.md](2026-11-11_tile-explorer.md) (`box_summary`, `candidates.yaml`) and [2026-10-28_jakarta-map-analysis.md](2026-10-28_jakarta-map-analysis.md) (lambda_f, `map_statistics.py`).

**Result**: `pytest tests/`: 114 passed, 2 failed. Both failures were there before and are unrelated: `test_streamed_trajectories` (polars 2.0) and `test_image_transform` (needs the optional `affine` package).
- Scripts were run on synthetic maps. The `find_cutouts.py` scan values for the top box equal the exact `box_summary` values (lambda_p, h_max, blockage, ground range, edge building cells). The comparison figure was checked by eye.
- Notable result of the synthetic run: the 16-cell cube arrays are 32 m tall. With a 320 m top (nz 160) their blockage maximum is 5 %, above the AIJ limit of 3 %. Below 3 % needs a top of about 534 m (nz about 267). This is for kaka to decide on; nothing was changed because of it.
- **Not run on the real Jakarta map** (it lives on the lab PC only). No real Jakarta strip has been picked yet.
- All Macdonald and Kanda coefficients were written from memory and are marked [U] until checked against the papers.

## Commit 1b7addf: frontal_area_index divides by dx (bug fix)

**What was wrong**: `frontal_area_index` returned the sum of windward wall heights divided by the cell count. That is lambda_f x dx when heights are in m. The old comment said "dx cancels"; it does not when heights are in m and not in cells. With the 2 m Jakarta map, lambda_f came out twice too large. It was found because the aligned cube test (known lambda_f = 0.25) gave 0.5.

| File | Change | Why |
|---|---|---|
| [physics_core/urban_morphology.py](../physics_core/urban_morphology.py) | `frontal_area_index(hb, axis)` becomes `frontal_area_index(hb, axis, dx=1.0)`. Old: `sum(positive steps) / s.size`. New: `sum(positive steps) / (s.size * dx)`. Docstring rewritten. | Wall area (height x dx) over plan area (cells x dx^2) = sum of heights / (cells x dx). |
| same | `box_summary` now calls `frontal_area_index(hb, axis=1, dx=dx)`. | Its `lambda_f_x` (added 2026-11-11 in `5dd6a7a`, see [2026-11-11_tile-explorer.md](2026-11-11_tile-explorer.md)) was twice too large too. |
| [scripts/jakarta-map-analysis/map_statistics.py](../scripts/jakarta-map-analysis/map_statistics.py) | `lambda_f_i` and `lambda_f_j` rows pass `dx=DX`. | Same bug in the Jakarta statistics. |
| [tests/test_urban_morphology.py](../tests/test_urban_morphology.py) | New `test_frontal_area_heights_in_metres`: 10 m block, 2 m cells, 4 x 4 cells, expects 10 x 2 / (16 x 4). | Guards the metre case. The old test (heights in cells) still passes because the default is `dx=1.0`. |

**Effect on numbers (numerics change)**
- Old behaviour: lambda_f (with heights in m) = true value x dx. New behaviour: the true value.
- 2026-10-28 `summary.csv` (see [2026-10-28_jakarta-map-analysis.md](2026-10-28_jakarta-map-analysis.md)): `lambda_f_i` 0.306 and `lambda_f_j` 0.294 should be **0.153** and **0.147**. Rerun `map_statistics.py` to refresh the file. The values in the older entry are not edited; this entry is the correction.
- Any `box_summary` or candidate CSV made on 2026-11-11 has `lambda_f_x` twice too large. Regenerate it.
- To revert (not advised): call with `dx=1.0`, which gives the old numbers for heights in cells only.

## Commit e68fef9: cube arrays, street width, Macdonald 1998, Kanda 2013

All new code is in [physics_core/urban_morphology.py](../physics_core/urban_morphology.py) (140 lines) with 41 lines of tests in [tests/test_urban_morphology.py](../tests/test_urban_morphology.py). The tests use synthetic arrays with known values.

| Function | Change | Why |
|---|---|---|
| `cube_array(n_i, n_j, size, height, gap_i, gap_j, arrangement)` | Builds a periodic array of square blocks (array shape `(n_j, n_i)`). `aligned`: a regular grid. `staggered`: every other row (along i) is shifted by half a pitch in j, as in Coceal et al. (2006). Raises `ValueError` if the domain is not a whole number of pitches (for staggered, 2 pitches along i, 1 along j). Pitch = size + gap. | The reference idealised cases. The check makes sure the array is really periodic. 512 x 128 with 16-cell cubes and 16-cell gaps gives pitch 32: 16 pitches along i, 4 along j. |
| `mean_open_run(hb, axis, periodic=True)` | Mean length (cells) of open gaps between two buildings along a line: the street or gap width W seen by the wind. Periodic wrap by default, so the gap across the seam counts. Lines with no building are skipped. | Needed for H/W. An earlier version counted fully open rows as streets and gave W = 90 m for the aligned cubes instead of the correct 32 m (16 cells x 2 m). |
| `macdonald_1998(lambda_p, lambda_f, height, arrangement, cd=1.2)` | d and z0 from Macdonald, Griffiths & Hall (1998), Atmos. Environ. 32, 1857-1864. Staggered: A 4.43, beta 1.0. Aligned: A 3.59, beta 0.55. C_D 1.2, kappa (`KARMAN`) 0.4. `d/H = 1 + A^(-lambda_p) (lambda_p - 1)`. Returns z0 = 0 if lambda_f <= 0. | Standard morphometric estimate of d and z0 for regular arrays. [U] coefficients written from memory, not checked against the paper. |
| `kanda_2013(lambda_p, lambda_f, h_mean, h_max, sigma_h, cd=1.2)` | d and z0 corrected for height variety, Kanda, Inagaki, Miyamoto, Gryschka & Raasch (2013), Boundary-Layer Meteorol. 148, 357-377. Constants a0 1.29, b0 0.36, c0 -0.17, a1 0.71, b1 20.21, c1 -0.77. `z0_mac` comes from the staggered Macdonald with H = `h_mean`. Returns (0, 0) if `h_max` or `h_mean` <= 0. | kaka asked for both methods; real Jakarta heights vary a lot, which Macdonald ignores. Inagaki, a co-author, is kaka's professor. [U] coefficients and the choice of Macdonald variant for `z0_mac` not checked against the paper. |
| `morphology_parameters(hb, dx=2.0, arrangement="staggered", min_cells=(10, 16), periodic=True)` | One flat dict per map: lambda_p, lambda_f x and y, H_av, H_mean, H_max, sigma_H, sigma_H / H_mean, H_max / H_mean, most common height and its share (the 6 m default of the Jakarta map), building count, building widths narrower than 10 and 16 cells (by count and by volume), W in x and y, H/W in x and y, d and z0 by both methods (also / H_mean). | Puts every number kaka wants in one place, for cubes and maps alike. H_mean and sigma_H are over building cells (plan-area weighted). `arrangement` picks the Macdonald coefficients; real cities use staggered. |

## Commit 345ecf1: the two scripts

| File | Change | Why |
|---|---|---|
| [scripts/compare_urban_parameters.py](../scripts/compare_urban_parameters.py) | New (240 lines). `python scripts/compare_urban_parameters.py CONFIG.yaml [--out FOLDER]`. The YAML has `dx`, `arrangement` and a list of `entries`, each of type `cubes` (generated from `domain_cells`, `size_cells`, `height_cells`, `gap_cells`, `arrangement`), `map` (a box of a map set, by `box` or `box_name` from a candidates file) or `case` (a whole LBM-city case). An optional `nz` adds the domain checks: top / H_max, length / H_max, blockage. | One script for any set of cube arrays and map boxes, as kaka asked. |
| same | Outputs `urban_parameters.csv` (one column per entry) and `urban_parameters.png` (bars of the shape numbers, volume by height, top views). | The CSV is for tables, the figure for the talk. Purpose, reference and units are in the script docstring. |
| [scripts/compare_urban_parameters_example.yaml](../scripts/compare_urban_parameters_example.yaml) | New. Aligned and staggered 16-cell cubes (512 x 128, `nz` 160, `dx` 2.0) plus `Jakarta J1` from a candidates file. Paths are for the lab PC (`F:/TSUBAME4_12m/map`); adjust them. | Starting point that lists every option. |
| [scripts/jakarta-map-analysis/find_cutouts.py](../scripts/jakarta-map-analysis/find_cutouts.py) | New (182 lines). Tests every box of `--size` (default 512 x 128) on a `--stride` grid (default 16 cells, must divide the size), using block reductions so the whole map is scanned fast. Criteria: top >= 5 H_max, length >= 10 H_max, blockage < 3 % per cross-section, ground range <= 2 m (`--max-ground-range`), lambda_p >= 0.2 (`--min-lambda-p`). `--nz` default 160 (top = nz x 2 m). | The "pick a Jakarta strip that meets the domain criteria" request. Criteria are the AIJ checks from [2026-11-11_tile-explorer.md](2026-11-11_tile-explorer.md) plus flat ground and enough buildings. |
| same | Ranking: first by volume share in buildings at least 16 cells wide (`--min-cells`), then by fewest building cells on the periodic edges. The best `--top` (default 5) non-overlapping boxes are measured with `box_summary`. `--candidates FILE` writes them as J1, J2, ... and replaces any older `J*` entries. Outputs `find_cutouts_<ni>x<nj>.csv` and `_best.csv`. | Resolved buildings matter most for LES with 16 cells per side (professor's rule). Few cut buildings at the seams keep the periodic box clean. Building width is that of the whole building, also where the box cuts it. |
| [README.md](../README.md), [scripts/jakarta-map-analysis/README.md](../scripts/jakarta-map-analysis/README.md) | New command blocks, a table row for `find_cutouts.py`, and a caveat that lambda_f before 2026-11-12 was dx times too large. | Make the scripts findable and state the bug. |

## What was deliberately left alone

- Map storage and provenance in LBM-city. That is a proposal only and not part of this repo.
- No real Jakarta strip was chosen: `find_cutouts.py` has to be run on the lab PC first.
- The 3 % blockage question for the cube arrays (needs nz about 267, see Result) was only reported, not acted on.

## How to check

```sh
pytest tests/test_urban_morphology.py
python scripts/compare_urban_parameters.py scripts/compare_urban_parameters_example.yaml   # -> urban_parameters.csv / .png
M=<map folder>
python scripts/jakarta-map-analysis/find_cutouts.py $M --land-columns 1279 7750 --size 512 128 --nz 160 \
    --candidates <out>/candidates.yaml                                                       # best boxes -> J1, J2, ...
python scripts/jakarta-map-analysis/map_statistics.py ...                                    # refresh summary.csv (lambda_f fix)
```

A quick sanity check for the fix: an aligned array of 16-cell cubes with 16-cell gaps must give lambda_p = 0.25 and lambda_f = 0.25 (cube height = size, pitch 2 x size).

Still to do on the lab PC: run `find_cutouts.py` and `compare_urban_parameters.py` on the real Jakarta map, rerun `map_statistics.py`, and check the [U] coefficients against Macdonald et al. (1998) and Kanda et al. (2013).
