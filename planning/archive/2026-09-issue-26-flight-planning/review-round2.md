# Review round 2 — `26-generate-flight-plans-from-boundaries-we`

Reviewer: fresh-eyes subagent, 2026-09-26. Scope: the fixes in `f74b513` for round 1's ten
findings, plus the four scripts read in full. Every finding below was reproduced by running
the code in a scratch copy; the repo working tree was not modified.

Baseline re-measured first, so the findings are relative to a **green** run:

```
flight_coverage.py --selftest          COVERAGE SELFTEST PASS                 exit 0
flight_wpml.py     --roundtrip *.kmz   ROUNDTRIP PASS: 5 fixture(s)           exit 0
flight_plan.py     --validate-fixtures FIXTURE VALIDATION PASS                exit 0
flight_budget.py   --selftest (py3)    BUDGET SELFTEST PASS: 7 flown missions exit 0
```

Restored-defect probes (in a copy under the scratchpad, never the working tree):

| fix | probe | result |
|---|---|---|
| #8 template.kml gate | mutated `<wpml:author>` in `render_template_kml` | `ROUNDTRIP FAILED`, exit 1, diff shown |
| #9 flight count | `measure_flights` stubbed to 2 of 7 rows | `calibrated on 7 flights but found 2`, exit 1 |
| #10 spacing guard | `plan_transects(..., side_overlap=1.0)` | `ValueError: transect spacing must be positive` |

---

## The mechanism behind round 1

Round 1's findings 1, 2, 3 and 5 are one shape:

> **A degenerate result is carried through the arithmetic as an ordinary small number
> instead of being branched on as a third state.**

`path_m == 0` was read as "fits". A `None` mission was read as a slot that had been used.
`budget_path <= 0` was read as "nothing to do here". "Over budget" was read as a warning
rather than as a state the exit status must carry. In every case the pipeline had a number
where it needed *absent / impossible / refused* — `code-check.md`, "Zero-length, empty and
unset are three different things", meeting "A guard that fails toward pass".

The round-1 fixes each added **one specific branch** (`n == 0`, `budget_path <= 0`,
iterate-don't-slice, exit non-zero) rather than making the degenerate state something the
pipeline carries. So the mechanism survives wherever a quantity can go degenerate by a route
the new branch does not name. It still reaches:

| # | site | state |
|---|---|---|
| a | `flight_plan.py:172-178` — `budget_path` small but **positive** | **finding 1, proven** — component vanishes with no record |
| b | `flight_plan.py:181, 194` — the two `min_block_ha` strip filters | **finding 1** — the only two places that discard area into no bucket |
| c | `flight_plan.py:179-185` — the loop bound derives from the same unbounded estimate | **finding 2, proven** — degenerate input becomes a hang, not a refusal |
| d | `flight_plan.py:67-76, 315-319` — `_max_transit_m` is the transit at which the survey path is **zero** | **finding 4** — reported as reach, so the user is told the wrong boundary |
| e | `flight_plan.py:402-412` — problems counted over all blocks, not the requested ones | **finding 3, proven** — exit 1 on a correct run |
| f | `flight_plan.py:411` — `skipped` | **finding 3** — dead arm; `split_to_budget:208` already removed every zero-station block |

---

## Findings

### [bug] `scripts/flight_plan.py:172-195` — a component inside the reported battery reach can still vanish with no record, and the run reports `PLAN COMPLETE` / exit 0

Round 1's finding 3 was fixed by recording `budget_path <= 0` as `unreachable`. The same
silent loss happens for `budget_path` **> 0 but small**, and nothing records it.

`lower = max(1, math.ceil(survey(comp)[0] / budget_path))` (178) is unbounded. When the
minimal-`n` search fails, the fallback at 188 is `_equal_area_strips(comp, lower)`, and every
one of those `lower` strips is below `MIN_BLOCK_HA`, so the filter at 194 discards all of
them. Neither that filter nor the identical one at 181 adds to any counter — `dropped`
counts only original components, `unreachable` only `budget_path <= 0`, `unflyable` only
blocks that reached the post-split check.

Measured, 10 ha at 4180 m transit — **inside** the 4223 m reach the script itself prints:

```
10.0 ha at 4180 m: budget_path 85.6 m, path 1101 m, lower 13, fallback strip size 0.77 ha < MIN_BLOCK_HA 1.0
-> 0 blocks in 0.2s ; meta={'dropped': 0, 'dropped_ha': 0.0, 'over_budget': 0,
                            'unreachable': 0, 'unreachable_ha': 0.0, 'unflyable': 0, 'unflyable_ha': 0.0}
-> AREA ACCOUNTED: 0.00 ha of 10.00 ha   <-- 10.00 ha vanished with no record
```

End to end, that component beside one good one, `--batteries 2 --radius 5000`:

```
=== Synthetic: 90.0 ha total, 90.0 ha within 5000 m of launch
=== split into 2 block(s) that each fit one battery
  synthetic_01: 40.0 ha ... OK
  synthetic_02: 40.0 ha ... OK
PLAN COMPLETE: 2 mission(s), 80.0 ha, 2 block(s) available
EXIT: 0
```

90 ha in, 80 ha planned, 10 ha gone, exit 0, and not even the
`(N further block(s) not written)` line fires because `len(blocks) == len(written)`.

The band is computable rather than exotic. A compact component loses everything whenever
`budget_path < 1e4 / transect_spacing ≈ 99 m`, i.e. transit above ~4174 m at 350 m AGL —
a 49 m band immediately inside the reach the script advertises, and the same band the default
`--radius 5000` sweeps over on every run.

**Fix shape:** the two `min_block_ha` strip filters need a bucket. Either accumulate the
discarded strips into `dropped`/`dropped_ha` (they are a different kind of drop from the
input slivers, so a separate key is clearer), or refuse earlier — treat
`budget_path < <one transect's worth of path>` as unreachable rather than only
`budget_path <= 0`.

---

### [bug] `scripts/flight_plan.py:179-185` — the minimal-`n` search is O(`lower`²) in geometry operations with `lower` unbounded, so the same input hangs rather than refusing

`while n <= max(lower * 2, 24)` bounds the search by the same unbounded estimate. Each
iteration runs `_equal_area_strips(comp, n)` (`(n-1) × 40` polygon intersections) and then
`flyable_and_fits` (a full `plan_transects`) per strip.

Measured on a **4-vertex** 100 ha square at 4180 m — the cheapest possible geometry:

```
budget_path=85.6 m  lower=128  loop runs n=1..256
  n=  1: _equal_area_strips     0.0 ms
  n=128: _equal_area_strips    80.5 ms, 128 pieces, 0 >= 1 ha
  n=256: _equal_area_strips   160.9 ms, 256 pieces, 0 >= 1 ha
  extrapolated total for the n-search: 20 s on a 4-vertex square
```

`_equal_area_strips` alone is ~20 s; adding ~32,000 `plan_transects` calls, the full
`split_to_budget` on that one square **did not finish in over five minutes** and had to be
killed. A real floodplain multipolygon (Peacock Creek ff04 is 25 parts) is far heavier, and
the loop runs **per component**.

Note the search is also provably futile in exactly this regime: from `n = 128` upward every
strip is under 1 ha, so `strips` is empty and `if strips and all(...)` can never be true.
The run grinds to `n = 256` to discover what the first empty `strips` already established.

`code-check-shell.md` calls this the expensive direction — an operation that hangs looks like
a slow query, not a bad input. Cap the search (a strip cannot usefully be smaller than
`min_block_ha`, which bounds `n` at `comp.area / (min_block_ha × 1e4)`), and break as soon as
`strips` comes back empty.

---

### [bug] `scripts/flight_plan.py:402-419` — the new non-zero exit counts blocks the user never asked to fly, and fires on the default flags over a correct plan

`problems` reads `split_meta` wholesale, which is computed over **every** block, while only
`args.batteries` of them are written. So a run that produced exactly what was asked for
exits 1. Measured, one good component and one 36 ha component at 4.4 km, stock flags:

```
=== Synthetic: 116.0 ha total, 115.6 ha within 5000 m of launch
    note: at 350 m one battery reaches about 4223 m of transit, less than --radius 5000 m;
          anything beyond that is reported as unreachable
  synthetic_01: 40.0 ha ... 913 s / 1500 s OK
  synthetic_02: 40.0 ha ... 1075 s / 1500 s OK
PLAN INCOMPLETE: 2 mission(s) written, 80.0 ha, but:
  - 1 component(s) beyond battery reach (35.6 ha)
EXIT: 1
```

Both requested missions were written, both fit, nothing flyable was lost — and the line the
script printed four lines earlier *announces that unreachable area is the expected outcome*
of `--radius 5000` against a 4223 m reach. So with stock flags, **any reach extending past
4.2 km exits 1 on a successful plan.** A status that is non-zero on the normal path is what
trains an operator to stop reading it, which is precisely what round 1's finding 5 set out to
prevent (`code-check.md`, "No arm labelled FAIL may exit 0", pointed the other way).

Two sub-parts of the same guard:

- **`over_budget` has the same problem in the sharper direction.** `split_to_budget` returns
  13 over-budget blocks for a 100 ha component at 3800 m (`over_budget: 13`); with
  `--batteries 3` the three written missions may all be `OK` and the run still exits 1 citing
  ten blocks nobody was going to fly.
- **`skipped` (411-412) is unreachable.** `split_to_budget:200-208` removes every block with
  `n == 0`, and `block_mission` recomputes the same deterministic `plan_transects`, so
  `mission is None` at 352 cannot happen. It is a counted problem state with no route to it —
  the opposite failure from the one the fix was written for, in the same `if`.

**Fix shape:** split the accounting into *what was planned* and *what was written*. Exit
non-zero on problems affecting the written set (an over-budget block that was actually
emitted) and on area lost with no plan for recovering it; report unreachable/unwritten blocks
as information, since the `--radius` note has already told the user to expect them.

---

### [fragile] `scripts/flight_plan.py:67-76, 315-319` — `_max_transit_m` reports the transit at which a battery can fly a **zero-metre** survey, and that number is handed to the user as "reach"

The bisection is correct for what it computes: `max_path_m(h, transit) > 0` is monotone, so
it converges on the transit at which the remaining survey path hits exactly 0. But the survey
path *at that boundary* is zero — no block can be flown there. What the note prints is:

```
note: at 350 m one battery reaches about 4223 m of transit
```

Measured usable survey path against transit at 350 m:

```
transit 3800 m -> 846 m of survey path
transit 4000 m -> 446 m
transit 4100 m -> 246 m
transit 4180 m ->  86 m     (less than one transect across a 1 ha block)
```

So the advertised reach overstates the useful one, and the 4174-4223 m tail it opens is
exactly where findings 1 and 2 bite. Report the transit at which a *minimum-size block*
still fits (`max_path_m(h, t) >= one transect's path`) rather than the zero crossing, and use
the same threshold for the `unreachable` branch at 173.

---

### [fragile] `scripts/flight_coverage.py:130` — a cut that grazes the polygon at a single point raises `AttributeError`, not a handled empty

```python
parts = [cut] if cut.geom_type == "LineString" else list(cut.geoms)
```

A `Point` result has no `.geoms`. Verified on shapely 2.1.2:

```
B2 vertex-tangent cut: Point
   AttributeError: 'Point' object has no attribute 'geoms'
```

`GeometryCollection` (the mixed Point+LineString case) is handled correctly, and the filter
on the next line would drop the point — it is only the *bare* `Point` that crashes. Reachable
on a raster-derived delineation whose parts touch at a pixel corner when a cut lands on that
x. Low probability, but it aborts a whole plan with a message that points at shapely rather
than at the geometry. One-line fix: `else list(getattr(cut, "geoms", []))`, or test
`cut.geom_type in ("LineString", "MultiLineString", "GeometryCollection")`.

Stress-tested for reassurance: 120 random 1-3 lobe blobs through `plan_transects` produced
**0 exceptions**, so this is the tail, not the common case.

---

### [fragile] `scripts/flight_plan.py:394-419` — `main()` does not flush stdout before writing its stderr verdict, so a redirected log reads verdict-first

The three gates all call `sys.stdout.flush()` immediately before their stderr summary
(`flight_coverage.py:245`, `flight_budget.py:246`, `flight_plan.py:266`). `main()` does not.
Under any redirection — which is how an operational script's output becomes the record —
stdout is block-buffered and the stderr block lands first. Observed in every captured run
above, e.g.:

```
    WARNING: 11 block(s) still over budget after splitting
PLAN INCOMPLETE: 2 mission(s) written, 80.0 ha, but:
  - 11 block(s) still over budget
comp 15.0 ha  transit 4150 m ...          <- the work that produced it, printed after
=== Synthetic: 95.0 ha total ...
```

The warnings at 332/335/338 have the same problem, printing before the `=== split into ...`
line they are qualifying. One `sys.stdout.flush()` before line 330 and one before 396.

---

## Checked, and *not* a problem

Recorded so round 3 does not re-derive them.

- **The serpentine regrouping (`flight_coverage.py:123-143`) is correct, and the reversal is
  correct in both halves.** Round 1's two-lobe fixture went from `turns 17151` to
  `turns 5908`, and the hops now alternate gap / spacing instead of crossing the gap on every
  transect:
  ```
  two lobes: 20 transects wayline 8000 turns 5908
  hops: 500 101 500 101 500 101 500 101 500 101 500 101 500 101 500 101 500 101 500
  ```
  Three lobes behave the same way (`300 300 101` repeating). The square case is unchanged
  (`101` throughout). The `reversed(segs)` **and** per-segment `coords[::-1]` are both needed
  and both present; dropping either would show up as a gap-crossing hop, and none appears.
- **`stations_along` is still consistent with it.** Stations are generated per line in flight
  order, and the endpoint append (`151-152`) guarantees the last station sits on the line end,
  so `turns_m` (measured end-to-start on `lines`) equals the distance actually flown between
  the last station of one transect and the first of the next.
- **`blocks = [b for b in blocks if b not in unflyable]` does what it looks like.** Shapely
  2.1.2's `__eq__` is structural, so `not in` is a geometric comparison and the filter works.
  The one misbehaviour is that *geometrically identical* blocks are all removed when one is
  unflyable — verified (three blocks, two identical, one in `unflyable` → two removed, one
  left) — which would under-report `unflyable_ha` and lose a flyable block. Not scored as a
  finding: `_equal_area_strips` cuts at distinct positions, so coordinate-identical strips are
  not produced.
- **`--review-layers` is consistent with the `.kmz` files.** `plan_transects` is
  deterministic, the layers are appended inside the write loop so they cover only missions
  actually written, and the station counts agree with the waypoint counts
  (`synthetic_01/02: 5 transects, 60 waypoints` / `stations rows: 120`). The recompute costs a
  second `plan_transects` per block and nothing else.
- **`actionGroupId` now increments and matches the fixtures' shape.** Measured across all
  five exports: myKMZ-2 and myKMZ-3 carry `i,i` per waypoint with the gimbal spanning
  `i..i+1` and the photo at `i..i`, exactly as `block_mission:238-243` emits. Two details the
  comment does not mention, neither of them a defect: the fixtures are not uniform (myKMZ-1
  and jet_lwd01 skip the photo on many waypoints — myKMZ-3 has 28 photos over 37 waypoints),
  and three of the five fixtures leave the **final** waypoint with no action group at all,
  where the generated file gives it a `takePhoto`. More photo stations than Map Pilot writes
  is the safe direction, but "Match the real exports exactly" is stronger than what the five
  files show.
- **`--validate-fixtures`' header no longer over-claims.** `flight_plan.py:23-28` now states
  the ~2.3-8.8 m/s band and that it does not exercise the splitter. Accurate.
- **The `_max_transit_m` bisection itself is sound** — `max_path_m` is monotone decreasing in
  transit, `hi = 50000` is far beyond any root (2×50000/6.21 s alone exceeds the budget), and
  a height whose climb/descent exhausts the budget returns `0.0` rather than looping. The
  problem is what the number means (finding 4), not how it is computed.
- **A `GeometryCollection` `working` geometry yields zero blocks.** `split_to_budget:161`
  tests `geom_type.startswith("Multi")`, which is False for `GeometryCollection`, so the whole
  collection becomes one "part" whose `geom_type != "Polygon"` and `kept` comes back empty.
  Fails loudly (`PLAN INCOMPLETE: no missions written`, exit 1) with a message that does not
  say why. Pre-existing, low reachability (needs `reach.intersection(buffer)` to yield mixed
  dimensions), not scored.

---

## Suggested order

1. **Finding 1** — it hands a field crew a plan that silently omits area and says
   `PLAN COMPLETE`. Same class as round 1's worst finding, one axis over.
2. **Finding 2** — the same input that triggers finding 1 hangs first, so finding 1 is only
   reachable on the small components. Both are fixed by bounding `n` against
   `min_block_ha`.
3. **Finding 3** — the exit status is the repo's gating convention and it is currently 1 on
   the default happy path, which is how a status stops being read.
4. **Findings 4-6** — one number that misleads, one crash in the tail, one ordering bug in
   the log.
