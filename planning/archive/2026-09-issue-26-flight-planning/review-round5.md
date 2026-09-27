# Review round 5 — `26-generate-flight-plans-from-boundaries-we`

Reviewer: fresh-eyes subagent, 2026-09-26. Scope as briefed and **narrow**: round 4's
fixes only, at `3ea4a0b`, hunting for a defect inside them. Rounds 1–4 read; round 4 read
in full and its six fixes taken one at a time.

Every probe ran in `/private/tmp/.../scratchpad/probe`, against a **copy** of the four
scripts. The working tree was never modified — md5s identical at start and end
(`flight_plan.py` `85e104de0e6166b0684c68bb2fec574d`) and `git status --short` empty both
times.

## Baseline, re-measured first

```
flight_coverage.py --selftest                  COVERAGE SELFTEST PASS                  exit 0
flight_wpml.py     --roundtrip ~/Downloads/*.kmz  ROUNDTRIP PASS: 5 fixture(s)         exit 0
flight_plan.py     --validate-fixtures         FIXTURE VALIDATION PASS: 5 missions     exit 0
flight_budget.py   --selftest (system py3)     BUDGET SELFTEST PASS: 7 flown missions  exit 0
```

and the real Peacock plan, byte-for-byte what round 4 reports (4.8 s wall):

```
=== Peacock Creek: 187.3 ha total, 187.3 ha within 5000 m of launch
    note: at 350 m one battery reaches about 4173 m of transit ...
=== split into 5 block(s) that each fit one battery
    area in 187.3 ha = planned 184.9 + slivers 1.85 (20) + unreachable 0.3 (3)
                     + unsurveyable 0.0 (0) + undersized-after-split 0.33 (8)
                     + unsplittable 0.0 (0) + non-polygon 0.00 (0) + unaccounted -0.00
PLAN COMPLETE: 3 mission(s), 143.2 ha, 5 block(s) available          EXIT 0
```

All four gates green and the reference run reproduced. Findings below are relative to that.

---

## The three enumerations

Produced by parsing `flight_plan.py` with `ast`, not by reading it — script at
`scratchpad/enumerate_buckets.py`. Recollection is what left the sixth message unpinned in
trap#28; these are counts.

### 1. Every bucket, in dict / summary / accounting

Seven keys in the dict literal at `:208-209`. `accounting` iterates `buckets.items()`
(`:275`) and `unaccounted_ha` subtracts `sum(... for k in buckets)` (`:278`), so the
accounting is **structurally** over all buckets — it cannot go stale when one is added.
The summary line at `:408-417` is the hand-written half and is the one that can.

| # | bucket | in dict | `_ha` in summary | count in summary | in accounting |
|---|---|---|---|---|---|
| 1 | `planned` | yes | yes (`planned_ha`) | **not in the area line** — reported one line above as `len(blocks)` at `:403`, and `blocks = sorted(buckets["planned"])` at `:273`, so the two are equal by construction | yes |
| 2 | `sliver` | yes | yes | yes | yes |
| 3 | `unreachable` | yes | yes | yes | yes |
| 4 | `unsurveyable` | yes | yes | yes | yes |
| 5 | `undersized_after_split` | yes | yes | yes | yes |
| 6 | `unsplittable` | yes | yes | yes | yes |
| 7 | `nonpolygon` | yes | yes | yes | yes |

Reverse direction checked too: **no `split_meta[...]` key in the file lacks a matching
bucket** (15 keys referenced, all either `<bucket>`, `<bucket>_ha`, `area_in_ha` or
`unaccounted_ha`). No bucket is invisible and no summary field is orphaned. **Round 4's
fix 6 is complete.**

### 2. Every budget consumer, and the speed it uses

Nine call sites. Three are the *producer* `effective_speed_for` (they take the commanded
speed, which is their input, so "speed" does not apply); six are consumers that take a
`speed_ms`.

| # | line | call | speed passed | verdict |
|---|---|---|---|---|
| 1 | 111 | `budget.max_path_m(height_m, transit_m=mid, speed_ms=speed_ms)` | `_max_transit_m`'s own `speed_ms` | threaded |
| 2 | 235 | `budget.fits(path, …, speed_ms=eff)` | `eff` | threaded |
| 3 | 261 | `_max_transit_m(height_m, min_block_ha, speed_ms=eff)` — the reach disc | `eff` | threaded (round 4's fix) |
| 4 | 318 | `budget.fits(path, height_m, transit_m=0.0)` — `_validate_fixtures` | default `EFFECTIVE_SPEED_MS` | **deliberate**, and accepted in round 4 §4: the fixture gate pins the sizing constant at the calibrated command |
| 5 | 390 | `_max_transit_m(args.height, speed_ms=budget.effective_speed_for(args.speed))` — the operator note | scaled | threaded (round 4's fix) |
| 6 | 439 | `budget.fits(meta["path_m"], …, speed_ms=budget.effective_speed_for(args.speed))` — per-mission | scaled | threaded |

Producers: `:201` (`eff = effective_speed_for(commanded_ms)`), `:391`, `:440`.

Measured, not inferred — the disc radius now equals the transit at which the fit test
stops approving a minimum block, at every speed, **with a positive control** that restores
round 3's defect and shows the probe can see it (`probe/p1_speed.py`):

```
   cmd   eff m/s   disc used  true reach   ratio
   2.0      1.24         795         795    1.00
   5.0      3.10        2061        2061    1.00
  10.0      6.21        4173        4173    1.00
  20.0     12.42        8396        8396    1.00
  26.0     16.15       10929       10929    1.00

  note printed by main() vs disc buffered by split_to_budget:  AGREE at 2, 10 and 26 m/s

  POSITIVE CONTROL (disc pinned at the default speed, as round 3 had it):
    --speed  2.0: disc 4173 m vs true  795 m  ratio 5.25  <-- probe FIRES
    --speed 26.0: disc 4173 m vs true 10929 m ratio 0.38  <-- probe FIRES
```

**Round 4's fix 1 is complete and correct.** One reservation about how it was made is
finding 4 below.

### 3. Every `dispose()` exit path, and the bucket it reaches

Six `return` statements plus one recursion, at `:217-249`. Five appends, each immediately
followed by its `return`, so no piece can reach two buckets.

| # | line | guard | bucket | area at risk |
|---|---|---|---|---|
| 1 | 219 | `poly.is_empty` | **none** | zero by definition, and **unreachable**: every caller passes `_polygons(...)` output, and `_flatten` drops empty leaves. Belt-and-braces |
| 2 | 227 | `poly.area/1e4 < min_block_ha` | `sliver` if `depth == 0` else `undersized_after_split` | — but the label is wrong for two cases, **finding 2** |
| 3 | 234 | `n == 0` after `survey()` | `unsurveyable` | — |
| 4 | 237 | `budget.fits(...)[0]` | `planned` | — |
| 5 | 242 | `depth >= max_depth` | `unsplittable` | — |
| 6 | 246 | `len(halves) < 2` | `unsplittable` | — |
| 7 | 249 | else | recurses on `_polygons(h)` for each half | non-Polygon leaves inside a half are dropped; all have zero area |

Exactly one bucket per path, or zero on two zero-area paths. Confirmed numerically over
**72 runs** (36 shapes × launch/no-launch — a 40 m × 3 km arm, a 40-bar comb, an annulus,
a 1600 ha square, a 3014 ha blob, an L, 30 randomised unions), worst `|unaccounted|`
**0.000000000 ha**, zero failures, with a positive control that drops one bucket from the
sum and fires at 36.60 ha (`probe/p2_dispose.py`). The disc clip partitions each component
into `difference` and `intersection`, which are disjoint, so double-counting — which would
show as *negative* unaccounted — cannot occur either.

**The ordering is right and the partition is sound. What is wrong is one label**, below.

---

## Findings

### [bug] `flight_plan.py:488-492` — the `plan.gpkg` sweep is on the wrong branch, so the QGIS review file accumulates and names blocks the same run just deleted

This is a defect **inside round 4's fix 3**. Round 4 moved the destructive step after the
writes (correct, and verified below) and, addressing its own nit 6, added `plan.gpkg` to the
sweep — under `if not args.review_layers`:

```python
if not args.review_layers:
    gp = out / "plan.gpkg"
    if gp.exists():
        gp.unlink()
```

So it deletes `plan.gpkg` **exactly when nothing is going to regenerate it**, and leaves it
**exactly when it is about to be written again**. And the write appends: `:471-476` use
`mode="a"` for `launch`, `blocks`, `transects` and `stations` (only `floodplain` is
`mode="w"`).

Two `--review-layers` runs into one `--out`, measured end to end (`probe/p8_gpkg.sh`):

```
run 1: --review-layers --batteries 3        PLAN COMPLETE: 3 mission(s)
run 2: --review-layers --batteries 1        PLAN COMPLETE: 1 mission(s)
  removed stale mission from a previous run: peacock_creek_02.kmz
  removed stale mission from a previous run: peacock_creek_03.kmz

   .kmz on disk:  peacock_creek_01.kmz

   plan.gpkg:
     launch          2 row(s)
     blocks          4 row(s) -> ['peacock_creek_01','peacock_creek_02',
                                  'peacock_creek_03','peacock_creek_01']
     transects      69 row(s)     (was 47)
     stations      355 row(s)     (was 261)
```

The sweep deletes `_02.kmz` and `_03.kmz` and prints that it did, and four lines later the
file whose whole stated purpose is *"for review in QGIS before flying"* (`:350-352`) still
draws both of them — plus `peacock_creek_01` twice. The header's idempotency claim
(`:15-16`, *"re-running overwrites the same block .kmz files in --out and nothing else"*)
is false for this file, and a reviewer has no way to tell the live blocks from the dead
ones: the attribute table has no run stamp.

`code-check.md`, "A guard's scope, escape hatches, and remedies" — *a remedy that repairs
the subset it knows about reports success and leaves the rest*. The benign half (a
`plan.gpkg` nothing will rewrite) was fixed; the harmful half was not.

**Fix shape:** move the `plan.gpkg` unlink out of the `not args.review_layers` branch so it
runs unconditionally once `written` is non-empty, and do it **before** `:466`, ahead of the
writes — or drop the `mode="a"` scheme and write the whole file in one pass. The kmz half
already deletes-after-write because its replacements are per-name; `plan.gpkg` is a single
file that is fully regenerated, so for it delete-before-write is the correct order and
carries no window.

**Second, smaller half of the same clause:** `plan.gpkg` is **not stream-keyed** where the
`.kmz` sweep carefully is (`{stem}_[0-9][0-9].kmz`). A run of a *different* stream into the
same `--out` deletes the first stream's review file. Measured:

```
after Peacock --review-layers:   peacock_creek_01.kmz peacock_creek_02.kmz plan.gpkg
$ flight_plan.py --stream "Nanika River" ... --out <same dir>     # no --review-layers
  removed stale plan.gpkg from a previous run
after:                           nanika_river_01.kmz peacock_creek_01.kmz peacock_creek_02.kmz
```

The `.kmz` files survived — the stem key works. `plan.gpkg` did not. Either name it
`{stem}_plan.gpkg` or scope its removal the way the missions are scoped.

---

### [bug] `flight_plan.py:226` — `depth == 0` is a proxy for "arrived small", and **two** cuts happen before a depth is assigned

This is a defect **inside round 4's fix 2**, and it is round 4's own mechanism one axis
over. The comment states the intent plainly at `:221-225`:

> *A piece that arrived small is a native sliver of the delineation and is expected; a
> piece the recursion drove small is area this planner failed to use.*

`depth == 0` does not mean "arrived small". It means "has not yet been cut **by
`_equal_area_strips`**". Two other cutters run first and neither increments anything:

1. **the reach disc**, `:260-269` — `comp.intersection(disc)` then `dispose(g, 0)`;
2. **`--radius`**, `:381` — `working = reach.intersection(launch.buffer(args.radius))`, in
   `main()`, before `split_to_budget` is ever called, so the splitter cannot see it even in
   principle.

Reproduced on the **real Peacock reach**, default height and speed, varying only
`--radius` (`probe/p4_radius.py`). "radius-born" counts small components of `working` whose
parent in the unclipped reach was ≥ `min_block_ha`:

```
  radius  working ha   sliver  sliver ha  radius-born       ha
    5000      187.33       20       1.85            0     0.00
    2000      185.67        5       0.46            0     0.00
    1000      102.07        1       0.30            1     0.30   <-- mislabelled native
     600       30.23        0       0.00            0     0.00
```

and synthetically for the disc, which is the larger of the two (`probe/p2_dispose.py`) — a
12 ha block straddling the 4173 m disc edge:

```
component area: 12.00 ha   (well above min_block_ha)
  of which inside the disc: 0.551 ha
  buckets: sliver=1(0.551 ha)  undersized_after_split=0  unreachable=1(11.449 ha)
  -> filed as: sliver
```

0.30 ha on the real reach is small. The defect is not the magnitude — it is that the
bucket round 4 created **to carry provenance** reports the wrong provenance, in the
reassuring direction, and the check that would catch it (round 4 §3's *"no piece may be
filed as `sliver` unless it was already below `min_block_ha` when the splitter first saw
it"*) is exactly the assertion this breaks. `code-check.md`, "A proxy is not the property":
the condition names a **mechanism** (which recursion level) where the requirement is a
**property** (was this piece ever cut).

**Fix shape:** carry the property rather than the depth. `dispose(poly, depth, native)`
where `native` is `True` only for the `else: dispose(comp, 0, True)` branch at `:271` and
for a disc-clipped piece whose parent component was *itself* already under
`min_block_ha`; `False` for every disc remnant and every recursive half. For the `--radius`
clip, which happens in `main()`, pass the unclipped `reach` into `split_to_budget` and let
the radius be one more parameter, or accept that `sliver` means "small when the splitter
first saw it" and say **that** in the comment instead of "native sliver of the delineation".
The second is a one-line change and is honest; the first is the one that makes the
cross-bucket assertion writable.

---

### [gap] `flight_plan.py:505-514` — the two new buckets are visible but not load-bearing, which is the half of round 4's own fix that did not land

Round 4's finding 2 prescribed two things: separate the causes into buckets, **and** *"add
`unsurveyable_ha` and any `sliver` piece born at `depth > 0` to the `problems` list at
`:471`, because both are area the splitter failed on rather than area the flags excluded."*
The buckets and the summary line landed. The gating did not — parsed, not read:

```
   unsurveyable               appears in problems block: False
   undersized_after_split     appears in problems block: False
   unaccounted_ha             appears in problems block: True
   bad_written                appears in problems block: True
   len(written)               appears in problems block: True
```

So the exact scenario round 4 measured still exits 0. Reproduced, and the second row is the
silent one:

```
40 thin ribbons alone (96 ha)      planned 0.0 ha | unsurveyable 40 (96.00 ha)
                                   -> 0 blocks -> shortfall -> exit 1     (loud, fine)
ribbons + one good 100 ha block    planned 99.5 ha in 10 blocks | unsurveyable 40 (96.00 ha)
                                   -> 49% of input unusable, problems = NONE -> exit 0
```

and on the **real** reach at `--speed 2`:

```
area in 187.3 ha = planned 49.7 + slivers 0.00 (0) + unreachable 129.0 (27)
                 + unsurveyable 0.0 (0) + undersized-after-split 8.64 (15) + ...
PLAN COMPLETE: 3 mission(s), 13.7 ha, 14 block(s) available          exit 0
```

8.64 ha the splitter halved into uselessness, at exit 0. The code's own rule for what
gates (`:500-504`) is *"Area outside `--batteries`, or outside battery reach, is the
expected consequence of the flags"* — `undersized_after_split` and `unsurveyable` are
neither. By the comment's own test they belong in `problems`.

Whether to gate is a judgement (a threshold would be needed — gating on any non-zero
`undersized_after_split` would fail the default Peacock run, which has 0.33 ha). But the
current state is the worst of both: a bucket created to raise an alarm that raises none.
Either gate it on a fraction of `area_in_ha`, or say in the comment that these two are
reported-not-gated and why.

---

### [fragile] `flight_plan.py:91, 106-107` — `speed_ms` was added as an **optional** argument defaulting to the old wrong value

Round 4's fix 1 threaded the speed correctly through both call sites (enumeration 2 above).
It also left the hatch that produced the defect:

```python
def _max_transit_m(height_m, min_block_ha=None, speed_ms=None):
    ...
    if speed_ms is None:
        speed_ms = budget.EFFECTIVE_SPEED_MS
```

`EFFECTIVE_SPEED_MS` is precisely the value round 4 proved wrong by 5.25x at `--speed 2`.
Both current callers pass `speed_ms`, so the fallback is dead code today — and it is a
default that decides: the next caller that omits it silently reproduces round 4's finding 1
with no error and no diff to point at. `code-check.md`, "Defaults that decide": *make the
argument required, so omission is an error rather than a fallback.*

**Fix shape:** `def _max_transit_m(height_m, speed_ms, min_block_ha=None)`. Two call sites,
both already pass it.

---

### [nit] `flight_plan.py:256` — the comment references `flyable_and_fits`, deleted in the same commit

```
256:    # Same speed as flyable_and_fits, or the disc and the fit test disagree: at
```

Verified by grep across `scripts/`, `README.Rmd` and `CLAUDE.md`: this is the **only**
surviving reference to the deleted function, and nothing calls it. Round 4's brief asked
whether anything else called it — nothing does. Reword to "the fit test at :235".

### [nit] `flight_plan.py:484` — the `[0-9][0-9]` glob cannot see a three-digit mission

```
peacock_creek_099.kmz  no such name is produced; names are {n:02d}
peacock_creek_100.kmz  matched by peacock_creek_[0-9][0-9].kmz: False
```

`f"{len(written)+1:02d}"` produces `100` once past 99, so a previous run with
`--batteries > 99` leaves orphans the sweep cannot remove. No gnis_name in the layer
carries `[`, `]`, `*` or `?` (32 checked), so the glob is otherwise safe. `[0-9][0-9]*`
would close it, or `:03d`.

### [nit] `flight_plan.py:202-207` — `make_valid()` changes area, and the header line is computed from the unrepaired geometry

Round 4's fix 5 works and is correctly **ordered** — `area_in` is computed after the repair
at `:207`, so the invariant is unaffected. Measured, with a positive control that removes
the repair and shows the exception return:

```
  bowtie (self-intersecting)   caller .area=  0.00 ha  after make_valid=  50.00 ha  unaccounted +0.000000
  overlapping MultiPolygon     caller .area=200.00 ha  after make_valid= 150.00 ha  unaccounted +0.000000
  valid square (control)       caller .area=100.00 ha  after make_valid= 100.00 ha  unaccounted +0.000000

  POSITIVE CONTROL: without make_valid -> GEOSException: TopologyException: side
                    location conflict at 500 500        <-- control FIRES
                    with make_valid    -> no exception   <-- fix works
```

So the answer to *"check this cannot change area"* is: **it can, by ±50 ha on these
inputs**, and that is fine because `area_in` is derived after it. The residual is
cosmetic — `main()` prints `working.area/1e4` at `:386` from the *unrepaired* geometry and
`split_meta['area_in_ha']` at `:408` from the repaired one, so on invalid input the two
lines would disagree with nothing explaining why. **Unreachable through `main()`**:
all 32 reaches in `co_ff04_by_gnis_name` produce a valid `reach` and a valid `working`
(checked; `probe/p7_final.py`), because `union_all()` and an intersection of valid
geometry are valid. Latent, for a library caller only.

---

## Confirmed working, with evidence

- **Fix 3's ordering is right for the `.kmz` half.** A zero-block re-run no longer empties
  the directory — the failure round 4 found:
  ```
  before: peacock_creek_01.kmz _02.kmz _03.kmz
  $ flight_plan.py ... --radius 70 --out <same dir>    PLAN INCOMPLETE  exit 1
  after:  peacock_creek_01.kmz _02.kmz _03.kmz         <-- intact
  ```
- **The `keep` set matches what was written.** A 3-battery run, a planted `_09.kmz` from a
  pretend larger run, then a 2-battery run: `_03` and `_09` removed, `_01` and `_02` kept,
  each removal announced. `write_kmz` returns the `pathlib.Path` it was given
  (`flight_wpml.py:264`), so `{p.name for p in written}` is exactly the set written.
- **Fix 4 is complete.** `math` is imported in all three files that now use `isfinite`
  (`flight_plan.py:30`, `flight_budget.py:29`, `flight_coverage.py:20`), and all three
  guards now share one grammar. Round 4's finding 4 — `+inf` accepted — is closed at every
  site:
  ```
  cov.spacing(inf)                -> ValueError: height must be positive and finite, got inf
  budget.effective_speed_for(inf) -> ValueError: commanded speed must be positive and finite, got inf
  --height inf                    -> exit 2  must be positive and finite, got inf
  ```
  (`-inf`, `nan`, `0` and negatives all refuse too.)
- **Fix 6 is complete** — the 7×4 bucket table above, both directions.
- **Round 3 row 18 is closed**, not carried: `CRS_METRIC` / `CRS_WGS84` were deleted from
  `flight_coverage.py` in this commit. Round 4's nit 7 no longer applies.
- **The accounting invariant survives the reordered `dispose()`** — 72 runs, worst
  `|unaccounted|` 0.000000000 ha, with a positive control at 36.60 ha.

---

## Verdict — the class is NOT closed

Three of round 4's six fixes carry a defect, and the two `[bug]`s are both inside fixes
round 4 wrote:

| round 4 fix | state |
|---|---|
| 1. speed threading | **correct**, positive-controlled — but shipped with an optional-argument hatch (finding 4) |
| 2. `dispose()` reorder + provenance buckets | ordering and partition correct; **the provenance label is wrong** for disc- and radius-cut pieces (finding 2) |
| 3. delete ordering | `.kmz` half **correct**; `plan.gpkg` half on the wrong branch and unscoped (finding 1) |
| 4. `math.isfinite` | **complete** |
| 5. `make_valid` | **correct and correctly ordered**; one cosmetic residual (nit) |
| 6. new buckets | dict/summary/accounting **complete**; the gating half of its own prescription did not land (finding 3) |

**What can be said as a measurement rather than an impression**, which is the part of the
brief I can answer affirmatively:

- All **7** buckets are in the dict, the summary line and the accounting — parsed, both
  directions, no orphans. The accounting is structural (`for k, v in buckets.items()`), so
  only the summary line can rot, and today it does not.
- All **6** budget consumers taking a `speed_ms` are enumerated; **5** carry the scaled
  speed and **1** (`_validate_fixtures`) deliberately does not, for the reason round 4
  accepted. The disc now equals the true reach at 2, 5, 10, 20 and 26 m/s, ratio 1.00, with
  a positive control proving the probe can see the old defect.
- All **7** `dispose()` exit paths are enumerated; **5** reach exactly one bucket, **2**
  reach none and are provably zero-area (one of them unreachable). 72 runs at
  0.000000000 ha unaccounted, positive-controlled.

**And the honest counterweight.** Those three enumerations prove *completeness of
partition* — no hectare is lost, no bucket is invisible, no consumer disagrees about
speed. They do not prove *correctness of disposition*, and findings 2 and 3 are both in
that gap, exactly where round 4 said the next round should look. The Peacock run at
`--speed 2` accounts perfectly and exits 0 with 8.64 ha the splitter destroyed.

**What would actually close this**, and it is not another round of reading. The recurring
mechanism across all five rounds has one shape: *a state known at the point of production
is carried onward as a number and re-derived downstream* — `path_m == 0` read as fits, a
small `budget_path` lost, an all-or-nothing fit test, a speed re-derived from a default, and
now a provenance re-derived from a recursion depth. Terminating means enumerating, once,
**every value in `split_to_budget` that is derived rather than carried**, and showing each
either has one producer or cannot disagree. That set is small — `eff`, `transit(poly)`,
`path`/`n`, `depth`, `area_in` — and it is finite, which is what would make "closed" a count
instead of a claim. The cross-bucket assertion round 4 named (*no piece filed as `sliver`
unless it was under `min_block_ha` when the splitter first saw it*) is the concrete first
instance, and finding 2 is the reason it cannot be written today.

Suggested order: **finding 1** (a review artifact that lies about what will be flown, and
the only finding that misinforms a crew), then **finding 2** (one boolean, and it is what
makes the invariant's companion assertion writable), then **4** (one signature), then
**3** (needs a threshold decision), then the nits.
