# 3D map viewer: roads, view names, cut-out coordinates, map.yaml (2026-11-16)

**Commits**: `c3482a6`, `1d42e78` (range `bff1565..1d42e78`, branch `analysis/scalar2-outputs`)

**Goal**: kaka asked (2026-11-16) for three things in the universal 3D viewer `scripts/view_map_3d.py`:

1. Show the Jakarta roads in 3D, as colouring, whenever the Jakarta map is opened.
2. Write the case or candidate name automatically when saving an image.
3. For Jakarta, write the coordinates of the cut-out.

Builds on the road raster from [2026-11-12_road-sources.md](2026-11-12_road-sources.md) and the viewer and cut-out boxes from [2026-10-16_map-3d-viewer.md](2026-10-16_map-3d-viewer.md) and [2026-11-11_tile-explorer.md](2026-11-11_tile-explorer.md).

**Result**: tests: 145 passed. One failure that is not from this work remains: `test_particle_io::test_streamed_trajectories_read_11_column_file`. Offscreen renders of a synthetic 400 x 200 map with roads (box J1, whole map at stride 4, and `--no-roads`) looked right.

- **Not run on the real Jakarta map.** The cloud has no map data; this must be tried on the lab PC.
- **Window mode (`s` key) not tried interactively.** It goes through the same code path as `--save` (`write_location`), but nobody pressed the key.

## Decisions (kaka approved the plan)

- **`map.yaml` next to the `.dat` files.** It names the map and points to the georef, the road raster and the candidates, so the viewer finds them without flags. This is the first piece of the map library proposal `planning/map_library_proposal_2026-11-12.md` (a project file, not in this repo). Flags `--roads`, `--georef` and `--no-roads` override it. A map without `map.yaml` (flat, cube maps) looks as before.
- **Road coarsening rule.** A coarse block takes the smallest non-zero code, so the biggest road wins and elevated roads (11-14) lose to ground roads. This is the same rule as the 2D `roads_overlay.png` from `rasterize_roads.py`.
- **Road drawing.** Flat tiles 0.2 m above the ground, one mesh per class, colours as in `rasterize_roads.py`, plus a legend. Roads under buildings are hidden inside the building, not cut out.
- **Pale ground when roads are shown.** The `terrain` colormap's blues and greens clashed with the road colours in a test render, so with roads the ground uses a pale two-tone ramp (`#f5f2ea` to `#a89f8c`). Without roads the old colormap stays.
- **Names.** `<map>_<box>_NN.png`, `<map>_crop_i0-i1_j0-j1`, or `<map>` for the whole map; the name is also written as a title on the image. A bug is fixed on the way: a folder called `map` used to give `map_01.png`; the name is now the `map.yaml` name or the parent folder's name. `--save` without a value writes `<figures>/map_3d/<name>.png`.
- **Coordinates.** Cell edges (not centres), corners in the CRS and in lon/lat, centre, size, and which real direction map x and y point to. Written on the image (lower left) and into `<png>.yaml` next to every PNG, from the `s` key and from `--save`.
- **Left out on purpose.** `scripts/jakarta-map-analysis/explore_tiles.py` is not changed: its `v` key still opens the viewer with `--crop`, so images from there are named `crop_...`, not with the candidate name.

## Commit `c3482a6`: library pieces and tests

| File:function | What changed | Why |
|---|---|---|
| `data_loaders/map_meta.py` (new):`load_map_meta` | Reads `<map_dir>/map.yaml` (keys `name`, `georef`, `roads`, `candidates`, all optional). Path keys become `Path`, relative ones are taken from the folder holding `map.yaml`. Returns `{}` without the file. | One place that finds the extra layers of a map. |
| `data_loaders/map_meta.py`:`map_label` | `map.yaml` name, else folder name, or the parent's name when the folder is called `map`. | Fixes `map_01.png` names. |
| `data_loaders/map_meta.py`:`load_road_raster` | Loads `road_class.npy` or `road.dat` as uint8 `[j, i]`. | Reads what `rasterize_roads.py` writes. |
| `data_loaders/map_georef.py`:`box_location` | Dict for a cell box `[i0, i1, j0, j1]` (end exclusive): `box_cells`, `box_m`, `size_m`, `crs`, `corners_crs`, `corners_lonlat`, `centre_crs`, `centre_lonlat`, `x_points`, `y_points`. Edges use `cell_to_crs` at `i - 0.5`, because that function gives the cell centre. Needs pyproj. Also new: `AXIS_WORDS`. | Coordinates of the cut-out (item 3). |
| `plotting_core/map_3d.py`:`crop_and_coarsen_codes` | Crops and trims a code raster like `crop_and_coarsen`; coarse blocks take the smallest non-zero code. | Roads must line up with the coarsened map. |
| `plotting_core/map_3d.py`:`flat_tiles` | One horizontal quad per masked cell at height `z[j, i]`; `None` if no cell. | Road tiles. |
| `plotting_core/map_3d.py`:`road_layers` | One mesh per group (`motorway` 1, `arterial` 2, `collector` 3, `local` 4, `elevated` 11-14); empty groups left out; height = ground x zscale + lift. | Road colouring by class. |
| `plotting_core/pyvista_helpers.py`:`add_snapshot_key` | New optional `on_save(path)` callback, run after each screenshot. | Lets the `s` key write the `.yaml` next to the PNG. Default `None`, so other callers are unchanged. |
| `tests/test_map_3d.py` | Five new tests: `test_codes_coarsen_keeps_biggest_road_and_ground_over_elevated`, `test_road_layers_one_tile_per_cell_above_ground`, `test_map_meta_paths_relative_to_map_folder`, `test_box_location_corners_are_cell_edges` (for the Jakarta georef), `test_view_names`. | Checks for the above. |

Note: `test_view_names` tests `view_name`, which is added in `1d42e78`. The two commits belong together; `c3482a6` alone is not self-consistent for that test (checked: the test needs both commits).

## Commit `1d42e78`: viewer, READMEs

| File:function | What changed | Why |
|---|---|---|
| `scripts/view_map_3d.py`:`main` | New flags `--roads`, `--no-roads`, `--georef`; `--save` now takes an optional value. Reads `map.yaml`; candidates, roads and georef come from it unless a flag is given. `--box` also accepts candidates from `map.yaml`. Road layers are added after the trees, with a legend. A road raster whose shape differs from the map stops with an error. Title text (upper left) and, with a georef, the location text (lower left). | Items 1 to 3. |
| `scripts/view_map_3d.py`:`main` (ground colour) | Ground uses the pale ramp when roads are shown. | See decisions. |
| `scripts/view_map_3d.py`:`view_name` (new) | `<map>_<box>`, `<map>_crop_i0-i1_j0-j1`, or `<map>`. | Item 2. |
| `scripts/view_map_3d.py`:`location_text`, `write_location` (new) | Text lines for the image (cells, metres, centre and corners as lat, lon, axis directions); `<png>.yaml` with `view` plus the `box_location` numbers. | Item 3. |
| `scripts/view_map_3d.py`:`resolve_inputs` | For a plain folder the label is now `None`, so `main` takes it from `map_label`. | Fixes the `map` folder name. |
| `scripts/view_map_3d.py`:`main` (save) | `--save` writes to `<figures>/map_3d/<name>.png` without a value; `s` key snapshot uses the name and, with a georef, writes the `.yaml` through `on_save`. | Items 2 and 3. |
| `README.md`, `scripts/jakarta-map-analysis/README.md` | Example command `view_map_3d.py <map> --box J1 --save` and what `map.yaml` adds. | Usage. |

## How it was checked

- `pytest`: 145 passed, 1 unrelated failure (above).
- Offscreen renders of a synthetic 400 x 200 map with roads: box J1, whole map at stride 4, `--no-roads`. Looked right; the renders are not saved in the repo.

**Not checked**: the real Jakarta map; window mode and the `s` key interactively; lon/lat of a real box against a known place [U]. The whole-map corners from `box_location` on the Jakarta georef.yaml match its `corners_lonlat` to within one cell (106.85678 E, 6.09174 S vs 106.856771, 6.09175 for cell (0, 0)).

Note on `--save` without a value: put the map folder before it (`view_map_3d.py F:/.../map --box J1 --save`), otherwise argparse takes the folder as the PNG path.

## Open items and known limits

- `explore_tiles.py` `v` key gives `crop_...` names (see decisions).
- Roads under buildings are hidden inside the building, not cut.
- Coarse views widen roads as they widen buildings (smallest-code rule); pick on a `--stride 1` crop.
- A `map.yaml` still has to be written by hand on the lab PC (the example is in the docstring of `data_loaders/map_meta.py`, with the lab PC paths).
- Inferred, not tried: `--save` now takes an optional value, so a `--save` placed directly before the map folder on the command line would take the folder as its value (argparse behaviour; put the folder first, as in the README examples).

## How to see the change

```sh
git log --oneline bff1565..1d42e78
git diff bff1565..1d42e78 --stat
git diff -w bff1565..1d42e78 -- scripts/view_map_3d.py plotting_core data_loaders
pytest tests/test_map_3d.py
python scripts/view_map_3d.py <map folder with map.yaml> --box J1 --save   # lab PC
```
