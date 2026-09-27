#!/usr/bin/env python3
# Footprint, spacing and transect geometry for UAV survey planning (#26).
#
# Given a camera, a flying height and an overlap target, this returns the ground
# footprint and the two spacings a survey grid is built from: transect spacing
# (across track, set by side overlap) and photo spacing (along track, set by
# forward overlap). It then lays serpentine transects over a polygon and places a
# photo station along each.
#
# Pure geometry -- no battery, no waypoints, no file format. flight_budget.py
# decides whether a block fits a battery; flight_wpml.py writes the .kmz.
#
# Self-test (the gate; non-zero exit on any mismatch):
#   conda run -n dff python scripts/flight_coverage.py --selftest
#
# Usage as a library:
#   from flight_coverage import footprint, spacing, plan_transects
#   print(spacing(350))            # (transect_m, photo_m) at 350 m AGL
import argparse
import math
import sys

from shapely import affinity
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# Camera geometry. ONE definition, deliberately.
#
# Source: fly#70, which derives the Mini 4 Pro's sensor from manufacturer specs
# rather than a calibration report: 1/1.3" CMOS, 8064 x 6048 at 48 MP, 6.72 mm
# actual focal length, giving a 9.68 x 7.26 mm sensor and a 1.2004 um pixel.
#
# SUPERSEDE WITH fly::fly_footprint() WHEN fly#70 LANDS. It is open as of
# 2026-09-26 and `fly` currently has no UAV sizing route at all, so the maths
# lives here for now. Keeping it in one block is what makes that swap a one-place
# edit instead of a hunt.
#
# Validated, not assumed: at 300 m this predicts 64.8 m along-track photo spacing
# at 80% forward overlap, and the median segment length across all five real Map
# Pilot missions over the Morice is 64.9 m. A competing derivation from the
# rounded 24 mm equivalent gives a 1.250 um pixel and would predict 67.5 m, which
# the fixtures rule out.
# ---------------------------------------------------------------------------
SENSOR_W_MM = 9.68
SENSOR_H_MM = 7.26
PIXELS_W = 8064
PIXELS_H = 6048
FOCAL_MM = 6.72

# Matches all five flown missions.
DEFAULT_SIDE_OVERLAP = 0.80     # across track -> transect spacing
DEFAULT_FORWARD_OVERLAP = 0.80  # along track  -> photo spacing

# Metric CRS for every distance and area operation here.
CRS_METRIC = "EPSG:3005"  # BC Albers
CRS_WGS84 = "EPSG:4326"


def gsd(height_m):
    """Ground sample distance in metres per pixel at `height_m` above terrain."""
    pitch_m = (SENSOR_W_MM / PIXELS_W) / 1000.0
    return pitch_m * height_m / (FOCAL_MM / 1000.0)


def footprint(height_m):
    """(across_track_m, along_track_m) ground footprint at `height_m`."""
    g = gsd(height_m)
    return PIXELS_W * g, PIXELS_H * g


def spacing(height_m, side_overlap=DEFAULT_SIDE_OVERLAP,
            forward_overlap=DEFAULT_FORWARD_OVERLAP):
    """(transect_spacing_m, photo_spacing_m) for the given height and overlaps."""
    across, along = footprint(height_m)
    return across * (1.0 - side_overlap), along * (1.0 - forward_overlap)


def long_axis_bearing(polygon):
    """Bearing in degrees of the polygon's longest side, from its rotated bbox.

    Flying along the long axis minimises the number of turns, which is where
    budget is lost -- a turn costs distance that covers nothing new.
    """
    rect = polygon.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    best, best_len = 0.0, -1.0
    for i in range(4):
        dx, dy = xs[i + 1] - xs[i], ys[i + 1] - ys[i]
        length = math.hypot(dx, dy)
        if length > best_len:
            best_len, best = length, math.degrees(math.atan2(dx, dy)) % 180.0
    return best


def transect_lines(polygon, transect_spacing_m, bearing_deg=None):
    """Serpentine transects clipped to `polygon`, in the polygon's own CRS.

    The polygon is rotated so transects are axis-aligned, cut, then rotated back
    -- simpler and less error-prone than intersecting rotated lines directly.
    Alternate lines are reversed so the aircraft serpentines rather than
    deadheading back to the same edge each pass.
    """
    if transect_spacing_m <= 0:
        # side_overlap >= 1.0 reaches here. The while loop below would never
        # advance, so this must raise rather than hang -- an infinite loop in a
        # planner looks like a slow query, not a bad argument.
        raise ValueError(f"transect spacing must be positive, got {transect_spacing_m}; "
                         f"side_overlap >= 1.0 gives zero spacing")
    if bearing_deg is None:
        bearing_deg = long_axis_bearing(polygon)
    origin = polygon.centroid
    # Rotate so the flight direction lies along +y, i.e. transects step in x.
    rot = affinity.rotate(polygon, -bearing_deg, origin=origin, use_radians=False)
    minx, miny, maxx, maxy = rot.bounds

    # Keep the cut index with each part. A cut across a multipart block yields
    # several collinear segments; they belong to ONE transect and must be flown
    # together before stepping to the next. Alternating by a flat index instead
    # makes a two-lobed block ping-pong between lobes on every transect -- turns
    # measured at 68% of total path on a pair of lobes 900 m apart, which the
    # budget then charges for.
    cuts = []
    # Start half a spacing in so the first and last transects sit inside the
    # polygon rather than on its edge, which would half-cover the margin.
    x, k = minx + transect_spacing_m / 2.0, 0
    while x < maxx:
        cut = LineString([(x, miny - 1.0), (x, maxy + 1.0)]).intersection(rot)
        if not cut.is_empty:
            # A cut can graze a vertex and come back a bare Point, which has no
            # .geoms -- that raised AttributeError rather than yielding nothing.
            # Ask for the attribute rather than enumerating the types that have it.
            parts = list(cut.geoms) if hasattr(cut, "geoms") else [cut]
            segs = [p for p in parts if p.geom_type == "LineString" and p.length > 0]
            if segs:
                cuts.append((k, sorted(segs, key=lambda s: s.centroid.y)))
                k += 1
        x += transect_spacing_m

    out = []
    for k, segs in cuts:
        if k % 2 == 1:                       # serpentine by TRANSECT, not by segment
            segs = [LineString(list(s.coords)[::-1]) for s in reversed(segs)]
        for s in segs:
            out.append(affinity.rotate(s, bearing_deg, origin=origin, use_radians=False))
    return out


def stations_along(line, photo_spacing_m):
    """Photo stations along a transect, including both endpoints."""
    n = max(1, int(math.floor(line.length / photo_spacing_m)))
    pts = [line.interpolate(i * photo_spacing_m) for i in range(n + 1)]
    end = line.interpolate(line.length)
    if pts[-1].distance(end) > 1.0:
        pts.append(end)
    return pts


def plan_transects(polygon, height_m, side_overlap=DEFAULT_SIDE_OVERLAP,
                   forward_overlap=DEFAULT_FORWARD_OVERLAP, bearing_deg=None):
    """(stations, lines, meta) for one block polygon in a metric CRS."""
    t_sp, p_sp = spacing(height_m, side_overlap, forward_overlap)
    lines = transect_lines(polygon, t_sp, bearing_deg)
    stations = []
    for ln in lines:
        stations.extend(stations_along(ln, p_sp))
    across, along = footprint(height_m)
    wayline_m = sum(ln.length for ln in lines)
    # Turn-around distance between consecutive transects, which the aircraft
    # flies and which covers nothing new. Counted so the budget model sees it.
    turns_m = sum(LineString([lines[i].coords[-1], lines[i + 1].coords[0]]).length
                  for i in range(len(lines) - 1))
    meta = {
        "gsd_cm": gsd(height_m) * 100.0,
        "footprint_m": (across, along),
        "transect_spacing_m": t_sp,
        "photo_spacing_m": p_sp,
        "n_transects": len(lines),
        "n_stations": len(stations),
        "wayline_m": wayline_m,
        "turnaround_m": turns_m,
        "path_m": wayline_m + turns_m,
        "area_ha": polygon.area / 10000.0,
        "bearing_deg": bearing_deg if bearing_deg is not None else long_axis_bearing(polygon),
    }
    return stations, lines, meta


# --- gate -----------------------------------------------------------------

# Measured across all five Map Pilot exports, 2026-09-26: the median segment
# length of the wayline. At 300 m and 80/80 this IS the along-track photo
# spacing, so it is the number the camera model has to reproduce.
MEASURED_PHOTO_SPACING_300M = 64.9
MEASURED_TRANSECT_SPACING_300M = 86.0  # from fly#70's measurement of the same set
TOLERANCE_M = 0.5


def _selftest():
    fails = []
    t_sp, p_sp = spacing(300.0)
    print(f"  at 300 m: gsd {gsd(300)*100:.2f} cm/px  footprint "
          f"{footprint(300)[0]:.0f} x {footprint(300)[1]:.0f} m")
    print(f"            transect {t_sp:.1f} m (measured {MEASURED_TRANSECT_SPACING_300M})  "
          f"photo {p_sp:.1f} m (measured {MEASURED_PHOTO_SPACING_300M})")
    if abs(p_sp - MEASURED_PHOTO_SPACING_300M) > TOLERANCE_M:
        fails.append(f"photo spacing {p_sp:.2f} m differs from measured "
                     f"{MEASURED_PHOTO_SPACING_300M} m by more than {TOLERANCE_M} m")
    if abs(t_sp - MEASURED_TRANSECT_SPACING_300M) > TOLERANCE_M:
        fails.append(f"transect spacing {t_sp:.2f} m differs from measured "
                     f"{MEASURED_TRANSECT_SPACING_300M} m by more than {TOLERANCE_M} m")

    t350, p350 = spacing(350.0)
    print(f"  at 350 m: gsd {gsd(350)*100:.2f} cm/px  footprint "
          f"{footprint(350)[0]:.0f} x {footprint(350)[1]:.0f} m")
    print(f"            transect {t350:.1f} m  photo {p350:.1f} m")
    # Linearity: spacing must scale exactly with height. Catches a stray constant.
    if abs(p350 / p_sp - 350.0 / 300.0) > 1e-9:
        fails.append("spacing is not linear in height — a constant has crept in")

    # Geometry: a 1 km square must produce transects that tile it at the spacing.
    from shapely.geometry import box
    sq = box(0, 0, 1000, 1000)
    stations, lines, meta = plan_transects(sq, 350.0)
    print(f"  1 km square @350 m: {meta['n_transects']} transects, "
          f"{meta['n_stations']} stations, wayline {meta['wayline_m']:.0f} m, "
          f"turns {meta['turnaround_m']:.0f} m")
    expected_transects = int(1000 / t350)
    if not (expected_transects - 1 <= meta["n_transects"] <= expected_transects + 1):
        fails.append(f"{meta['n_transects']} transects over a 1 km square at "
                     f"{t350:.1f} m spacing; expected about {expected_transects}")
    # Serpentine: consecutive transects must start where the last one ended, near
    # enough that the turn is a turn and not a transit back across the block.
    if len(lines) >= 2:
        hop = Point(lines[0].coords[-1]).distance(Point(lines[1].coords[0]))
        if hop > t350 * 1.5:
            fails.append(f"transects are not serpentine: {hop:.0f} m between the end "
                         f"of one and the start of the next, spacing is {t350:.1f} m")
    # Coverage: every station's footprint unioned must cover the block.
    halves = [footprint(350.0)[0] / 2.0, footprint(350.0)[1] / 2.0]
    covered = unary_union([p.buffer(min(halves), cap_style=3) for p in stations])
    frac = covered.intersection(sq).area / sq.area
    print(f"  coverage of the square by station footprints: {frac*100:.1f}%")
    if frac < 0.99:
        fails.append(f"stations cover only {frac*100:.1f}% of the block")

    print()
    sys.stdout.flush()
    if fails:
        print(f"COVERAGE SELFTEST FAILED: {len(fails)} check(s)", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("COVERAGE SELFTEST PASS: camera model matches the flown missions")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="assert the camera model against the flown missions (gate)")
    ap.add_argument("--height", type=float, metavar="M",
                    help="print footprint and spacing at this height and exit")
    args = ap.parse_args()
    if args.height:
        t, p = spacing(args.height)
        across, along = footprint(args.height)
        print(f"{args.height:.0f} m AGL: gsd {gsd(args.height)*100:.2f} cm/px  "
              f"footprint {across:.0f} x {along:.0f} m  "
              f"transect {t:.1f} m  photo {p:.1f} m")
        return 0
    if args.selftest:
        return _selftest()
    ap.error("nothing to do — pass --selftest or --height")


if __name__ == "__main__":
    sys.exit(main())
