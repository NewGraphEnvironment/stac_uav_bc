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
from shapely.geometry import Point, box
from shapely.validation import make_valid

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


def _flatten(geom):
    """Every leaf geometry inside `geom`, whatever containers it arrived in."""
    if geom.is_empty:
        return []
    if hasattr(geom, "geoms"):
        out = []
        for g in geom.geoms:
            out.extend(_flatten(g))
        return out
    return [geom]


def _polygons(geom):
    """Every Polygon inside `geom`, whatever container it arrived in.

    A GeometryCollection is a real result of intersecting a floodplain with a
    radius disc when a component is tangent to the circle, and it is the shape
    that defeated the first accounting invariant.
    """
    if geom.is_empty:
        return []
    return [g for g in _flatten(geom) if g.geom_type == "Polygon"]


def _max_transit_m(height_m, speed_ms, min_block_ha=None):
    """Transit beyond which one battery cannot fly a USEFUL survey.

    Defined against a minimum worthwhile block rather than against a zero-metre
    path. The zero-path figure overstates reach badly and the overstated tail is
    exactly where blocks go unflyable: at 350 m it reports 4223 m, but the usable
    survey path there is 86 m -- less than one transect across a 1 ha block.
    """
    if min_block_ha is None:
        min_block_ha = MIN_BLOCK_HA
    # Path needed to survey a min_block_ha square at this height, turns included.
    side = math.sqrt(min_block_ha * 1e4)
    t_sp, _ = cov.spacing(height_m)
    n_t = max(1.0, side / t_sp)
    need = side * n_t + t_sp * (n_t - 1.0)
    lo, hi = 0.0, 50000.0
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if budget.max_path_m(height_m, transit_m=mid, speed_ms=speed_ms) >= need:
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


def split_to_budget(polygon, height_m, launch_pt, min_block_ha=MIN_BLOCK_HA,
                    max_depth=8, commanded_ms=10.0, input_is_whole=True):
    """(blocks, accounting) — every hectare of input lands in exactly one bucket.

    Three rounds of review found one mechanism here: a degenerate or awkward result
    carried through the arithmetic instead of being disposed of as its own state.
    First `path_m == 0` read as "fits"; then a small-but-positive `budget_path` lost
    a component into no counter; then an all-or-nothing fit test over a whole
    component sent 173 flyable hectares to `unsplittable` because one far strip did
    not fit.

    So disposition is per PIECE and recursive, not per component and all-or-nothing.
    A piece that fits is planned and is not cut further, which is what keeps blocks
    full; a piece that does not is halved and its halves disposed of independently.
    Every piece ends in exactly one bucket, and `area_in_ha` must equal their sum.
    """
    def transit(poly):
        return launch_pt.distance(poly) if launch_pt is not None else 0.0

    def survey(poly):
        if poly.is_empty or poly.area <= 0:
            return 0.0, 0
        stations, _, meta = cov.plan_transects(poly, height_m)
        return meta["path_m"], len(stations)

    # area_in is the WHOLE input, before any filtering. Computing it from the
    # filtered parts made the invariant balance against an already-reduced total,
    # so a GeometryCollection could lose its polygon and still report 0.00.
    eff = budget.effective_speed_for(commanded_ms)
    if not polygon.is_valid:
        # A self-intersecting ring makes difference()/intersection() raise
        # GEOSException("side location conflict") from inside shapely. Repair it
        # once, here, rather than letting every geometry call be a trap.
        polygon = make_valid(polygon)
    area_in = polygon.area / 1e4
    buckets = {k: [] for k in ("planned", "sliver", "unreachable", "unsurveyable",
                               "undersized_after_split", "unsplittable", "nonpolygon")}

    # Non-polygonal input, bucketed by area so the invariant sees it. Lines and
    # points have zero area and contribute nothing, which is correct.
    for g in _flatten(polygon):
        if g.geom_type != "Polygon":
            buckets["nonpolygon"].append(g)

    def dispose(poly, depth, native):
        if poly.is_empty:
            return
        if poly.area / 1e4 < min_block_ha:
            # WHY it is small matters. A piece that arrived small is a native
            # sliver of the delineation and is expected; a piece any cut drove
            # small is area this planner failed to use. `native` is CARRIED from
            # the caller rather than inferred from recursion depth -- depth only
            # knows about _equal_area_strips, and the reach disc and --radius both
            # cut before it ever runs.
            buckets["sliver" if native else "undersized_after_split"].append(poly)
            return
        path, n = survey(poly)
        if n == 0:
            # No stations at this height's transect spacing. Halving CANNOT help --
            # the pieces only get narrower -- so recursing is wasted work and the
            # wrong verdict. Distinct from over-budget, where halving is the remedy.
            buckets["unsurveyable"].append(poly)
            return
        if budget.fits(path, height_m, transit_m=transit(poly), speed_ms=eff)[0]:
            buckets["planned"].append(poly)
            return
        if depth >= max_depth:
            # Bounded: an unbounded search over O(n) geometry ops per level took a
            # 100 ha component past five minutes without finishing.
            buckets["unsplittable"].append(poly)
            return
        halves = [h for h in _equal_area_strips(poly, 2) if not h.is_empty]
        if len(halves) < 2:
            buckets["unsplittable"].append(poly)
            return
        for h in halves:
            for g in _polygons(h):
                dispose(g, depth + 1, False)

    # Clip to what the battery can reach BEFORE disposing. transit() measures to a
    # piece's nearest point, so a component straddling the reach boundary would
    # otherwise never be cut successfully and would land entirely in unsplittable,
    # with unreachable reading 0.0 -- four lines under the note promising
    # out-of-reach area would be reported there.
    # Same speed as flyable_and_fits, or the disc and the fit test disagree: at
    # --speed 2 the disc was 5.25x too large and at --speed 26 it was 2.6x too
    # small, both proven end to end. Round 3 threaded the scaled speed through two
    # of the three budget consumers and this was the third.
    disc = launch_pt.buffer(
        _max_transit_m(height_m, eff, min_block_ha)) if launch_pt else None
    # `input_is_whole` is False when main() already clipped to --radius, so a
    # piece the radius trimmed is not reported as native either.
    native = input_is_whole
    for comp in _polygons(polygon):
        if disc is not None:
            outside = comp.difference(disc)
            if not outside.is_empty:
                buckets["unreachable"].extend(_polygons(outside))
            inside = _polygons(comp.intersection(disc))
            # Clipping to the disc IS a cut: a piece the disc trimmed did not
            # arrive small, so it is not a native sliver.
            clipped = len(inside) != 1 or not inside[0].equals(comp)
            for g in inside:
                dispose(g, 0, native and not clipped)
        else:
            dispose(comp, 0, native)

    blocks = sorted(buckets["planned"], key=transit)
    acc = {"area_in_ha": area_in}
    for k, v in buckets.items():
        acc[k] = len(v)
        acc[f"{k}_ha"] = sum(g.area for g in v) / 1e4
    acc["unaccounted_ha"] = area_in - sum(acc[f"{k}_ha"] for k in buckets)
    return blocks, acc


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

    # Validate before anything is computed. Unvalidated, --speed nan wrote
    # "<wpml:waypointSpeed>nan</wpml:waypointSpeed>" into a mission and reported
    # PLAN COMPLETE at exit 0; --height 0 was a ZeroDivisionError traceback and
    # --height -350 reported a LARGER battery reach than the real one.
    def _finite_positive(name, v):
        if not math.isfinite(v) or v <= 0:
            ap.error(f"{name} must be positive and finite, got {v}")
    _finite_positive("--height", args.height)
    _finite_positive("--speed", args.speed)
    _finite_positive("--radius", args.radius)
    if args.batteries < 1:
        ap.error(f"--batteries must be at least 1, got {args.batteries}")
    if not (-180.0 <= args.launch[0] <= 180.0 and -90.0 <= args.launch[1] <= 90.0):
        ap.error(f"--launch is not a lon/lat pair: {args.launch}")

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
    reach_m = _max_transit_m(args.height, budget.effective_speed_for(args.speed))
    if args.radius > reach_m:
        print(f"    note: at {args.height:.0f} m one battery reaches about "
              f"{reach_m:.0f} m of transit, less than --radius {args.radius:.0f} m; "
              f"anything beyond that is reported as unreachable")

    t_sp, p_sp = cov.spacing(args.height)
    print(f"=== {args.height:.0f} m AGL: gsd {cov.gsd(args.height)*100:.2f} cm/px, "
          f"transect {t_sp:.1f} m, photo {p_sp:.1f} m")

    blocks, split_meta = split_to_budget(working, args.height, launch,
                                        commanded_ms=args.speed,
                                        input_is_whole=(working.equals(reach)))
    print(f"=== split into {len(blocks)} block(s) that each fit one battery")
    # Full accounting, always printed: every hectare of input lands in one bucket
    # and the buckets are shown whether or not they are zero, so area cannot go
    # missing quietly. This replaces four independent counters that each covered
    # one way of losing area and between them still missed a fifth.
    print(f"    area in {split_meta['area_in_ha']:.1f} ha = "
          f"planned {split_meta['planned_ha']:.1f} "
          f"+ slivers {split_meta['sliver_ha']:.2f} ({split_meta['sliver']}) "
          f"+ unreachable {split_meta['unreachable_ha']:.1f} ({split_meta['unreachable']}) "
          f"+ unsurveyable {split_meta['unsurveyable_ha']:.1f} ({split_meta['unsurveyable']}) "
          f"+ undersized-after-split {split_meta['undersized_after_split_ha']:.2f} "
          f"({split_meta['undersized_after_split']}) "
          f"+ unsplittable {split_meta['unsplittable_ha']:.1f} ({split_meta['unsplittable']}) "
          f"+ non-polygon {split_meta['nonpolygon_ha']:.2f} ({split_meta['nonpolygon']}) "
          f"+ unaccounted {split_meta['unaccounted_ha']:.2f}")

    out = pathlib.Path(args.out)
    stem = args.stream.lower().replace(" ", "_")
    written, total_ha, bad_written = [], 0.0, 0
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
            # split_to_budget already removes zero-station blocks and
            # block_mission recomputes the same deterministic geometry, so this is
            # belt-and-braces rather than an expected path. Counted as a written
            # shortfall below if it ever fires.
            print(f"  SKIP {name}: no stations (block too small for one transect)")
            continue
        transit_m = launch.distance(b)
        ok, est, usable = budget.fits(meta["path_m"], args.height, transit_m=transit_m,
                                      speed_ms=budget.effective_speed_for(args.speed))
        path = write_kmz(mission, out / f"{name}.kmz")
        written.append(path)
        total_ha += meta["area_ha"]
        if not ok:
            bad_written += 1
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
        # Removed first: geopandas appends with mode="a", so re-running into the
        # same --out accumulated layers and the file drew missions that had just
        # been deleted as stale. A review artifact that disagrees with the missions
        # beside it is worse than none.
        gpkg = out / "plan.gpkg"
        if gpkg.exists():
            gpkg.unlink()
        gpd.GeoDataFrame({"name": [args.stream]}, geometry=[reach],
                         crs=CRS_METRIC).to_file(gpkg, layer="floodplain", driver="GPKG")
        gpd.GeoDataFrame({"name": ["launch"]}, geometry=[launch],
                         crs=CRS_METRIC).to_file(gpkg, layer="launch", driver="GPKG", mode="a")
        for lname, (rows, geoms) in layers.items():
            if geoms:
                gpd.GeoDataFrame(rows, geometry=geoms, crs=CRS_METRIC).to_file(
                    gpkg, layer=lname, driver="GPKG", mode="a")
        print(f"  review layers -> {gpkg}")

    # Now that this run's missions exist, remove the ones a LARGER previous run
    # left behind. Deleting first made a zero-block re-run empty the directory --
    # a destructive-then-rebuild sequence whose failure leaves nothing to fly.
    if written:
        keep = {p.name for p in written}
        for stale in sorted(out.glob(f"{stem}_[0-9]*.kmz")):
            if stale.name not in keep:
                stale.unlink()
                print(f"  removed stale mission from a previous run: {stale.name}")

    print()
    sys.stdout.flush()
    if not written:
        print("PLAN INCOMPLETE: no missions written", file=sys.stderr)
        return 1

    # The exit status judges WHAT WAS ASKED FOR. Area outside --batteries, or
    # outside battery reach, is the expected consequence of the flags and is
    # reported above; failing on it made a correct three-mission plan exit 1 on
    # default flags. What fails: a requested mission that could not be produced,
    # or one that was written and does not fit.
    problems = []
    if len(written) < args.batteries:
        problems.append(f"{args.batteries} mission(s) requested, {len(written)} written "
                        f"— only {len(blocks)} flyable block(s) available")
    if bad_written:
        problems.append(f"{bad_written} written mission(s) over budget — these will "
                        f"truncate in the air")
    # Area the planner FAILED to use, as opposed to area it was never asked about.
    # Native slivers and unreachable ground are expected consequences of the
    # delineation and the flags; these three are not. Gated at 5% of input rather
    # than at zero because a few cut-born fragments are normal on a sinuous
    # floodplain -- the honest Peacock run leaves 0.33 ha, 0.2%.
    wasted = (split_meta["unsurveyable_ha"] + split_meta["undersized_after_split_ha"]
              + split_meta["unsplittable_ha"])
    if split_meta["area_in_ha"] > 0 and wasted / split_meta["area_in_ha"] > 0.05:
        problems.append(
            f"{wasted:.1f} ha ({wasted / split_meta['area_in_ha'] * 100:.0f}% of input) "
            f"could not be planned — unsurveyable "
            f"{split_meta['unsurveyable_ha']:.1f}, undersized after split "
            f"{split_meta['undersized_after_split_ha']:.1f}, unsplittable "
            f"{split_meta['unsplittable_ha']:.1f}")
    if abs(split_meta["unaccounted_ha"]) > 0.5:
        problems.append(f"{split_meta['unaccounted_ha']:.1f} ha unaccounted for between "
                        f"input and blocks — the split lost area")

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
