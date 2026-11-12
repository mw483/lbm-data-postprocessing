"""
Download the OpenStreetMap roads inside a located map and save them as road lines.

Purpose: the road layer for placing particle sources on streets (professor's
task, 2026-11). The map's buildings are 2023 OSM, so the roads come from OSM
too, by default as OSM was on 2024-01-01 (the map was made Jan-Mar 2024), so
that streets and buildings are the same snapshot.

    pip install -e .[gis]
    python scripts/jakarta-map-analysis/fetch_osm_roads.py --georef <out>/georef.yaml            # -> <out>/roads/
    python scripts/jakarta-map-analysis/fetch_osm_roads.py --georef <out>/georef.yaml \\
        --from-json <out>/roads/osm_roads_2024-01-01.json                                         # offline, re-classify only

Needs the internet (one request to the public Overpass API, a few MB). The raw
answer is saved next to the result, so later runs can use --from-json.

Output (<out>/roads/):
- osm_roads_<date>.json  raw Overpass answer (all highway ways in the box)
- roads.gpkg             kept roads as lines in the georef CRS; columns osm_id,
                         highway, road_class (1 motorway/trunk, 2 primary/secondary,
                         3 tertiary/unclassified, 4 residential/living_street/service),
                         width_m, width_from (width | lanes | default), elevated, tunnel, name
- roads_fetch.csv        ways per highway tag, kept or not, total length [km]
Classes, widths and what is left out: physics_core/road_network.py.
"""
import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from data_loaders.map_georef import cell_to_lonlat, load_georef
from physics_core.road_network import classify_way, overpass_query, overpass_ways

ENDPOINT = "https://overpass-api.de/api/interpreter"


def lonlat_box(geo, margin_m):
    """(south, west, north, east) in degrees around the map, with a margin in metres."""
    m = margin_m / geo["cell_size"]
    ii = np.array([-m, -m, geo["nx"] - 1 + m, geo["nx"] - 1 + m])
    jj = np.array([-m, geo["ny"] - 1 + m, -m, geo["ny"] - 1 + m])
    lon, lat = cell_to_lonlat(ii, jj, geo)
    return float(np.min(lat)), float(np.min(lon)), float(np.max(lat)), float(np.max(lon))


def download(query, endpoint, path):
    print(f"Asking {endpoint} ...")
    body = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(endpoint, data=body, headers={"User-Agent": "lbm-data-postprocessing road fetch"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    if "remark" in data:
        print(f"[WARN] Overpass remark: {data['remark']}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"Saved {path}")
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--georef", required=True, help="georef.yaml of the map (fit_map_location.py)")
    ap.add_argument("--date", default="2024-01-01", help="OSM as of this date, YYYY-MM-DD; 'now' for current OSM")
    ap.add_argument("--margin", type=float, default=200.0, help="extra margin around the map [m]")
    ap.add_argument("--endpoint", default=ENDPOINT, help="Overpass API URL")
    ap.add_argument("--from-json", help="use a saved Overpass answer instead of downloading")
    ap.add_argument("--out", help="output folder (default <georef folder>/roads)")
    args = ap.parse_args()

    import geopandas as gpd
    from shapely.geometry import LineString

    geo = load_georef(args.georef)
    out = Path(args.out) if args.out else Path(args.georef).parent / "roads"
    out.mkdir(parents=True, exist_ok=True)
    date = None if args.date == "now" else args.date

    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        box = lonlat_box(geo, args.margin)
        print(f"Box S {box[0]:.5f} W {box[1]:.5f} N {box[2]:.5f} E {box[3]:.5f}, date {date or 'now'}")
        data = download(overpass_query(*box, date=date), args.endpoint, out / f"osm_roads_{args.date}.json")

    rows, geoms, skipped = [], [], []
    for osm_id, tags, coords in overpass_ways(data):
        if len(coords) < 2:
            continue
        a = classify_way(tags)
        line = LineString(coords)
        if a is None:
            skipped.append({"highway": tags.get("highway", ""), "geometry": line})
            continue
        rows.append({"osm_id": osm_id, **a})
        geoms.append(line)
    if not rows:
        raise SystemExit("[ERROR] no roads in the answer")
    roads = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326").to_crs(geo["crs"])
    roads.to_file(out / "roads.gpkg", driver="GPKG")
    print(f"Saved {len(roads)} roads to {out / 'roads.gpkg'}")

    # inventory: ways and length per highway tag, kept or not
    rest = gpd.GeoDataFrame(skipped, geometry="geometry", crs="EPSG:4326").to_crs(geo["crs"]) if skipped else None
    parts = [pd.DataFrame({"highway": roads["highway"], "kept": True, "km": roads.length / 1000.0})]
    if rest is not None:
        parts.append(pd.DataFrame({"highway": rest["highway"], "kept": False, "km": rest.length / 1000.0}))
    inv = (pd.concat(parts).groupby(["kept", "highway"])["km"].agg(ways="size", km="sum")
           .reset_index().sort_values(["kept", "km"], ascending=[False, False]))
    inv.to_csv(out / "roads_fetch.csv", index=False)
    print(inv.to_string(index=False))
    print(f"Width from tag: {(roads['width_from'] != 'default').mean():.1%} of roads; "
          f"elevated {roads['elevated'].sum()}, tunnels {roads['tunnel'].sum()}")


if __name__ == "__main__":
    main()
