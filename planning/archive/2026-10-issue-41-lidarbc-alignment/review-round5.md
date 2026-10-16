# Code-check round 5 — branch `41-fit-each-flight-to-lidarbc-our-uav-eleva` vs `main` (merge-base ec6dd31)

Reviewed 2026-10-16 (UTC), fresh eyes over the whole diff through `242f0b4` plus the full
contents of every changed code and doc file, against the repo's code-check conventions
(general, shell, R, spatial, Python) in full. Every probe ran read-only on the repo and the
production trees (both selftests, `--check` on prod and on the mirror, a direct comparison of
the two join statements over every table row) or on a copy of the mirror under
`scratchpad/review/work/r5_mirror`; nothing under `~/Projects/gis/` was written and no
publish or release script was run.

## Findings

No bug in a shipped code path. Round 4's fixes hold on the live trees and the join's two
statements agree on every row (measured below). Two fragile points, both in the operator path
the round 4 recipe change opened, and one stale line in `CLAUDE.md`.

- **[fragile]** `scripts/config/README.md:67` ("Re-stitching a published dataset") against
  `scripts/catalogue_release.sh:34-57` and the retraction recipe at `:50-56` — the recipe
  still cannot complete as written, one step on from round 4's finding. It says: delete the
  COG and prod copies, run steps 2–3, then **release**, "as for a retraction". Two things
  are missing, one loud and one silent:
  - *Loud:* the three old item ids stay registered (stacs is upsert-only), the rebuild drops
    their links and the `sync --delete` removes their objects, so the release's `stacs verify`
    reports them orphaned and exits 1 after the sync and register (the retraction recipe's
    step 4, `item_unregister.sh` first, says exactly this; "as for a retraction" only
    implies it).
  - *Silent:* after that release the dataset is **retracted**, not re-stitched: no items, no
    S3 objects, and the recipe never says to run step 4 (publish) again. Measured on a mirror
    copy: with a fitted dataset's prod dir removed, `--check --base <copy>` reports
    `ALIGN CHECK OK` while `collection.json` still links its three items (3 matches), so the
    release proceeds and drops it; nothing afterwards names the dataset as missing (a row
    with no published tif is not a `--check` line, by design). The sequence that completes is
    delete COG + prod copies → steps 1–3 → `item_unregister.sh` the three ids → release →
    step 4 (publish). Say so in the paragraph, and in the `--check` remedy line that sends
    the operator there (`:621`, "delete the dataset's COG and prod copies, then fit it again
    and release").

- **[fragile]** `scripts/dataset_align-lidarbc.py:628-632` (the items arm) against
  `scripts/catalogue_release.sh:34-44` — the arm's remedy, "release, which rebuilds every item
  from the table", is wrong for a JSON under a dataset dir that the rebuild does **not**
  rewrite: an old-id JSON left by a rename (recipe step 2, which the README itself calls easy
  to miss) or a retracted dataset's leftover JSONs. Measured on a mirror copy: a stray
  `skeena-bulkley-2025-bulkley_br5_OLDNAME-odm_dem-dtm.json` with no `alignment:` fields
  under a fitted dataset is reported as `item … does not carry the row's alignment: fields
  (row fitted): release, which rebuilds every item from the table` and `--check` exits 1. The
  rebuild never deletes a JSON, so the release the message prescribes is refused again at the
  same line — and because `--check` now runs *before* the audit whose `--expect n_links`
  names the real cause ("an item JSON the collection does not link"), the operator never sees
  that message. Narrow: once the #41 release has run, a stray JSON a later rename leaves
  carries the same values as the row and is not flagged here (only the audit catches it); it
  bites on a stray that predates the fields or whose row has since changed. The arm already
  knows the item ids a dataset can have (`"-".join(k + tif.parent.parts + (tif.stem,))` for
  each raster in `RASTERS` present in prod): a JSON under the dir whose name is not one of
  them is not this dataset's item, and the line can say "not an item of this dataset: delete
  it (rename recipe step 2)" instead of prescribing a release. Same class as
  `code-check.md`'s "A guard that fires correctly and then points at the wrong fix"
  (stac_dem_bc#34 row).

Minor, not blocking:

- `CLAUDE.md:19` — "`--check` finds stale rows (both publish scripts run it first)" is stale
  since round 4 moved the release's `--check` after its rebuild. `scripts/config/README.md:72`
  and the script header (`:52`) carry the current order; `CLAUDE.md` is the file every
  session loads, so it is the copy that will be believed.

## Round 4's fixes, re-read against the code and the live trees

- **`item_fields` against `alignment_props`.** Both modules loaded under the `titiler`
  env (`scratchpad/review/work/r5_equiv.py`; neither imports laspy at module level) and the
  two run over all 83 rows of `data/alignment_lidarbc.csv`: **0 direct differences, 0 after a
  `json.dumps`/`json.loads` round trip**, same key set and same Python types on every row.
  The two statements name the same ten keys: `reference`, `model` (str);
  `shift_x_m`, `shift_y_m`, `offset_m`, `tilt_m_per_100m`, `misfit_m` (float; `ALIGN_NUMBERS`
  and the float entries of `ITEM_FIELDS` list them in the same set); `surface`, `centre`
  (lists of float); `points` (int). Float equality after the JSON round trip is exact
  (`json.dumps` writes `repr`, which round-trips; the table's `-0.0` reads back as `-0.0` and
  `-0.0 == 0.0` either way); `int` against `int` for `points`. So a disagreement that would
  fail every fitted dataset forever is excluded on this table, not only on the mirror.
- **The items arm's walk.** `rglob("*.json")` under the dataset dir, one `break` per
  dataset, dict comparison of the `alignment:`-prefixed properties against `item_fields(row)`
  (`{}` for a non-fitted row). On the real prod tree the only JSONs under dataset dirs are the
  245 items (81 `dtm`, 81 `dsm`, 81 `odm_orthophoto`, 2 `ortho`; 246 JSONs with
  `collection.json`), so the walk reads exactly the items today; a stray JSON is the case in
  the second finding.
- **`--check` on the real prod tree:** `ALIGN CHECK FAILED: 46 row(s)`, 47 lines, all 46
  drift lines from the items arm (items built before #41), no raster or cloud line, 18 s.
  **On the mirror** (`scratchpad/mirror2`, 245 symlinked tifs, 246 real JSONs rebuilt from the
  current table by the branch's `item_create.py`): `ALIGN CHECK OK: 83 rows`, 18 s. Both
  selftests PASS on the branch tree (`ITEM SELFTEST PASS`; `ALIGN SELFTEST PASS`, 70 s).
- **The moved `--check` in `catalogue_release.sh`.** The rebuild (`:28`) writes every item
  JSON and `collection.json` into prod before `--check` (`:34`) can refuse; nothing is
  validated, synced or registered before it (validate `:39`, audit `:44`, sync `:47`,
  register `:50`, verify `:57`). A refused release therefore leaves a rebuilt prod tree, which
  is the state the pre-existing validate/audit gate already produced and which
  `dataset_publish.sh` already guards by validating and auditing the whole tree before any
  upload — and now its own `--check` refuses on the same cause first, so nothing stale is
  pushed. In the release the items arm reads what the rebuild just wrote from the same table,
  so it can only fire on the two statements disagreeing (excluded above) or on a JSON the
  rebuild did not write (the second finding); the cloud and raster arms still stop a stale
  cloud or raster before the sync.
- **The hold, and deadlocks.** Walked each sequence: first publish after #41 → held by the
  46 stale items → the #41 release rebuilds them → `--check` OK → proceeds. Release →
  re-fit (table T2) → publish → items arm refuses ("release") → release rebuilds from T2 →
  OK. Cloud re-stitched and not re-fitted → both scripts refuse on the cloud line → re-fit →
  the raster line → delete COG + prod copies → `--check` OK → release drops the dataset →
  publish rebuilds its items (links no longer name the deleted JSONs, so `links_check`
  passes; the ids are no longer in `existing`, so additive mode builds them). No state loops
  except the stray-JSON one in the second finding, and the recipe gap in the first is a
  missing instruction, not a gate that cannot clear.
- **Selftest fixtures for the items arm** (`:931-953` of the diff's listing): fields on an item
  whose row is `no_reference` (reported), an item carrying exactly the fitted row's fields
  (clean), the row's `misfit_m` moved after the item was written (reported). The clean
  fixture is written through `item_fields` itself, so it pins round-trip self-consistency
  rather than agreement with `item_create.py`; that tie is held by the mirror check and by
  the direct comparison above, which is the right instrument for it.

## The chain, checked once more

Copies: raw `.laz` → raw DTM/DSM/ortho → COG tree → prod → prod item JSONs → S3 → API.
Ties as the code has them, each read against the state it must separate:

| copy ↔ copy | tie | state it cannot see |
|---|---|---|
| row ↔ raw `.laz` | count, date, size (`--check`, both scripts) | a same-size rewrite (accepted, round 3) |
| raw `.laz` ↔ raw DTM | `check_dtm` at fit time | a DTM regenerated later on the same cloud, which the next row then catches as raw ≠ prod |
| raw ↔ COG tree, raw ↔ prod | grid + five data-bearing windows, floor on cells | a same-grid change outside the windows (accepted) |
| table ↔ prod items | `item_fields` read back (round 4) | a JSON the rebuild does not write, with a remedy that cannot clear it (finding 2) |
| prod ↔ S3 ↔ API | sync; `stacs verify` by digest; presence check | by design, pre-#41 |

No copy is missing between the fields' claim and the rasters. The one open state is not a
tie but an instruction: the re-stitch recipe ends with the dataset retracted (finding 1).

## The whole diff, once more

- Shell: the two embedded `python3 -c "…"` programs carry no `"`, `` ` ``, `$` or `\`; the
  page-full guards are `sys.exit`; `uv run … --check || exit 1` under `set -euo pipefail` in
  both scripts; no `conda run` output is piped; no new absolute path beyond the ones the
  scripts already hardcode; `bash -n` not needed beyond rounds 1–4.
- `item_create.py`: `alignment_props()` refuses an unreadable or non-finite fitted row before
  any write; the no-row refusal runs before the build loop in both modes; `published` is read
  identically in `build_item()` and `alignment_problems()`; `FIELD_PREFIXES` carries
  `alignment`.
- Table and docs: status counts re-counted from the committed table, 46 fitted / 31
  `no_reference` / 3 refused / 3 `no_cloud`, matching README, NEWS and the research doc; the
  table is unchanged since round 4 (the numbers rounds 1–4 re-derived still describe it).
- `README.Rmd`: chunk labels unique; the new chunk is `eval=FALSE`; the `ext_filter`
  back-tick form matches the existing `fwa:` example.
- `git status` clean at `242f0b4` before and after the probes; the mirror copy, the
  comparison script and the `--check` log live under `scratchpad/review/work/`.
