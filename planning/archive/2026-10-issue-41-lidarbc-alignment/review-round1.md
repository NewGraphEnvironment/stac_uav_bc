# Code-check round 1 — branch `41-fit-each-flight-to-lidarbc-our-uav-eleva` vs `main` (merge-base ec6dd31)

Reviewed 2026-10-16 (UTC). Inputs: the full diff plus the full contents of every changed code and doc
file, and the repo's code-check conventions (general, shell, R, spatial, Python) in full.

## Findings

No defect in a shipped code path. Three fragile points and three minor notes, in order of weight.

- **[fragile]** `scripts/dataset_align-lidarbc.py:94-98` and `research/uav_pointclouds.md:133-135` —
  the justification written beside `MAX_SHIFT_SPREAD = 2.0` describes the **plane** run, not the
  shipped **quadratic** table, and the shipped table does not have the gap the sentence claims.
  Measured from `data/alignment_lidarbc.csv` (46 fitted rows): the largest fitted spreads are
  **1.95** (`richfield_lower_RC3-2021`), 1.46, 1.46, 1.35, 1.27 m, and the `shift_unstable` refusals
  sit at **2.6** (`197912_roberthatch`) and 5.6 m (the moose post flight). So under the quadratic the
  gap is 1.95 → 2.6 and the cut sits 5 cm from a fitted row, not "nothing until 5.5 m and 8.5 m".
  The research doc's version also names `maxan_mx1` (5.5 m) and "the moose pre flight" (8.5 m) as
  the undetermined cases; in the shipped table both are fitted (spreads 0.5 and 0.79). The cut
  itself is not re-litigated here; the sentence is a present-tense justification for a live
  threshold (`code-check.md`, "A restatement is either a LIVE justification or a HISTORICAL
  measurement"), so either date it as the plane-run measurement or restate it from the quadratic
  table. Nothing executable depends on it.

- **[fragile]** `README.Rmd:177` (rendered at `README.md:162`, `index.html`) and `NEWS.md:24-26` —
  the sentence enumerating which datasets carry no `alignment:` fields covers 34 of the 37. The
  table has 83 rows, 46 `fitted`; the 37 without fields are 31 `no_reference` + 3 `refused` +
  **3 `no_cloud`** (`skeena/bulkley/2024/bulkley-byman-richfield`,
  `skeena/bulkley/2024/bulkley-mckilligan-barren`, `skeena/bulkley/2025/buck_buc7`). The README and
  NEWS name the 31 and the 3 refused and omit the 3 with no ODM cloud (the research doc does say
  "3 have no ODM cloud"). A reader of the README would expect every dataset outside those two groups
  to carry the fields. Every other number in the README/NEWS/research text was re-derived from the
  committed table and matches (46/31/3/3; median 0.42, quartiles 0.32–0.69 numpy-linear; 42 ≤ 1 m,
  26 ≤ 0.5 m; |dz_raw| median 8.26 → "8.3", range −96.66..+92.18; shift median 3.24, max 12.39).

- **[fragile]** `scripts/dataset_publish.sh:54-61`, `scripts/dataset_align-lidarbc.py:324`
  (`check_dtm`) and `:533-544` (`check_table`) — nothing in the publish or release path ties a
  `fitted` row to the cloud or raster that is actually published. `dataset_publish.sh` checks only
  that a row **exists** (any status); `item_create.py` `alignment_problems()` the same.
  `check_dtm` validates the fit against the **raw tree's** `odm_dem/dtm.tif`, and `check_table`
  (`--check`) compares `cloud_points`/`cloud_date` against the raw laz, but `--check` is run by
  nothing (`scripts/config/README.md` lists it as a one-off tool). So a dataset re-stitched between
  step 3 (fit) and step 4 (publish) of the recipe — the #27 re-stitch shape — publishes items whose
  `alignment:` fields describe a different cloud than the COG beside them, with every gate green;
  the row records `cloud_points`/`cloud_date` precisely so this is detectable, and the only
  consumer is manual. The cheap closure is to run `uv run scripts/dataset_align-lidarbc.py --check`
  (83 laz headers, seconds) in `dataset_publish.sh` before the COG step and in
  `catalogue_release.sh` before the rebuild; the publish's own python check cannot do it, because
  laspy lives only under `uv`. Same shape as "A guard that detects a stale input after the write is
  TIED, not GUARDED" (`code-check.md`), here with no tie at all in the pipeline.

Minor, not blocking:

- `scripts/catalogue_release.sh:55,84,118` — all three live checks, the new alignment block
  included, read one `limit: 1000` page and never assert the page was not full (the sibling
  `search_dems()` in the fitter does assert it). Live today: 245 items, server honours 1000, no
  `next` link; the inherited shape fails toward pass only past 1000 items. One line
  (`assert len(feats) < 1000`) closes it; inherited from the registry check on `main`.
- `README.Rmd:188` documents `alignment:reference` as "the LidarBC delivery the fit used
  (`093/093g/2024`)"; one fitted row carries a `;`-joined pair
  (`mackenzie/parsnip/2026/199663_parsnip_trib_chco_11000`: `093/093j/2025;093/093o/2025`), so a
  CQL2 equality filter on a delivery misses it. Say the field can carry several, `;`-joined.
- `scripts/catalogue_release.sh:116` — the comment says the asset href path is
  `<bucket>/<region>/<wsg>/<year>/<item>/...`; the code takes the first four path segments, which
  is right for the virtual-hosted `bucket_url` (`https://imagery-uav-bc.s3.amazonaws.com/<region>/…`,
  verified against a live item). A path-style URL would shift the key by one and refuse every
  fitted dataset (loud, not silent); the comment is what misleads.

## Checked and clean

- `conda run -n titiler python scripts/item_create.py --selftest` and
  `uv run scripts/dataset_align-lidarbc.py --selftest`: both PASS on the branch tree.
- Restore-the-bug, in scratch copies (`scratchpad/review/work/`): `alignment` removed from
  `FIELD_PREFIXES` → red (2 checks); `alignment_props()` writing fields for every status → red (2);
  finite check removed → red (2: `nan` and `Infinity` pass); fitter spread refusal removed → red
  ("a flat site refused as shift_at_bound … not shift_unstable"). Four of the sixteen claimed
  mutants re-measured; all fired.
- The two python programs embedded in the shell scripts were extracted and run offline:
  `catalogue_release.sh`'s alignment check returns OK on an agreeing feature set and
  RELEASE INCOMPLETE (rc 1) in both disagreeing directions; `dataset_publish.sh`'s row check passes a
  present key (fitted or not) and refuses an absent one. `bash -n` clean on both scripts. The
  double-quoted `python3 -c "…"` block carries no `"`, `` ` ``, `$` or `\`, so bash leaves it
  intact (the shape `code-check-shell.md` warns about is present but inert here).
- Live API probes: the prod collection search at `limit: 1000` returns 245 features, no `next`;
  `stac-elevation-bc` at `limit: 200` returns exactly 200 with a `next` link and 374 at 1000, so the
  fitter's `len(feats) >= SEARCH_LIMIT` page guard is sound; `lidarbc:delivery` and the `dem` asset
  exist as the fitter expects.
- `data/alignment_lidarbc.csv` equals the trial grid's quadratic/none arm cell for cell on every
  shared column (0 differences over 46 rows), as the findings claim; 83 rows, 27 columns each, no
  `nan`/`inf` cell; every `surface` has 6 coefficients; keys ⊂ `sites.csv` (the two rows of
  `sites.csv` absent from the table are both `published=false`).
- Sign convention: the README's "corrected (x, y) = published + shift; corrected z = published z −
  s(u, v)" matches the model the selftest plants (`z = dem(x + dx, y + dy) + surface`) and
  `shift_back()` carries the tile-CRS shift into the cloud CRS through the centre.
- `published` is read identically in `build_item()` and `alignment_problems()`
  (`.strip().lower() == "false"`), so the two skips cannot disagree.
- The table writer uses `newline=""` + `lineterminator="\n"`, read-back shape equals write shape
  (selftest round-trips and merges), rows sorted by key, so a partial run merges without churn.
