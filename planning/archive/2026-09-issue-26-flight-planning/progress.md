# Progress — Generate flight plans from boundaries we define (#26)

## Session 2026-09-26

- Plan-mode exploration — two Explore agents (`fly` API surface; this repo's script conventions)
- Established `fly` provides nothing for flight planning and fly#70 is still open — v1 does not
  depend on it
- Validated fly#70's sensor geometry against the five real KMZ missions: predicted 64.8 m photo
  spacing vs 64.9 m measured
- Found two fixture traps (`wpml:duration` is a constant; `morr_jet_lwd01` requests an impossible
  26 m/s) and the `morr_jet_lwd01` ↔ `wedzin_lwd001` ground-truth pairing
- Located the ff04 floodplain polygon: `floodplain.gpkg` over `/vsicurl/`, queryable by gnis name
- Phases approved by user
- Created branch `26-generate-flight-plans-from-boundaries-we` off main
- Next: Phase 1, the WPML writer

### Phase 1 — WPML writer (done)

- `scripts/flight_wpml.py`: reader + writer, action groups preserved verbatim on read
- All five fixtures re-emit **byte-for-byte exactly** (628 waypoints total)
- Found and fixed: Map Pilot's files end at `</kml>` with **no trailing newline**
- Found and fixed a defect in the gate itself: `splitlines()` discards the trailing-newline
  difference, so the detector fired while the explainer printed nothing. Added an arm that
  reports the trailing bytes when every line matches
- Gate proven both directions: trailing-byte difference caught and explained; a 1 m coordinate
  mutation caught at the exact line

### Phase 2 — Footprint and spacing (done)

- `scripts/flight_coverage.py`: gsd, footprint, spacing, long-axis bearing, serpentine transects,
  photo stations. Camera constants in one block, marked for supersession by fly#70
- Gate: at 300 m the model gives transect 86.4 m / photo 64.8 m against measured 86.0 / 64.9
- Also asserts spacing is linear in height, transect count over a 1 km square, serpentine ordering
  (the hop between transects is a turn, not a transit), and 100% footprint coverage of the block
- Guard proven: substituting the wrong 10.08 mm sensor width (the rounded-24mm-equivalent
  derivation) fails both spacing checks at 67.50 / 90.00 m

### Phase 3 — Budget model (done)

- `scripts/flight_budget.py`, calibrated on all seven published 2026 MORR flights from image EXIF
- **Commanding 10 m/s yields 6.2-10.5 m/s effective (median 7.5).** Every mission sets
  `toPointAndStopWithDiscontinuityCurvature`, so the aircraft stops at each photo station. A budget
  at the commanded speed over-promises coverage by about a third
- Sizing uses the **slowest** observed speed, not the median: too-small costs a battery, too-large
  truncates the flight. `wedzin_lwd001` is the recorded instance — 165 stations planned, 97 taken
- The gate caught my own budget constant: 18 min airborne (#26's figure) and my first 25 min both
  refuse `wedzin_cedric`, which spent 1308 s photographing and so was airborne ≥ 23.8 min. Budget
  is now 30 min with a 5 min reserve, bounded below by a flight that demonstrably happened
- Env split, deliberate: Pillow is only in system python3, the spatial stack only in `dff`. Model
  functions are pure stdlib and import from either; the EXIF read is lazy and **refuses** rather
  than returning empty when Pillow is absent
- One battery at 350 m: **85 ha** from the block edge, 75 ha with 500 m transit, 65 ha with 1 km

### Phases 4 and 5 — splitting and the Peacock Creek set (done)

- `scripts/flight_plan.py`: reads the floodplain gpkg over `/vsicurl/`, selects a reach by gnis
  name, clips to a radius of the launch point, splits to battery-sized blocks, writes one .kmz each
- Fixture gate passes: the three missions #26 flagged as over budget are called over, the two that
  fit are called fits, from their own `wpml:distance`
- Three wrong splits before this one, each caught by running it:
  - recursive bisection gave **129 blocks** for a 187 ha reach — a complex boundary fragments on
    every cut, and each fragment recursed
  - equal-area strips fixed that but exploding strips into their disjoint parts gave 10 blocks of
    12-30 ha; a mission can cover disjoint pieces, so strips are now kept whole
  - `ceil(path / budget)` over-split, leaving every battery ~70% full; now searches for the
    smallest n whose strips all fit
- **Peacock Creek, 3 batteries at 350 m: 109.2 ha**, blocks of 36.4 ha at 73-89% of budget, 6
  blocks available for the whole 187 ha reach
- Generated `template.kml` is **exactly 871 bytes**, matching Map Pilot's stub; all three generated
  missions round-trip through the reader exactly
- End-to-end against the real `wedzin_lwd001`: actual flown photo spacing 61.7 m against the
  model's 64.8 m and the mission file's planned 64.9 m
