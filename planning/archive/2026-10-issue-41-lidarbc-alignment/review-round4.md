# Code-check round 4 — branch `41-fit-each-flight-to-lidarbc-our-uav-eleva` vs `main` (merge-base ec6dd31)

Reviewed 2026-10-16 (UTC), fresh eyes over the whole diff through `a711b19` plus the full
contents of every changed code and doc file, against the repo's code-check conventions
(general, shell, R, spatial, Python) in full. Every probe ran read-only on the repo and the
production trees (both selftests, `--check`, raster and laz reads) or on copies under
`scratchpad/review/work/` (a prod mirror with symlinked tifs and copied JSONs, rebuilt
there); nothing under `~/Projects/gis/` was written and no publish or release script was run.

## Findings

No bug in a shipped code path. Round 3's fixes hold on the live tree (measured below). One
fragile point, which is the next copy in round 3's own enumeration, and three minor notes.

- **[fragile]** `scripts/item_create.py:490-492` (additive mode: `if item_id in existing:
  SKIP`) and `:247-269` (`links_check`) against `scripts/config/README.md:67` (the new
  "Re-stitching a published dataset" paragraph) and `scripts/dataset_align-lidarbc.py:591`
  (the `--check` remedy "delete the dataset's COG and prod copies and publish it again") —
  the corrected enumeration in `findings.md` ("prod ↔ items by the path-key join and its
  refusals") is a **build-time** tie, and nothing re-checks a prod item JSON against the
  table after it is built. That is the same shape round 3 named (`check_dtm` at fit time,
  the windows over the bbox): a pair pinned once, at production time, by a proxy that cannot
  see the copy changing afterwards. Two reachable states, one silent and one loud, both
  measured on a mirror of prod rebuilt with the branch's `item_create.py`:
  - **Silent: a re-fit with no re-stitch leaves the items stale, and every gate is green.**
    A fitted row changes without its cloud or rasters changing (the fitter re-run after a
    code or default change, `--model plane`, a newer LidarBC delivery landing). Measured:
    `bulkley_bul24`'s `misfit_m` edited 0.27 → 0.99 in a copy of the table; `--check` on that
    table reports `ALIGN CHECK OK` (cloud and rasters are unchanged, which is all it reads);
    `dataset_publish.sh`'s item step on that dataset's three tifs prints `SKIP (already in
    collection)` ×3 and leaves the item at `alignment:misfit_m: 0.27`; the release's live
    alignment check, run over those items against the edited table, reports `disagree with
    table: 0`, because it tests presence iff fitted and never a value. So the committed table
    and the API disagree until the next `catalogue_release.sh`, whose `--rebuild` heals it;
    meanwhile `dataset_publish.sh` for *that* dataset cannot refresh its items at all, which
    contradicts the recipe's "then steps 2–4 again" when step 4 is the publish.
  - **Loud, with the wrong remedy: the documented re-stitch recipe cannot complete at
    step 4.** The paragraph says delete `imagery_uav_bc/<key>` and
    `stac/prod/imagery_uav_bc/<key>` and run steps 2–4 again. Deleting the prod dir deletes
    the dataset's three item JSONs (they sit beside the tifs) while `collection.json` keeps
    linking them, so after the COG copy `item_create.py`'s `links_check` refuses with
    `LINKS FAILED: 3/245 item link(s) name no file … links written before #35 are only
    rewritten by a full rebuild: run item_create.py --rebuild (or scripts/catalogue_release.sh)`
    (measured on the mirror: delete the three JSONs, run additive on the three tifs, rc 1).
    Loud, but the message blames #35 and the only completing route is a release, which the
    recipe does not say; the `--check` line's own remedy sends the operator down the same
    path. The retraction recipe (`:50-56`) already knows this — its step 5 is "Release as
    usual … the rebuild drops the collection links" — so the two recipes disagree about what
    a deleted prod dir needs.

  Three closures, not alternatives, and the first has an ordering trap: (1) make the recipe
  and the `--check` remedy say "then a release (or `item_create.py --rebuild`)" rather than
  "publish it again"; (2) give the publish a way to rebuild the requested datasets' items
  (drop the SKIP for ids whose tifs were requested, removing their collection links first),
  which is what "publish it again" implies today; (3) have `--check` compare each fitted
  row's fields with the prod item JSONs beside its rasters (`alignment_props(row)` against
  the JSON's `alignment:` keys; the JSONs are cheap to read and `item_create.py` cannot be
  imported under `uv`, so restate the join or read the JSON directly) — but note
  `catalogue_release.sh` runs `--check` *before* `--rebuild`, so that arm would refuse the
  release that heals it unless it runs after the rebuild or reports as its own line the
  release tolerates. Whichever lands, the live check could compare values, not presence,
  for the dataset(s) a publish just built.

Minor, not blocking:

- `scripts/dataset_align-lidarbc.py:573` — `valid` sums the `both` cells of each window, so
  overlapping windows count a cell more than once and the `DTM_MIN_VALID` floor is on a
  sum, not on distinct cells. On the live tree it does not matter (480 pairs: fewest
  16,314 summed = 16,314 distinct; 16 pairs overlap, worst ratio 1.11), but the selftest's
  "collar around a small patch" fixture (`:845-854`) holds **900** distinct valid cells
  (30 × 30), under the 1,000 floor, and passes as "compared" only because its five windows
  all contain the whole patch (5 × 900 = 4,500). A later change to count distinct cells
  would flip that fixture to "too few to tell" and read as a regression. Either count
  distinct cells (`set` of `(row, col)`, or `|` the window masks on a coarse canvas) or make
  the fixture's patch comfortably above the floor (say 40 × 40) so the premise matches the
  comment.
- `scripts/dataset_align-lidarbc.py:319` / `data/alignment_lidarbc.csv` `cloud_date` — the
  value is laspy's `date(year, 1, 1) + (day_of_year − 1)` and ODM writes day 0, so every
  cloud reads as **31 December of the year before** it was processed (`2025-12-31` for the
  2026 files, `2024-12-31` for 2025's; two values over 80). As a tie it is fine (it is only
  compared for equality); as a column a reader takes as a date it is off by a year. Worth a
  word in the header comment or the column name.
- `scripts/dataset_align-lidarbc.py:595` — `--check` compares only `odm_dem/dtm.tif`,
  `odm_dem/dsm.tif` and `odm_orthophoto/odm_orthophoto.tif`, so the two Maps Made Easy
  datasets' `ortho.tif` is never compared with anything, while the OK line says "every
  published and COG-tree raster of a dataset with a row is the raw tree's". No `alignment:`
  field is at stake (both are `no_cloud`); the sentence overclaims by two.

## Round 3's fixes, re-read against the code and the live trees

- `published_matches` (`:548-579`): the overview mask is `dataset_mask(out_shape=(h//f,
  w//f))` with `f = max(w, h) // 256`; on the live tree the orthophotos are 4-band uint8
  with an alpha band (mask flags `per_dataset, alpha`, all 160 pairs) and the DEMs float32
  with nodata −9999 (flag `nodata`, all 320 pairs), so the mask is read from alpha or nodata
  respectively; a raster with neither would mask all-valid and draw windows anywhere, which
  is right. The coarse → full mapping centres a 64-cell window on the coarse cell's centre
  and clamps to the raster (`min(max(0, c − 32), max(0, w − 64))`, width `min(64, w − c)`),
  so a raster under 64 cells is read whole. Instrumented over all 480 pairs `--check`
  compares (80 datasets × DTM, DSM, ortho × COG, prod): no window with 0 valid cells, fewest
  valid cells 16,314 (`bulkley-wilson01` COG DTM), 0 cells differ, `f` from 9 to 30. The
  uint8 arithmetic `np.abs(va.filled(0) − vb.filled(0)) > 0.01` wraps on Byte but any
  difference is nonzero and so counted; the mask disagreement term `(ma != mb)` covers a
  cell valid in one copy only. `rng.choice(cells, size=min(5, len(cells)), replace=False)`
  on an all-masked copy gives 0 windows and the "only 0 valid cells … too few to tell"
  line, not a pass. Grid check unchanged from round 2.
- `check_table` (`:582-609`): the raster loop runs over `(COG, prod) × (DTM, DSM, ORTHO)`
  for every row before the cloud check, so the `no_cloud` rows' rasters are compared
  (round 3's minor) and a `no_cloud` row whose laz has since appeared is reported (`head`
  differs from the row's blanks). `--cog` defaults to `ROOT / "imagery_uav_bc"`, which is
  `dataset_publish.sh`'s `COG_TREE`. A row whose raw tree lacks the raster is skipped
  silently (`(raw / tif).is_file()` false), which only loses the overclaim above.
- `cloud_header` (`:312-319`): `path.stat().st_size` beside count and date; `CLOUD`
  names the three and the row carries them under the same names, compared as strings.
- The backfilled table: against `134202d` the only change is one column, `cloud_bytes`,
  inserted between `cloud_date` and `run_date` (27 → 28 columns); 0 cell differences on
  the 27 shared columns, row order identical, 83 rows. Independently of the fitter, every
  one of the 80 rows with a laz has `cloud_bytes` equal to `os.stat().st_size` of
  `odm_georeferencing/odm_georeferenced_model.laz`; the 3 `no_cloud` rows carry blanks.
- The new selftest fixtures (`:804-867`): the same-count-same-date-other-size laz is
  reported; a stale COG copy is a second line beside the stale prod one; the collar
  fixture reports a +1 m patch (`cells differ`) and the 5 × 5 patch as "too few to tell".
  The 900-cell premise is the minor note above.
- Both gates on the branch tree: `uv run scripts/dataset_align-lidarbc.py --selftest`
  ALIGN SELFTEST PASS (67 s); `conda run -n titiler python scripts/item_create.py --selftest`
  ITEM SELFTEST PASS; `--check` on the real trees `ALIGN CHECK OK: 83 rows` (18.5 s).

## The corrected enumeration, checked

Copies: raw `.laz` → raw DTM/DSM/ortho → COG tree → prod → S3 → API, with the prod **item
JSONs** as a derived copy of (table, prod rasters) that the enumeration folds into "prod ↔
items". Ties as the code has them:

| copy ↔ copy | tie | state the tie cannot see |
|---|---|---|
| row ↔ raw `.laz` | count, date, size (`--check`, run first by both scripts) | — (a same-size rewrite of a LAZ is not a state ODM produces) |
| raw `.laz` ↔ raw DTM | `check_dtm` at fit time | a DTM regenerated after the fit on the same cloud — covered one copy down, since raw ↔ prod then differs |
| raw ↔ COG tree, raw ↔ prod | grid + five data-bearing windows, floor on cells compared | a same-grid change outside the five windows (not a pipeline state) |
| **table ↔ prod items** | **the join at build time only** | **a row changed after the build (the finding above): `--check` OK, publish SKIPs, live check tests presence only** |
| prod ↔ S3 ↔ API | sync, `stacs register`/`verify`, presence check | by design, pre-#41 |

Nothing else sits between the fields' claim and the rasters. The remaining proxy is the
one above: the items are the one copy the pipeline writes from the table and never reads
back against it.

## Checked and clean

- Shell: both `uv run … --check || exit 1` lines are plain commands under `set -euo
  pipefail`; the embedded `python3 -c "…"` programs carry no `"`, `` ` ``, `$` or `\`; the
  page-full guards are `sys.exit`; no `conda run` output is piped; `bash -n` not needed
  beyond rounds 1–3.
- `item_create.py`: `alignment_props()` refuses an unreadable or non-finite fitted row
  before any write; `alignment_problems()` and `build_item()` read `published`
  identically; the no-row refusal runs before the build loop in both modes; the mirror
  rebuild (245 items from 245 tifs, 245 links resolve) carries the fields on exactly the
  fitted datasets' items.
- `catalogue_release.sh`: `--check` before the rebuild; the live alignment check keys off
  the virtual-hosted href's first four segments; a missing `image` asset raises (loud).
- Rename recipe: the alignment row's `item` is renamed with the registry's; `--check` then
  finds the laz under the new key with the same header, size included.
- Every number in README/NEWS/research is unchanged by round 3 (the table's 27 shared
  columns are cell-for-cell what round 2 re-derived them from).
- `git status` clean at `a711b19` before and after the probes; the mirror and table copy
  live under `scratchpad/review/work/`.
