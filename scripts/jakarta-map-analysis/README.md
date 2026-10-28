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
```

| Script | Shows | Notes |
|---|---|---|
| `check_map_set.py` | Absolute heights, whole metres, odd heights, tree heights, trees on buildings and in the sea fetch, one-cell buildings and gaps, buildings on the domain edges, ground step across the y seam | Exit code 1 on a FAIL |
| `fit_map_location.py` | Position, orientation (8 axis-aligned options) and match scores of the map against building polygons; `--compare` scores other polygon sets at that position and gives their edge offsets | Needs geopandas, rasterio, pyproj (`.[gis]`) |
| `map_statistics.py` | Terrain percentiles; plan area fraction λp; building height statistics, most common height; H_av; frontal area index λf along x and y; buildings by height class, footprint and smallest width vs the 16-cell rule; tree cover; 500 m tiles; per-column transect | Land columns = domain without the flat 0 m strips at both ends (override with `--land-columns`) |
| `plot_map_statistics.py` | terrain.png, built_along_x.png, building_heights.png, building_widths.png, tiles.png | Each figure's purpose, reference and units are in the script docstring |
| `_common.py` | Shared argument handling | Not run directly |

Library code: `physics_core/urban_morphology.py` (λp, λf, H_av, building labelling, tiles) and `data_loaders/map_georef.py` (georef.yaml, cell → CRS / lon-lat).

## Caveats

- "Building" = a 4-connected group of building cells. The raster carries no building IDs, so touching buildings merge into one block, and isolated single cells count as buildings. The building count, footprint and width statistics describe these groups, not real buildings.
- λf uses the raster definition: the positive height steps met by the wind. Walls behind taller ones count only by the part that sticks out.
- The location fit only tries shifts and 90° turns/mirrors at scale 1.
