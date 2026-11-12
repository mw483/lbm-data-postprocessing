"""
Roads on an LBM-city map grid: OSM road classes and widths, burning road
polygons into the 2 m grid, and particle sources along road centrelines.

Used by scripts/jakarta-map-analysis/{fetch_osm_roads,rasterize_roads,place_road_sources}.py.
Plan: planning/jakarta_road_sources_plan_2026-11-12.md (project files).

Conventions
- Map arrays are (ny, nx) indexed [j, i], as read from the .dat files.
- Map positions in metres: cell i covers x in [i*dx, (i+1)*dx), likewise j / y.
  The solver compares particle x with cell edges in metres (Generate_Particle_GPU.cu),
  and the flat cases put sources on these coordinates.
- Road class codes in the raster: 0 = no road, 1-4 = ground road (table below),
  ELEVATED + class = bridge / flyover / layer > 0 (e.g. 11 = elevated motorway).
"""
import numpy as np

# OSM highway tag -> class. 1 motorway, 2 arterial, 3 collector, 4 local.
HIGHWAY_CLASS = {
    "motorway": 1, "motorway_link": 1, "trunk": 1, "trunk_link": 1,
    "primary": 2, "primary_link": 2, "secondary": 2, "secondary_link": 2,
    "tertiary": 3, "tertiary_link": 3, "unclassified": 3,
    "residential": 4, "living_street": 4, "service": 4,
}
CLASS_NAMES = {1: "motorway", 2: "arterial", 3: "collector", 4: "local"}
# Carriageway width [m] used when a way has neither a width nor a lanes tag.
# Assumed values (plan sec. 2), not from a reference [U]; checked against the map's
# building gaps in rasterize_roads.py (road cells under buildings).
DEFAULT_WIDTH = {1: 20.0, 2: 14.0, 3: 10.0, 4: 6.0}
LANE_WIDTH = 3.5          # m per lane when only lanes is tagged [U, common design value]
MIN_WIDTH, MAX_WIDTH = 2.0, 60.0   # tagged widths outside this are treated as errors
ELEVATED = 10


def _number(text):
    """First number in an OSM tag value ('7 m', '3;2', '12.5'), or None."""
    if text is None:
        return None
    s = str(text).replace(",", ".").split(";")[0].strip().lower().replace("m", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def road_width(tags, road_class):
    """(width [m], where it came from: 'width' | 'lanes' | 'default')."""
    w = _number(tags.get("width"))
    if w is not None and MIN_WIDTH <= w <= MAX_WIDTH:
        return w, "width"
    lanes = _number(tags.get("lanes"))
    if lanes is not None and 1 <= lanes <= 16:
        return lanes * LANE_WIDTH, "lanes"
    return DEFAULT_WIDTH[road_class], "default"


def is_elevated(tags):
    """True for bridges, flyovers and ways drawn above ground (layer > 0)."""
    if tags.get("bridge") not in (None, "no"):
        return True
    layer = _number(tags.get("layer"))
    return layer is not None and layer > 0


def is_tunnel(tags):
    return tags.get("tunnel") not in (None, "no") or (_number(tags.get("layer")) or 0) < 0


def classify_way(tags):
    """Dict of road attributes for one OSM way's tags, or None if it is not a road we keep."""
    c = HIGHWAY_CLASS.get(tags.get("highway"))
    if c is None or tags.get("area") == "yes":
        return None
    w, src = road_width(tags, c)
    return {"highway": tags["highway"], "road_class": c, "width_m": w, "width_from": src,
            "elevated": is_elevated(tags), "tunnel": is_tunnel(tags), "name": tags.get("name", "")}


def overpass_query(south, west, north, east, date=None, timeout=180):
    """Overpass QL for all highway ways in a lon/lat box, with geometry; date = 'YYYY-MM-DD' for OSM as it was then."""
    head = f'[out:json][timeout:{timeout}]'
    if date:
        head += f'[date:"{date}T00:00:00Z"]'
    return f'{head};way["highway"]({south},{west},{north},{east});out geom;'


def overpass_ways(data):
    """(tags, [(lon, lat), ...]) for each way in an Overpass JSON answer that has geometry."""
    for el in data.get("elements", []):
        if el.get("type") == "way" and el.get("geometry"):
            yield el["id"], el.get("tags", {}), [(p["lon"], p["lat"]) for p in el["geometry"]]


def map_from_north_up(img, orientation):
    """Inverse of data_loaders.map_georef.north_up: a north-up image back to the (ny, nx) map array [j, i]."""
    i_dir, j_dir = (p.split(":")[1] for p in orientation.split(","))
    row_dir, col_dir = (i_dir, j_dir) if i_dir in "NS" else (j_dir, i_dir)
    a = img
    if col_dir == "W":
        a = a[:, ::-1]
    if row_dir == "N":
        a = a[::-1, :]
    return a.T if i_dir in "NS" else a


def crs_to_map_xy(e, n, geo):
    """Map position (x, y) in metres of CRS points (easting, northing); inverse of map_georef.cell_to_crs."""
    d = geo["cell_size"]
    col = (np.asarray(e, float) - geo["e_topleft"]) / d      # continuous, 0 at the image's west edge
    row = (geo["n_topleft"] - np.asarray(n, float)) / d      # continuous, 0 at the image's north edge
    i_dir, j_dir = (p.split(":")[1] for p in geo["orientation"].split(","))
    ni, nj = geo["nx"], geo["ny"]
    if i_dir in "NS":
        i = row if i_dir == "S" else ni - row
        j = col if j_dir == "E" else nj - col
    else:
        j = row if j_dir == "S" else nj - row
        i = col if i_dir == "E" else ni - col
    return i * d, j * d


def burn_order(road_class, elevated):
    """Sort key: elevated roads first, then local -> motorway, so the larger ground road wins where they overlap."""
    return (0 if elevated else 1, -int(road_class))


def rasterize_roads(geoms, codes, geo):
    """
    uint8 map array (ny, nx) [j, i] of road class codes. geoms = road polygons in
    geo['crs'] (lines already buffered to their width), codes = class code per polygon,
    burnt in the given order (later polygons overwrite earlier ones). A cell is road
    if its centre is inside a polygon (rasterio default, all_touched=False).
    """
    from rasterio.features import rasterize
    from data_loaders.map_georef import image_shape, image_transform
    shapes = [(g, int(c)) for g, c in zip(geoms, codes) if g is not None and not g.is_empty]
    img = rasterize(shapes, out_shape=image_shape(geo), transform=image_transform(geo),
                    fill=0, dtype="uint8") if shapes else np.zeros(image_shape(geo), np.uint8)
    return np.ascontiguousarray(map_from_north_up(img, geo["orientation"]))


def centreline_points(line, step):
    """Points every `step` m along a shapely line, the first at step/2 (one at the middle if shorter than step)."""
    length = line.length
    if length <= 0:
        return []
    dist = np.arange(step / 2.0, length, step) if length > step else np.array([length / 2.0])
    return [line.interpolate(float(s)) for s in dist]


def source_cell_ok(i, j, maps, land_columns=None, box=None):
    """
    Boolean mask for integer cells (i, j); maps = load_map_set dict ("topo", "build", "veg").
    True when inside the map (or box = [i0, i1, j0, j1], end
    exclusive), inside the land columns, not inside a building or a tree.
    """
    from physics_core.urban_morphology import object_heights
    hb, hv = object_heights(maps)
    ny, nx = hb.shape
    i, j = np.asarray(i), np.asarray(j)
    ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny)
    if land_columns is not None:
        ok &= (i >= land_columns[0]) & (i < land_columns[1])
    if box is not None:
        ok &= (i >= box[0]) & (i < box[1]) & (j >= box[2]) & (j < box[3])
    ic, jc = np.clip(i, 0, nx - 1), np.clip(j, 0, ny - 1)
    ok &= (hb[jc, ic] <= 0) & (hv[jc, ic] <= 0)
    return ok


def write_particle_sources(folder, x, y, z, velocity=(0.0, 0.0, 0.1), group=1, id_digit=4):
    """
    particle_position.txt (x y z u v w group id, tab separated, id = source * 10^id_digit + 1)
    and particle_number.txt, in the format of LBM-city tools/lbmcase/gen_inputs.write_sources.
    Velocity default = cases/defaults.yaml. Raises if the IDs overflow the solver's int32.
    """
    from pathlib import Path
    n = len(x)
    if (n + 1) * 10 ** id_digit > 2**31 - 1:
        raise ValueError(f"[ERROR] {n} sources overflow int32 particle IDs with id_digit {id_digit}")
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    u, v, w = velocity
    with open(out / "particle_position.txt", "w", newline="\n") as f:
        for k in range(n):
            f.write("%.6f\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f\t%d\t%d\n"
                    % (x[k], y[k], z[k], u, v, w, group, (k + 1) * 10 ** id_digit + 1))
    with open(out / "particle_number.txt", "w", newline="\n") as f:
        f.write("%d\n" % n)
    return n


def write_map_dat(path, arr, fmt="%d"):
    """A (ny, nx) array as an LBM-city style .dat: line 1 'nx<TAB>ny', then ny rows of nx tab-separated values."""
    ny, nx = arr.shape
    with open(path, "w", newline="\n") as f:
        f.write("%d\t%d\n" % (nx, ny))
        np.savetxt(f, arr, fmt=fmt, delimiter="\t")
