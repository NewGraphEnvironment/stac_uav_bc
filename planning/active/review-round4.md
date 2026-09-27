# Review round 4 — `26-generate-flight-plans-from-boundaries-we`

Reviewer: fresh-eyes subagent, 2026-09-26. Scope: the four scripts at `4dba4be`, read in
full, against rounds 1–3. **This round was a re-verification, not a fresh hunt**: re-walk
round 3's 62-row enumeration against the rewritten `split_to_budget`, then attack round 3's
own fixes.

Every probe ran in `/private/tmp/.../scratchpad`. The working tree was never modified —
`flight_plan.py` md5 `6f7b7a7bb4162bad4b7687e7a074b191` and `git status --short` empty at
both start and end.

Baseline re-measured first, so findings are relative to a **green** run:

```
flight_coverage.py --selftest             COVERAGE SELFTEST PASS                  exit 0
flight_wpml.py     --roundtrip *.kmz      ROUNDTRIP PASS: 5 fixture(s)            exit 0
flight_plan.py     --validate-fixtures    FIXTURE VALIDATION PASS                 exit 0
flight_budget.py   --selftest (py3)       BUDGET SELFTEST PASS: 7 flown missions  exit 0
```

and the real end-to-end, which is **better than round 3's** and is the reference for what
"working" looks like now (4.7 s wall):

```
=== Peacock Creek: 187.3 ha total, 187.3 ha within 5000 m of launch
    area in 187.3 ha = planned 184.9 + slivers 2.18 (28) + unreachable 0.3 (3)
                     + unsplittable 0.0 (0) + non-polygon 0.00 (0) + unaccounted -0.00
PLAN COMPLETE: 3 mission(s), 143.2 ha, 5 block(s) available          EXIT 0
```

(round 3 measured 136.5 ha in 3 missions from 5 blocks; the per-piece recursion recovers
6.7 ha and keeps the blocks fuller.)

---

## 1. Re-walk of round 3's 62-row enumeration

Every row re-checked against the new code, and every row that carried a **fix** re-probed
rather than re-read. **No row's handling was lost in the rewrite.** Three rows moved,
eleven closed, two remain open unchanged, and one row's guard turns out to close only half
of what its own comment claims (finding 4 below).

### Rows whose handling MOVED (and is still present)

| row | round 3 site | where it lives now | verdict |
|---|---|---|---|
| 3, 4, 13 | `t_sp`/`p_sp` guarded at the consumer (`:104`) or not at all | `spacing()` itself, `flight_coverage.py:84-89` | **closed at the producer**, both outputs |
| 51–53 | `area_in` derived from the filtered parts | `area_in = polygon.area / 1e4`, `flight_plan.py:204`, plus a `nonpolygon` bucket at `:210-212` | **closed** — §3 below |
| 54–57 | `budget_path`, `n_max`, `len(strips)==n`, `all(flyable_and_fits)` | all four deleted; replaced by `dispose()` `:214-233` + the disc clip `:240-248` | **replaced**; the quantities they guarded no longer exist |
| 58 | dead `else: buckets["planned"]` arm | deleted | closed |
| 61 | stale `.kmz` | `:398-401` unlink loop | **present but destructive-first** — finding 3 |
| 62 | unused `LineString`, `unary_union` imports | deleted | closed |
| 29 | hardcoded `climb_descent_s(300.0)` | `CALIBRATION_HEIGHT_M`, `flight_budget.py:81,252` | closed (named) |
| 40 | `FileNotFoundError` missing from the except tuple | `flight_wpml.py:276` | closed — unmatched glob now `exit 1, clean FAIL`, no traceback |
| 36, 37, 43–46 | unvalidated `--speed` / `--height` / `--radius` / `--batteries` | `_finite_positive` + range checks, `flight_plan.py:345-354` | closed |

Measured, all eight CLI degenerates now refuse at `exit 2` with a message naming the flag:

```
--height 0     exit 2  --height must be positive and finite, got 0.0
--height nan   exit 2  --height must be positive and finite, got nan
--height -350  exit 2  --height must be positive and finite, got -350.0
--speed  nan   exit 2  --speed must be positive and finite, got nan
--speed  0     exit 2  --speed must be positive and finite, got 0.0
--radius 0     exit 2  --radius must be positive and finite, got 0.0
--batteries 0  exit 2  --batteries must be at least 1, got 0
--launch 999 999  exit 2  --launch is not a lon/lat pair: [999.0, 999.0]
```

and round 3's three spacing probes now all raise at the producer:

```
side_overlap=1.0     -> ValueError: side_overlap must be in [0, 1), got 1.0
forward_overlap=1.0  -> ValueError: forward_overlap must be in [0, 1), got 1.0
forward_overlap=1.5  -> ValueError: forward_overlap must be in [0, 1), got 1.5     [was SILENT]
```

### Rows carried unchanged (still correct, or still a nit)

| row | state |
|---|---|
| 5 | `spacing(nan)` now **raises**; `spacing(inf)` returns `(inf, inf)` — finding 4 |
| 6, 7 | `long_axis_bearing` on a degenerate MRR: still fenced, and `dispose()` cannot create a sub-1 ha piece that reaches it (the size arm fires first) |
| 9 | nested `MultiLineString` inside a `GeometryCollection` cut: **still latent**, unchanged, still not reproduced from a real cut |
| 18 | `flight_coverage.CRS_METRIC` / `CRS_WGS84` still dead constants (2 references = the 2 definitions). Carried nit |
| 20 | `estimate_s(speed_ms=0)` still divides by zero; now unreachable — `effective_speed_for(0)` raises first |
| 32–35, 38, 39, 41, 42 | `flight_wpml.py` otherwise untouched by round 3; all verdicts hold |
| 59 | `mission is None` still an unreachable belt-and-braces arm, still harmless |

### Rows where a NEW quantity appeared and was checked

`effective_speed_for` (`flight_budget.py:110-121`) and `max_depth` / `dispose` are new
since round 3's enumeration. Probed:

```
effective_speed_for(0)    -> ValueError          effective_speed_for(nan) -> ValueError
effective_speed_for(-5)   -> ValueError          effective_speed_for(inf) -> inf        <-- finding 4
effective_speed_for(10.0) == EFFECTIVE_SPEED_MS  -> True
max_path_m(350, transit_m=99999)                 -> 0.0 (clamped)
```

`unsplittable` is **not** dead under `max_depth=8` — a 3014 ha blob puts 267.93 ha in it
(24 pieces), a 1600 ha square at the disc edge 35.91 ha (6). So the classifier's states are
all live except `nonpolygon`, which is exercised only by mixed-container input.

---

## 2. Findings — three of them inside round 3's own fixes

### [bug] `flight_plan.py:240` and `:369` — `_max_transit_m()` does not see `--speed`, so the reach disc round 3 introduced is computed at a speed the fit test no longer uses

Round 3 wired the commanded speed into the budget through `budget.effective_speed_for()`.
It reached **two** of the three consumers — `flyable_and_fits` (`:199`) and the per-mission
check (`:421`) — and not the third. `_max_transit_m` (`:90-112`) calls
`budget.max_path_m(height_m, transit_m=mid)` at the default `EFFECTIVE_SPEED_MS`, and its
signature does not even take a speed:

```
signature: (height_m, min_block_ha=None)
mentions speed? False
```

That third consumer is the one that now **defines the `unreachable` bucket** (`:240`) and
prints the operator note (`:369-373`). So the disc and the fit test disagree, by up to 5x:

```
--speed   2.0  eff  1.24 m/s   disc used    4173 m   true reach     795 m   ratio 5.25
--speed   5.0  eff  3.10 m/s   disc used    4173 m   true reach    2061 m   ratio 2.02
--speed  10.0  eff  6.21 m/s   disc used    4173 m   true reach    4173 m   ratio 1.00
--speed  20.0  eff 12.42 m/s   disc used    4173 m   true reach    8396 m   ratio 0.50
--speed  26.0  eff 16.15 m/s   disc used    4173 m   true reach   10929 m   ratio 0.38
```

**Both directions are reachable and both are wrong.**

*Too large* — real Peacock Creek, stock flags plus `--speed 2`:

```
=== Peacock Creek: 187.3 ha total, 187.3 ha within 5000 m of launch
    note: at 350 m one battery reaches about 4173 m of transit, ...
          anything beyond that is reported as unreachable
=== split into 27 block(s) that each fit one battery
    area in 187.3 ha = planned 60.2 + slivers 126.83 (250) + unreachable 0.3 (3)
                     + unsplittable 0.0 (0) + non-polygon 0.00 (0) + unaccounted 0.00
  peacock_creek_01: 5.7 ha ... 1337 s / 1500 s OK
PLAN COMPLETE: 3 mission(s), 12.1 ha, 27 block(s) available          EXIT 0
```

143.2 ha at `--speed 10` becomes **12.1 ha** at `--speed 2`, 127 ha is filed under
`slivers` (250 of them), `unreachable` reads **0.3** four lines under the note promising it
would be reported there, and the verdict is `PLAN COMPLETE` at **exit 0**. The note itself
is wrong as printed: at `--speed 2` the real reach is 795 m, not 4173 m.

*Too small* — a 9 ha block 6000 m out, which the budget's own verdict says fits:

```
--speed 10.0 eff  6.21: budget.fits -> False (2250 s / 1500 s) | splitter: planned 0.0  unreachable 9.0
--speed 26.0 eff 16.15: budget.fits -> True  ( 951 s / 1500 s) | splitter: planned 0.0  unreachable 9.0
```

At 26 m/s the block fits with 550 s to spare and the splitter files all 9 ha as unreachable,
because the disc is pinned at the 6.21 m/s figure.

This is `code-check.md`, "A fix lands in one of two callers that share a harness" — and the
count is the signal: `effective_speed_for` was threaded through three sites in one commit
and one was missed.

**Fix shape:** `_max_transit_m(height_m, min_block_ha=None, speed_ms=EFFECTIVE_SPEED_MS)`,
pass `budget.effective_speed_for(commanded_ms)` from `:240` and
`budget.effective_speed_for(args.speed)` from `:369`. One argument, three call sites, and
it makes the printed note true for every `--speed`.

---

### [bug] `flight_plan.py:215-218` — `dispose()` tests SIZE before FLYABILITY, so a piece the recursion drove under `min_block_ha` is reported as a `sliver` whatever drove it there

```python
def dispose(poly, depth):
    if poly.is_empty or poly.area / 1e4 < min_block_ha:
        if not poly.is_empty:
            buckets["sliver"].append(poly)        # <-- reached by TWO different causes
        return
    if flyable_and_fits(poly):
        ...
```

A piece arrives here for one of two reasons: it was a sub-hectare fragment of the raster
delineation (a genuine sliver, "not a survey target", `:125-128`), or `dispose` halved it
repeatedly because it would not fit and the halves fell under the threshold. The second is
a **budget or coverage failure wearing a size label**, and `sliver` is the reassuring one:
it is printed with `.2f`, it is what the header explains away, and — unlike
`unsplittable` in round 3's cliff — **it never gates the exit status** (`:471-480` counts
only missing missions, over-budget missions and `unaccounted_ha`).

The cleanest instance is coverage rather than budget, and it fires at **default flags**. A
reach narrower than half a transect spacing produces zero transects, and halving it
perpendicular to its long axis can never change that — measured on a 40 m × 3 km arm
(12 ha), which is an ordinary shape for a ff04 delineation:

```
the arm alone: 12.0 ha -> 0 transects, 0 stations   (transect spacing 100.8 m at 350 m AGL)
depth 0: halves -> [(6.0 ha, 0 transects), (6.0, 0)]
depth 1: halves -> [(3.0, 0), (3.0, 0)]
depth 2: halves -> [(1.5, 0), (1.5, 0)]
depth 3: halves -> [(0.75, 0), (0.75, 0)]   <-- now under min_block_ha -> bucket "sliver"
```

15 `plan_transects` calls, every one returning 0 transects, every one guaranteed in advance
to, and the result is 16 "slivers". Beside one good block, that is the silent case:

```
in 76.0 ha -> blocks 1  planned 64.0  sliver 11.89 (16)  unreach 0.1  unsplit 0.0  unacc +0.000
  area in 76.0 ha = planned 64.0 + slivers 11.89 (16) + unreachable 0.1 (0) + ...
  with --batteries 1: 1 of 1 block(s) written, no shortfall -> PLAN COMPLETE, exit 0
```

**16 slivers averaging 0.74 ha each** is the tell a human might catch; nothing in the code
catches it. A 40-bar comb (96 ha of 30 m ribbons) produces `sliver 96.00 (160)` the same way.

`flyable_and_fits` (`:195-199`) is where the two causes are conflated:

```python
return n > 0 and budget.fits(...)[0]
```

`n == 0` means *cannot be surveyed at this height at all* — cutting makes it strictly worse.
`fits(...) == False` means *too big for one battery* — cutting is exactly the remedy. The
recursion treats them the same, which is round 3's own mechanism one more axis over: an
awkward result carried through the arithmetic (here, through eight levels of halving)
instead of being disposed of as its own state at the point it is known.

**Fix shape:** split the predicate and give the coverage failure its own bucket.

```python
path, n = survey(poly)
if n == 0:
    buckets["unsurveyable"].append(poly)   # too narrow for one transect at this height
    return                                  # halving cannot help — do not recurse
```

and move the size test **after** it, so `sliver` means only "was small on arrival". Then
add `unsurveyable_ha` and any `sliver` piece born at `depth > 0` to the `problems` list at
`:471`, because both are area the splitter failed on rather than area the flags excluded.

Provenance is measurable today, which is what makes the two causes separable — instrumented
on the real Peacock run, the 28 slivers are **20 native (1.85 ha) and 8 cut-born (0.33 ha,
largest 0.125 ha)**, so the default run is honest and the bucket is doing its job there. At
`--speed 2` it is 250 pieces and 126.83 ha, all cut-born.

---

### [bug] `flight_plan.py:398-401` — the stale-`.kmz` sweep runs BEFORE anything is written, so a run that produces no blocks empties the directory the crew flies from

Round 3's finding 11 fix is correct about *what* to delete and wrong about *when*:

```
unlink at char 5185, first write_kmz at char 6432 -> DESTRUCTIVE FIRST
```

Measured — a good three-mission directory, then one re-run with a flag combination that
yields zero blocks:

```
before: peacock_creek_01.kmz peacock_creek_02.kmz peacock_creek_03.kmz
$ flight_plan.py --stream "Peacock Creek" --launch ... --radius 70 --out <same dir>
=== split into 0 block(s) that each fit one battery
PLAN INCOMPLETE: no missions written                                   exit 1
after:  (empty)
```

`code-check-shell.md`, "`cmd dir/*` dies on ARG_MAX at scale": *"a destructive-then-rebuild
sequence turns 'retry it' into an outage. Build the replacement first and make the
destructive step the last one."* Note the earlier guard at `:361` (`working.is_empty`)
catches only the empty-intersection case — `--radius 1` exits before the unlink and the
files survive, which is what makes this look safe on the obvious test.

**Fix shape:** collect `(name, mission)` in the loop, write to `out` only after the loop,
and unlink the stale set immediately before the writes — or write into a temp dir and
`os.replace` it in. Either keeps the header's idempotency claim and removes the window.

---

### [fragile] `flight_coverage.py:88` and `flight_budget.py:119` — both new guards reject NaN and accept `+inf`, using a different grammar from the CLI's own check

Round 3 added two producer guards, written to the same shape, and both miss the same value:

```
spacing(nan)              -> ValueError: height must be positive and finite, got nan
spacing(inf)              -> (inf, inf)                                        <-- accepted
effective_speed_for(nan)  -> ValueError: commanded speed must be positive and finite
effective_speed_for(inf)  -> inf                                               <-- accepted
```

`not (v > 0) or v != v` is True for NaN and False for `+inf`. `_finite_positive` in
`flight_plan.py:345-347` gets it right (`or v == float("inf")`), so the CLI is covered and
only a library caller is exposed — `spacing(inf)` yields 0 transects downstream and
`effective_speed_for(inf)` makes every block fit. Both comments claim to reject the
non-finite case; they reject half of it.

`code-check-shell.md`, "A value validated with one numeric grammar and consumed with
another": normalise once. `math.isfinite(v) and v > 0` in all three places.

---

### [fragile] `flight_plan.py:132-167, 241-248` — an invalid input polygon is an uncaught `GEOSException` from inside the splitter

```
bowtie (self-intersecting Polygon) -> GEOSException: TopologyException: side location
                                      conflict at 500 500
```

Not reachable through `main()` — `load_reach` uses `union_all()` and `working` is an
intersection of valid geometry — but `split_to_budget` is a public function and the
traceback points at shapely rather than at the caller's input. One `if not polygon.is_valid:
raise ValueError(...)` at the head of `split_to_budget`, or a `make_valid()`, closes it.

---

### [nit] `flight_plan.py:399-401` — the stale sweep clears `*.kmz` and not `plan.gpkg`

Round 3's fix text named both; the code globs only `{stem}_[0-9][0-9].kmz`. Confirmed: a
`--review-layers` run's `plan.gpkg` survives a later non-review run of the same stream and
then describes blocks that no longer exist. The glob itself is safe — `load_reach` raises
before it for any stream not in the layer, so `stem` is always a real `gnis_name`, and
`peacock_creek_[0-9][0-9].kmz` cannot match `peacock_creek_east_01.kmz`.

### [nit] `flight_coverage.py:56-57` — `CRS_METRIC` / `CRS_WGS84` are still dead (round 3 row 18, carried).

---

## 3. The accounting invariant, re-attacked with `area_in = polygon.area`

**Eleven attacks, including every one the brief named. All held.** Round 3's finding 5 is
closed and the fix is stronger than the hole it filled.

| attack | `.area` | `sum(parts)` | `area_in` | disposed | `unaccounted` | guard |
|---|---|---|---|---|---|---|
| **overlapping MultiPolygon (invalid)** | 200.0000 | 200.0000 | 200.0000 | 200.0000 | +0.0000 | — |
| polygon with a hole | 336.0000 | 336.0000 | 336.0000 | 336.0000 | +0.0000 | — |
| `GeometryCollection(Polygon, LineString)` | 49.0000 | 49.0000 | 49.0000 | 49.0000 | +0.0000 | — |
| nested `GC(GC(MultiPolygon))` | 49.0000 | 49.0000 | 49.0000 | 49.0000 | +0.0000 | — |
| bare LineString / empty Polygon | 0 | 0 | 0 | 0 | +0.0000 | — |
| component tangent to the disc, outside | 153.6909 | 153.6909 | 153.6909 | 153.6909 | −0.0000 | — |
| component tangent to the disc, inside | 153.6909 | 153.6909 | 153.6909 | 153.6909 | −0.0000 | — |
| component straddling the disc edge | 128.0000 | 128.0000 | 128.0000 | 128.0000 | +0.0000 | — |
| component wholly outside the disc | 120.0000 | 120.0000 | 120.0000 | 120.0000 | +0.0000 | — |
| 60 randomised unions of 1–4 boxes | — | — | — | — | worst **0.000000** | — |
| **positive control**: `_polygons` stubbed to drop one 81 ha component | — | — | — | — | **+81.00** | **FIRES** |

The specific worry in the brief — *does `polygon.area` differ from what `dispose()`
accumulates on an invalid, self-overlapping MultiPolygon?* — is answered **no**, and for a
reason worth writing down: GEOS computes a MultiPolygon's area as the **sum of its
components**, not as the area of their union. Measured directly:

```
overlapping MP  is_valid=False  .area=2000000.0  sum(parts)=2000000.0  union area=1500000.0
```

So `area_in = polygon.area` and `sum(_polygons(polygon))` agree by construction on exactly
the geometry where a union-based total would not. The invariant is tight on the double-count
axis, not lucky.

The disc clip is also exact: `comp.difference(disc).area + comp.intersection(disc).area ==
comp.area` to floating point for every tangency case above, and `_equal_area_strips(poly, 2)`
conserves area to `0.000000e+00` on a disjoint MultiPolygon, a polygon with a hole and an
L-shape.

**A piece cannot reach two buckets.** Each `dispose` call ends in exactly one `append`
followed by `return`, or recurses without appending; the clip loop partitions each component
into `difference` and `intersection` with no overlap. Double-counting would show as a
*negative* `unaccounted`, and the worst over 60 randomised unions was `0.000000 ha`.

**The limitation round 3 stated is the one that survives, and finding 2 is it.** A total
disposition proves nothing was lost, not that anything was disposed of *correctly*. At
`--speed 2` the accounting is perfect — `187.3 ha in, unaccounted 0.00` — and 127 of those
hectares are in the wrong bucket. The missing companion assertion is still a cross-bucket
one, and it is now cheap to write, because the causes are separable at the point of
disposal: **no piece may be filed as `sliver` unless it was already below `min_block_ha`
when the splitter first saw it.** That is one boolean passed down the recursion.

---

## 4. Checked, and NOT a problem

- **`dispose()` terminates and is fast.** `max_depth=8` bounds it; worst measured case over
  awkward shapes (a 40-bar fragmenting comb, an annulus, a 1600 ha square at the disc edge,
  a 3014 ha blob) was **0.09 s**, and the real Peacock run is 4.7 s end to end including the
  `/vsicurl/` read. Round 3's 10.66 s worst case is gone with the `n`-search it belonged to.
- **`_equal_area_strips(poly, 2)` returns nothing unexpected** on a disjoint MultiPolygon, a
  polygon with a hole or an L-shape: 2 pieces, all `Polygon`, area conserved exactly. The
  `len(halves) < 2` arm at `:228` correctly disposes the degenerate return as
  `unsplittable` rather than dropping it.
- **`_flatten` / `_polygons` recurse correctly on nested containers** — `GC(GC(MP))` is
  flattened to its leaf Polygon and accounted in full.
- **`effective_speed_for(10.0) == EFFECTIVE_SPEED_MS`** exactly, so the default path is
  byte-identical to the pre-round-3 behaviour. The budget `--selftest` does not exercise
  `effective_speed_for` at all — the linear-scaling assumption is documented at
  `flight_budget.py:113-117` and is ungated, which is honest but worth knowing.
- **The stale-`.kmz` glob cannot delete another stream's output** (see the nit above).
- **`--validate-fixtures` still uses the default `EFFECTIVE_SPEED_MS`**, not
  `effective_speed_for`, including for `20260722_morr_jet_lwd01` which was commanded at
  26 m/s. That is the right choice — the fixture gate pins the *sizing* constant at the
  calibrated command — and the header already states the gate is coarse.
- **All four gates pass green**, and the round-trip, selftest and fixture verdicts are
  byte-identical to round 3's.

---

## Suggested order

1. **Finding 1** (`_max_transit_m` ignores `--speed`). It is the third site of a three-site
   change made in one commit, it is wrong in both directions, and one of them silently
   refuses area the budget says is flyable. One argument.
2. **Finding 2** (`dispose()` size-before-flyability). It is the round-4 instance of the
   mechanism, it fires on **default flags** for an ordinary narrow reach, and it is the only
   route left by which area is lost at `exit 0`. It is also what makes finding 1 quiet
   rather than loud.
3. **Finding 3** (destructive-first stale sweep). It is the only finding that destroys
   something a crew already has.
4. **Findings 4 and 5** and the two nits — one line each, none changes an output today.

**On terminality.** Findings 1 and 2 are both inside round 3's fixes, so the class is *not*
closed and this round does not claim it is. What can be said as a measurement: round 3's
62-row enumeration was re-walked row by row and **no row's handling was lost** in the
rewrite; the accounting invariant now survives every attack in §3 including the one that
defeated it last round, with a positive control proving it still fires; and the two new
findings are both *the same mechanism at a new grain* — a state known at the point of
production (`n == 0`; the speed the budget will actually use) carried onward as a number
instead of being disposed of there. Round 5 should re-probe exactly that: for each new
guard, whether the quantity it checks is the one its consumer uses.
