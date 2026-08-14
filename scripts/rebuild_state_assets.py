"""Rebuild the US state geometry assets for choropleth charts.

Source: US Census Bureau TIGER/Line cartographic boundary files
(cb_2018_us_state_5m). Outputs:

- viz/assets/us-states.geojson      (interactive Plot.geo)
- viz/assets/us-states-polygons.csv (static R geom_polygon)

CRITICAL — topology-preserving simplification:
  Simplifying each state INDEPENDENTLY (shapely .simplify per feature,
  even with preserve_topology=True) keeps different vertices on each side
  of shared borders, producing white slivers between states (the
  UT/CO/WY/KS/TX/TN glitch, commit 1fc72b8). This script therefore shells
  out to mapshaper, which simplifies shared ARCS once so borders stay
  snapped, then post-processes with shapely. Do not reintroduce
  per-feature simplification.

Geometry rules that matter for the two renderers:

- Exteriors must be CLOCKWISE in lon/lat (shapely orient(sign=-1.0)).
  d3-geo fills the area to the left of a ring's traversal, so shapely's
  planar CCW convention inverts every state into a full-frame rectangle.
  ggplot does not care about winding.
- Micro-islands are dropped by mapshaper (-filter-islands min-area=0.05):
  they make d3's frame clip emit full-viewport rects.
- Duplicate closing points are stripped (d3 closes rings itself; a stored
  first==last point creates a degenerate segment).

Requires: pyshp not needed (mapshaper reads the .shp directly); shapely;
Node/npx for mapshaper. The source shapefile must be extracted first:
  unzip cb_2018_us_state_5m.zip -d /tmp/census_shp/

Verification: the script measures total pairwise overlap area between all
state pairs after processing (sliver detector) and fails loudly if any
pair overlaps by more than 1e-6 deg^2. ALSO run scripts/map_holes.py
against a rendered choropleth before committing new geometry.
"""

from __future__ import annotations

import csv
import itertools
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.geometry.polygon import orient

OUT = Path(__file__).resolve().parent.parent / "viz" / "assets"
SHP = "/tmp/census_shp/cb_2018_us_state_5m.shp"

# Drop territories (PR, VI, GU, AS, MP). AK and HI are KEPT: the albers-usa
# projection draws them as inset boxes, and the ACS data includes them.
MAPSHAPER_FILTER = 'STUSPS!="PR" && STUSPS!="VI" && STUSPS!="GU" && STUSPS!="AS" && STUSPS!="MP"'

# 12% of removable vertices retained, keep-shapes prevents ring collapse.
# Matches the geometry validated in commit a6c61d0 (9,695 enclosed-white px,
# max component 278 px, vs 59,988 px with per-feature simplification).
SIMPLIFY = "12%"
MAX_PAIR_OVERLAP_DEG2 = 1e-6


def run_mapshaper(dst: Path) -> None:
    cmd = [
        "npx",
        "-y",
        "mapshaper",
        SHP,
        "-filter",
        MAPSHAPER_FILTER,
        "-simplify",
        SIMPLIFY,
        "keep-shapes",
        "-filter-islands",
        "min-area=0.05",
        "-o",
        "format=geojson",
        "precision=0.001",
        str(dst),
        "force",
    ]
    subprocess.run(cmd, check=True)


def postprocess(src: Path) -> list[dict]:
    g = json.loads(src.read_text())
    features = []
    for f in g["features"]:
        p = f["properties"]
        geom = shape(f["geometry"])
        oriented = orient(geom, sign=-1.0)  # type: ignore[arg-type]  # d3: CW exteriors in lon/lat
        gj = mapping(oriented)
        polys = gj["coordinates"] if gj["type"] == "MultiPolygon" else [gj["coordinates"]]
        for pi, poly in enumerate(polys):
            poly = [list(r) for r in poly]
            for ri, ring in enumerate(poly):
                ring = [list(c) for c in ring]
                if len(ring) > 1 and ring[0] == ring[-1]:
                    ring.pop()  # d3 closes rings itself
                poly[ri] = ring
            polys[pi] = poly
        gj["coordinates"] = polys if gj["type"] == "MultiPolygon" else polys[0]
        features.append(
            {
                "type": "Feature",
                "properties": {"name": p["NAME"], "stusps": p["STUSPS"], "statfp": p["STATEFP"]},
                "geometry": gj,
            }
        )
    return features


def verify_no_slivers(features: list[dict]) -> None:
    geoms = {f["properties"]["stusps"]: shape(f["geometry"]) for f in features}
    worst = 0.0
    for a, b in itertools.combinations(sorted(geoms), 2):
        area = geoms[a].intersection(geoms[b]).area
        if area > worst:
            worst = area
        if area > MAX_PAIR_OVERLAP_DEG2:
            sys.exit(f"SLIVER: {a}-{b} overlap {area:.2e} deg^2 — geometry not snapped")
    print(f"sliver check OK: max pairwise overlap {worst:.2e} deg^2")


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "us-states-ms.geojson"
        run_mapshaper(tmp)
        features = postprocess(tmp)

    verify_no_slivers(features)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "us-states.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features})
    )

    csv_rows: list[list[object]] = []
    for f in features:
        p = f["properties"]
        polys = (
            f["geometry"]["coordinates"]
            if f["geometry"]["type"] == "MultiPolygon"
            else [f["geometry"]["coordinates"]]
        )
        for pi, poly in enumerate(polys):
            for ri, ring in enumerate(poly):
                ring_id = f"{p['stusps']}:{pi}:{ri}"
                for vi, (lon, lat) in enumerate(ring):
                    csv_rows.append([p["name"], p["stusps"], ring_id, vi, lon, lat])
    with (OUT / "us-states-polygons.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "stusps", "ring", "order", "lon", "lat"])
        w.writerows(csv_rows)

    print(f"wrote {len(features)} features -> viz/assets/us-states.geojson")
    print(f"wrote {len(csv_rows)} vertices -> viz/assets/us-states-polygons.csv")
    print("REMINDER: render a choropleth and run scripts/map_holes.py before committing.")


if __name__ == "__main__":
    main()
