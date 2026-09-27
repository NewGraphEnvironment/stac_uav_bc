#!/usr/bin/env python3
# Plan a UAV survey over a floodplain polygon and write one .kmz per battery (#26).
#
# Reads the floodplain delineation straight from the published stac-floodplains-bc
# asset over /vsicurl/ (no download), selects a named reach, clips it to a working
# radius of the launch point, splits it into blocks that each fit one battery, lays
# serpentine transects, and writes a DJI WPML mission per block.
#
# The three modules it orchestrates each carry their own gate, and each is worth
# running before trusting an output here:
#   flight_coverage.py --selftest   camera model vs the flown missions
#   flight_budget.py   --selftest   endurance vs the seven flown missions (system python3)
#   flight_wpml.py     --roundtrip  writer vs the five Map Pilot exports
#
# Idempotent: re-running overwrites the same block .kmz files in --out and nothing
# else, so an interrupted run is safe to repeat.
#
# Usage (conda `dff` is the only env with geopandas/fiona/GDAL):
#   conda run -n dff python scripts/flight_plan.py \
#     --stream "Peacock Creek" --launch -126.79270 54.36067 \
#     --height 350 --batteries 3 --out /tmp/peacock
#
# --validate-fixtures checks the BUDGET VERDICT against the five Map Pilot
# missions, using each mission's own wpml:distance. It does not exercise the
# splitter, and it is a coarse check: the fixture path lengths sit far either side
# of the cutoff, so any sizing speed in roughly 2.3-8.8 m/s passes it. The speed
# constant itself is pinned in flight_budget.py --selftest, against the measured
# per-flight minimum.
import argparse
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import geopandas as gpd
from shapely import affinity
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

import flight_budget as budget
import flight_coverage as cov
from flight_wpml import Mission, Waypoint, gimbal_action, photo_action, write_kmz

# The published floodplain asset. Either MORR item carries the same delineation --
# both report identical ff02/ff04/ff06 areas and differ only in species scenario.
FLOODPLAIN_GPKG = ("/vsicurl/https://stac-floodplains-bc.s3.us-west-2.amazonaws.com/"
                   "morr_ch_ff06/floodplain.gpkg")
DEFAULT_LAYER = "co_ff04_by_gnis_name"
CRS_METRIC = "EPSG:3005"   # BC Albers; every distance and area below is in metres
CRS_WGS84 = "EPSG:4326"

# Fixture path lengths, read from each mission's own wpml:distance (2026-09-26).
# These are the known-good answers the splitter is checked against: the budget model
# must call the first three over and the last two within one battery.
FIXTURE_PATHS_M = {
    "myKMZ-1": 12651.0,
    "myKMZ-2": 12097.0,
    "20260722_morr_jet_lwd01": 17406.0,
    "myKMZ-3": 3221.0,
    "20220722_morr_braid04-2": 306.0,
}
FIXTURE_FITS = {"myKMZ-3", "20220722_morr_braid04-2"}
FIXTURE_HEIGHT_M = 300.0


def _max_transit_m(height_m):
    """Transit distance at which one battery has no survey path left."""
    lo, hi = 0.0, 50000.0
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if budget.max_path_m(height_m, transit_m=mid) > 0:
            lo = mid
        else:
            hi = mid
    return lo


def load_reach(stream, gpkg=FLOODPLAIN_GPKG, layer=DEFAULT_LAYER):
    """The floodplain polygon for one named stream, in a metric CRS."""
    gdf = gpd.read_file(gpkg, layer=layer)
    hit = gdf[gdf["gnis_name"] == stream]
    if hit.empty:
        named = sorted(str(v) for v in gdf["gnis_name"].dropna().unique())
        raise SystemExit(f"no reach named {stream!r} in {layer}. Available: {named}")
    return hit.to_crs(CRS_METRIC).geometry.union_all()


# A floodplain delineation is a raster-derived multipolygon, so it carries a tail of
# sub-hectare slivers -- Peacock Creek ff04 is 187.3 ha in 25 parts, of which 23 are
# 0.09 ha each. They are not survey targets, and treating each as a block is how a
# 187 ha reach turned into 129 "blocks" on the first attempt.
MIN_BLOCK_HA = 1.0


def _equal_area_strips(poly, n):
    """Cut `poly` into n strips of equal area, perpendicular to its long axis.

    Bisection on the cut position rather than repeated halving of the polygon: a
    complex floodplain boundary fragments into many parts every time it is cut, so
    recursing on the pieces multiplies them. Cutting the ORIGINAL polygon n-1 times
    keeps the fragmentation to one pass.
    """
    if n <= 1:
        return [poly]
    bearing = cov.long_axis_bearing(poly)
    origin = poly.centroid
    rot = affinity.rotate(poly, -bearing, origin=origin)
    minx, miny, maxx, maxy = rot.bounds
    target = rot.area / n

    cuts, lo = [], miny
    for k in range(1, n):
        want = target * k
        a, b = miny, maxy
        for _ in range(40):  # ~1e-12 of the span; far finer than the geometry
            mid = (a + b) / 2.0
            got = rot.intersection(box(minx - 1, miny - 1, maxx + 1, mid)).area
            if got < want:
                a = mid
            else:
                b = mid
        cuts.append((a + b) / 2.0)

    out, edges = [], [miny - 1.0] + cuts + [maxy + 1.0]
    for i in range(len(edges) - 1):
        piece = rot.intersection(box(minx - 1, edges[i], maxx + 1, edges[i + 1]))
        if piece.is_empty:
            continue
        out.append(affinity.rotate(piece, bearing, origin=origin))
    return out


def split_to_budget(polygon, height_m, launch_pt, min_block_ha=MIN_BLOCK_HA):
    """Blocks that each fit one battery, nearest the launch point first.

    Per component: compute the survey path, divide by what one battery can fly, and
    cut that many equal-area strips in a single pass. Components under
    `min_block_ha` are dropped and reported rather than flown.
    """
    def survey(poly):
        """(path_m, n_stations). n_stations == 0 means UNFLYABLE, not free."""
        if poly.is_empty or poly.area <= 0:
            return 0.0, 0
        stations, _, meta = cov.plan_transects(poly, height_m)
        return meta["path_m"], len(stations)

    def flyable_and_fits(poly):
        """A block must have stations AND fit. budget.fits(0.0) is True, so a
        block too narrow for a single transect would otherwise pass every check
        -- which is how the minimal-n search terminated on 50 m strips against a
        100.8 m spacing and reported over_budget: 0."""
        path, n = survey(poly)
        if n == 0:
            return False
        return budget.fits(path, height_m, transit_m=transit(poly))[0]

    def transit(poly):
        return launch_pt.distance(poly) if launch_pt is not None else 0.0

    parts = list(polygon.geoms) if polygon.geom_type.startswith("Multi") else [polygon]
    kept = [p for p in parts if p.geom_type == "Polygon" and p.area / 1e4 >= min_block_ha]
    dropped = [p for p in parts if p not in kept]

    blocks, unreachable = [], []
    for comp in kept:
        # Search for the SMALLEST n whose strips all fit, rather than estimating it
        # from total path. The estimate over-splits badly: turn-around is a large
        # share of the path on a sinuous floodplain, it does not divide evenly, and
        # a ceil() on top left every battery at about 70% full. Minimal n is what
        # makes three batteries cover as much as three batteries can.
        budget_path = budget.max_path_m(height_m, transit_m=transit(comp))
        if budget_path <= 0:
            # Out of reach: the transit alone exhausts the battery. Record it --
            # dropping it silently loses area the user was just told is in scope.
            unreachable.append(comp)
            continue
        lower = max(1, math.ceil(survey(comp)[0] / budget_path))
        chosen, n = None, 1
        while n <= max(lower * 2, 24):
            strips = [s for s in _equal_area_strips(comp, n) if s.area / 1e4 >= min_block_ha]
            if strips and all(flyable_and_fits(s) for s in strips):
                chosen = strips
                break
            n += 1
        # Fall back to the estimate rather than looping forever; the post-split
        # verification below reports anything still over budget.
        for strip in (chosen if chosen is not None else _equal_area_strips(comp, lower)):
            # Keep a strip whole even when the cut leaves it multipart. One mission
            # can cover disjoint pieces -- the aircraft simply flies between them,
            # and the transect generator handles a MultiPolygon. Exploding strips
            # into parts is what left the first working version with ten blocks of
            # 12-30 ha each where one battery covers 85.
            if strip.area / 1e4 >= min_block_ha:
                blocks.append(strip)

    # A strip can still come out over budget where the cut lands badly, so verify
    # rather than assume -- the split is a prediction and this is the check on it.
    over, unflyable = [], []
    for b in blocks:
        path, n = survey(b)
        if n == 0:
            unflyable.append(b)
        elif not budget.fits(path, height_m, transit_m=transit(b))[0]:
            over.append(b)
    # Unflyable blocks are removed, not emitted: a mission with no stations is
    # not a mission. They are reported so the area is not silently lost.
    blocks = [b for b in blocks if b not in unflyable]

    # Nearest first: the launch point is fixed, so the closest blocks spend least of
    # the battery getting there.
    blocks.sort(key=lambda b: transit(b))
    return blocks, {"dropped": len(dropped),
                    "dropped_ha": sum(p.area for p in dropped) / 1e4,
                    "over_budget": len(over),
                    "unreachable": len(unreachable),
                    "unreachable_ha": sum(p.area for p in unreachable) / 1e4,
                    "unflyable": len(unflyable),
                    "unflyable_ha": sum(b.area for b in unflyable) / 1e4}


def block_mission(polygon_metric, height_m, speed_ms, name):
    """Build a Mission (WGS84 waypoints) for one block."""
    stations, lines, meta = cov.plan_transects(polygon_metric, height_m)
    if not stations:
        return None, meta
    pts = gpd.GeoSeries(stations, crs=CRS_METRIC).to_crs(CRS_WGS84)

    waypoints = []
    last = len(pts) - 1
    for i, p in enumerate(pts):
        # Match the real exports exactly: every waypoint carries its OWN groups,
        # with the id incrementing, the gimbal spanning i..i+1 and the photo at
        # i..i. Measured on myKMZ-3 -- 37 waypoints, 36 gimbal groups (the last
        # has no i+1 to span), ids 0..35. Emitting id 0 everywhere is what the
        # first version did, and the round-trip gate cannot see it because the
        # reader replays action groups as raw text.
        actions = []
        if i < last:
            actions.append(gimbal_action(group_id=i, start=i, end=i + 1))
        actions.append(photo_action(group_id=i, index=i))
        waypoints.append(Waypoint(lon=p.x, lat=p.y, height=height_m,
                                  speed=speed_ms, action_xml=actions))

    dist = sum(stations[i].distance(stations[i + 1]) for i in range(len(stations) - 1))
    mission = Mission(waypoints=waypoints, auto_speed=speed_ms,
                      takeoff_security_height=str(int(height_m)), distance=dist)
    meta["name"] = name
    meta["n_waypoints"] = len(waypoints)
    return mission, meta


def _validate_fixtures(height_m=FIXTURE_HEIGHT_M):
    """The budget verdict on each real mission must match what actually happened."""
    print(f"  budget verdict at {height_m:.0f} m, launching from the block edge:")
    fails = []
    for name, path in sorted(FIXTURE_PATHS_M.items(), key=lambda kv: -kv[1]):
        ok, est, usable = budget.fits(path, height_m, transit_m=0.0)
        expect = name in FIXTURE_FITS
        mark = "fits" if ok else "OVER"
        print(f"    {name:<28} {path:>7.0f} m  {est:>6.0f} s / {usable:.0f} s  {mark}")
        if ok != expect:
            fails.append(f"{name}: model says {'fits' if ok else 'over budget'}, "
                         f"expected {'fits' if expect else 'over budget'}")
    print()
    sys.stdout.flush()
    if fails:
        print(f"FIXTURE VALIDATION FAILED: {len(fails)} mission(s)", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"FIXTURE VALIDATION PASS: {len(FIXTURE_PATHS_M)} missions classified correctly")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stream", help="gnis_name of the reach, e.g. 'Peacock Creek'")
    ap.add_argument("--launch", nargs=2, type=float, metavar=("LON", "LAT"),
                    help="launch point in WGS84")
    ap.add_argument("--height", type=float, default=350.0, help="metres AGL (default 350)")
    ap.add_argument("--speed", type=float, default=10.0,
                    help="commanded speed m/s (default 10; effective is lower — see flight_budget)")
    ap.add_argument("--batteries", type=int, default=3, help="blocks to emit (default 3)")
    ap.add_argument("--radius", type=float, default=5000.0,
                    help="metres around the launch point to consider (default 5000)")
    ap.add_argument("--layer", default=DEFAULT_LAYER)
    ap.add_argument("--gpkg", default=FLOODPLAIN_GPKG)
    ap.add_argument("--out", help="directory for the .kmz files")
    ap.add_argument("--review-layers", action="store_true",
                    help="also write plan.gpkg beside the missions (floodplain, launch, "
                         "blocks, transects, stations) for review in QGIS before flying")
    ap.add_argument("--validate-fixtures", action="store_true",
                    help="check the budget verdict against the five real missions (gate)")
    args = ap.parse_args()

    if args.validate_fixtures:
        return _validate_fixtures()
    if not (args.stream and args.launch and args.out):
        ap.error("need --stream, --launch and --out (or --validate-fixtures)")

    launch_wgs = Point(args.launch[0], args.launch[1])
    launch = gpd.GeoSeries([launch_wgs], crs=CRS_WGS84).to_crs(CRS_METRIC).iloc[0]

    reach = load_reach(args.stream, args.gpkg, args.layer)
    working = reach.intersection(launch.buffer(args.radius))
    if working.is_empty:
        raise SystemExit(f"{args.stream!r} has no floodplain within {args.radius:.0f} m "
                         f"of the launch point")
    print(f"=== {args.stream}: {reach.area/1e4:.1f} ha total, "
          f"{working.area/1e4:.1f} ha within {args.radius:.0f} m of launch")
    # The radius is the user's search window; the battery sets the real one. Say so
    # up front rather than silently dropping everything between the two -- at 350 m
    # the reachable transit is 4223 m while --radius defaults to 5000.
    reach_m = _max_transit_m(args.height)
    if args.radius > reach_m:
        print(f"    note: at {args.height:.0f} m one battery reaches about "
              f"{reach_m:.0f} m of transit, less than --radius {args.radius:.0f} m; "
              f"anything beyond that is reported as unreachable")

    t_sp, p_sp = cov.spacing(args.height)
    print(f"=== {args.height:.0f} m AGL: gsd {cov.gsd(args.height)*100:.2f} cm/px, "
          f"transect {t_sp:.1f} m, photo {p_sp:.1f} m")

    blocks, split_meta = split_to_budget(working, args.height, launch)
    print(f"=== split into {len(blocks)} block(s) that each fit one battery")
    if split_meta["dropped"]:
        print(f"    ({split_meta['dropped']} sliver(s) under {MIN_BLOCK_HA} ha dropped, "
              f"{split_meta['dropped_ha']:.2f} ha total — not survey targets)")
    if split_meta["unreachable"]:
        print(f"    {split_meta['unreachable']} component(s) beyond battery reach, "
              f"{split_meta['unreachable_ha']:.1f} ha — not planned", file=sys.stderr)
    if split_meta["unflyable"]:
        print(f"    {split_meta['unflyable']} block(s) too narrow for a transect, "
              f"{split_meta['unflyable_ha']:.1f} ha — dropped", file=sys.stderr)
    if split_meta["over_budget"]:
        # Loud, not silent: a block that does not fit will truncate in the air.
        print(f"    WARNING: {split_meta['over_budget']} block(s) still over budget "
              f"after splitting", file=sys.stderr)

    out = pathlib.Path(args.out)
    written, total_ha, skipped = [], 0.0, 0
    layers = {"blocks": ([], []), "transects": ([], []), "stations": ([], [])}
    # Iterate until `--batteries` missions are WRITTEN. Slicing the block list
    # first let an unsurveyable block consume a battery slot, and blocks are
    # sorted nearest-first, so those slots were the ones being eaten.
    for b in blocks:
        if len(written) >= args.batteries:
            break
        name = f"{args.stream.lower().replace(' ', '_')}_{len(written) + 1:02d}"
        mission, meta = block_mission(b, args.height, args.speed, name)
        if mission is None:
            print(f"  SKIP {name}: no stations (block too small for one transect)")
            skipped += 1
            continue
        transit_m = launch.distance(b)
        ok, est, usable = budget.fits(meta["path_m"], args.height, transit_m=transit_m)
        path = write_kmz(mission, out / f"{name}.kmz")
        written.append(path)
        total_ha += meta["area_ha"]
        print(f"  {name}: {meta['area_ha']:.1f} ha, {meta['n_transects']} transects, "
              f"{meta['n_waypoints']} waypoints, path {meta['path_m']:.0f} m, "
              f"transit {transit_m:.0f} m, {est:.0f} s / {usable:.0f} s "
              f"{'OK' if ok else 'OVER BUDGET'}")
        print(f"      -> {path}")
        if args.review_layers:
            stations, lines, _ = cov.plan_transects(b, args.height)
            layers["blocks"][0].append(
                {"block": name, "area_ha": round(meta["area_ha"], 1),
                 "transects": meta["n_transects"], "stations": len(stations),
                 "path_m": round(meta["path_m"]), "transit_m": round(transit_m),
                 "est_s": round(est), "budget_s": round(usable), "fits": bool(ok)})
            layers["blocks"][1].append(b)
            for j, ln in enumerate(lines):
                layers["transects"][0].append({"block": name, "transect": j})
                layers["transects"][1].append(ln)
            for j, st in enumerate(stations):
                layers["stations"][0].append({"block": name, "station": j})
                layers["stations"][1].append(st)

    if args.review_layers and written:
        # Review before flying. One file, five layers, opens straight in QGIS.
        gpkg = out / "plan.gpkg"
        gpd.GeoDataFrame({"name": [args.stream]}, geometry=[reach],
                         crs=CRS_METRIC).to_file(gpkg, layer="floodplain", driver="GPKG")
        gpd.GeoDataFrame({"name": ["launch"]}, geometry=[launch],
                         crs=CRS_METRIC).to_file(gpkg, layer="launch", driver="GPKG", mode="a")
        for lname, (rows, geoms) in layers.items():
            if geoms:
                gpd.GeoDataFrame(rows, geometry=geoms, crs=CRS_METRIC).to_file(
                    gpkg, layer=lname, driver="GPKG", mode="a")
        print(f"  review layers -> {gpkg}")

    print()
    if not written:
        print("PLAN INCOMPLETE: no missions written", file=sys.stderr)
        return 1

    # Anything that costs the user area or would truncate in the air makes this a
    # non-zero exit, so a caller gating on the status is not told everything is
    # fine. Reporting a problem and exiting 0 is the shape this is avoiding.
    problems = []
    if split_meta["over_budget"]:
        problems.append(f"{split_meta['over_budget']} block(s) still over budget")
    if split_meta["unflyable"]:
        problems.append(f"{split_meta['unflyable']} block(s) too narrow to fly "
                        f"({split_meta['unflyable_ha']:.1f} ha)")
    if split_meta["unreachable"]:
        problems.append(f"{split_meta['unreachable']} component(s) beyond battery reach "
                        f"({split_meta['unreachable_ha']:.1f} ha)")
    if skipped:
        problems.append(f"{skipped} block(s) skipped for having no stations")

    if problems:
        print(f"PLAN INCOMPLETE: {len(written)} mission(s) written, {total_ha:.1f} ha, "
              f"but:", file=sys.stderr)
        for pr in problems:
            print(f"  - {pr}", file=sys.stderr)
        return 1
    print(f"PLAN COMPLETE: {len(written)} mission(s), {total_ha:.1f} ha, "
          f"{len(blocks)} block(s) available")
    if len(blocks) > len(written):
        print(f"  ({len(blocks) - len(written)} further block(s) not written — "
              f"raise --batteries to include them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
