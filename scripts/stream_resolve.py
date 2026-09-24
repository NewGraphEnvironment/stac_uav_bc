#!/usr/bin/env python3
# Resolve candidate FWA stream names for a flight, to fill data/sites.csv.
#
# Reads the GPS in each dataset's images/ EXIF, takes the flight centroid, and
# asks the public fwapg REST API (features.hillcrestgeo.ca — no SSH tunnel, no
# local Postgres) for the nearest streams. Prints candidates with their distance
# so a human picks the row value; the registry is the source of truth and this
# never writes to it.
#
# The distance is what the registry's `guess_nearest_<n>m` name_source records,
# so re-running this on an already-registered dataset reproduces that number —
# which is the positive control that the method still matches the one the
# existing rows were built with.
#
# Usage:
#   python3 scripts/stream_resolve.py <project-dir> [<project-dir>...]
#
# project-dir is a dataset dir holding images/, e.g.
#   /Users/airvine/Projects/gis/uav_imagery/skeena/morice/2026/wedzin_pimpernel
import json
import pathlib
import sys
import urllib.parse
import urllib.request

from PIL import ExifTags, Image

API = "https://features.hillcrestgeo.ca/fwa/functions/fwa_indexpoint/items.json"
TIMEOUT = 30  # a hung fetch must fail loud rather than stall the run
GPS_TAG = {v: k for k, v in ExifTags.GPSTAGS.items()}
EXIF_TAG = {v: k for k, v in ExifTags.TAGS.items()}


def _dms(val, ref):
    d, m, s = (float(x) for x in val)
    deg = d + m / 60 + s / 3600
    return -deg if ref in ("S", "W") else deg


def image_points(proj):
    """(lon, lat, capture-time) for every image in proj/images that carries GPS."""
    pts = []
    for p in sorted(pathlib.Path(proj, "images").glob("*.JPG")):
        with Image.open(p) as im:
            ex = im.getexif()
            gps = ex.get_ifd(EXIF_TAG["GPSInfo"])
            if not gps:
                continue
            pts.append((
                _dms(gps[GPS_TAG["GPSLongitude"]], gps[GPS_TAG["GPSLongitudeRef"]]),
                _dms(gps[GPS_TAG["GPSLatitude"]], gps[GPS_TAG["GPSLatitudeRef"]]),
                ex.get(EXIF_TAG["DateTime"]),
            ))
    return pts


def nearest_streams(lon, lat, limit=5, tolerance=5000):
    q = urllib.parse.urlencode({
        "x": lon, "y": lat, "srid": 4326,
        "tolerance": tolerance, "num_features": limit, "limit": limit,
    })
    with urllib.request.urlopen(f"{API}?{q}", timeout=TIMEOUT) as r:
        feats = json.load(r)["features"]
    return [f["properties"] for f in feats]


def main(projs):
    if not projs:
        sys.exit(f"usage: {pathlib.Path(sys.argv[0]).name} project-dir [project-dir ...]")
    for proj in projs:
        proj = proj.rstrip("/")
        name = pathlib.Path(proj).name
        if not pathlib.Path(proj, "images").is_dir():
            print(f"=== {name}\n    SKIP: no images/ under {proj}")
            continue
        pts = image_points(proj)
        if not pts:
            print(f"=== {name}\n    SKIP: no GPS in any image")
            continue
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        print(f"=== {name}  ({len(pts)} images, {pts[0][2]} -> {pts[-1][2]})")
        print(f"    centroid {lon:.6f}, {lat:.6f}")
        for s in nearest_streams(lon, lat):
            gnis = s["gnis_name"] or "(unnamed)"
            print(f"    {s['distance_to_stream']:8.1f} m  {gnis:<28}"
                  f" blk={s['blue_line_key']}  wscode={s['wscode_ltree']}")


if __name__ == "__main__":
    main(sys.argv[1:])
