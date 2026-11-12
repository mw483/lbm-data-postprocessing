# Jakarta map analysis

Quantitative checks of an LBM-city map set (`topography.dat`, `building.dat`, `vegetation.dat`), first for the Jakarta 12 m map (`F:\TSUBAME4_12m\map`, byte-identical to `jakarta_sim`). The qualitative view is `scripts/view_map_3d.py`. Plan and reference datasets: `planning/jakarta_map_check_plan_2026-10-28.md` in the project files.

Purpose: a data check before the map is used. Is it internally consistent, does it describe the real city, and can the 2 m grid resolve it?

All scripts take a map folder or `--case NAME` (reads `<lbm_cases>/NAME/map`). Outputs go to `<figures>/jakarta_map_analysis/<map name>/` unless `--out` is given. Run them from the repo root.

```sh
M=F:/TSUBAME4_12m/map
python scripts/jakarta-map-analysis/check_map_set.py $M                      # consistency checks -> checks.csv
pip install -e .[gis]                                                        # once, for the location fit
python scripts/jakarta-map-analysis/fit_map_location.py $M \
    --reference E:/Jakarta/Bldg/east/w_height.shp E:/Jakarta/Bldg/east/wo_height.shp \
    --compare E:/Jakarta/Bldg/west/buildingJakarta.shp                       # -> georef.yaml (about 4 min)
python scripts/jakarta-map-analysis/map_statistics.py $M --georef <out>/georef.yaml   # -> summary.csv, buildings.csv, ...
python scripts/jakarta-map-analysis/plot_map_statistics.py --stats <out>     # -> PNG figures
D=D:/LBM_Jakarta_2023
python scripts/jakarta-map-analysis/compare_reference.py $M --georef <out>/georef.yaml --land-columns 1279 7750 \
    --dem $D/DEMNAS/DEMNAS_1209-44_v1.0.tif \
    --ghsl-s $D/GHSL/BUILT_S/GHS_BUILT_S_E2018_GLOBE_R2023A_54009_10_V1_0_R10_C29.tif \
    --ghsl-h $D/GHSL/BUILT_H/GHS_BUILT_H_AGBH_E2018_GLOBE_R2023A_54009_100_V1_0_R10_C29.tif \
    --source-topo $D/dataset/topo1_new.tif \
    --source-building "$D/dataset/w and wo height(6) AREA1 rasterized new new.tif"   # -> compare_summary.csv, figures
```

Choosing a cut-out to simulate (interactive window, or `--save` for the figure to show the professor):

```sh
python scripts/jakarta-map-analysis/explore_tiles.py $M --georef <out>/georef.yaml --nz 256          # window
python scripts/jakarta-map-analysis/explore_tiles.py $M --georef <out>/georef.yaml \
    --candidates <out>/candidates.yaml --save <out>/candidates.png                                    # -> PNG + candidates.csv
python scripts/view_map_3d.py $M --box A --candidates <out>/candidates.yaml                          # one box in 3D
python scripts/jakarta-map-analysis/find_cutouts.py $M --land-columns 1279 7750 --size 512 128 --nz 160 \
    --candidates <out>/candidates.yaml                                                                # best 512 x 128 boxes -> J1, J2, ...
```

`--land-columns 1279 7750` leaves out the south end of the Jakarta map, where the terrain ramps down from about 14.5 m to 0 over columns 7750-7939 and has no buildings (made for the boundary, not real terrain).

| Script | Shows | Notes |
|---|---|---|
| `check_map_set.py` | Absolute heights, whole metres, odd heights, tree heights, trees on buildings and in the sea fetch, one-cell buildings and gaps, buildings on the domain edges, ground step across the y seam | Exit code 1 on a FAIL |
| `fit_map_location.py` | Position, orientation (8 axis-aligned options) and match scores of the map against building polygons; `--compare` scores other polygon sets at that position and gives their edge offsets | Needs geopandas, rasterio, pyproj (`.[gis]`) |
| `map_statistics.py` | Terrain percentiles; plan area fraction λp; building height statistics, most common height; H_av; frontal area index λf along x and y; buildings by height class, footprint and smallest width vs the 16-cell rule; tree cover; 500 m tiles; per-column transect | Land columns = domain without the flat 0 m strips at both ends (override with `--land-columns`) |
| `plot_map_statistics.py` | terrain.png, built_along_x.png, building_heights.png, building_widths.png, tiles.png | Each figure's purpose, reference and units are in the script docstring |
| `compare_reference.py` | Map against DEMNAS and the source terrain file (bias, RMSE, r, open vs building cells), against GHSL BUILT-S/H per 100 m pixel (built-up fraction, AGBH, ANBH, totals), and against the source building raster (height classes, 6 m rule) | Figures by `plot_compare_reference.py`; every input optional |
| `explore_tiles.py` | Window: buildings from above + one 500 m tile statistic (keys 1-4); drag a box or click a tile to get its numbers; `a` saves it to `candidates.yaml`, `v` opens it in `view_map_3d.py`, `w` writes PNG + CSV. `--save`: candidates drawn on the maps + `candidates.csv` | Box numbers from `box_summary` (full 2 m map): λp, heights, 6 m share, trees, ground range, building cells on each periodic edge, same-size street-aligned shift, buildings narrower than 10/16 cells, open-ground sources, and for `--nz`: top/H_max, length/H_max, blockage per cross-section (AIJ < 3%), width/top, cells and wall time [est]. Wind along +i |
| `find_cutouts.py` | Every box of `--size` cells on a `--stride` grid, tested against: top >= 5 H_max, length >= 10 H_max, blockage < 3% (AIJ), ground range <= 2 m, λp >= 0.2. Passing boxes ranked by building volume in buildings >= 16 cells wide, then by building cells on the edges; the best non-overlapping ones measured with `box_summary` and optionally added to `candidates.yaml` as J1, J2, ... | Building width is that of the whole building, also where the box cuts it. Outputs `find_cutouts_<ni>x<nj>.csv` and `_best.csv` |
| `_common.py` | Shared argument handling | Not run directly |

Library code: `physics_core/urban_morphology.py` (λp, λf, H_av, building labelling, tiles, cut-out box numbers) and `data_loaders/map_georef.py` (georef.yaml, cell → CRS / lon-lat).

## Caveats

- "Building" = a 4-connected group of building cells. The raster carries no building IDs, so touching buildings merge into one block, and isolated single cells count as buildings. The building count, footprint and width statistics describe these groups, not real buildings.
- λf uses the raster definition: the positive height steps met by the wind. Walls behind taller ones count only by the part that sticks out.
- The location fit only tries shifts and 90° turns/mirrors at scale 1. The Jakarta georef.yaml was then snapped by hand to the map-making domain box `D:/LBM_Jakarta_2023/dataset/area1_west.gpkg` (under 1 m from the fit; key `snapped_to`).
- GHSL heights are estimated from 30 m global DEMs; treat them as an independent estimate, not the truth.
- Box blockage is the periodic stand-in for the AIJ blockage ratio (Tominaga et al. 2008, sec. 3.1): for each column, the share of the y-z cross-section (box width x domain top) filled by buildings. AIJ defines it for an inflow/outflow domain as the frontal projection of all buildings, which has no direct meaning when the city repeats.
- Wall time scales the 512 x 128 x 1024 benchmark (0.068 s per step on 4 GPUs, dt 0.008 s) linearly with the cell count; GPU memory is not checked.
- λf before 2026-11-12 was too large by a factor dx (2 for the 2 m maps): `frontal_area_index` divided by the cell count but not by dx. The Jakarta `summary.csv` of 2026-10-28 (λf 0.306 / 0.294) should read 0.153 / 0.147; rerun `map_statistics.py`.
