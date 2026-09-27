# Review round 3 — `26-generate-flight-plans-from-boundaries-we`

Reviewer: fresh-eyes subagent, 2026-09-26. Scope: the four scripts read in full at
`5ae643b`, plus rounds 1 and 2. **This round's job was enumeration**, per the brief: walk
the files mechanically for every quantity that can go degenerate, say for each whether it
is branched on or carried as a number, and attack the round-2 accounting invariant
adversarially.

Every probe ran in `/private/tmp/.../scratchpad`; the repo working tree was never modified
(`git status --short` clean, `flight_plan.py` md5 `7c4e33e1…` unchanged at start and end).

Baseline re-measured first, so findings are relative to a **green** run:

```
flight_coverage.py --selftest          COVERAGE SELFTEST PASS                 exit 0
flight_wpml.py     --roundtrip *.kmz   ROUNDTRIP PASS: 5 fixture(s)           exit 0
flight_plan.py     --validate-fixtures FIXTURE VALIDATION PASS                exit 0
flight_budget.py   --selftest (py3)    BUDGET SELFTEST PASS: 7 flown missions exit 0
```

and one real end-to-end run, which is correct and is the reference for what "working"
looks like:

```
=== Peacock Creek: 187.3 ha total, 187.3 ha within 5000 m of launch
    area in 187.3 ha = planned 185.2 + slivers 2.13 (23) + unreachable 0.0 (0)
                     + unsplittable 0.0 (0) + unaccounted 0.00
PLAN COMPLETE: 3 mission(s), 136.5 ha, 5 block(s) available          EXIT 0
```

---

## 1. Enumeration — the complete candidate set

Walked mechanically: every division, every `len()`/index, every `float()` parse, every
`max`/`min` clamp, every geometry-type dispatch, every CLI argument. **58 quantities.**
`prod` = where produced, `cons` = where consumed, `state?` = is a degenerate value branched
on as a distinct state, or carried as a number.

### `flight_coverage.py`

| # | quantity | prod | cons | degenerate route | state? | verdict |
|---|---|---|---|---|---|---|
| 1 | `gsd(h)` | :60 | :66 | `h=0` → 0; `h<0` → negative; `h=nan/inf` | carried | downstream guards catch 0/negative; nan/inf reach #5 |
| 2 | `footprint(h)` | :66 | :72,:167,:240 | same as #1 | carried | same |
| 3 | `t_sp` (transect spacing) | :72 | :104,:126,:138 | `side_overlap>=1.0` → `<=0` | **branched** :104 | **HANDLED** (round-1 fix #10) — probe A1 raises `ValueError` |
| 4 | `p_sp` (photo spacing) | :72 | **:151** | `forward_overlap>=1.0` → 0 | **carried** | **FINDING 1** — `ZeroDivisionError` |
| 5 | `t_sp` = NaN/inf | :72 | :104 | `h=nan` → `nan<=0` is False | **carried** | guard bypassed; yields 0 transects → caught later by #16. Not a finding |
| 6 | `long_axis_bearing` | :79 | :111,:119,:184 | zero-area poly → MRR is LineString → `.exterior` AttributeError | unguarded | fenced by `min_block_ha`; **0 of 25** real Peacock parts give a non-finite bearing (probe G1). Not a finding |
| 7 | `rect.exterior.coords` 4-side loop | :88 | :92 | MRR with <4 sides | unguarded | same fence |
| 8 | `cut` geom type | :128 | :133 | bare `Point` | **branched** :133 `hasattr` | **HANDLED** (round-2 fix #5) |
| 9 | `cut` = GeometryCollection(**MultiLineString**) | :128 | :134 | nested multi-part | **carried** — filter drops it | **FINDING 6** (latent; not reproduced from a real cut in 400 trials) |
| 10 | `segs` empty | :134 | :135 | cut is all points | **branched** :135 | HANDLED |
| 11 | `cuts` empty (strip narrower than spacing) | :127 | :140 | `minx+t_sp/2 > maxx` | carried → `lines=[]` | consumed as `n_stations==0` at #16, **branched** there. HANDLED (round-1 fix #1) |
| 12 | `n` in `stations_along` | :151 | :152 | `line.length < p_sp` → `max(1,0)`=1 | **branched** `max(1,…)` | HANDLED |
| 13 | `p_sp < 0` | :72 | :151 | `forward_overlap>1.0` | **carried** | **FINDING 1b** — no raise, 30 stations where 150 are needed |
| 14 | `turns_m` on `len(lines)<2` | :171 | :182 | `range(-1)` empty | naturally 0 | correct |
| 15 | `wayline_m` on empty lines | :168 | :182 | 0 | carried → `path_m`=0 | branched at #16 |
| 16 | `n_stations` | :179 | `flight_plan:170,174` | 0 = **unflyable** | **branched** `n > 0` :174 | HANDLED (round-1 fix #1) |
| 17 | selftest `covered` union of 0 stations | :241 | :242 | empty → `frac`=0 | branched (`frac<0.99`) | HANDLED |
| 18 | `CRS_METRIC`/`CRS_WGS84` | :56-57 | *nowhere* | — | — | dead constants (nit) |

### `flight_budget.py`

| # | quantity | prod | cons | degenerate route | state? | verdict |
|---|---|---|---|---|---|---|
| 19 | `climb_descent_s(h)` | :102 | :108,:124,:227 | `h<0` → negative | carried | no CLI route; `flight_plan` fences |
| 20 | `speed_ms` | param | :109,:110,:124 | 0 → ZeroDivisionError | unguarded | no caller passes 0 (`--speed` is **not** wired here — see #45) |
| 21 | `max_path_m` clamp | :125 | `flight_plan:189` | `max(0.0, …)` collapses "negative remaining" to 0 | **branched** at `flight_plan:197,212` | HANDLED (round-1 fix #3) |
| 22 | `max_path_m` small-but-positive | :125 | `flight_plan:189` | round-2 finding 1 | **branched** via `n_max` bound + `len(strips)==n` | HANDLED (round-2 fix) |
| 23 | `image_points` ImportError | :138 | :143 | no Pillow | **branched** → RuntimeError | HANDLED (accepted as deliberate) |
| 24 | `len(pts) < 3` skip | :150 | :159 | dataset loses images | carried (silently fewer rows) | **branched** by `len(rows)!=7` :200. HANDLED (round-1 fix #9) |
| 25 | `elapsed <= 0` skip | :157 | :159 | one-second flight | same | same. HANDLED |
| 26 | `rows == []` | :161 | :187 | root missing | **branched** :187 | HANDLED |
| 27 | `speed_ms = path/elapsed` = 0 | :160 | :193,:207 | path 0 | carried | caught by `abs(sp[0]-6.21)>0.05` |
| 28 | `strptime` on bad EXIF | :152 | — | malformed tag | raises | loud |
| 29 | `climb_descent_s(300.0)` hardcoded | :227 | :228 | flights not all at 300 m | **carried** | round-1 minor, **still present** — FINDING 7 (nit) |
| 30 | median calc `sp[len//2]` | :174 | :176 | `len(sp)==0` | fenced by :166 | correct |
| 31 | `math.cos(la)` in `_haversine` | :131 | — | lat 90 → 0 | n/a for BC | fine |

### `flight_wpml.py`

| # | quantity | prod | cons | degenerate route | state? | verdict |
|---|---|---|---|---|---|---|
| 32 | `_tag()` → `None` (tag absent) | :90 | :109,:116 | missing tag | **carried into `float(None)`** | raises `TypeError` — loud, acceptable |
| 33 | `_tag()` → `""` (tag present-but-empty) | :90 | :117-124 | `"" or DEFAULT` | **conflated with absent** | silently substitutes a constant; the round-trip gate then FAILs loudly. Not a finding |
| 34 | `coords.group(1)` | :105 | :106 | no `<coordinates>` | `None.group` | raises — loud |
| 35 | `float(_tag(…,"distance") or 0.0)` | :123 | :177 | empty → 0.0 | **branched** (`or`) | correct |
| 36 | `w.lon/lat/height/speed` = NaN/inf | caller | :183,:186,:187 | `--speed nan` | **carried** | **FINDING 3** — writes `nan` into the .kmz, exit 0 |
| 37 | `_num(v)` on nan/inf | :207 | :176 | `is_integer()` False | **carried** | same finding |
| 38 | `m.waypoints == []` | :180 | :180 | empty mission | loop no-ops | a 0-waypoint .kmz is writable; `block_mission` fences it |
| 39 | `z.read("wpmz/template.kml")` | :99 | :126 | absent member | **branched** `except KeyError` | HANDLED |
| 40 | `_roundtrip` path missing | :273 | :276 | unmatched shell glob | `FileNotFoundError` **not** in the except tuple | **FINDING 8** (nit) — traceback not a clean FAIL; fails toward refusal |
| 41 | `len(paths)` as denominator | :322,:324 | report only | duplicates/dirs | cosmetic | fine |
| 42 | `wpml:duration` | :82 | :178 | constant | — | accepted, out of scope |

### `flight_plan.py`

| # | quantity | prod | cons | degenerate route | state? | verdict |
|---|---|---|---|---|---|---|
| 43 | `args.height` | :294 | :328,:334,:338 | **`0` → ZeroDivisionError at :80**; `nan`/`inf` → reach `0.0`; `<0` → bogus reach then `ValueError` | **no validation** | **FINDING 4** |
| 44 | `args.batteries` | :297 | :358,:421 | `0`/negative → breaks immediately | carried → "no missions written", exit 1 | loud enough; nit |
| 45 | `args.speed` | :295 | **only** `block_mission:256,259` | never reaches `budget.fits` | **carried** | **FINDING 2** — commanded speed is decoupled from the budget that gates it |
| 46 | `args.radius` | :298 | :319 | `0`/negative → empty → `SystemExit` | **branched** :320 | HANDLED |
| 47 | `args.stream` in a filename | :360 | :371 | `/` in a gnis_name | unguarded | data-sourced; nit |
| 48 | `_max_transit_m` `side/t_sp` | :80 | :81 | `t_sp==0` (h=0) | **carried** | FINDING 4 |
| 49 | `_max_transit_m` result | :89 | :329 | zero-path reach | **fixed** to a min-block reach (round-2 fix #4) | HANDLED — reports 4173 m, not 4223 m |
| 50 | `working` is empty | :319 | :320 | radius misses | **branched** :320 | HANDLED |
| 51 | `working` is a **GeometryCollection** | :319 | :176-177 | tangent intersection (**reproduced**, probe B4) | **carried** — filtered out, area never enters `area_in` | **FINDING 5** |
| 52 | `parts` type filter | :177 | :180 | drops non-Polygon | **carried** | FINDING 5 — the filter runs *before* `area_in` |
| 53 | `area_in` | :180 | :223,:231 | derived from the **filtered** list | — | FINDING 5 — one fact derived twice |
| 54 | `budget_path <= 0` | :189 | :197,:212 | out of reach | **branched** → `unreachable` | HANDLED (round-1 fix #3) |
| 55 | `n_max` | :195 | :197,:198 | unbounded search | **bounded** :195 | HANDLED (round-2 fix #2) — 187 ha worst case now 10.6 s, was >5 min |
| 56 | `len(strips) == n` | :204 | :204 | strips lost to the min-area filter | **branched** | HANDLED (round-2 fix #1) — closes the 10 ha silent loss |
| 57 | `all(flyable_and_fits(x))` over strips | :204 | :204 | one far strip out of reach kills every n | **carried, all-or-nothing** | **FINDING 9 — the headline** |
| 58 | `else: buckets["planned"].append(comp)` | :215 | — | — | **unreachable arm** | FINDING 10 (nit) — proven dead |
| 59 | `mission is None` | :362 | :367 | — | **unreachable** (round 2 said so; confirmed in 40-union sweep) | dead but harmless belt-and-braces |
| 60 | `unaccounted_ha` | :231 | :427 | see §3 | **branched** :427 | **partially blind** — §3 |
| 61 | stale `.kmz` in `--out` | :371 | field crew | a shorter re-run | **not handled** | **FINDING 11** |
| 62 | unused imports `LineString`, `unary_union` | :38-39 | — | — | — | nit |

---

## 2. Members still reachable — the findings

### [bug] `flight_plan.py:204` — **a component that straddles the battery-reach boundary is classified wholly `unsplittable`, and 120+ ha of flyable floodplain yields zero missions.** This is round 2's mechanism one axis over

`flyable_and_fits` is applied to **every** strip and the split is accepted only if **all**
of them fit (`all(...)` at :204). Reachability is not a property of a component — it varies
*within* one. `transit(comp)` at :189 is the distance to the **nearest** point, so a
component with one foot inside the reach never lands in `unreachable`; then no `n`
satisfies `all(...)`, `chosen` stays `None`, and :212-213 puts the **whole** component into
`unsplittable`.

Synthetic, a 300 m-wide ribbon running away from launch — the shape a river reach *is*:

```
      span from launch      ha  planned  sliver  unreach  unsplit  blocks
            200-4000 m   114.0    114.0     0.0      0.0      0.0      16
            200-4200 m   120.0    120.0     0.0      0.0      0.0      27
            200-4500 m   129.0      0.0     0.0      0.0    129.0       0   <-- cliff
            200-5000 m   144.0      0.0     0.0      0.0    144.0       0
```

The same area cut into 200 m chunks and planned separately yields **120.0 ha flyable**.
Nine hectares of unreachable tail destroy the plan for the 120 ha that were fine.

**Reproduced on the real Peacock Creek geometry**, launch moved along the valley:

```
 launch offset    near     far   in_ha  planned  unreach  unsplit  blocks
             0     152    2992   186.5    185.2      0.0      0.0       7
          1000    1017    3990   186.0    185.2      0.0      0.0      23   <-- 8 ha/battery
          2000    2008    4988   184.4      0.0      2.3    182.1       0
          2500    2507    5488   162.2      0.0      0.0    162.2       0
```

End to end at offset 2500, stock flags:

```
=== Peacock Creek: 187.3 ha total, 162.2 ha within 5000 m of launch
    note: at 350 m one battery reaches about 4173 m of transit, less than --radius 5000 m;
          anything beyond that is reported as unreachable
=== split into 0 block(s) that each fit one battery
    area in 162.2 ha = planned 0.0 + slivers 0.00 (0) + unreachable 0.0 (0)
                     + unsplittable 162.2 (1) + unaccounted 0.00
PLAN INCOMPLETE: no missions written                                    EXIT 1
```

Three things are wrong with that report, beyond the zero blocks:

- `unreachable` reads **0.0** — the one bucket that names the real cause is empty, and the
  note four lines above has just promised the operator that out-of-reach area "is reported
  as unreachable". It is not.
- `unsplittable` reads as *"this geometry is too awkward to cut"*. The geometry is a
  1.4 km-wide floodplain; the cause is range.
- The accounting is **honest** (162.2 in, 162.2 disposed) and still useless, because a
  total disposition says nothing about whether the disposition was *right*.

The `--radius 5000` default exceeds the 4173 m reach on every run, so this is the default
configuration, not an edge case. `code-check.md` calls it the mirror mistake: *"a guard that
fails toward **abort** on an operation where partial failure is certain"* — round 2 fixed
"lose area silently" into "refuse everything loudly", and the intermediate state (plan the
reachable part, report the rest) is the one nobody built.

Note also the offset-1000 row: 23 blocks for 185 ha, 8 ha per battery. The minimal-`n`
search is being driven to a large `n` purely to make the far strips fit, which defeats the
stated aim at :190-194 ("Minimal n is what makes three batteries cover as much as three
batteries can") **before** it reaches the cliff.

**Fix shape:** clip each component to the reachable disc before splitting —
`comp.intersection(launch.buffer(_max_transit_m(height_m)))` — plan the intersection, and
put the difference in `unreachable` (where the note already promised it). That makes
reachability a property of the *geometry* rather than a scalar per component, keeps the
total disposition exact, and turns a 0-mission exit 1 into a correct 3-mission plan plus an
accurate unreachable figure.

---

### [bug] `flight_coverage.py:151` — `photo_spacing_m <= 0` divides by zero; the round-1 fix landed on `side_overlap`'s twin and never on this one

Round 1's finding 10 guarded `transect_spacing_m <= 0` at :104. `p_sp` is the **other**
output of the same `spacing()` call, a parameter of the same public `plan_transects()`
signature, and consumed 47 lines later with no guard. Measured:

```
A1: side_overlap=1.0    -> ValueError: transect spacing must be positive, got 0.0   [guarded]
A2: forward_overlap=1.0 -> ZeroDivisionError: float division by zero                [NOT guarded]
```

`code-check.md`, "A fix lands in one of two callers that share a harness": *"if you have
fixed the same class twice in one of a pair, the pair is the bug."*

**And the negative branch is the silent one, which is worse.** `forward_overlap > 1.0`
raises nothing and returns a plausible answer:

```
A3: forward_overlap=1.5 -> NO RAISE. p_sp=-189.1  n_stations=30  path_m=10908
    first 3 stations: [(50.4, 0.0), (50.4, 810.9), (50.4, 1000.0)]
```

30 stations over a 1 km square where the correct answer is 150 — a survey with 80% of its
photographs missing, and a `path_m` the budget will happily approve.

**Fix:** move the guard into `spacing()` (or the head of `plan_transects`) so it covers
both outputs, rather than adding a second one-site branch — which is the exact edit that
produced this finding.

---

### [bug] `flight_plan.py:295,256,259` — `--speed` never reaches the budget model that gates the mission

`args.speed` is consumed **only** by `block_mission` (`Waypoint(speed=…)`, `auto_speed=…`)
and written into the `.kmz`. `budget.fits` is called at :370 with no `speed_ms`, so it
always uses `EFFECTIVE_SPEED_MS = 6.21`:

```
commanded --speed   2.0: budget.fits() -> est 1428 s
commanded --speed  10.0: budget.fits() -> est 1428 s
commanded --speed  26.0: budget.fits() -> est 1428 s
grep: does flight_plan.py pass args.speed to budget?  False
```

The 6.21 m/s constant is the *measured effective* speed at a commanded 10 m/s — the
module's own headline (`flight_budget.py:50-54`). It is not a speed-independent constant.
`--speed 2` writes a mission the aircraft will fly at roughly a fifth of the assumed rate
and the plan reports `OK`; `--speed 26` is exactly what `20260722_morr_jet_lwd01.kmz` did
and what `flight_budget.py:10-12` names as untrustworthy, and it is accepted silently.

**Fix shape:** either refuse any `--speed` other than the calibrated 10.0 (the only
commanded speed the model has evidence for), or scale — `EFFECTIVE_SPEED_MS * args.speed /
10.0` — and say in `--help` which it is. Leaving the two unconnected is the bad option,
because the flag *looks* like it is being honoured.

---

### [bug] `flight_plan.py:294-295` — `--speed nan` writes `nan` into the flight plan and reports `PLAN COMPLETE`, exit 0

Neither `--height` nor `--speed` is validated. `--speed nan` produces a mission file the
aircraft cannot parse, with a success verdict:

```
PLAN COMPLETE: 1 mission(s), 42.0 ha, 2 block(s) available            EXIT 0
  <wpml:autoFlightSpeed>nan</wpml:autoFlightSpeed>
  <wpml:waypointSpeed>nan</wpml:waypointSpeed>
```

`--height 0` is the loud sibling — an unhandled `ZeroDivisionError` traceback from inside a
bisection helper:

```
    reach_m = _max_transit_m(args.height)
  File ".../flight_plan.py", line 80, in _max_transit_m
    n_t = max(1.0, side / t_sp)
ZeroDivisionError: float division by zero
```

`--height nan` and `--height inf` both report `reach 0.0 m` and then classify everything
unsplittable; `--height -350` reports a **5042 m** reach (larger than the real one) before
dying in `transect_lines`. Four degenerate heights, four different failure shapes, none of
them a message naming the argument.

**Fix:** one `ap.error` block after `parse_args` — `math.isfinite` and a positive range on
`--height`, `--speed`, `--radius`, and `>= 1` on `--batteries`. `code-check-shell.md`, "A
value validated with one numeric grammar and consumed with another": normalise once, at the
boundary, rather than adding a predicate per consumer.

---

### [bug] `flight_plan.py:177,180` — the accounting invariant computes `area_in` from the already-filtered parts, so the one real area-loss route is invisible to it

This is §3's answer, and it is a finding rather than only an observation.

```python
parts = [p for p in parts if p.geom_type == "Polygon" and not p.is_empty]   # :177
area_in = sum(p.area for p in parts) / 1e4                                   # :180
```

The type filter runs **before** the number the invariant is checked against. Anything it
drops never enters `area_in`, so the buckets balance perfectly against a total that has
already been reduced. Measured:

```
B2: GeometryCollection(Polygon 40 ha, LineString)
   TRUE input area   : 40.0056 ha
   acc['area_in_ha'] : 0.0000 ha
   buckets           : planned 0.0  sliver 0.0  unreach 0.0  unsplit 0.0
   unaccounted_ha    : 0.0000   -> main() flags? False
   REAL area lost    : 40.0056 ha   <<< HIDDEN
```

And a `GeometryCollection` is a **reproduced** output of the intersection at :319, not a
hypothetical — a component tangent to the radius circle gives one with real area:

```
B4: tangent case geom_type = GeometryCollection  area=10000.0000
```

Restore-the-defect, both directions:

```
M1 (drop one chosen strip, AFTER area_in): unaccounted_ha = 39.99  -> guard fires? True
M2 (type filter drops a 200 ha polygon, BEFORE area_in): unaccounted_ha = 0.00 -> fires? False
```

So the guard is not decoration — it can fire — but it is blind on exactly the route that
loses area. `code-check.md`, "One fact derived twice": *"derive the expectation from the
artifact the consumer actually consumes"*, and "Verification that reads its own output":
the expectation and the thing checked share a producer three lines apart.

The whole-GeometryCollection case does end in `exit 1` ("no missions written"), so it is not
*silent* — but the printed accounting says `area in 0.0 ha` two lines under a header saying
`162.2 ha within 5000 m of launch`, which points a reader at the radius rather than at the
geometry type.

**Fix:** `area_in = polygon.area / 1e4` (the unfiltered input), and give the dropped
non-polygon parts their own bucket (`nongeometric`, or fold into `unaccounted`). One line
each, and the invariant then covers the route it was written for.

---

### [fragile] `flight_coverage.py:133-134` — a nested `MultiLineString` inside a `GeometryCollection` cut is dropped with no error

```python
parts = list(cut.geoms) if hasattr(cut, "geoms") else [cut]
segs  = [p for p in parts if p.geom_type == "LineString" and p.length > 0]
```

The round-2 fix moved from an explicit type list to `hasattr`, which is the right shape —
but `parts` is only flattened one level, and the filter then requires `"LineString"`
exactly:

```
I1: GeometryCollection([MultiLineString(...)])
    parts=['MultiLineString']  segs kept=0  -> 20 m of transect DROPPED, no error
```

**Not reproduced from a real cut** (400 randomised cuts over an L-shaped polygon and three
deliberate tangencies produced only `LineString` and `MultiLineString` at the top level —
GEOS flattens). Recorded as a latent hole in a filter whose whole job is to handle the
shapes GEOS might return, and whose failure direction is silent under-coverage.

**Fix:** flatten recursively, or `segs = [g for g in cut.geoms if …]` after
`shapely.get_parts(cut)`, which flattens fully.

---

### [fragile] `flight_budget.py:227` — the budget check still hardcodes `climb_descent_s(300.0)` for flights that were not all at 300 m

Round 1 raised this as a minor; it is unchanged. `rows` iterates all seven datasets and each
is credited with the climb/descent of a 300 m flight. Every fixture *was* at 300 m today, so
the number is right and the **premise is unstated** — a dataset flown at 350 m would be
checked against the wrong floor, in the loose direction. One line: carry the height per row,
or assert in the comment that the calibration set is all-300 m and make *that* the thing
that breaks.

---

### [fragile] `flight_wpml.py:276` — `FileNotFoundError` is not in the except tuple, so an unmatched glob is a traceback rather than a clean FAIL

The module header prescribes `--roundtrip ~/Downloads/*.kmz`. When the glob matches nothing
the shell passes the literal, and:

```
    self.fp = io.open(file, filemode)
FileNotFoundError: [Errno 2] No such file or directory: '.../nope-*.kmz'
```

Non-zero exit, so it fails toward refusal — the safe direction. It is the gate's own
documented invocation producing a traceback that reads as a code defect rather than "you
pointed me at nothing". Add `FileNotFoundError` to the tuple at :276.

---

### [fragile] `flight_plan.py:357-371` — a shorter re-run leaves the previous run's `.kmz` files in `--out`, and the header claims otherwise

Block names are `{stream}_{len(written)+1:02d}`, so a 2-battery run overwrites `_01` and
`_02` and leaves `_03` from a 3-battery run:

```
after a 3-battery run:     ['peacock_creek_01.kmz','peacock_creek_02.kmz','peacock_creek_03.kmz']
after a 2-battery re-run:  ['peacock_creek_01.kmz','peacock_creek_02.kmz','peacock_creek_03.kmz']
```

`flight_plan.py:15-16` states *"Idempotent: re-running overwrites the same block .kmz files
in --out and nothing else, so an interrupted run is safe to repeat."* The first clause is
true and the guarantee a field crew needs is the other one: the directory is what gets
loaded into the controller, and a stale `_03` is a block that belongs to no current plan and
carries nothing to say so. Same class as `code-check.md`, "Written data outlives the fix".

**Fix:** remove `{stream}_*.kmz` from `--out` before the write loop (and `plan.gpkg`), or
write into a per-run subdirectory. Either makes the header's claim true.

---

### [nit] `flight_plan.py:215` — the `else: buckets["planned"].append(comp)` arm is unreachable

Reaching it needs `chosen is None` **and** `budget_path > 0` **and**
`flyable_and_fits(comp)`. But the sliver filter at :183 guarantees
`comp.area/1e4 >= min_block_ha`, hence `n_max >= 1`; `_equal_area_strips(comp, 1)` returns
`[comp]`; so `n=1` gives `len(strips)==1` and `all(flyable_and_fits([comp]))` — and `chosen`
is set. Instrumented and run over 60 randomised components: the arm never fired. The
`n_max >= 1` conjunct at :197 is likewise always true.

Harmless, but it is a dead state inside a classifier whose value is that its states are
total and exhaustive — the same shape round 2 flagged for `skipped`. Either delete it or
turn it into an assertion that says what it believes.

### [nit] `flight_plan.py:38-39` — `LineString` and `unary_union` are imported and never used.

---

## 3. Adversarial test of the accounting invariant

`acc["unaccounted_ha"]` is meant to make area loss impossible to hide. **Seven attacks; one
succeeded.**

| # | attack | result |
|---|---|---|
| 1 | **Area lost inside a chosen split** — strips filtered by `min_block_ha` | **held.** `len(strips) == n` at :204 rejects any `n` where a strip was filtered, so `chosen` always tiles the component. This is round 2's fix and it works |
| 2 | **Rotation round-trip loss** in `_equal_area_strips` | **held.** Measured on a square, a skew quadrilateral and an L-shape at n=2,5,13: `sum(pieces) - poly.area` is `0.0` or `3.7e-16` relative. The 0.5 ha tolerance at :427 is ~13 orders of magnitude of headroom |
| 3 | **Overlapping components / MultiPolygon parts that touch** | **held.** A valid MultiPolygon's parts have disjoint interiors, so `sum(p.area)` equals the union area. 40 randomised `unary_union`s of 1-4 boxes: worst real loss `-0.000000000 ha` |
| 4 | **A component counted into two buckets** | **impossible by construction.** Each `comp` reaches exactly one `append` before a `continue`; the 40-union sweep would have shown it as a *negative* loss and did not |
| 5 | **Floating-point accumulation over many parts** | **held.** Real Peacock Creek: 25 parts, 187.3 ha, `unaccounted 0.00` |
| 6 | **Loss injected after `area_in` is computed** (positive control) | **guard fires** — `unaccounted_ha = 39.99`, `abs(...) > 0.5` True. The guard is not decoration |
| 7 | **Non-Polygon input filtered out before `area_in`** | **GUARD BLIND** — 199.9 ha lost, `unaccounted_ha = 0.00`. See finding 5 |

So the invariant is genuinely strong over the domain it covers — Polygon and MultiPolygon
input, any split, any bucket — and its one hole is structural rather than numerical:
**`area_in` is derived downstream of the filter it would need to be upstream of.** Attacks
1-5 all failed, which is the valuable half of this answer; the round-2 fix does what it
claims within its domain.

**A separate limitation worth stating, because it is what finding 9 exploits:** a *total*
disposition proves nothing was lost, not that anything was disposed of correctly. In the
straddling case the accounting reads `162.2 ha in = 162.2 ha unsplittable, unaccounted 0.00`
— perfectly balanced, zero missions, and 100+ ha of it flyable. An invariant that can be
satisfied by putting everything in one bucket cannot be the terminal check on its own. The
missing companion assertion is a *cross-bucket* one: no component may be `unsplittable` if
its intersection with the reachable disc is itself splittable.

---

## 4. Checked, and *not* a problem

- **Round 2 finding 2 (the unbounded hang) is fixed and the bound is adequate.** The
  `n_max` cap at :195 turned round 2's ">5 minutes, killed" into a measured worst case:
  `187 ha, no viable split: 10.66 s`; `100 ha: 3.0 s`; every succeeding case `≤ 0.01 s`.
  Real Peacock Creek (182 ha component, 25 parts) plans in well under a second.
- **Round 2 finding 6 (stdout/stderr ordering) is fixed.** With a direct interpreter the
  redirected log reads in order: the `===` block, the per-block lines, then `PLAN
  INCOMPLETE`. The `sys.stdout.flush()` at :410 does it. *Caveat worth one line in the
  header:* under `conda run -n dff` — the invocation the module documents — conda buffers
  and emits stderr first, so a captured log still reads verdict-first. That is conda, not
  the script, and `conda run --no-capture-output` avoids it.
- **`long_axis_bearing` does not produce NaN on real data.** The
  `invalid value encountered in oriented_envelope` warnings on the Peacock run are the
  accepted square/degenerate-aspect case: **0 of 25** parts give a non-finite bearing, and
  both parts ≥ 1 ha give clean bearings (131.987°, 126.656°).
- **The NaN-height route is closed downstream even though the `<= 0` guard misses it.**
  `spacing(nan)` → `nan <= 0` is False, so `transect_lines` does not raise — but
  `while nan < maxx` is False, so 0 transects, 0 stations, and `n > 0` at :174 catches it.
  The guard that *should* have fired did not; the one two layers down did.
- **`block_mission` returning `None` is unreachable**, confirmed over the 40-union sweep in
  addition to round 2's reasoning. `split_to_budget` requires `n > 0` per chosen strip and
  `plan_transects` is deterministic.
- **`--batteries 0` / negative** breaks on the first block and exits 1 with "no missions
  written". Ugly, not wrong.
- **`_tag()` conflating absent with present-but-empty** substitutes a module default, which
  the round-trip gate then catches as a byte difference. The gate covers it.
- **`--radius 0` / negative** yields an empty `working` and a named `SystemExit`.
- **The `--validate-fixtures` header, the `actionGroupId` shape, the env-split refusal, the
  serpentine regrouping and `_max_transit_m`'s bisection** were all re-read and remain as
  round 2 left them.

---

## Suggested order

1. **Finding 9** (straddling components → 0 missions). It is the only one that hands a crew
   nothing on a reach that is mostly flyable, it is on the default flags, and it is round
   2's own mechanism one axis over — the third instance of "the degenerate state is carried
   at the wrong grain", now the grain being *the component* rather than *the number*.
2. **Finding 5** (`area_in` after the filter). Two lines, and it is what makes the round-2
   invariant terminal rather than nearly-terminal.
3. **Finding 1** (`photo_spacing_m`) and **finding 2** (`--speed`). Both are a produced
   quantity reaching a consumer that never checks it; finding 1 is the documented sibling
   pattern, finding 2 silently invalidates the budget.
4. **Finding 4** (argument validation) and **finding 11** (stale `.kmz`). One `ap.error`
   block and one `unlink` loop; both turn a bad output into a refusal.
5. **Findings 6, 7, 8** and the two nits — none changes an output today.
