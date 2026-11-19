# Jakarta map: comparison with reference data (2026-10-29)

**Commits**: `92da746` (range `8399b30..92da746`, branch `analysis/scalar2-outputs`)

**Goal**: Stage 2 of the Jakarta map check, approved by Mikael (kaka) on 2026-10-29. Stage 1 ([2026-10-28_jakarta-map-analysis.md](2026-10-28_jakarta-map-analysis.md)) gave the map's own numbers and its location. Stage 2 sets the 12 m map (`F:\TSUBAME4_12m\map`) against (a) independent data the map was not made from (DEMNAS terrain, GHSL built-up surface and building height) and (b) the files it was made from, found in `D:\LBM_Jakarta_2023\dataset`. The question: is the map terrain and building height consistent with the real city, and is it really made from those source files?

**Result**: `pytest`: 94 passed, 1 failed. The failure is the known `test_streamed_trajectories_read_11_column_file` (polars), unrelated and failing before this commit. The new scripts were run on the 12 m map in the cloud container, on files copied from Mikael's PC (results below). **Not run yet on the lab PC.** Open Buildings (still downloading) is not used yet.

## Context

- Inputs that were used (all in `D:\LBM_Jakarta_2023`):
  - DEMNAS tile `1209-44`, covers the map. Mikael infers it is from 2022 (not confirmed from the file).
  - GHSL `GHS_BUILT_S_E2018` 10 m and `GHS_BUILT_H_AGBH_E2018` 100 m (World Mollweide, tile R10_C29).
  - Map source files: `dataset/topo1_new.tif`, `dataset/w and wo height(6) AREA1 rasterized new new.tif`, and the domain box `dataset/area1_west.gpkg` (E 234370-239490, N 810440-826440, EPSG:23834).
- `georef.yaml` (an output file, not in the repo) was snapped by hand to the `area1_west` domain box. The fitted position from stage 1 was within 1 m of it. With the snapped box, the map terrain equals the source terrain (rounded down) in 95.0 % of cells.
- `--land-columns 1279 7750` leaves out the artificial ramp at the south end of the map (columns 7750-7939), where the ground falls from about 14.5 m to 0 and the buildings are removed. Stage 1 used columns 1279-7938, so numbers here are not directly comparable to the stage 1 table.
- Decisions recorded in the brief:
  - GHSL is compared on its own 100 m grid by adding up map cells, not by interpolating GHSL to the 2 m grid.
  - AGBH is taken as building volume / pixel area (GHSL Data Package 2023, checked in the data package PDF). This is the same quantity as the map's H_av. ANBH = AGBH / built fraction.
  - A GHSL pixel counts as fully covered when it holds at least 95 % of the median number of map cells per pixel. Map cell centres fall unevenly into the sheared Mollweide pixels. A first rule of "99 % of the area" left striped gaps.
  - DEMNAS has no CRS tag, so EPSG:4326 is assumed (option `--dem-crs`).

## Commit 92da746: compare the map with DEMNAS, GHSL and the map's source rasters

| File | Change | Why |
|---|---|---|
| [data_loaders/map_georef.py](../data_loaders/map_georef.py) | New `image_transform(geo)` (affine transform of the north-up map image), `image_shape(geo)` (rows, cols) and `warp_to_map(path, geo, resampling, src_crs, band, use_nodata)` (rasterio `reproject` onto the north-up map grid, float32, NaN where the file has no data). `use_nodata=False` keeps the file's nodata value as data. | Put any raster on the map grid. `use_nodata=False` is needed because the source building raster tags 0 = no building as nodata; with the tag honoured, every open cell would become NaN. |
| [scripts/jakarta-map-analysis/compare_reference.py](../scripts/jakarta-map-analysis/compare_reference.py) | New. Terrain differences (map minus DEMNAS and minus source topography: bias, RMSE, MAE, r, 5th/95th percentile, split into all / open / building cells, coverage, share equal to the reference rounded or rounded down); GHSL per 100 m pixel (built-up fraction, AGBH, ANBH, totals of area and volume); height-class table of the map against the source building raster. Writes `compare_summary.csv`, `ghsl_pixels.csv`, `source_building.csv`. All inputs optional. | The numbers for stage 2. |
| [scripts/jakarta-map-analysis/plot_compare_reference.py](../scripts/jakarta-map-analysis/plot_compare_reference.py) | New. `terrain_compare.png`, `ghsl_scatter.png`, `ghsl_maps.png`. Called from `compare_reference.py`, not run on its own. | Figures of the comparison. |
| [scripts/jakarta-map-analysis/README.md](../scripts/jakarta-map-analysis/README.md) | New command block and table row; note on `--land-columns 1279 7750`; note that `georef.yaml` was snapped to `area1_west.gpkg` (key `snapped_to`); note that GHSL heights are an independent estimate, not truth. | Make the new script findable and reproducible. |
| [tests/test_urban_morphology.py](../tests/test_urban_morphology.py) | New test `test_image_transform_matches_cell_to_crs`: `image_transform` and `image_shape` agree with `cell_to_crs` / `image_index` for three cells. | The warp depends on this transform being right. |

No solver physics or numerics changed. This is analysis code only. The map files were not changed.

## Results on the 12 m map

Run in the cloud container on the staged 12 m map, land columns 1279-7749. Outputs are in the project files, `jakarta_map_analysis/TSUBAME4_12m/`: `compare_summary.csv`, `ghsl_pixels.csv`, `source_building.csv`, `terrain_compare.png`, `ghsl_scatter.png`, `ghsl_maps.png`.

### Terrain

| Reference | Result |
|---|---|
| Source file `topo1_new.tif` | Map = source rounded down to whole metres in 95.0 % of cells. Bias -0.48 m, RMSE 0.69 m, r 0.995. A few patches (ponds, lakes) differ. |
| DEMNAS | Map is 2.3 m lower on average (open cells -1.9 m, building cells -3.2 m). RMSE 4.6 m, r 0.78. DEMNAS sea is at about -3.3 m, the map sea is 0 m. **Cause not known**: possibly the vertical datum, DEMNAS being partly a surface model, or subsidence [U]. |

The -0.48 m bias against the source file is what rounding down to whole metres gives (about half a metre on average). So the map terrain is the source terrain, as the 95.0 % shows.

### GHSL (6476 pixels of 100 m)

| Quantity | Map | GHSL | Other |
|---|---|---|---|
| Built-up fraction (mean) | 0.357 | 0.365 | r 0.80, RMSE 0.13 |
| Built area | 23.1 km2 | 23.7 km2 | |
| AGBH (mean) | 3.7 m | 5.7 m | r 0.48 |
| Building volume | 240 million m3 | 368 million m3 | map 35 % lower |
| ANBH (mean) | 11.1 m | 15.5 m | r 0.39 |

The built area agrees within 3 %. The heights do not: the map is lower. The map's low heights are consistent with its 6 m default height (inference, not tested). GHSL heights come from 30 m global DEMs and are known to underestimate tall buildings [U], so the true gap may differ.

### Source building raster ("w and wo height(6) AREA1 rasterized new new.tif")

- Building / no building agree in 91.4 % of cells.
- Heights are equal in 55.8 % of cells that are buildings in both. If every source building under 6 m is raised to 6 m, they are equal in 73 %.
- Cells with 2-5 m height: 21 thousand in the map, 1.14 million in the source.
- Cells at exactly 6 m: 49 % of source building cells, 73 % of map building cells.
- The source raster has no data on image rows 0-1290 (the sea strip).

Conclusion: the map is a close relative of this raster, not made from exactly this file. Which version it was made from is **not known**.

## Statistic explanation (CLAUDE.md rule)

Common purpose for all items: a data check of the new Jakarta map before it is used in simulations (validation against independent data and against its own source files). Per-figure explanations are also in the docstrings of `compare_reference.py` and `plot_compare_reference.py`. Not checked against the source documents unless stated: marked [U].

1. **Terrain difference map minus reference (bias, RMSE, r, open vs building cells)**
   - Measures: how many metres higher or lower the map ground is than the reference ground, cell by cell, and how well the two follow the same shape.
   - Why: asks whether the map terrain is real and correctly placed. A constant offset points to a height datum difference. A difference only under buildings points to a reference that includes buildings (surface model) or to a map that lowered the ground there, so open and building cells are split. Bias gives the offset, RMSE the typical error, r the shape agreement.
   - Reference: DEMNAS, Badan Informasi Geospasial, heights on the EGM2008 geoid [U]; and the map's own source file `topo1_new.tif`. For the source file the expectation is "equal after rounding down to whole metres"; for DEMNAS there is no published expectation here.
   - Units/sample: m (r dimensionless); 2 m cells of land columns 1279-7749; DEMNAS resampled bilinear, source terrain averaged onto the map cell.
2. **Share of cells equal to the reference rounded / rounded down**
   - Measures: the fraction of cells where the map height equals the reference after rounding (or rounding down) to whole metres.
   - Why: the map has whole-metre heights only, so this tests the specific claim "the map is the source file, floored", which bias and RMSE cannot show.
   - Reference: none; the expectation is close to 100 % if the source is the same file.
   - Units/sample: fraction; same cells as item 1.
3. **GHSL built-up fraction, AGBH, ANBH per 100 m pixel (bias, RMSE, r, totals)**
   - Measures: per 100 m square, the share covered by buildings, the building volume per ground area (AGBH, equal to the map's H_av), and the mean height of the buildings themselves (ANBH = AGBH / built fraction).
   - Why: GHSL is the only independent global building product with heights, so it is the reference for "is the map as built-up and as tall as satellite data says". The 100 m pixel is its native grid, so map cells are added up per pixel and GHSL is not interpolated. Fraction, AGBH and ANBH are shown separately so a footprint error is not confused with a height error.
   - Reference: GHS-BUILT-S and GHS-BUILT-H R2023A, Pesaresi & Politis 2023; GHSL Data Package 2023 (AGBH definition = building volume / pixel area, checked in the data package PDF). Further details of the products, and the statement that heights are from 30 m DEMs and underestimate tall buildings, are not checked [U]. GHSL is an estimate, not truth.
   - Units/sample: fraction (-) and m; 6476 pixels that hold at least 95 % of the median number of map cells per pixel, inside the land columns; totals in km2 and million m3.
4. **Source building raster: mask agreement, height class table, 6 m rule**
   - Measures: for cells covered by the source raster, how often map and source agree on building / no building, how often the heights are equal, and how the heights are distributed (class table).
   - Why: tests whether, and how, the map was made from this raster (for example by giving every building at least a default height). Raising source heights below 6 m to 6 m is the hypothesis behind the "if every building under 6 m is 6 m" row.
   - Reference: none published; the source file is the reference.
   - Units/sample: fractions and cell counts; 2 m cells inside the source raster's coverage.

## What was deliberately left alone

- Open Buildings is still downloading and is not used. It is a later step.
- No change to the map files, no repair of the findings, and no decision on the terrain offset to DEMNAS or on the 6 m default height. They are reported only.
- The DEMNAS vertical datum was not looked up; the 2022 date of the tile is Mikael's inference.
- The same scripts were not yet run on the lab PC.

## How to check

```sh
python -m pytest tests/test_urban_morphology.py
```

The full command with all inputs is in [scripts/jakarta-map-analysis/README.md](../scripts/jakarta-map-analysis/README.md). Short form, from the repo root (needs `pip install -e .[gis]`):

```sh
M=F:/TSUBAME4_12m/map
D=D:/LBM_Jakarta_2023
python scripts/jakarta-map-analysis/compare_reference.py $M --georef <out>/georef.yaml --land-columns 1279 7750 \
    --dem $D/DEMNAS/DEMNAS_1209-44_v1.0.tif \
    --ghsl-s $D/GHSL/BUILT_S/GHS_BUILT_S_E2018_GLOBE_R2023A_54009_10_V1_0_R10_C29.tif \
    --ghsl-h $D/GHSL/BUILT_H/GHS_BUILT_H_AGBH_E2018_GLOBE_R2023A_54009_100_V1_0_R10_C29.tif \
    --source-topo $D/dataset/topo1_new.tif \
    --source-building "$D/dataset/w and wo height(6) AREA1 rasterized new new.tif"
```
