# Review round 1 — `26-generate-flight-plans-from-boundaries-we`

Reviewer: fresh-eyes subagent, 2026-09-26. Scope: `git diff origin/main...HEAD`, four new
Python scripts under `scripts/` (~1160 lines). Every finding below was reproduced by
running the code, not inferred by reading; the probes are quoted.

All four gates were run first, so the findings are relative to a **green** baseline:

```
flight_coverage.py --selftest        COVERAGE SELFTEST PASS          exit 0
flight_wpml.py     --roundtrip *.kmz ROUNDTRIP PASS: 5 fixture(s)    exit 0
flight_plan.py     --validate-fixtures FIXTURE VALIDATION PASS       exit 0
flight_budget.py   --selftest (system python3) BUDGET SELFTEST PASS  exit 0
flight_budget.py   --selftest (conda dff)      refuses, RuntimeError exit 1   <- correct
```

The env-split refusal path is correct: under `dff` it raises with a message naming the
right interpreter and exits non-zero. It does not return an empty list and does not pass.

---

## Findings

### [bug] `scripts/flight_plan.py:125-129, 150-156` — `path_len()` returns 0.0 for a block that *cannot* be surveyed, and every guard downstream reads 0 as "fits"

`path_len()` returns `meta["path_m"]`. When a strip is narrower than the transect
spacing, `cov.transect_lines()` produces **zero** lines (`x = minx + spacing/2` already
exceeds `maxx`), so `wayline_m`, `turnaround_m` and `path_m` are all `0.0`. Then
`budget.fits(0.0, ...)` → `(True, 140.0, 1500.0)`.

Measured:

```
A narrow 40x3000 (12.0 ha): transects=0 stations=0 path_m=0.0
   budget.fits(path=0.0) -> (True, 140.0, 1500.0)
```

The consequence is not cosmetic. The minimal-`n` search at 150-156 is
`if strips and all(budget.fits(path_len(s), ...)[0] for s in strips)` — so the loop
**terminates as soon as the strips get thin enough to produce no transects at all**, and
reports that as the chosen split. Reproduced with a 100 ha component 4 km from launch
(`box(4000,0,5000,1000)`, launch at origin, 350 m):

```
blocks: 24 {'dropped': 0, 'dropped_ha': 0.0, 'over_budget': 0}
  block 1: 12.0 ha transit 100 m -> SKIP (no stations)
  block 2: 33.3 ha transit 2000 m -> 45 wpts
  block 3: 33.3 ha transit 2028 m -> 45 wpts
  block 4: 33.3 ha transit 2108 m -> 45 wpts
  block 5: 5.0 ha transit 4000 m -> SKIP (no stations)
  ... blocks 5-24 are all 5.0 ha, 50 m wide, 0 stations ...
```

Twenty of the twenty-four "blocks" are 50 m wide against a 100.8 m transect spacing and
cover nothing. The post-split verification at 170-175 — the code comment calls it "the
check on" the prediction — is blind to it for the same reason: `fits(0.0)` is `True`, so
`over_budget` reports **0**.

This is the "zero-length, empty and unset are three different things" mechanism:
`path_m == 0` conflates *nothing to fly* with *cannot be flown*. The guard has to
distinguish them — e.g. `path_len` returning `None` (or `meta["n_stations"]` being
carried alongside) and the `all(...)` requiring `n_stations > 0` as well as `fits`.

---

### [bug] `scripts/flight_plan.py:282-287` — an unsurveyable block consumes a `--batteries` slot

`for i, b in enumerate(blocks[:args.batteries], 1)` takes the slice **before** the
`if mission is None: … continue` skip at 285-287. So a block that yields no stations
still occupies one of the N requested missions, and viable blocks further down `blocks`
are never reached. Measured on the fixture above:

```
with --batteries 2, main() slices blocks[:2] -> writes: 1 mission(s) instead of 2
```

The user asked for two missions, got one, and the run still ends at line 303 with
`PLAN COMPLETE` and exit 0. Because `blocks` is sorted nearest-first (178), the
degenerate blocks are systematically the ones closest to launch — i.e. the slots most
likely to be consumed. Iterate and count written missions until `args.batteries` is
reached, rather than slicing up front.

---

### [bug] `scripts/flight_plan.py:145-147` — a whole component is dropped silently when transit exhausts the battery, and the default `--radius` makes that routine

```python
budget_path = budget.max_path_m(height_m, transit_m=transit(comp))
if budget_path <= 0:
    continue
```

`max_path_m` clamps at `max(0.0, ...)`, so an out-of-reach component `continue`s with no
record. It is not counted in `split_meta["dropped"]` (that key counts only the
sub-hectare slivers), so `main` prints nothing about it. Measured — two components, one
at 1 km and one 100 ha component at 4.6 km:

```
components in: 2  blocks out: 2  meta: {'dropped': 0, 'dropped_ha': 0.0, 'over_budget': 0}
-> the 100 ha component at 4.6 km is gone; split_meta reports nothing about it
```

The numbers say this is the normal case, not an edge case. At the default `--height 350`
the maximum round-trip transit the budget allows is 4223 m:

```
max_path_m(350, transit=4000) = 445.6
max_path_m(350, transit=4223) = 0.0
max_path_m(350, transit=5000) = 0.0   <- default --radius is 5000
```

So with stock flags, everything between 4.2 km and the 5 km working radius disappears —
immediately after line 263-264 has printed that area to the user as being *within* scope
(`"{working.area/1e4:.1f} ha within {args.radius:.0f} m of launch"`). Count and report
these the way the sliver drop is counted, or clamp `--radius` to the reachable transit and
say so.

---

### [bug] `scripts/flight_plan.py:196-197` — every `actionGroupId` in a generated mission is `0`; all five real exports use distinct, incrementing ids

`gimbal_action(group_id=0, …)` and `photo_action(group_id=0, index=i)` are called with the
default `group_id=0` for every waypoint. Generated output:

```
waypoints: 136  actionGroupIds distinct: ['0']  count: 137
first gimbal group start/end: ('0', '135')
```

Every real Map Pilot export disagrees. From `myKMZ-3.kmz`:

```
actionGroupIds: ['0','0','1','1','2','2','3','3','4','4','5','5','6','6','7','8','9','9','10','10']
```

— the id tracks the waypoint index, and the gimbal group is `startIndex=i / endIndex=i+1`,
not `0 / N-1`. This directly contradicts the design statement at `flight_wpml.py:31-33`
("Kept as named constants so a generated mission matches what has actually flown").

**The round-trip gate cannot catch this, by construction.** `read_kmz` captures action
groups as raw text (`action_xml`, line 111) and `render_waylines` re-emits that text
verbatim (line 199), so `gimbal_action()` and `photo_action()` are **never executed** by
`--roundtrip`. The five PASSes say the parser and the pass-through are exact; they say
nothing about the two functions that invent action XML for a new mission — which is the
only part of the writer a generated plan depends on.

Whether the aircraft rejects duplicate `actionGroupId`s is untested here and is not
something this review can settle. The finding is that the generated file departs from all
five known-good files on a field the module set out to match, and no gate can see it.

---

### [fragile] `scripts/flight_plan.py:275-278, 300-308` — `PLAN COMPLETE` and exit 0 over blocks that will truncate in the air

The over-budget warning goes to stderr (277) and the per-block line prints `OVER BUDGET`
(296), but `main` returns 0 and prints `PLAN COMPLETE` as long as **one** mission was
written. A caller gating on the exit status — which is how every other gate in this repo
is consumed — sees success. `split_meta["over_budget"] > 0` and any skipped block should
either return non-zero or at minimum not be announced as complete. (Same shape as
`code-check.md`, "No arm labelled FAIL may exit 0"; here the label is WARNING, but the
consequence — an aircraft that comes home with the block half-flown — is the one the whole
budget model exists to prevent.)

---

### [fragile] `scripts/flight_plan.py:52-60, 209-229` — `--validate-fixtures` has a ~4x margin on both sides and cannot discriminate the decision it exists to protect

The gate passed, and the printed numbers show why that means little:

```
20260722_morr_jet_lwd01        17406 m    2923 s / 1500 s  OVER
myKMZ-1                        12651 m    2157 s / 1500 s  OVER
myKMZ-2                        12097 m    2068 s / 1500 s  OVER
myKMZ-3                         3221 m     639 s / 1500 s  fits
20220722_morr_braid04-2          306 m     169 s / 1500 s  fits
```

The fits/over boundary is at `(1500-120) * 6.21 = 8570 m`. The nearest fixtures are 3221
and 12097 — nothing within a factor of 2.6 of the boundary in either direction. Solving
for what still passes:

- `EFFECTIVE_SPEED_MS` anywhere in **[2.33, 8.77] m/s** passes. That range contains
  `EFFECTIVE_SPEED_MEDIAN_MS = 7.50` — the value `flight_budget.py:56-59` argues must
  never be used for sizing because it truncates flights.
- usable budget anywhere in **[639, 2068) s** passes. That range contains 960 s, i.e.
  #26's rejected "18 min airborne, 2 min reserve", which `flight_budget.py:79-95`
  explicitly overturns.

So the gate is green for both the calibrated constants and the two specific alternatives
the modules were written to rule out. It is a smoke test for `fits()` being wired up, not
evidence for the constants. Worth saying so in the header rather than leaving it reading
as a calibration check.

Related, `flight_plan.py:23-24` claims `--validate-fixtures` "checks the splitter against
the five Map Pilot missions". It does not touch the splitter, does not open the fixtures,
and is pure arithmetic over two dicts defined 30 lines above it. The `--help` string at
246-247 is accurate; the header comment is not.

---

### [fragile] `scripts/flight_coverage.py:126-133` — serpentine alternates by global index, not per connected part, so a deliberately-multipart strip ping-pongs

`lines.sort(key=lambda ln: (round(ln.centroid.x, 3), ln.centroid.y))` then
`if i % 2 == 1: coords.reverse()`. When one x-cut crosses two disjoint parts, both parts
sit at the same rounded x and the alternation runs across them. `flight_plan.py:160-164`
deliberately keeps such strips whole ("One mission can cover disjoint pieces"), so this is
a planned input, not a pathological one.

Measured on two 40 ha lobes 900 m apart (`MultiPolygon([box(0,0,1000,400), box(0,900,1000,1300)])`, 350 m):

```
two lobes: 20 transects, wayline 8000 turns 17151
hops: 900 906 900 906 900 906 900 906 900 906 900 906 900 906 900 906 900 906 900
turnaround 68% of path
```

The aircraft crosses the 900 m gap on **every** transect: 8 km of survey costs 25 km of
flying. `turns_m` is computed and fed to the budget (`flight_coverage.py:159-160`), so this
will not truncate a flight — but it inflates the path by ~3x, which makes `split_to_budget`
cut ~3x as many blocks, defeating the stated aim at `flight_plan.py:150-155` ("Minimal n is
what makes three batteries cover as much as three batteries can").

The selftest cannot reach it: `box(0,0,1000,1000)` yields exactly one part per cut, so the
`lines[0] → lines[1]` hop check at 222-226 only ever sees the single-part case. A
two-lobe fixture is the one-line addition that would.

Fix shape: group `lines` by the part they came from (or by a gap in centroid.y at equal x),
alternate within a group, and order groups nearest-first.

---

### [fragile] `scripts/flight_wpml.py:267-310` — the round-trip gate reads only `waylines.wpml`; `render_template_kml` is never checked

`_roundtrip` reads `wpmz/waylines.wpml` (274) and compares against `render_waylines` (279).
`write_kmz` emits **two** files (262-263), and the second one is never compared to
anything. `render_template_kml`'s output happens to match the fixtures (verified by hand
here), but that is not what the gate asserts, and the module comment at 10-14 states the
contract as "parsing a real Map Pilot export and re-emitting it must reproduce it exactly"
— which reads as covering both members of the zip.

Two lines to close: read `wpmz/template.kml` alongside and diff it the same way.

Adjacent, and worth knowing rather than fixing: a generated `.kmz` re-emitted through this
module's own reader is exact by construction —

```
self round-trip of generated file exact: True
```

— so that result is not evidence about anything (`code-check.md`, "Verification that reads
its own output"). The five real fixtures are the only load-bearing part of this gate.

---

### [fragile] `scripts/flight_budget.py:180-200` — the selftest never asserts the flight count

`measure_flights` skips any dataset with `len(pts) < 3` (146-147) and any with
`elapsed <= 0` (153-154). `_selftest` then guards only two numbers: `sp[0]` against
`EFFECTIVE_SPEED_MS` and `max(elapsed_s)` against `OBSERVED_MAX_PHOTO_TIME_S`. Both are
extremes belonging to specific datasets (`wedzin_canyon_km25`, `wedzin_cedric`). If the
other five lose their `images/` directory — moved, re-stitched, archived — the gate passes
and prints `model consistent with 2 flown missions` while the docstring table at 38-49
pins seven rows. `if len(rows) != 7` is the missing line; the count is already printed at
190, so it is one comparison away from being asserted.

(The same two guards do correctly catch a *changed* extreme, and `rows == []` correctly
refuses at 183-187. This is only the partial-loss direction.)

Minor, same function: the budget check at 213-219 uses `climb_descent_s(300.0)` hardcoded
while the flights it iterates may not all have been at 300 m.

---

### [fragile] `scripts/flight_coverage.py:114-122` — `transect_spacing_m <= 0` is an infinite loop

`while x < maxx: … x += transect_spacing_m`. `spacing()` returns `across * (1 - side_overlap)`,
which is `0.0` at `side_overlap = 1.0` and negative above it. `side_overlap` is a
parameter of both `spacing()` and `plan_transects()`, so a caller passing 1.0 hangs with no
output rather than erroring. Not reachable from any CLI today (no overlap flag exists), but
it is the failure mode that hangs rather than fails, which is the expensive direction. One
guard at the top of `transect_lines`.

---

## Checked and *not* a problem

Recorded so the next reviewer does not re-derive them.

- **The `oriented_envelope` divide-by-zero RuntimeWarning is benign.** It fires on
  `minimum_rotated_rectangle` of a square. The result is correct:
  `mrr: POLYGON ((0 0, 0 1000, 1000 1000, 1000 0, 0 0))`, `bearing on square: 0.0`,
  not NaN. A rectangle gives `bearing 2000x500: 90.0`. Suppressing or "fixing" it would be
  churn; it is shapely reporting an interior division on a degenerate-aspect case.
- **The env split and its refusal path are correct.** `stream_resolve.py` imports
  `PIL` at module level, so `from stream_resolve import image_points` raises `ImportError`
  under `dff`, which `measure_flights` converts to a `RuntimeError` naming the right
  interpreter, and both `--selftest` and `--calibrate` exit 1. It does not return `[]`.
- **`wpml:distance` round-trips at full precision.** The fixture carries
  `3221.03105532339`; `float()` → `f"{m.distance}"` reproduces it exactly, which is why the
  gate passes. Coordinate `:.6f`, height `:.1f` and speed `:.2f` likewise match all five
  fixtures byte for byte — the 6 dp on longitude is ~0.065 m at latitude 54, against an
  86 m transect spacing.
- **`takeOffSecurityHeight`.** Generated missions write the survey height into
  `waylines.wpml` and `20` into `template.kml`. All five fixtures are `300` / `20`, and all
  five flew at 300 m — so the generated `350` / `20` is consistent with the observed
  convention rather than a divergence.
- **`dropped = [p for p in parts if p not in kept]`** works: shapely 2's `__eq__` makes
  `in` a structural comparison and the sliver accounting came out right
  (`{'dropped': 1, 'dropped_ha': 0.01}`). It would misclassify two byte-identical
  components, which a raster-derived delineation is not going to produce.
- **`long_axis_bearing` raises `AttributeError` on a zero-area polygon** (its
  `minimum_rotated_rectangle` is a `LineString`, which has no `.exterior`). Loud, and the
  `min_block_ha` filter stands in front of every call site, so not reported as a finding.

---

## Suggested order

1. `path_len` returning 0 for an unsurveyable block (finding 1) — it is the root of
   findings 2 and the `over_budget: 0` in finding 3's output, and it is the one that hands
   a field crew a plan covering nothing.
2. The `--batteries` slice (finding 2) and the silent component drop (finding 3) — both
   small, both change what the user is handed today with default flags.
3. `actionGroupId` (finding 4) — cheap to change, and it is the only finding whose
   consequence is the aircraft refusing the file at the trailhead.
4. The gate weaknesses (6, 7, 8, 9) — none change an output, all change what a green run
   is worth.
