# Road sources for the Jakarta map: OSM roads to particle sources (2026-11-12)

**Commits**: `7169840`, `cd30156` (range `74558b8..cd30156`, branch `analysis/scalar2-outputs`)

**Goal**: The professor asked kaka (for the zemi, about 2026-11-14) for road and street data on the Jakarta map (`TSUBAME4_12m`, 8000 x 2560 cells at 2 m, georef EPSG:23834; map x runs real north to south, row 0 = east), so that particle sources sit on streets. kaka approved the plan on 2026-11-12: `planning/jakarta_road_sources_plan_2026-11-12.md` (a project file, not in this repo). kaka asked for two source sets: all road classes, and main roads only (classes 1-2). Builds on the map georeference from [2026-10-28_jakarta-map-analysis.md](2026-10-28_jakarta-map-analysis.md) and the cut-out boxes from [2026-11-11_tile-explorer.md](2026-11-11_tile-explorer.md).

**Result**: `tests/test_road_network.py`: 25 passed (synthetic grids, all 8 map orientations, and an end-to-end run of the three scripts on a synthetic map). One earlier failure unrelated to this work remains (`test_particle_io`, polars).
- **Not run on the real map.** The cloud cannot reach Overpass, and the map lives on the lab PC. `fetch_osm_roads.py` has to run on the lab PC first.
- The default road widths are assumed values, marked [U].

## Why these choices (from the brief)

- **OSM as the source.** The map's buildings are 2023 OSM data, so OSM roads match them. The roads are fetched "as of 2024-01-01" (the map was made Jan-Mar 2024) with Overpass's date filter. No road layer exists on the lab PC. The raw Overpass JSON is saved, so the fetch can be re-run offline.
- **Four classes.** 1 motorway/trunk, 2 primary/secondary, 3 tertiary/unclassified, 4 residential/living_street/service. Footways and paths are left out.
- **Width.** From the `width` tag, else `lanes` x 3.5 m, else a class default of 20 / 14 / 10 / 6 m (assumed [U]).
- **Elevated flag.** Jakarta has many flyovers and elevated toll roads. Ground sources cannot represent them, so they are left out of the sources by default (`--include-elevated` keeps them).
- **Points on the centreline every 16 m, not a source on every road cell.** Emission per road length then does not depend on road width, and the source count stays under the int32 ID limit of 214,748 (`id_digit` 4). The earlier user script put a source on every `building == 0` cell, which put 58 % of the sources at sea.
- **Drops.** A source is dropped inside building or tree cells, outside the land columns (sea fetch, south ramp, columns 7750-7939), or outside a cut-out `--box` (positions are then relative to the box corner).
- **Height.** z is absolute: topography + 1 m (`--z-offset`).
- **Position convention.** Cell i covers [i dx, (i+1) dx). The solver compares the particle x with cell edges in metres.
- **File format.** `particle_position.txt` copies `write_sources` of LBM-city `tools/lbmcase/gen_inputs`: `x y z u v w group id`, tab separated, id = n x 10^4 + 1, default velocity 0 0 0.1 (from `defaults.yaml`).

## Commit 7169840: road_network library and tests

| File | Change | Why |
|---|---|---|
| [physics_core/road_network.py](../physics_core/road_network.py) | New (198 lines). `HIGHWAY_CLASS` maps OSM `highway` tags to class 1-4. `DEFAULT_WIDTH = {1: 20, 2: 14, 3: 10, 4: 6}` m, `LANE_WIDTH = 3.5` m, tagged widths outside 2-60 m are ignored. | Classes and widths as in the plan. Defaults are assumed [U]. |
| same | `road_width(tags, class)` returns the width and its source (`width`, `lanes` or `default`). `classify_way` returns the attributes of one way, or None for non-roads and `area=yes`. | One place for the width rule. |
| same | `is_elevated` (bridge not `no`, or layer > 0) and `is_tunnel` (tunnel not `no`, or layer < 0). Raster codes: 0 none, 1-4 ground road, `ELEVATED` (10) + class for elevated (11-14). | Elevated roads are kept apart from ground roads. |
| same | `overpass_query(south, west, north, east, date)` builds `[out:json][timeout:180][date:"<date>T00:00:00Z"]; way["highway"](...); out geom;`. `overpass_ways` parses the answer. | Fetch as of the map snapshot. |
| same | `map_from_north_up` (inverse of `map_georef.north_up`) and `crs_to_map_xy` (inverse of `map_georef.cell_to_crs`). | Roads come in CRS metres, north-up. The map array has its own orientation, so both directions are needed. Tested for all 8 orientations. |
| same | `burn_order` and `rasterize_roads`: elevated first, then local to motorway, so the larger ground road wins where they overlap. A cell is road if its centre is inside the polygon (rasterio `all_touched=False`). Output `uint8 (ny, nx)` `[j, i]`. | Clear rule for overlaps. |
| same | `centreline_points(line, step)`: first point at step/2, then every step; one point in the middle if the line is shorter than step. | Source spacing independent of width. |
| same | `source_cell_ok(i, j, maps, land_columns, box)`: inside the map, land columns and box, and no building or tree (`object_heights`). | The drop rules above. |
| same | `write_particle_sources(folder, x, y, z, velocity, group, id_digit)` writes `particle_position.txt` and `particle_number.txt`. Raises `ValueError` if `(n + 1) * 10^id_digit > 2^31 - 1`. `write_map_dat` writes a `.dat` map. | Solver format; protects the int32 ID limit. |
| [tests/test_road_network.py](../tests/test_road_network.py) | New (151 lines, 25 tests with the orientation cases): inverses, width rules, class filter, burn order, Overpass query and parse, point spacing, an L-shaped road, drop rules, file format, and the three scripts end to end on a synthetic map. | Checks without the real map or internet. |

## Commit cd30156: the three scripts and the README

All three are in [scripts/jakarta-map-analysis/](../scripts/jakarta-map-analysis/).

| File | Change | Why |
|---|---|---|
| [fetch_osm_roads.py](../scripts/jakarta-map-analysis/fetch_osm_roads.py) | New (121 lines). Downloads OSM highway ways in the map box from Overpass and saves `roads.gpkg` (class, width, width source, elevated, tunnel, name) plus the raw JSON. Options: `--georef` (required), `--date` (default `2024-01-01`, `now` for current OSM), `--margin` (200 m), `--endpoint`, `--from-json` (offline re-run), `--out` (default `<georef folder>/roads`). | Gets the data. Needs the internet, so lab PC only. |
| [rasterize_roads.py](../scripts/jakarta-map-analysis/rasterize_roads.py) | New (191 lines). Burns the roads into the 2 m grid: `road_class.npy` and `road.dat` (0 none, 1-4 class, 11-14 elevated). Per class: length, area, share of land, share under buildings and trees; share of open land that is road; overlay and zoom figures (`--candidates` gives one zoom per box, `--no-figures` skips them). | A check of the default widths against the map's own building gaps. `road.dat` is not read by the solver. |
| [place_road_sources.py](../scripts/jakarta-map-analysis/place_road_sources.py) | New (192 lines). Sources every `--step` m (16) along the centrelines of `--classes` (default 1 2 3 4). Options: `--z-offset` (1.0), `--include-elevated`, `--box` (4 numbers or a candidate name), `--velocity` (0 0 0.1). Writes `<out>/roads/sources_<name>/`: `road_sources.csv`, `particle_position/`, `sources_summary.csv`, `sources_<name>.png`. Warns above 125,000 sources (half of `STACK_LIMIT_SOURCES` = 250,000) and refuses to write `particle_position` above the ID limit 214,748. | The deliverable: the two sets `--name all --classes 1 2 3 4` and `--name main --classes 1 2`. |
| [README.md](../scripts/jakarta-map-analysis/README.md) | New command block and three table rows; `road_network.py` added to "Library code". | Make the scripts findable. |

## Known caveats

- `Generate_Particle.cu` keeps the sources in 8 stack arrays of 4 bytes each, so an 8 MB stack holds about 250,000 sources [U, stack size on TSUBAME not checked]. The script warns from 125,000 (half of that); the solver itself does not warn.
- `road.dat` is not read by the solver; it is for checking only.
- The default widths and the 3.5 m lane width are assumed, not from a reference [U]. Judge them by the "share under buildings" numbers from `rasterize_roads.py`.
- Elevated roads and tunnels are absent from the sources unless `--include-elevated` is given.

## What was deliberately left alone

- Footways, paths and tracks are not fetched as roads.
- No traffic volumes or emission weights: one source per 16 m, all equal.
- No solver changes.
- Nothing was run on the real map.

## How to check

```sh
pytest tests/test_road_network.py                      # 25 tests, synthetic
# on the lab PC (internet needed for the first step), M = map folder, G = georef.yaml
python scripts/jakarta-map-analysis/fetch_osm_roads.py --georef $G
python scripts/jakarta-map-analysis/rasterize_roads.py $M --georef $G --roads <out>/roads/roads.gpkg --land-columns 1279 7750
python scripts/jakarta-map-analysis/place_road_sources.py $M --georef $G --roads <out>/roads/roads.gpkg --land-columns 1279 7750 --name all  --classes 1 2 3 4
python scripts/jakarta-map-analysis/place_road_sources.py $M --georef $G --roads <out>/roads/roads.gpkg --land-columns 1279 7750 --name main --classes 1 2
```

Still to do on the lab PC: run the fetch, look at the overlay figures, check the share of road cells under buildings, and the source counts against the limits above.
