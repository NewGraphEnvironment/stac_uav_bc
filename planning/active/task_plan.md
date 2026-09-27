# Task: Generate flight plans from boundaries we define, split to fit the battery (#26)

Flight boundaries are drawn by hand in Map Pilot and **never survive export** — every KMZ carries a
byte-identical 871-byte stub `template.kml` with no polygon. So there is no record of what a flight
was meant to cover, no way to re-edit a mission, and no systematic way to plan coverage of a large
area. Blocks are also sized by eye and three of four measured missions exceed the battery budget.

Immediate driver: three batteries from a launch point at the **Peacock Creek confluence**
(-126.79270, 54.36067), flying the Morice floodplain at **350 m AGL, 10 m/s**, **ff04** delineation.

## Phase 1: WPML writer

- [ ] `scripts/flight_wpml.py` — waypoints + params → `wpmz/template.kml` + `wpmz/waylines.wpml` → `.kmz`
- [ ] Emit the 871-byte `template.kml` stub verbatim; it is constant across all five exports
- [ ] Pin every field observed constant in the fixtures: `executeHeightMode=relativeToStartPoint`,
      `finishAction=goHome`, `gimbalPitchRotateAngle=-85`, `globalTransitionalSpeed=9.5`,
      `waypointHeadingMode=followWayline`, `useStraightLine=1`
- [ ] Round-trip test: parse each of the five real KMZs, re-emit, assert equal ignoring
      `createTime`/`updateTime` — proves the writer reproduces known-good files before it invents any
- [ ] Record `droneEnumValue 68` as observed-not-understood (#26 open question); do not silently change it

## Phase 2: Footprint and spacing

- [ ] `scripts/flight_coverage.py` — camera + height + overlap → footprint, transect spacing, photo spacing
- [ ] Constants from fly#70, with the derivation in a comment; **assert 300 m → 64.8 m** against the
      measured 64.9 m as a regression test
- [ ] Serpentine transect generation over a polygon, with bearing chosen along the polygon's long axis

## Phase 3: Budget model, calibrated on ground truth

- [ ] Elapsed time per published 2026 MORR dataset from image EXIF (first → last capture)
- [ ] Pair each with its KMZ where one exists; model climb + transit + survey + RTH + descent
- [ ] Fit and report climb/descent rate rather than assuming it
- [ ] Assert the model reproduces each paired flight's measured elapsed time within a stated tolerance
- [ ] **Never read `wpml:duration`** — test asserting the parser ignores it

## Phase 4: Block splitting

- [ ] Split a polygon until each block fits one battery at the configured height/speed
- [ ] Must flag all three known over-budget missions (myKMZ-1, myKMZ-2, morr_jet_lwd01)
- [ ] Must leave myKMZ-3 (25 ha) unsplit
- [ ] Block naming `<stream>_<feature><NN>`, `_p1`/`_p2` when split

## Phase 5: Peacock Creek set

- [ ] `scripts/flight_plan.py` — read `floodplain.gpkg` over `/vsicurl/`, select ff04 by gnis name,
      clip to a radius of the launch point, split, order, write KMZs
- [ ] Produce the three-battery set from the Peacock Creek launch point
- [ ] Review in QGIS against the ortho before anything flies

## Phase 6: Does DJI Fly import it (field, not code)

- [ ] Load one generated KMZ into DJI Fly on the Mini 4 Pro and report what happens
- [ ] Untestable from here — Map Pilot is the known-good consumer since it wrote these files

## Validation

- [ ] Round-trip: all five fixture KMZs re-emit equal
- [ ] Spacing: 300 m predicts 64.8 m against the measured 64.9 m
- [ ] Budget: reproduces each paired flight's EXIF elapsed time within tolerance
- [ ] Splitting: catches all three over-budget fixtures, leaves the in-budget one alone
- [ ] End-to-end: generated waypoints for the `lwd001` block fall within the actual image GPS spread
      of `wedzin_lwd001`
- [ ] `/code-check` clean on each commit
- [ ] PWF checkboxes match landed work
- [ ] `/planning-archive` on completion
