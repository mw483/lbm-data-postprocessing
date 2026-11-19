# Jakarta map analysis (2026-10-28)

**Commits**: `74e9157`, `3a6f2c9` (range `be6d191..HEAD`, branch `analysis/scalar2-outputs`)

**Goal**: The professor asked Mikael to check that the new Jakarta map data is fit to use. The 3D viewer ([2026-10-16_map-3d-viewer.md](2026-10-16_map-3d-viewer.md)) gives a qualitative look; these scripts give the numbers. Is the map internally consistent, does it describe the real city, and can the 2 m grid resolve it?

**Result**: `pytest`: 93 passed, 1 failed. The failure is the known `test_streamed_trajectories_read_11_column_file` (polars 2.0), unrelated and also failing before these commits. The 19 tests in `tests/test_urban_morphology.py` pass. The scripts were run on the 12 m map in the cloud container, on files copied from Mikael's PC (results below). **Not run yet on Mikael's PC.**

## Context

- Mikael approved a plan (project file `planning/jakarta_map_check_plan_2026-10-28.md`) and chose the folder name `scripts/jakarta-map-analysis` (with a hyphen). The scripts are run by path, not imported, so the hyphen causes no problem.
- The professor recommends the 12 m map (`F:\TSUBAME4_12m\map`, trees 12 m). It was checked byte-identical (SHA-256) to the old `jakarta_sim` copy.
- The professor said the buildings come from OSM. The location fit below confirms it.
- Tile size 500 m for the tile statistics is Mikael's choice.

## Commit 74e9157: urban morphology and georeference helpers

| File | Change | Why |
|---|---|---|
| [physics_core/urban_morphology.py](../physics_core/urban_morphology.py) | New. Object heights (absolute minus topography); plan area fraction lambda_p; area-weighted mean height H_av; frontal area index lambda_f on the raster (positive height steps met by the wind, divided by plan area, Grimmond & Oke 1999); building labelling as 4-connected groups (`scipy.ndimage.label`); building table; tile statistics; `empty_edge_columns` to drop flat 0 m strips such as the sea fetch. | Library functions for the numbers, kept apart from the scripts so they can be tested. |
| [data_loaders/map_georef.py](../data_loaders/map_georef.py) | New. `georef.yaml` format, the 8 axis-aligned orientations, `north_up` image, cell to CRS and to lon/lat (pyproj). | Needed to place the map on the real city and to report where features (e.g. the tallest building) are. |
| [pyproject.toml](../pyproject.toml) | New optional extra `gis = ["geopandas", "rasterio", "pyproj"]`. | Only the location fit needs these. Install with `pip install -e .[gis]`. |
| [tests/test_urban_morphology.py](../tests/test_urban_morphology.py) | New, 19 tests, including all 8 orientations and a synthetic location search. | Check the arithmetic and the orientation handling. |

## Commit 3a6f2c9: scripts/jakarta-map-analysis

| File | Change | Why |
|---|---|---|
| [_common.py](../scripts/jakarta-map-analysis/_common.py) | New. Map folder or `--case NAME`; output folder `<figures>/jakarta_map_analysis/<map name>`; `--land-columns`. | Shared argument handling. |
| [check_map_set.py](../scripts/jakarta-map-analysis/check_map_set.py) | New. Consistency checks, writes `checks.csv`, exit code 1 on a FAIL. | Find data problems before the map is used. |
| [fit_map_location.py](../scripts/jakarta-map-analysis/fit_map_location.py) | New. Rasterises reference polygons at 2 m; FFT search over the 8 orientations at 4-cell blocks, with offsets where the map mostly sticks out of the reference ignored; then refines cell by cell. Scores: `ncc`, `map_in_ref`, `ref_in_map`, `iou`. `--compare` scores other polygon sets and gives their edge offsets. Writes `georef.yaml`. | Find where on Earth the map is, and test which building data it was made from. |
| [map_statistics.py](../scripts/jakarta-map-analysis/map_statistics.py) | New. Writes `summary.csv`, `buildings.csv`, `tallest_buildings.csv`, `tiles_500m.csv`, `transect_i.csv`, `building_cell_heights_hist.npz`. | The numbers on terrain, buildings and trees. |
| [plot_map_statistics.py](../scripts/jakarta-map-analysis/plot_map_statistics.py) | New. `terrain`, `built_along_x`, `building_heights`, `building_widths`, `tiles` PNGs. Single-hue colours, one axis per panel. | Figures of the statistics. Each figure's explanation is in the script docstring. |
| [README.md](../scripts/jakarta-map-analysis/README.md), [../README.md](../README.md) | New folder README with commands, and a pointer in the main README. | Make the scripts findable. |

No solver physics or numerics changed. This is analysis code only.

## Results on the 12 m map

Run in the cloud container. Outputs are in the project files, `jakarta_map_analysis/TSUBAME4_12m/`.

### Location (fit_map_location)

- Reference: 2023 OSM building polygons in `E:\Jakarta\Bldg\east` (`w_height` + `wo_height`, EPSG:23834). Scale 1.
- Scores: `ncc` 0.86, `iou` 0.75. 82% of map building cells are OSM buildings. 90% of OSM cells inside the map are map buildings.
- Orientation `i:S, j:W`: map x runs north to south, row 0 is the east side.
- Corners: lon 106.8105-106.8569 E, lat 6.0918-6.2365 S.
- The 2017 strip (`E:\Jakarta\Bldg\west\buildingJakarta.shp`) scores only `iou` 0.42 (0.46 inside its extent). The map was not made from it. This agrees with the professor: the buildings are from OSM.
- Why the map is about 350 m wider than the 2017 strip: the map is a fixed 2560 x 2 m = 5.12 km box. The strip's west edge lies 191 m west of the map's west edge, and its east edge 531 m west of the map's east edge. So the map extends past the strip, and 12% of map building cells lie outside it.

### Consistency checks (check_map_set)

No FAIL. Findings to know about:

| Check | Value |
|---|---|
| Heights in whole metres | yes |
| Building cells with odd heights | 12.5% |
| Tree height | only 12 m |
| Tree cells on building cells | 44,935 |
| Tree cells in the sea fetch (columns 1009-1210) | 10,894 |
| 4-connected building groups | 99,066, of which 52,581 are single cells |
| One-cell gaps between buildings | 18,599 along i, 18,908 along j |
| Building cells on row j=0 / j=2559 | 3,428 / 2,360 |
| Ground step across the y seam | mean 3.16 m, max 16 m |

The last two rows matter only if the Jakarta run uses periodic boundaries in y, so that the two y edges touch. The boundary setting for this case is not decided yet.

### Statistics (map_statistics)

Land columns 1279-7938, area 68.2 km2.

| Quantity | Value |
|---|---|
| Ground height | mean 4.6 m, median 3 m, max 22 m |
| lambda_p (plan area fraction) | 0.346 |
| Building height | mean 10.3 m, median 6 m, p99 100 m, max 383 m |
| Most common building height | 6 m, on 72.8% of building cells (possibly a default height for OSM buildings without height; not confirmed) |
| H_av (area-weighted mean height) | 3.56 m |
| lambda_f (frontal area index) | 0.31 (x), 0.29 (y) |
| Groups taller than 100 m / 300 m | 140 / 4 |
| Tallest | 383 m at lon 106.82124, lat -6.19905 |
| Tree cover | 0.144 |

**Caveat**: a "building" is a 4-connected group of building cells. Touching buildings merge into one block and isolated single cells count as buildings. So building count, footprint and width statistics describe groups, not real buildings. Stated in the folder README.

## Statistic explanation (CLAUDE.md rule)

Common purpose for all items: a data check of the new Jakarta map before it is used in simulations. Not checked against the source papers: marked [U].

1. **Location scores (`ncc`, `iou`, `map_in_ref`, `ref_in_map`)**
   - Measures: how much the map's building cells overlap the cells of a reference polygon set (1 = identical).
   - Why: asks whether the map really is the real city and from which building data it was made. `iou` is strict (penalises misses and extras); the two `*_in_*` fractions show which side differs; `ncc` is what the FFT search maximises.
   - Reference: none published. The expectation is "high for the source data, clearly lower for other data"; the OSM set (iou 0.75) against the 2017 strip (0.42) shows that.
   - Units/sample: dimensionless; all building cells, 2 m grid, reference rasterised at 2 m.
2. **Plan area fraction lambda_p and H_av**
   - Measures: the fraction of ground covered by buildings, and the mean building height weighted by footprint area.
   - Why: they are the standard inputs for judging urban roughness, so the map can be compared with the real city and with literature values for dense cities.
   - Reference: Grimmond & Oke 1999, J. Appl. Meteorol. 38, 1262-1292, for the definitions and typical urban ranges [U].
   - Units/sample: lambda_p dimensionless; H_av in m (over all land cells, so 3.56 m is below the building mean of 10.3 m); land columns only, 68.2 km2.
3. **Frontal area index lambda_f**
   - Measures: the wall area facing the wind per unit ground area, here taken from the positive height steps met along x (or y).
   - Why: it sets how much the buildings slow the wind, so it is what a roughness estimate needs, and the wind direction matters.
   - Reference: Grimmond & Oke 1999 (same paper) [U]. Raster version: walls behind taller ones count only by the part that sticks out.
   - Units/sample: dimensionless; land columns, whole map.
4. **Building height and width statistics, 16-cell rule**
   - Measures: how tall buildings are, and how many cells wide the smallest side is.
   - Why: the 2 m grid can only resolve a building that is several cells wide; the width figure shows how many are too narrow. Statistics are on groups (see caveat).
   - Reference: the professor's resolution rule for this lab, >= 16 cells across a building width (stated by the professor; no published source). The figure draws it as a line.
   - Units/sample: m and cells; land columns.
5. **500 m tiles and the transect**
   - Measures: the same statistics in 500 m squares, and per column along x.
   - Why: shows where the map is dense or open, and whether the sea fetch and edges behave. Tile size is Mikael's choice.
   - Reference: none.
   - Units/sample: as above; tiles of 250 x 250 cells.

Per-figure explanations are in the docstring of `plot_map_statistics.py`. Not re-read by the changelog writer.

## What was deliberately left alone

- Comparison with public reference data (GHSL, Open Buildings, FABDEM and others) is the next stage and is not in these commits.
- `scripts/view_map_3d.py` stays in `scripts/` because it is used for every case.
- No change to the map files and no repair of the findings above (trees on buildings, edge buildings, seam step). They are reported, not fixed.

## How to check

```sh
python -m pytest tests/test_urban_morphology.py
```

The commands for the scripts are in [scripts/jakarta-map-analysis/README.md](../scripts/jakarta-map-analysis/README.md). Short form, from the repo root:

```sh
M=F:/TSUBAME4_12m/map
python scripts/jakarta-map-analysis/check_map_set.py $M
pip install -e .[gis]
python scripts/jakarta-map-analysis/fit_map_location.py $M --reference E:/Jakarta/Bldg/east/w_height.shp E:/Jakarta/Bldg/east/wo_height.shp --compare E:/Jakarta/Bldg/west/buildingJakarta.shp
python scripts/jakarta-map-analysis/map_statistics.py $M --georef <out>/georef.yaml
python scripts/jakarta-map-analysis/plot_map_statistics.py --stats <out>
```
