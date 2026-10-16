# Code-check round 2 — branch `41-fit-each-flight-to-lidarbc-our-uav-eleva` vs `main` (merge-base ec6dd31)

Reviewed 2026-10-16 (UTC), fresh eyes over the whole diff (`7b122ef` included) plus the full
contents of every changed code and doc file, against the repo's code-check conventions (general,
shell, R, spatial, Python) in full. Every probe below ran read-only on the repo (selftests,
`--check`) or on copies under `scratchpad/review/work/`; nothing under `~/Projects/gis/` was touched
and no publish or release script was run.

## Findings

No bug, security issue or data-loss path found in a shipped code path. Two fragile points, one of
them the half of round 1's `--check` closure that is still open, and two minor notes.

- **[fragile]** `scripts/dataset_publish.sh:46`, `scripts/catalogue_release.sh:28` (the new
  `--check` gates) against `scripts/dataset_align-lidarbc.py:535-547` (`check_table`) and
  `scripts/config/README.md:88-105` ("Renaming a published dataset", unchanged by the diff) —
  the gate makes the documented rename recipe end in a refused publish/release with a remedy that
  cannot apply. The recipe renames the dataset dir in all three trees and updates the row's `item`
  in `data/sites.csv` only (step 3, line 99); it says nothing about `data/alignment_lidarbc.csv`,
  which is keyed the same way. After a rename the old key's `fitted` row remains and its laz is
  gone, so `--check` fails (measured on a scratch copy of the table with one `item` renamed:
  `skeena/bulkley/2025/bulkley_br5: published, no row` and
  `skeena/bulkley/2025/bulkley_br5_OLD_NAME: cloud gone, row says fitted`, rc 1). The message says
  `re-run the script on them` (line 776), but the fitter has no delete: re-run on the vanished dir
  it writes a phantom `no_cloud` row for the old key (measured: `[1/1] …/bulkley_br5_RENAMED_AWAY:
  no_cloud`, and `--check` then reports OK on 84 rows), so the one remedy that clears the gate
  mislabels a dataset that no longer exists. Hand-editing the CSV is the real remedy and nothing
  says so. Two cheap closures: add the alignment row to the rename recipe (rename its `item`, or
  delete it and refit under the new key), and give the `cloud gone` arm its own remedy text, since
  "re-run" is right for the other two drift arms and wrong for this one. Two related notes, neither
  a defect: `--check <project-dir>` silently ignores the project args and checks the whole table
  (the `args.check` branch at line 771 runs before `keys` is built; measured), and the gate's scope
  is the whole table, so an unrelated dataset being re-stitched while `dataset_publish.sh` runs for
  another one (laz absent or rewritten mid-run) refuses that publish until the re-stitch finishes
  and is refitted. Loud, and stricter than the publish needs, which only builds the requested
  datasets' items.

- **[fragile]** `scripts/dataset_align-lidarbc.py:425` (`check_dtm(proj / DTM, …)`, the raw tree's
  DTM) and `:535-547` (`--check`, the raw laz header) against `scripts/dataset_publish.sh:72-92`
  (`if [ ! -f "$out" ]` skips the COG conversion, `cp -np` never overwrites prod) — round 1's
  closure ties a `fitted` row to the **raw cloud** and nothing ties it to the **published raster**.
  The comment at `dataset_publish.sh:42-44` says the gate stops "a cloud re-stitched since its fit"
  from publishing another cloud's fields; the other direction is open: re-stitch a published
  dataset, re-fit it (row now describes the new cloud, `--check` OK, `check_dtm` passes against the
  new raw DTM), then publish without deleting `$COG_TREE/<key>` and `$PROD/<key>` — the COG step is
  skipped, the old rasters stay, and every gate is green (`--check`, `check_dtm`, the per-project
  row check, the release's live alignment check, which only tests field presence) while the items
  carry a fit for ground the published DTM does not hold. No doc names deleting the COG/prod copies
  on a re-stitch (grep over `scripts/config/README.md`, `CLAUDE.md`, `NEWS.md`: the #27 dataset
  "was re-stitched before publication", so no instance yet). Measured today: for all 46 fitted
  datasets the raw `odm_dem/dtm.tif` equals the published COG (same grid, 400 sampled pixels within
  1 cm; 0 differ, 0 missing), so it is latent. Cheapest closure in the file's own idiom:
  `canopy_height()` (line 273) already prefers `proj_prod` when the published rasters exist;
  `check_dtm` can do the same, or `--check` can compare the prod DTM's grid/sample against the raw
  one beside the laz header. Same shape as round 1's finding, one artifact over.

Minor, not blocking:

- `scripts/catalogue_release.sh:60, 95, 131` — the three page-full guards are Python `assert`s
  inside `python3 -c`, which `PYTHONOPTIMIZE` / `-O` strips (measured: under `PYTHONOPTIMIZE=1` the
  identical `assert len(f) < 1000` passes a 1000-item list and prints). `PYTHONOPTIMIZE` is unset on
  this machine, `set -euo pipefail` carries a failed assert out of the `n_items=$(…)` substitution,
  and the fitter's own `search_dems()` uses an explicit `raise`, so the guards work today and fail
  toward pass only under an env var nobody sets. One line each (`if len(feats) >= 1000:
  sys.exit(…)`) removes the dependence.
- `README.Rmd:175` (rendered `README.md:143`, `index.html`) — "Measured against the LidarBC 1 m DEM
  for the 49 datasets that have one under them, the published rasters sit a median of 8.3 m …
  (from −97 to +92 m) and 3.2 m horizontally (up to 12.4 m)". Those four figures are over the **46
  fitted** rows: the 3 refused rows carry no `dz_raw_m` or shift, and the research doc's own Result
  paragraph (line 151) states the same numbers "over the 46". The sentence names a population three
  larger than the one the numbers come from. NEWS states no population and is fine.

## Checked and clean

- `uv run scripts/dataset_align-lidarbc.py --selftest` (ALIGN SELFTEST PASS) and
  `conda run -n titiler python scripts/item_create.py --selftest` (ITEM SELFTEST PASS) on the branch
  tree; `uv run scripts/dataset_align-lidarbc.py --check` on the real trees: `ALIGN CHECK OK: 83
  rows`, 0.12 s. A planted `cloud_points` drift (+1 on one row, scratch copy via `--out`) is reported
  with the real header (`cloud is 14222206 points of 2024-12-31, row fitted 14222207 …`) and rc 1.
- Round 1's fixes, each re-read: the `MAX_SHIFT_SPREAD` comment and the research bullet now date the
  cut to the plane run and state the quadratic table's spreads; re-derived from
  `data/alignment_lidarbc.csv`: largest fitted spread 1.95 (`richfield_lower_RC3-2021`), then 1.46,
  1.46, 1.35, 1.27; refusals at 2.6 (`197912_roberthatch`) and 5.6 (the moose post flight); and from
  the grid's plane/none arm: max fitted spread 1.25, refusals 3.2 / 5.5 / 8.5, consistent with the
  comment's "four between 1.0 and 1.3 m, then 5.5 and 8.5" for the lifted-cut scan (the 3.2 one hit
  the bound there, as findings.md records). README and NEWS now name the 3 `no_cloud` datasets
  (`bulkley-byman-richfield`, `bulkley-mckilligan-barren`, `buck_buc7`, measured). `--check` runs
  first in both scripts. The page-full assertions are in all three live checks. `alignment:reference`
  `;`-joining is documented (one such row, `199663_parsnip_trib_chco_11000`). The href comment is
  right for the virtual-hosted URL.
- The `uv run … --check || exit 1` lines: both scripts run `set -euo pipefail`; a missing `uv` is
  exit 127 → `|| exit 1`, a failed dependency resolve or a failed check is non-zero → loud. `uv` is
  `/opt/homebrew/bin/uv` 0.12.5 here. The fitter's defaults (`ROOT`, `PROD`, `TABLE`) equal
  `dataset_publish.sh`'s `ROOT`/`PROD`, `item_create.py`'s `--base` and `--alignment`, and
  `catalogue_release.sh`'s `PROD`; no symlink on the path, so `project_key()`'s `resolve()` and the
  publish script's string prefix agree.
- Every number in README/NEWS/research re-derived from the committed table and grid: 83 rows,
  46/31/3/3; |dz_raw| median 8.26 → 8.3, range −96.66..+92.18; shift median 3.24, max 12.39; misfit
  median 0.4195, quartiles 0.316–0.688, 42 ≤ 1 m, 26 ≤ 0.5 m, one > 2 m; every `surface` has 6
  coefficients; table keys ⊂ `sites.csv` (the two absent are `published=false`); the table equals
  the grid's quadratic/none arm cell for cell (0 diffs). The trial table (8 arms: n, median,
  quartiles, ≤ 1, ≤ 0.5, paired median, lower/of) matches the grid on every cell; the verdict
  paragraph's `slope` +0.000 (19/42), `open` −0.006 (34/46, one better by > 0.1 m, none worse),
  `slope+open` −0.006 (27/45), and the two datasets the quadratic does not lower
  (`richfield_lower_RC3` 0.529 → 0.846, `richfield_upper_RC1` 0.647 → 0.654) all match. The 31
  `no_reference` rows are 17 Morice + 4 Parsnip + 10 others, so "mostly" holds.
- `index.html`: the two 84 KB changed lines are identical modulo the DT widget id (the data table
  is unchanged); `README.Rmd` chunk labels are unique (`filter-alignment` is new).
- Sign convention: README's `corrected (x, y) = published + shift`, `corrected z = published z −
  s(u, v)` with `s` over `[1, u, v, u², uv, v²]` matches `design()`, the selftest's planted model
  and `shift_back()`; `alignment:centre` and the surface are in the cloud CRS, which `check_dtm`
  pins to the DTM's, which is the item's `proj:epsg`.
- `item_create.py`: `alignment_props()` refuses an unreadable or non-finite fitted row before any
  write; `alignment_problems()` and `build_item()` read `published` identically; the no-row refusal
  runs before the build loop in both modes; the live alignment check reads the `image` asset every
  item carries (`asset_name="image"`, `stacs.toml`).
- Shell: the two embedded `python3 -c "…"` programs carry no `"`, `` ` ``, `$` or `\`; the
  single-quoted one in `dataset_publish.sh` is inert to the shell; `bash -n` not needed beyond
  round 1. No `conda run` output is piped. No new absolute path beyond the ones the scripts already
  hardcode.
