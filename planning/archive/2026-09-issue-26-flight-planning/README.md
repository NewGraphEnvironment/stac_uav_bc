# Flight-plan generation for the Morice floodplain (#26)

## Outcome

Four scripts under `scripts/` turn a floodplain polygon and a launch point into DJI WPML
`.kmz` missions sized to one battery each: `flight_wpml.py` (read/write), `flight_coverage.py`
(footprint, spacing, serpentine transects), `flight_budget.py` (endurance) and `flight_plan.py`
(the driver). Shipped in PR #34.

Delivered for the immediate driver: **three missions over Peacock Creek, 143.2 ha**, at 350 m
AGL and 10 m/s from the confluence launch point, plus a `plan.gpkg` for review in QGIS.

## Measurement

The camera model is validated rather than assumed. fly#70's sensor geometry predicts 64.8 m
along-track photo spacing at 300 m; the median wayline segment across all five flown Map Pilot
missions is **64.9 m**. A competing derivation from the rounded 24 mm equivalent would predict
67.5 m and is ruled out by the fixtures.

The budget is calibrated on all seven published 2026 MORR flights from image EXIF. **Commanding
10 m/s yields 6.2-10.5 m/s effective, median 7.5** — every mission stops at each photo station —
so budgeting at the commanded speed over-promises coverage by about a third. That is the
recorded cause of `wedzin_lwd001` planning 165 stations and taking 97. Sizing uses the slowest
observed speed, because too-small costs a battery and too-large truncates a flight.

#26's 18-minute airborne budget is not consistent with the imagery: `wedzin_cedric` spent
1308 s photographing, so it was airborne at least 23.8 min. The model uses 30 min with a 5 min
reserve, bounded below by a flight that demonstrably happened.

## Evidence

- `planning/archive/2026-09-issue-26-flight-planning/review-round{1..5}.md` — five review rounds
- Fixtures: `~/Downloads/{myKMZ-1,myKMZ-2,myKMZ-3,20260722_morr_jet_lwd01,20220722_morr_braid04-2}.kmz`
- Calibration imagery: `~/Projects/gis/uav_imagery/skeena/morice/2026/wedzin_*`

## The durable lesson

Five review rounds, each finding its best defect **inside the previous round's fix**. Round 5
named the shape behind all of them: *a state known at the point of production, carried onward as
a number and re-derived downstream.* `path_m == 0` read as "fits"; a lost `budget_path`; an
all-or-nothing fit test that sent 162 flyable hectares to `unsplittable`; a speed re-derived from
a default and wrong by 5.25x; a provenance re-derived from recursion depth.

Two rounds of patching individual branches did not end it, and neither did a reviewer saying the
code looked right. What ended it was parsing `split_to_budget` and listing every name bound
inside it: one producer each for `eff`, `area_in`, `disc`, `native`, `path`, `n`, `clipped`,
`halves`, `inside`, `outside`, `blocks`, `buckets` and `polygon`. Nothing is derived twice and
able to disagree with itself. A count, not an opinion.

The second lesson is about the guard I added to prevent the first. `unaccounted_ha` was meant to
make area loss impossible to hide, and round 3 broke it in one attack out of seven: `area_in` was
summed *after* the polygon filter, so a `GeometryCollection` lost 199.9 ha and still reported
`0.00`. **An invariant measured after the loss cannot see the loss.** Six other attacks held, and
a positive control fired — which is what made the one failure meaningful.
