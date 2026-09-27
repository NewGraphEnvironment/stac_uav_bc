#!/usr/bin/env python3
# Battery-endurance model for UAV survey blocks, calibrated on flown missions (#26).
#
# Decides whether a block fits one battery. The inputs are the survey path length
# from flight_coverage.py plus the transit out and back from the launch point; the
# output is an estimated airborne time and a verdict.
#
# The model is calibrated against the SEVEN published 2026 MORR datasets rather
# than against the mission files, because the mission files cannot be trusted for
# timing: wpml:duration is the constant 200.324 in every export regardless of
# mission, and 20260722_morr_jet_lwd01.kmz requests 26 m/s, which the Mini 4 Pro
# cannot fly. Image EXIF is ground truth -- it records where the aircraft was and
# when, and nothing else in the pipeline does.
#
# ENV SPLIT, deliberate. Reading EXIF needs Pillow, which lives only in the system
# python3; the spatial stack (shapely, geopandas, GDAL) lives only in conda `dff`.
# No env on this machine has both. So the model functions here -- estimate_s,
# fits, max_path_m -- are pure stdlib and import cleanly from `dff`, and the EXIF
# read is lazy, inside measure_flights(). Only the two maintenance modes below
# need Pillow, and they run on the system python3:
#
#   python3 scripts/flight_budget.py --calibrate   # recompute from the imagery
#   python3 scripts/flight_budget.py --selftest    # the gate; non-zero on mismatch
#
# Run under an env without Pillow, both refuse and say so rather than skipping --
# a calibration gate that cannot read its own evidence must not report a pass.
import argparse
import datetime
import math
import pathlib
import sys

IMAGERY_ROOT = pathlib.Path("/Users/airvine/Projects/gis/uav_imagery")
CALIBRATION_SET = IMAGERY_ROOT / "skeena/morice/2026"

# ---------------------------------------------------------------------------
# Calibrated 2026-09-26 against the seven published 2026 MORR flights, measured
# photo-to-photo from image EXIF (first capture to last, path summed over the
# capture-ordered positions):
#
#   dataset                n   elapsed s   path m   effective m/s
#   wedzin_braid_001     123        1073     8458            7.88
#   wedzin_canyon_km25    89         967     6009            6.21
#   wedzin_cedric        134        1308     9808            7.50
#   wedzin_gosnell…       77         565     4492            7.95
#   wedzin_lwd001         97        1015     7183            7.08
#   wedzin_morice_km61   130         751     7901           10.52
#   wedzin_pimpernel     122         787     5774            7.34
#
# THE HEADLINE: commanding 10 m/s yields about 7.5 m/s on the ground. Every one of
# these missions sets waypointTurnMode to toPointAndStopWithDiscontinuityCurvature,
# so the aircraft STOPS at each photo station. A budget computed at the commanded
# speed over-promises coverage by roughly a third, which is how a block that looks
# like it fits comes home unfinished.
#
# Sizing uses the SLOWEST observed speed, not the median. The two directions are
# not symmetric: sizing a block too small costs a second battery, sizing it too
# large truncates the flight and leaves a hole in the survey. wedzin_lwd001 is the
# recorded instance -- its mission planned 165 photo stations and 97 were taken.
# The speed the seven calibration flights were COMMANDED at. The effective speeds
# above are what that produced on the ground, so they are not speed-independent --
# a mission commanded at a different speed has to scale off this.
CALIBRATED_COMMANDED_MS = 10.0

EFFECTIVE_SPEED_MS = 6.21      # slowest of the seven; the conservative choice
EFFECTIVE_SPEED_MEDIAN_MS = 7.50
EFFECTIVE_SPEED_RANGE_MS = (6.21, 10.52)

# Longest photo-to-photo time observed (wedzin_cedric, 1308 s = 21.8 min). The
# aircraft was airborne longer than this -- climb before the first photo and
# descent after the last are not in the EXIF -- so the real per-battery budget is
# at least this plus both. #26 assumed an 18 min airborne budget; that is not
# consistent with a flight that spent 21.8 min taking photographs.
OBSERVED_MAX_PHOTO_TIME_S = 1308.0

# How many flights the constants above were fitted to. Asserted, so a dataset
# appearing or disappearing is a loud failure rather than a quietly narrower fit.
CALIBRATION_N_FLIGHTS = 7

# Every calibration mission specifies executeHeight 300.0.
CALIBRATION_HEIGHT_M = 300.0

# Climb and descent to survey height. NOT measured -- EXIF starts at the first
# photo, by which time the aircraft is already up. #26 flags this as the open
# question that decides the per-battery ceiling, and it still is. These are the
# Mini 4 Pro's published rates, which the aircraft will not beat; treating them as
# exact is the remaining soft spot in this model.
CLIMB_RATE_MS = 5.0
DESCENT_RATE_MS = 5.0

# Airborne budget for one battery, and what is held back.
#
# This is the one constant the imagery cannot measure, because EXIF only spans the
# photographs. It is bounded from below by what has already been flown:
# wedzin_cedric spent 1308 s taking photographs, so it was airborne for at least
# 1308 + climb + descent = 1428 s, or 23.8 min. Any budget under that refuses a
# mission that demonstrably happened.
#
# 30 min sits above that and below the Mini 4 Pro's 34 min rating, which is a
# no-wind hover figure the aircraft will not meet on a survey. The 5 min reserve
# leaves 25 min usable. #26 assumed 18 min airborne with a 2 min reserve; that is
# not consistent with cedric, and would have refused three of the seven flights.
#
# Both are arguments to fits() and max_path_m(), so a colder day or an older
# battery is a parameter rather than an edit.
AIRBORNE_BUDGET_S = 1800.0   # 30 min
RESERVE_S = 300.0            # 5 min


def effective_speed_for(commanded_ms):
    """Effective speed to budget with, for a mission commanded at `commanded_ms`.

    Scaled linearly off the calibration, which is an ASSUMPTION and the weakest
    link in this model: the aircraft stops at every photo station, so some of the
    loss is per-station and does not scale with cruise speed at all. Linear is the
    conservative direction for a slower command and optimistic for a faster one --
    prefer re-calibrating over trusting this far from 10 m/s.
    """
    if not (commanded_ms > 0) or commanded_ms != commanded_ms:
        raise ValueError(f"commanded speed must be positive and finite, got {commanded_ms}")
    return EFFECTIVE_SPEED_MS * (commanded_ms / CALIBRATED_COMMANDED_MS)


def climb_descent_s(height_m):
    return height_m / CLIMB_RATE_MS + height_m / DESCENT_RATE_MS


def estimate_s(path_m, height_m, transit_m=0.0, speed_ms=EFFECTIVE_SPEED_MS):
    """Airborne seconds for a block: climb + transit out and back + survey + descent."""
    return (climb_descent_s(height_m)
            + 2.0 * transit_m / speed_ms
            + path_m / speed_ms)


def fits(path_m, height_m, transit_m=0.0, budget_s=AIRBORNE_BUDGET_S,
         reserve_s=RESERVE_S, speed_ms=EFFECTIVE_SPEED_MS):
    """(fits, estimated_s, usable_s) for one block on one battery."""
    est = estimate_s(path_m, height_m, transit_m, speed_ms)
    usable = budget_s - reserve_s
    return est <= usable, est, usable


def max_path_m(height_m, transit_m=0.0, budget_s=AIRBORNE_BUDGET_S,
               reserve_s=RESERVE_S, speed_ms=EFFECTIVE_SPEED_MS):
    """Longest survey path one battery can fly, after climb, descent and transit."""
    remaining = (budget_s - reserve_s) - climb_descent_s(height_m) - 2.0 * transit_m / speed_ms
    return max(0.0, remaining * speed_ms)


def _haversine(a, b):
    R = 6371000.0
    la = math.radians((a[1] + b[1]) / 2.0)
    return math.hypot((b[0] - a[0]) * math.cos(la), b[1] - a[1]) * math.pi / 180.0 * R


def measure_flights(root=CALIBRATION_SET):
    """Elapsed time, path and effective speed per dataset, from image EXIF."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    try:
        from stream_resolve import image_points
    except ImportError as e:
        # Pillow is absent from this interpreter. Say so and stop; do NOT return an
        # empty list, which every caller below would read as "no flights to check"
        # and therefore as a pass.
        raise RuntimeError(
            f"cannot read image EXIF here ({e}). Pillow lives in the system python3, "
            f"not in conda `dff` — run: python3 {pathlib.Path(__file__).name} --selftest"
        ) from e
    rows = []
    for d in sorted(p for p in pathlib.Path(root).iterdir() if (p / "images").is_dir()):
        pts = image_points(str(d))
        if len(pts) < 3:
            continue
        ts = [datetime.datetime.strptime(p[2], "%Y:%m:%d %H:%M:%S") for p in pts]
        order = sorted(range(len(pts)), key=lambda i: ts[i])
        elapsed = (ts[order[-1]] - ts[order[0]]).total_seconds()
        path = sum(_haversine(pts[order[i]][:2], pts[order[i + 1]][:2])
                   for i in range(len(order) - 1))
        if elapsed <= 0:
            continue
        rows.append({"dataset": d.name, "n": len(pts), "elapsed_s": elapsed,
                     "path_m": path, "speed_ms": path / elapsed})
    return rows


def _calibrate():
    rows = measure_flights()
    if not rows:
        print("CALIBRATION FAILED: no datasets with readable image GPS", file=sys.stderr)
        return 1
    print(f"{'dataset':<28} {'n':>4} {'elapsed s':>9} {'path m':>8} {'eff m/s':>8}")
    for r in rows:
        print(f"{r['dataset']:<28} {r['n']:>4} {r['elapsed_s']:>9.0f} "
              f"{r['path_m']:>8.0f} {r['speed_ms']:>8.2f}")
    sp = sorted(r["speed_ms"] for r in rows)
    med = sp[len(sp) // 2] if len(sp) % 2 else (sp[len(sp) // 2 - 1] + sp[len(sp) // 2]) / 2
    print()
    print(f"  effective speed: min {sp[0]:.2f}  median {med:.2f}  max {sp[-1]:.2f} m/s "
          f"over {len(sp)} flights")
    print(f"  longest photo-to-photo time: {max(r['elapsed_s'] for r in rows):.0f} s")
    print(f"  module constants: EFFECTIVE_SPEED_MS={EFFECTIVE_SPEED_MS} "
          f"median={EFFECTIVE_SPEED_MEDIAN_MS} max_photo_time={OBSERVED_MAX_PHOTO_TIME_S}")
    return 0


def _selftest():
    fails = []
    rows = measure_flights()
    if not rows:
        # Unreadable is a third state. It must not pass as "calibrated".
        print("BUDGET SELFTEST FAILED: calibration imagery unreadable — cannot verify",
              file=sys.stderr)
        return 1

    sp = sorted(r["speed_ms"] for r in rows)
    print(f"  {len(rows)} flights: effective speed {sp[0]:.2f}-{sp[-1]:.2f} m/s")

    # Assert the POPULATION, not just the extremes. Both numeric guards below are
    # owned by one dataset each, so losing five of seven imagery dirs leaves them
    # satisfied and the gate prints "consistent with 2 flown missions" — an
    # expectation derived from the artifact goes empty alongside it.
    if len(rows) != CALIBRATION_N_FLIGHTS:
        fails.append(f"calibrated on {CALIBRATION_N_FLIGHTS} flights but found "
                     f"{len(rows)} — datasets added or missing; re-run --calibrate "
                     f"and update the constants")

    # The constants must still describe the imagery they were fitted to. If a
    # dataset is added or re-stitched, this is what notices.
    if abs(sp[0] - EFFECTIVE_SPEED_MS) > 0.05:
        fails.append(f"slowest observed speed is {sp[0]:.2f} m/s, constant says "
                     f"{EFFECTIVE_SPEED_MS} — re-run --calibrate")
    longest = max(r["elapsed_s"] for r in rows)
    if abs(longest - OBSERVED_MAX_PHOTO_TIME_S) > 1.0:
        fails.append(f"longest photo-to-photo time is {longest:.0f} s, constant says "
                     f"{OBSERVED_MAX_PHOTO_TIME_S} — re-run --calibrate")

    # Sizing must be conservative: the speed used for planning is the slowest
    # observed, never the median. Getting this backwards truncates flights.
    if EFFECTIVE_SPEED_MS > EFFECTIVE_SPEED_MEDIAN_MS:
        fails.append("sizing speed is above the median — sizing must use the slowest "
                     "observed speed, or blocks come out too big and flights truncate")

    # The budget must accommodate every flight that actually happened, measured at
    # that flight's OWN elapsed time plus climb and descent. This tests the budget
    # constant. Testing it at the conservative sizing speed instead would conflate
    # two different constants and fail on the fast flights for the wrong reason.
    usable = AIRBORNE_BUDGET_S - RESERVE_S
    for r in rows:
        # 300 m is the height every calibration flight was PLANNED at (all five
        # mission files say executeHeight 300.0); it is named rather than inlined
        # so a future set flown at another height does not silently reuse it.
        airborne = r["elapsed_s"] + climb_descent_s(CALIBRATION_HEIGHT_M)
        if airborne > usable:
            fails.append(f"{r['dataset']}: was airborne at least {airborne:.0f} s "
                         f"({r['elapsed_s']:.0f} s of photos + climb/descent) but the "
                         f"usable budget is {usable:.0f} s — the budget refuses a flight "
                         f"that happened")

    # Sizing must be conservative in the right direction: planning at the slowest
    # observed speed must yield a SHORTER allowed path than planning at the median.
    # If this inverts, blocks come out too big and flights truncate.
    if max_path_m(350.0) >= max_path_m(350.0, speed_ms=EFFECTIVE_SPEED_MEDIAN_MS):
        fails.append("planning at the sizing speed allows at least as much path as the "
                     "median speed — the conservative direction has inverted")

    for h in (300.0, 350.0):
        print(f"  at {h:.0f} m, launching from the block edge: "
              f"max survey path {max_path_m(h):.0f} m")

    print()
    sys.stdout.flush()
    if fails:
        print(f"BUDGET SELFTEST FAILED: {len(fails)} check(s)", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"BUDGET SELFTEST PASS: model consistent with {len(rows)} flown missions")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibrate", action="store_true",
                    help="recompute speed and endurance from the flown imagery")
    ap.add_argument("--selftest", action="store_true",
                    help="assert the constants still describe the imagery (gate)")
    args = ap.parse_args()
    if args.calibrate:
        return _calibrate()
    if args.selftest:
        return _selftest()
    ap.error("nothing to do — pass --calibrate or --selftest")


if __name__ == "__main__":
    sys.exit(main())
