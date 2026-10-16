# Code-check round 3 — branch `41-fit-each-flight-to-lidarbc-our-uav-eleva` vs `main` (merge-base ec6dd31)

Reviewed 2026-10-16 (UTC), fresh eyes over the whole diff through `134202d` plus the full
contents of every changed code and doc file, against the repo's code-check conventions
(general, shell, R, spatial, Python) in full. Every probe ran read-only on the repo and the
production trees (both selftests, `--check`, `--check <project>`, raster and laz header
reads) or on copies under `scratchpad/review/work/`; nothing under `~/Projects/gis/` was
written and no publish or release script was run. The ODM facts below were read out of the
cached `opendronemap/odm:latest` image's source.

## The mechanism behind rounds 1 → 2 → 3

An item's `alignment:` fields make a claim about a **chain of copies**: the ground the fit
was computed on (the raw `.laz`), the rasters derived from it (raw `odm_dem/*.tif`,
`odm_orthophoto/*.tif`), the COG conversions of those (`imagery_uav_bc/<key>`), the prod
copies (`stac/prod/imagery_uav_bc/<key>`), the objects on S3, and the items the API serves.
The claim holds only if every copy is the one the fit describes. Each review round added a
guard that pins **one adjacent pair through a proxy chosen for cheapness** — a header's point
count and date (round 1), a grid plus five seeded windows (round 2) — and each proxy closed
the pair in front of it while leaving open (a) the next copy in the chain and (b) the states
the proxy cannot distinguish. In `code-check.md`'s terms it is "A proxy is not the property"
arriving through "A guard's scope … terminate by enumeration, not by a reviewer saying you
have converged": the candidate set is every copy the pipeline reads or writes, and a link is
closed only by a check that reads the artifact's **content** (or an identity the producer
cannot rewrite without changing) and has been shown to fire on the states it must separate.

The session's own enumeration (`planning/active/findings.md:205-215`) lists five links and
ends "every link down to the live item has a mechanical check that was shown to fire". Checked
against the code and the live trees, that sentence is false on two links and the table omits
one copy entirely:

| copy ↔ copy | tie in the branch | fires on | cannot fire on (measured or read) |
|---|---|---|---|
| table row ↔ raw `.laz` | `cloud_points` + `cloud_date` from the LAS header (`cloud_header`, fitter:306) | a re-stitch (+1 point stops it) | an in-place reclassification: ODM's `odm_dem` stage runs `pdal translate lasFile lasFile smrf` (`/code/opendm/dem/commands.py:33-41`), which `--dtm` turns on (`config.py:908`; the batch script passes `--dtm --dsm`). Same count, and `creation_date` is only the processing year: measured on the real clouds it is `2025-12-31` for a file written 2026-09-20 and `2024-12-31` for files written 2025-01-15 (two distinct values over all 80). A rerun of that stage with other `--smrf-*` values changes the class-2 set the fit reads and nothing the tie reads |
| raw `.laz` ↔ raw DTM | `check_dtm` at **fit time** (fitter:329, called at 428) | a DTM off its cloud when the fit runs | a DTM regenerated after the fit; `--check` never re-runs it (narrow: a same-cloud regeneration stays on the cloud) |
| raw DTM/DSM/ortho ↔ **COG tree** `imagery_uav_bc/<key>` | **none** — `check_table` (fitter:559-581) reads `prod` only; `dataset_publish.sh:74` reuses a COG that exists and `:94` copies it to prod with `cp -np` | — | a dataset whose prod copy is gone and whose COG copy is stale (finding 2) |
| raw DTM/DSM/ortho ↔ prod | grid + five seeded 64-cell windows of band 1 (`published_matches`, fitter:538-556) | a grid change; a value change under a window | a value change on a dataset whose five windows all fall in nodata: **1 of 46 fitted datasets today** (finding 1, measured) |
| prod ↔ items | `item_create.py` joins the row by the tif's path key; refuses no-row, unreadable, non-finite | the mirror rebuild, 4 mutants | — (clean) |
| prod ↔ S3 ↔ API | sync, `stacs register`/`verify`, the live presence check | — | by design, pre-#41 |

Three findings follow, in order of weight; all three are instances of the mechanism, and the
remedy for the class is the last column above: for each pair, compare content (or a
producer-proof identity), and prove the guard on the state the proxy misses.

## Findings

- **[bug]** `scripts/dataset_align-lidarbc.py:538-556` (`published_matches`, the round 2 tie)
  — the five windows are drawn uniformly over the raster's **bbox**, so on a thin diagonal
  reach they can all land in the nodata collar, and the function then compares zero cells and
  returns "matches". Measured over all 240 raster pairs `--check` compares (80 datasets × DTM,
  DSM, orthophoto): three pairs hold **0 valid cells** in their five windows, and all three
  belong to one `fitted` dataset, `skeena/bulkley/2022/bulkley_dickson_BR1-2021_BR2-2021`
  (DTM 13,894 × 22,976 at 0.1 m, valid share 0.069; ortho valid share 0.038). Restore-the-bug
  on the live tree: a copy of its raw DTM with **every valid cell raised 1 m** (21,924,006
  cells differ) handed to `published_matches(copy, prod_dtm, dataset_rng(key))` returns
  `None`, the same as the unchanged control. So for that dataset the round 2 closure is the
  grid check alone: any same-grid change to the published values — the reclassification
  rerun in the table above keeps the cloud's bounds and so the grid — ships with
  `ALIGN CHECK OK`. The selftest's fixture (fitter:777-795) is a 40 × 40 DTM with every cell
  valid, so it cannot reach this ("A fixture that cannot reach the failure mode"). Two cheap
  closures, both wanted: draw the windows from **valid** cells (read `b.dataset_mask()` at an
  overview shape, pick `DTM_WINDOWS` random coarse cells where it is > 0, map back to
  full-resolution offsets), and count the valid cells the windows compared, reporting a pair
  under a floor (say 1,000) as its own drift line ("compared N valid cells: could not tell")
  rather than as a pass — make vacuity visible. Then a selftest fixture with a nodata collar
  and a narrow valid strip, red with the +1 m copy under the old sampling.

- **[fragile]** `scripts/dataset_publish.sh:74,94` against `scripts/dataset_align-lidarbc.py:559-581`
  (`check_table`) — the publish reuses whatever sits in the COG tree (`if [ ! -f "$out" ]`
  skips the conversion; `cp -np` never overwrites prod), and `--check` reads the **prod**
  tree only. The gate's own comment (`dataset_publish.sh:44`, "the COG step below skips a COG
  that exists") names the COG step as the hazard, and the check never opens the file that
  step reads. Reachable path: re-stitch, re-fit, delete the prod copy but not the COG copy
  (the retraction recipe at `scripts/config/README.md:53` and the re-stitch note at `:67`
  both say to delete both, and nothing enforces either), then publish — `--check` runs first
  over a prod tree that no longer holds the dataset, passes, the stale COG is copied into prod
  and the items are built from the new row. Every gate is green until the next
  `catalogue_release.sh`, whose `--check` then refuses a dataset already live. Latent today:
  the COG tree holds 80 keys and prod 83 (the three extra are the `no_cloud` ones), with no
  COG-only key. Same shape as round 2's finding, one copy over. Two closures: give the fitter
  `COG = ROOT / "imagery_uav_bc"` and have `check_table` compare `cog / tif` with the raw tree
  wherever it exists, with its own remedy ("delete the dataset's COG copy"); and/or run
  `--check` a second time in `dataset_publish.sh` after the COG copy and before
  `item_create.py` (seconds), so a stale COG that reached prod stops before any item is built.

- **[fragile]** `scripts/dataset_align-lidarbc.py:306-309` (`cloud_header`) against
  `check_table` — the row ↔ cloud tie is `(point_count, creation_date)`, and on the real
  clouds `creation_date` carries only the processing year (two values over 80 files; see the
  table). ODM rewrites the laz **in place** when it classifies (`run_pdaltranslate_smrf(lasFile,
  lasFile, …)`), `--dtm` forces that classification, and the CLAUDE.md resume rule points
  operators at hand-run `docker run` with `--rerun-from`. A rerun from `odm_dem` with changed
  `--smrf-*` parameters therefore replaces the class-2 set the fit reads while leaving both
  header fields the tie compares unchanged; the DTM it regenerates then differs from the
  published one only where the windows look (finding 1). Narrow — it needs a partial rerun
  with changed classification parameters in the same year — but it is the one copy above the
  table, and the proxy cannot see it. Record a content identity the rewrite cannot preserve:
  the laz file size beside the count (a PDAL rewrite changes a LAZ's compressed length), or a
  digest of sampled byte ranges, or the file's md5 if the seconds are acceptable.

Minor, not blocking:

- `scripts/dataset_align-lidarbc.py:568-571` — a row whose dataset has no laz `continue`s
  before the raster loop, so the three `no_cloud` datasets' published orthophotos are never
  compared with the raw tree, while the OK line (`:855`) says "every published raster is the
  raw tree's". No `alignment:` field is at stake for them; the sentence overclaims by three.
  Either compare the rasters before the `continue`, or say "every raster of a dataset with a
  cloud".

## Round 2's fixes, re-read

- `published_matches`: the grid check (width, height, EPSG, `almost_equals` on the affine)
  is sound for the re-stitch case, which moves the bounds. Band 1 only is fine (a re-stitch
  moves every band). `va.filled(0) - vb.filled(0)` on a Byte orthophoto wraps, but any
  nonzero difference still exceeds 0.01. The one defect is the window placement, above.
- `check_dtm` selftest: both arms measured as described (EPSG:32609 → `dtm_crs_differs`,
  +0.5 m → `dtm_cloud_disagree`, 0 m → accepted). It pins the fit-time check only; nothing
  re-runs it later, noted in the table.
- Rename recipe (`scripts/config/README.md` step 3): after renaming the dir in all three
  trees and the row's `item` in both CSVs, `--check` finds the laz at the new key with the
  same header, and `published_keys()` sees the new key with a row — walked through, consistent.
  The hand edit leaves the row out of sort order until the next fitter run rewrites the table;
  churn, not a defect.
- `--check` argument refusal: `uv run scripts/dataset_align-lidarbc.py --check <project>` exits 2
  with "give it no project" (measured).
- Page-full `sys.exit`s in all three live checks: present, not stripped by `-O`.

## Checked and clean

- `uv run scripts/dataset_align-lidarbc.py --selftest` (ALIGN SELFTEST PASS) and
  `conda run -n titiler python scripts/item_create.py --selftest` (ITEM SELFTEST PASS) on
  the branch tree; `--check` on the real trees: `ALIGN CHECK OK: 83 rows`. `git status` clean.
- Every number in README/NEWS/research re-derived from `data/alignment_lidarbc.csv`:
  83 rows, 46/31/3/3; misfit median 0.419 (0.316–0.688), 42 ≤ 1 m, 26 ≤ 0.5 m; |dz_raw|
  median 8.26, range −96.66..+92.18; shift median 3.24, max 12.39 — all match the prose
  (8.3, −97 to +92, 3.2, 12.4). `cloud_points` is distinct across all 80 rows.
- `item_create.py`: `alignment_props()` refuses unreadable and non-finite fitted rows before
  any write; `alignment_problems()` and `build_item()` read `published` identically; the
  no-row refusal runs before the build loop in both modes; `alignment:points` is an int, the
  rest floats or arrays of floats; `FIELD_PREFIXES` carries `alignment`.
- `catalogue_release.sh`: `--check` before the rebuild; the alignment live check keys items
  off the virtual-hosted href's first four path segments and tests presence iff fitted, as
  designed; a missing `image` asset raises and exits 1 (loud).
- `dataset_publish.sh`: `--check || exit 1` under `set -euo pipefail` (a missing `uv` is 127,
  loud); the per-project row check reads `$rel` split on `/` against the four-key set; the
  single-quoted `python3 -c` program is inert to the shell; no `conda run` output is piped.
- Sign convention and CRS: `corrected = published + shift`, `z − s(u, v)` matches `design()`,
  the selftest's planted model and `shift_back()`; `check_dtm` pins the DTM's EPSG to the
  cloud's, which is the item's `proj:epsg`.
- Table writer: `newline=""` + `lineterminator="\n"`, read-back shape equals write shape,
  rows sorted by key; `--trial` resumes by key.
- Shell: both `uv run … --check` lines are plain commands, no heredoc, no `&`; `bash -n` not
  needed beyond rounds 1–2; no new absolute path beyond the ones the scripts already hardcode.
