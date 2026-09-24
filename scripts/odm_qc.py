#!/usr/bin/env python3
# QC gate on an ODM run, from odm_report/stats.json — step 2 of the add-imagery
# recipe in scripts/config/README.md, which asks "all images reconstructed?
# reprojection error ~1-2 px?" and left the reading to the eye.
#
# It does not replace eyeballing the ortho; it catches the failures that are
# invisible there — a flight reconstructed in two disconnected components, or a
# run that never finished — both of which still render a plausible orthophoto
# over the part that worked.
#
# Exits non-zero on a FAIL, so it can gate dataset_publish.sh:
#   python3 scripts/odm_qc.py <project-dir>... && scripts/dataset_publish.sh <project-dir>...
#
# Two severities, and every condition that holds is reported rather than the
# first one matched:
#   FAIL — blocking, and structural: no usable report, a split reconstruction,
#          or reprojection error past the recipe's stated tolerance
#   NOTE — advisory: a dropped-shot rate high against the rest of the catalogue.
#          Not blocking, because dropping images is normal here — measured over
#          the 76 datasets carrying a stats.json on 2026-09-23, the median rate
#          is 0.8%, p90 is 4.2%, and a dataset that dropped 11.9% is published
#          and good. A hard gate at zero would have refused 50 of those 76.
#
# A missing or unreadable stats.json is a FAIL, not a skip — "no report" and
# "a clean report" must not reach the same branch.
import json
import pathlib
import sys

# The recipe's stated tolerance, not a value derived from the data: it is the
# contract this repo chose. For reference the observed max across those 76
# datasets is 1.72 px, so this ceiling sits just above the population.
MAX_REPROJECTION_PX = 2.0

# Calibrated on that population: 10% is well clear of p90 (4.2%) and flags the
# three genuine outliers (24.8%, 17.6%, 11.9%) without firing on normal runs.
NOTE_DROPPED_PCT = 10.0


def check(proj):
    """(name, metrics, fails, notes) for one project dir."""
    name = pathlib.Path(proj).name
    stats = pathlib.Path(proj, "odm_report", "stats.json")
    if not stats.is_file():
        return name, {}, ["no odm_report/stats.json — ODM did not finish"], []
    try:
        d = json.loads(stats.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return name, {}, [f"stats.json unreadable: {e}"], []

    r = d.get("reconstruction_statistics", {})
    o = d.get("odm_processing_statistics", {})
    got, want = r.get("reconstructed_shots_count"), r.get("initial_shots_count")
    comp, px, gsd = r.get("components"), r.get("reprojection_error_pixels"), o.get("average_gsd")
    m = {
        "shots": f"{got}/{want}" if want else "?",
        "components": comp if comp is not None else "?",
        "reproj_px": px,
        "gsd_cm": gsd,
        "runtime": o.get("total_time_human", "?"),
    }

    fails, notes = [], []
    if comp is None:
        fails.append("component count absent from stats.json")
    elif comp != 1:
        fails.append(f"{comp} disconnected components — the flight did not reconstruct as one piece")

    if px is None:
        fails.append("reprojection error absent from stats.json")
    elif px > MAX_REPROJECTION_PX:
        fails.append(f"reprojection error {px:.2f} px > {MAX_REPROJECTION_PX} px")

    if got is None or not want:
        fails.append("shot counts absent from stats.json")
    else:
        dropped = want - got
        pct = dropped / want * 100
        m["dropped"] = f"{dropped} ({pct:.1f}%)"
        if pct > NOTE_DROPPED_PCT:
            notes.append(f"{dropped} of {want} images not reconstructed ({pct:.1f}%) — "
                         f"high against the catalogue; check the ortho for holes")

    return name, m, fails, notes


def main(projs):
    if not projs:
        sys.exit(f"usage: {pathlib.Path(sys.argv[0]).name} project-dir [project-dir ...]")
    failed = 0
    for proj in projs:
        name, m, fails, notes = check(proj.rstrip("/"))
        px = f"{m['reproj_px']:.2f}" if isinstance(m.get("reproj_px"), float) else "?"
        gsd = f"{m['gsd_cm']:.1f}" if isinstance(m.get("gsd_cm"), float) else "?"
        print(f"{'FAIL' if fails else 'PASS'}  {name}")
        if m:
            print(f"        shots {m['shots']}  dropped {m.get('dropped', '?')}  "
                  f"components {m['components']}  reproj {px} px  gsd {gsd} cm  "
                  f"runtime {m['runtime']}")
        for f in fails:
            print(f"        FAIL {f}")
        for n in notes:
            print(f"        NOTE {n}")
        if fails:
            failed += 1
    print()
    sys.stdout.flush()
    if failed:
        print(f"QC FAILED: {failed} of {len(projs)} dataset(s) — do not publish these", file=sys.stderr)
        return 1
    print(f"QC PASS: {len(projs)} dataset(s) — still eyeball the orthos before publishing")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
