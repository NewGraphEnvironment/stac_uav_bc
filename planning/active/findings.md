# Findings — Fit each flight to LidarBC: our UAV elevations are off by the drone's GPS altitude (#41)

## Issue context

## Problem

Every UAV DTM and DSM in `imagery-uav-bc-prod` sits at the drone's GPS altitude, and that is wrong by
a lot. Against the LidarBC 1 m DEM, 51 ODM flights are off vertically by a median of 9 m, from −107 to
+97 m, and horizontally by a median of 3.5 m (up to 19 m). The published `odm_dem/dtm.tif` matches its
point cloud to the centimetre, so the rasters carry the same error. No flight used ground control.
The geoid (−8 to −15 m here) does not explain it; the drone's GPS altitude does.

A shift plus a tilt, fitted robustly to LidarBC ground, brings the misfit to a median of 0.82 m
(NMAD): 29 of 51 flights within 1 m, 12 within 0.5 m. Measurements, method and per-flight table:
[`research/uav_pointclouds.md`](https://github.com/NewGraphEnvironment/stac_uav_bc/blob/main/research/uav_pointclouds.md) (in #44 until it merges).

## Scope

1. Promote the probe (`research/uav_pointclouds/uav_lidar_align.py`) to a pipeline script that,
   for each published dataset on a LidarBC DEM, fits shift + tilt against the newest LidarBC delivery
   and writes one row per dataset to a committed table under `data/`: shift, offset, tilt, misfit,
   the LidarBC delivery used, and the number of points compared.
2. Try two cheap improvements before settling the model, and keep whichever lowers misfit:
   a per-flight quadratic (the moose pair shows doming of about 12 m over 1.6 km that a plane cannot
   remove), and comparing only stable open ground (a slope or LidarBC-ground mask), so real change and
   vegetation stop counting as misfit.
3. Say in the README that UAV elevations are GPS-referenced, with the measured range.

## Decisions for the plan gate (stored data)

- **What the catalogue carries.** (a) the fitted transform as item fields, rasters untouched
  (recommended first: cheap, reversible); (b) corrected DTM/DSM published beside the originals;
  (c) corrected rasters replace the originals.
- **Field names**, if (a): they need a descriptive prefix in `FIELD_PREFIXES` (#38's rule).
- **The 31 flights with no LidarBC under them** (mostly Morice 2021–2026 and upper Parsnip 2022–2024):
  leave them flagged as unaligned, or find another reference.

## Acceptance

- Every published dataset on a LidarBC DEM has a row, and the script refuses a flight it could not
  fit rather than writing a guess.
- The misfit distribution is reported and matches or beats the research figure (median ≤ 0.82 m).
- Out of scope: publishing point clouds, change detection (their own issues).

## Exploration (2026-10-15, before the baseline)

- **Published datasets:** 81 with `odm_dem/dtm.tif` in the prod tree (245 items). 80 have an ODM
  `odm_georeferenced_model.laz` in the raw tree; `skeena/bulkley/2025/buck_buc7` has none (#31's
  duplicate). `kootenay/elk/2021/parker` was a `--split` run; its merged laz sits at the top level
  beside four submodel clouds.
- **Research table** (`research/uav_pointclouds/uav_lidarbc_offsets.csv`): 61 rows, 51 ODM, 10 Maps
  Made Easy, 7 datasets in both. ODM median `nmad_shift_tilt_m` 0.82, 29 ≤ 1 m, 12 ≤ 0.5 m. No ODM
  shift at the ±20 m bound. Six above 2 m: `124421_waterfall_11th` 2.08, `buck_buc64` 2.09,
  `buck_bulkley_buc7` 2.23, `199663…post_replacement` 3.2, `199663…11000` 5.93,
  `23502870_track_ck_johnson_fsr` 6.66. `kootenay/regent/20250616` has 0.7 M points.
- **Probe inputs:** `uav_pc_headers.py` (laspy header per cloud → `headers.jsonl`), `lidar_overlap.py`
  (bbox search of `https://images.a11s.one/search`, collections `stac-elevation-bc` and
  `stac-pointcloud-bc` → `overlap.json`; DEM items carry `dem` and sometimes `dsm` assets at
  `nrs.objectstore.gov.bc.ca`). `uav_lidar_align.py` takes both and writes JSON lines; it drops
  `albers10k2m` DEMs and keeps the newest year.
- **Python:** neither conda env has laspy (`titiler` runs `item_create.py`; `dff` runs `rio cogeo`).
  `uv` 0.12.5 is installed and the probes carry PEP 723 headers.
- **STAC Accuracy extension:** v1.0.0-beta.1, maturity Proposal; fields `accuracy:geometric_x_bias`,
  `_y_bias`, `_x_stddev`, `_y_stddev`, `geometric_rmse`, `measurement_relative`,
  `measurement_absolute`; rel types `elevation-model`, `geometric-accuracy`. No vertical bias, tilt
  or reference field, so the fit does not fit it; not chosen (plan gate).
- **`item_create.py`:** `REGISTRY_FIELDS` maps `sites.csv` columns to properties; `FIELD_PREFIXES`
  guards every property and asset key; registry checks run before the build loop and every item is
  built before any is saved. The join for the alignment table follows the same shape.
- **README render:** the `build` chunk in `README.Rmd` renders `README.md` (`github_document`,
  `rmd_on = FALSE`) and `index.html` (`rmd_on = TRUE`); the query is cached in
  `data/stac_result.rds` unless `update_query = TRUE`.

## Plan review (Plan agent, 2026-10-16, 30 findings)

Verified and adopted in `scripts/dataset_align-lidarbc.py` before the first full run:

| finding | what changed |
|---|---|
| the prod tree holds **83** datasets, not 81: two Maps Made Easy datasets publish only `ortho.tif` | enumerate by any tif; those two are `no_cloud` |
| nearest-cell DEM sampling adds slope × U(−0.5, 0.5) m per point and makes the 0.25 m search a step function | bilinear sampling, cell values at centres |
| the fitter (L2 + trim) is not the score (NMAD): 10 research rows got worse from shift-only to shift + tilt | Huber IRLS, k = 1.345 robust scales, 5 iterations |
| a flat site has no horizontal signal: the moose post flight gave 18.8/8.0 vs 16.5/9.3 m on two samples | the search runs on two disjoint 20k samples; > 1 m apart is `refused:shift_unstable` |
| `n_compared >= 2000` of 200 000 is 1 % coverage; a tilt fitted on a sliver is extrapolated | `coverage` recorded; < 0.5 refused, after falling back to an older delivery |
| the newest-year filter drops tiles (`199174_necr_trib` 2 × 2024 + 1 × 2019) | deliveries tried newest first until one covers half |
| the shift's frame: tiles are NAD83(CSRS) UTM, clouds WGS 84 UTM, PROJ applies ~1 m between them | the shift is carried back into the cloud's CRS through the centre (exact for a translation); `reference_crs` recorded |
| the module-level rng made every row depend on the rows before it | seeded per dataset key (crc32) |
| the plane's centre was the mean of sampled points, unrecoverable by a reader | `surface` (all coefficients) and `centre` published |
| geoid call silently returns 0 without the grid | dropped; the fit never used it |
| unclassified clouds fit canopy (research: 3.3 m median) | an ODM cloud with no class 2 is `refused:no_ground_class`; Maps Made Easy clouds are not fitted |
| nothing ties a row to the cloud it was fitted on | `cloud_points`, `cloud_date` recorded; `--check` reports drift and published datasets with no row |
| the DTM carries the fields, the cloud is what is fitted | gate: laz CRS = DTM CRS, and median DTM − cloud ground within 0.1 m over 2000 points |
| STAC search `limit=200` with no paging | a full page raises |
| NaN into items: `json.dumps` writes it, pystac accepts it, pgstac does not | `item_create.py` requires every number finite |
| the "no row" refusal belongs in the pre-loop check, filtered on `published` | done there, over the rebuild glob or the requested tifs |
| random halves of a 50 pts/m² cloud are twins | the held-out split is a 50 m checkerboard; masks apply to the fit points only and every arm is scored on the same unmasked points |

Not adopted: widening the search window once before refusing (cost ×4; no ODM flight hit the bound in the research); a report/`--write` split (a run writes the rows it computed, that is the point of running it); the Accuracy extension (plan gate). The datum step inside the shift (reviewer's blocker 3) was already handled by the inverse transform through the centre.

## Gates, with each defect restored (2026-10-16)

`uv run scripts/dataset_align-lidarbc.py --selftest`, 32 s, on a scratchpad copy with one line changed:

| defect planted | result |
|---|---|
| shift sign flipped (`X - dx`) | red: shift (−3.5, 2.25) against truth (3.5, −2.25) |
| Huber reweighting removed | red: offset 13.15 against 12.3 (the planted tenth of outliers) |
| at-bound refusal removed | red: a 30 m shift was fitted |
| spread refusal removed | red: a flat site was fitted |
| coverage refusal removed | red: a flight half off the DEM was fitted |
| table written CRLF | red |
| `--check` blind to a changed cloud | red (after fixing the selftest, which first crashed on the shorter drift list instead of failing) |
| nearest-cell sampling instead of bilinear | **green**: a quality choice the tolerances cannot see, not a guard |
| mask not applied to the fit points | red: the masked fit still sees the planted outliers; 500 kept points fitted |
| slope mask inverted (`>=`) | red: keeps 0.45 of the hill but the wrong half |
| open mask inverted | red: keeps the half under the trees |
| mask minimum removed | red: a mask keeping 500 points was fitted |
| `open` mask refuses a DSM and DTM on different grids (the exact-affine check the trial removed, Phase 2) | red: the refusal is a failed check and the mask keeps nothing (first try crashed the selftest from the second mask call, outside the `try`; wrapped) |

Re-run after Phase 2 (quadratic default, per-raster canopy sampling): the same 12 red, nearest-cell green (`mutants_quad.log`).

`conda run -n titiler python scripts/item_create.py --selftest`: `alignment` removed from `FIELD_PREFIXES` (red, 4 checks), fields written for every status (red, 3), finite check removed (red, 2: `nan` and `Infinity` pass), `published=false` ignored by the no-row check (red, 2).

## First fit, one dataset (2026-10-16)

`fraser/cottonwood/2026/198285_pedley_lake_creek_rd`, 30 s: `dz_raw` +69.81 m (research +69.83), shift (3.0, −4.88) ± 0.25 (research 3.0, −3.75), tilt 1.27 (research 1.29), misfit 0.98 held-out (research 1.09 in-sample). The y shift moved 1.1 m with bilinear sampling and the Huber fitter; the full-set comparison is below.

## First full run, and the checkerboard (2026-10-16)

The first run of all 83 datasets (26 min; plane, no mask; the fit on one half of a 50 m checkerboard, the misfit scored on the other half) gave 37 fitted, 31 `no_reference`, 3 `no_cloud`, 12 refused. Against the research table, `dz_raw` reproduced to 0.03 m on every dataset, but 16 of 37 shifts differed by more than 1 m and four of those scored **worse** than the research's shift would (`8530_sandstone_mcdonell` 8.9 m apart, misfit 2.5 against 1.68).

Probed by scoring the plane at both shifts with the same code (`probe_score.py`):

| dataset | shift | score on the fit's own 20k sample | score on every point |
|---|---|---|---|
| sandstone_mcdonell | table (−1.5, 1.5) | 0.56 | **2.65** |
| sandstone_mcdonell | research (7, −1) | 1.55 | 1.66 |
| helps_lawson | table (−5.4, 5.5) | 0.40 | 0.48 |
| helps_lawson | research (−2.25, 1.25) | 0.42 | 0.39 |
| simpson_nielson | table (17.9, −19.9), at the bound | 1.33 | 1.51 |
| simpson_nielson | research (0.75, −3.75) | 1.41 | 1.45 |

The two "independent" search samples both came from the black cells, so they shared the black half's bias and the spread test could not see it; the misfit scored on the white half then reported the damage honestly. A spatial split is the wrong instrument on a GPS-only reconstruction, whose error is itself spatially structured. With 10^5 points and 3 or 6 parameters a random held-out split tests nothing either. Dropped: the fit uses every point over the DEM (as the research did), the two search samples are random draws from all of them, and every arm of the trial is scored on every point. The refusal order also changed: both samples on the window's edge is `shift_at_bound`; otherwise a spread over the cut is `shift_unstable`.

That run also refused 10 datasets as `shift_unstable` at spreads of 1.1–4.9 m, mostly flat Bulkley 2025 floodplain sites. The 1 m cut was a guess; the research called 2.6 m apart "not well determined". Settled from a scan with the cut lifted (`tableA.csv`), below.

## Second full run, fit on every point, spread cut lifted (2026-10-16, 29 min)

47 fitted, 2 refused (the moose post flight `shift_at_bound` at (19.5, 6.25); `table_ck` `low_coverage` 0.27, no delivery covers half of it), 31 `no_reference`, 3 `no_cloud`. Against the research on the same 49 published datasets:

| | research | this run (47 fitted) |
|---|---|---|
| median misfit | 0.82 m | **0.79 m** |
| within 1 m | 28 | 28 |
| within 0.5 m | 12 | 12 |
| `dz_raw`, per dataset | | identical to 0.03 m |
| misfit, per dataset | | median −0.01, middle half −0.02 to 0.00, worst 0.18 m |
| tilt, per dataset | | median +0.01, worst 0.62 m/100 m |
| shift, per dataset | | median 0, middle half ±0.4 m; 9 datasets more than 1 m apart |

The nine shifts over 1 m apart sit on near-flat score valleys: `sandstone_mcdonell` scores 1.63 m at the table's (−0.4, 4.9) and 1.68 at the research's (7, −1), 9 m apart. **A site with one linear feature (a road, a bank) determines the shift across the feature, not along it, and the two-sample spread sees only sampling noise, not that ambiguity.** The misfit reports the fit's quality honestly; the shift's uncertainty along a feature is not recorded. Noted in the research doc as a limit.

**The spread cut.** Spreads of the 47: 41 at or under 1.0 m, four between 1.0 and 1.3 m (`track_ck` 1.03, `fern` 1.06, `buc87b` 1.06, `station_hwy16` 1.25), then 5.5 m (`maxan_mx1`: misfit 0.73, a flat site whose vertical fit is fine and whose shift is anyone's) and 8.5 m (the moose pre flight, misfit 5.9). `MAX_SHIFT_SPREAD = 2.0` sits in the gap and under the research's 2.6 m. Expected production result: 45 fitted, 4 refused.

## Production table, plane model (2026-10-16, 26 min)

`data/alignment_lidarbc.csv`: 83 rows; **45 fitted**, 4 refused (`199663…11000` `shift_unstable` 8.5 m, `…post_replacement` 3.2 m, `maxan_mx1` 5.5 m; `16701523_table_ck` `low_coverage` 0.27), 31 `no_reference`, 3 `no_cloud`. Identical to the lifted-cut scan except the three rows the cut turns. `--check` OK. Over the 45: raw vertical offset median +6.0 m (absolute median 7.2 m, −96.7 to +92.2 m); horizontal shift median 3.4 m (up to 10.9 m); misfit median 0.79 m, 27 within 1 m, 12 within 0.5 m. 49 datasets sit on LidarBC (45 + 4 refused).

## Trial grid and the production table, quadratic model (2026-10-16)

`--trial` over all 83 (1 h 50 min, resumed once after the progress-line crash): the grid is `research/uav_pointclouds/trials/grid.csv`, its table in `research/uav_pointclouds.md`. The quadratic against the plane, paired on the 44 datasets both fit: misfit median 0.78 → 0.42 m, −0.225 m per dataset, lower on 42 of 44 (worse on `richfield_lower_RC3` 0.53 → 0.85 and `richfield_upper_RC1` 0.65 → 0.65). Within 1 m: 27 → 41; within 0.5 m: 12 → 25. The masks, paired against no mask within the quadratic, move the median by under 5 mm and lower it on about half the datasets, so no mask is the default (ties to the simpler). The `open` mask was first refused on 16 datasets whose published DSM and DTM are not on one grid (a column, or a centimetre of origin, apart); the refusal was an exact affine comparison, replaced by sampling each raster on its own grid, and the 16 re-run.

**Production table, quadratic, no mask** (`data/alignment_lidarbc.csv`, 32 min): 83 rows; **46 fitted**, 3 refused (`197912_roberthatch` `shift_unstable` 2.6 m, the moose post flight 5.6 m, `16701523_table_ck` `low_coverage` 0.27), 31 `no_reference`, 3 `no_cloud`; `--check` OK. The rows equal the trial's quadratic/none arm cell for cell (same per-dataset random state), which is the reproduction check. Over the 46: raw vertical offset median 8.3 m in size (signed +5.8; −97 to +92 m); horizontal shift median 3.2 m (up to 12.4 m); misfit median **0.42 m** (quartiles 0.32–0.69), 42 within 1 m, 26 within 0.5 m; one dataset above 2 m (`track_ck_johnson_fsr`, 4.9 m). Against the plane table: the quadratic fits `maxan_mx1` (0.29 m) and the moose pre flight (1.53 m), whose plane shifts were unstable, and refuses `roberthatch`, whose plane shift was not. The shifts differ between the two models by a median of 1.3 m (25 datasets over 1 m, up to 6 m), the along-feature ambiguity again: the shift is the fit's least determined number and the misfit says nothing about it.

## Offline verification of the join (2026-10-16)

Prod tree mirrored into the scratchpad (245 tifs symlinked, 246 JSONs copied), `item_create.py --rebuild --base <mirror> --version 0.0.0-test`: 245 items from 245 tifs, 245 links resolve; `stacs validate` 246 validated, 0 invalid; `stacs audit --expect 245` OK. A second rebuild of the same tree with a table in which every row is `no_reference` is the control: the two builds differ only in the `alignment:` fields; every fitted dataset's three items carry identical values; no other item carries any (`mirror_check.py`). Comparing against prod itself is not possible yet: prod's items still carry the pre-#38 `nge:` fields, which the #38 release will replace.

Repeated on a fresh mirror with the quadratic table (`mirror2.log`): 245 items from 245 tifs, 245 links resolve; validate 246, 0 invalid; audit OK against 245; 46 fitted datasets carry the fields on every item, six coefficients in `alignment:surface`, and the build differs from the control only in the `alignment:` fields.

## Branch review (`/code-check branch`, 2026-10-16)

Round 1 (`review-round1.md`): no defect in a shipped path; three fragile points and three minor notes, all fixed:

| finding | fix |
|---|---|
| the justification beside `MAX_SHIFT_SPREAD` described the plane run; under the quadratic the largest fitted spread is 1.95 m and the refusals 2.6 and 5.6 m, so the cut is 5 cm from a fitted row | comment and research bullet restated: set from the plane run (dated), the quadratic's spreads given |
| README and NEWS said which datasets carry no fields and omitted the 3 with no ODM cloud | added |
| nothing in the pipeline ran `--check`: a cloud re-stitched between the fit and the publish would ship another cloud's fields with every gate green | `dataset_publish.sh` runs `--check` before anything (proved: a planted `cloud_points` drift stops it before the missing-tif check; 0.1 s) and `catalogue_release.sh` before the rebuild |
| the release script's three live checks read one 1000-item page with no page-full assertion (two inherited) | `assert len(feats) < 1000` in all three |
| `alignment:reference` can carry two deliveries `;`-joined (the two moose flights) | README field table says so |
| a comment named the href path as `<bucket>/<region>/…`; the code takes four segments under the virtual-hosted URL | comment fixed |

Round 2 (`review-round2.md`): no defect in a shipped path; two fragile points, both inside round 1's `--check` closure, and two minor notes. All fixed:

| finding | fix |
|---|---|
| the new gate breaks the documented rename recipe: the old key's fitted row stays with its cloud gone, `--check` refuses, and its remedy ("re-run the script") writes a phantom `no_cloud` row (the fitter never deletes) | rename recipe step 3 renames the alignment row too; every `--check` line ends with its own remedy; `--check <project>` is refused instead of silently checking the whole table |
| round 1 tied the row to the raw cloud; nothing tied it to the published raster: re-stitch, re-fit, publish without deleting the COG keeps the old rasters beside the new fit, every gate green (latent: all 46 published DTMs equal the raw ones today) | `--check` compares every published raster (DTM, DSM, orthophoto) with the raw tree's: grid, then five 64-cell windows of band 1; 7 s over the 80 datasets; the recipe says to delete the COG and prod copies before re-publishing a re-stitch |
| the three page-full guards were `assert`s, stripped under `PYTHONOPTIMIZE` | `sys.exit` |
| the README named 49 datasets for numbers over the 46 fitted | "the 46 … that could be fitted" |

The gate's scope (the whole table, so an unrelated in-flight re-stitch blocks another dataset's publish until refitted) is accepted: loud, and the remedy is on the line.

**Enumeration of the chain the fields claim** (what ends the inside-a-fix pattern, `code-check.md`): an item's `alignment:` fields say "the ground of this dataset's published rasters, shifted and corrected as stated, lands on LidarBC delivery R with misfit m". The artifacts between the claim and the rasters, and what ties each pair:

| link | tie | proved red |
|---|---|---|
| table row ↔ raw cloud (`.laz`) | `cloud_points`/`cloud_date` recorded at the fit; `--check` compares the header, run first by `dataset_publish.sh` and `catalogue_release.sh` | planted +1 point stops the publish; `check_blind` mutant |
| raw cloud ↔ raw DTM | `check_dtm` at fit time: same EPSG, median within 0.1 m over 2000 ground points, else `refused:dtm_*` and no numbers | selftest (new in round 2): 0.5 m off → `dtm_cloud_disagree`, other EPSG → `dtm_crs_differs`; `dtm_tol_off`, `dtm_crs_off` mutants |
| raw DTM, DSM, orthophoto ↔ published copies (prod tree) | `--check` grid + windows (new in round 2) | selftest: a published DTM one metre off is reported; `tie_blind`, `tie_values_blind` mutants |
| published rasters ↔ items beside them | `item_create.py` builds items from the prod tree's tifs and joins the row by the path's key; refuses a dataset with no row, a fitted row that is unreadable or non-finite; mirror rebuild: fields on exactly the fitted datasets' three items, identical | 4 item mutants; `mirror_check.py` against a no-fit control |
| prod tree ↔ live catalogue | `catalogue_release.sh`: `aws s3 sync` from prod (authoritative), `stacs register`/`verify`, and the live check that an item carries `alignment:reference` iff its row is fitted | reviewer ran the embedded check in both fail directions |

Nothing sits above the table but the raw cloud, and every link down to the live item has a mechanical check that was shown to fire. What stays unchecked by design: the rasters' bytes on S3 against prod (the sync is the pipeline's, before #41), and whether the raw cloud is the right stitch for the images (`odm_qc.py`, before the fit).

Round 3 (`review-round3.md`) checked that enumeration against the code and the live trees and found it wrong twice and short one copy. The mechanism it named: each round pinned one adjacent pair of copies through a proxy chosen for cheapness, which closed the pair in front and left open the next copy and the states the proxy cannot tell apart. Its findings, all fixed:

| finding | fix | proof |
|---|---|---|
| **bug, inside round 2's fix:** the five windows were drawn over the bounding box; on a thin diagonal reach they all fall in the nodata collar and the comparison passes on zero cells. `bulkley_dickson_BR1-2021_BR2-2021` (fitted; DTM 13 894 × 22 976, 7 % valid): a copy of its raw DTM with every valid cell raised 1 m passed | windows drawn where the published copy holds data (its mask at an overview shape, centred on valid coarse cells); the valid cells compared are counted and fewer than 1000 is reported as its own line, not a pass | on that dataset: old placement 0 valid cells, new 20 480; the +1 m copy now reports 20 480 cells differ; fewest valid cells compared over all 243 published rasters 16 314; selftest fixture of a 600-cell collar around a 30-cell patch; `bbox_windows`, `floor_off` mutants |
| the COG tree (`imagery_uav_bc/<key>`, which a publish reuses when the file exists) was not in the chain: delete the prod copy but not the COG copy after a re-stitch and the stale COG reaches prod under the new row | `--check` compares the COG tree's copies with the raw tree as well (`--cog`), with its own remedy | selftest: a stale COG copy is a second line; `cog_unchecked` mutant; the real check now covers 480 pairs in 18 s |
| the row ↔ cloud tie was point count + creation date, and the date is only the processing year on ODM's files (two values over 80); ODM reclassifies the laz in place when its DEM stage is re-run, same count and date | the row records the laz size too (`cloud_bytes`, backfilled on the 80 rows with a cloud; a PDAL rewrite changes a LAZ's compressed length) | selftest: same count and date, other size → reported; `bytes_blind` mutant |
| the three `no_cloud` datasets' rasters were skipped (`continue` before the loop) while the OK line said every published raster | rasters compared before the cloud check; the OK line says what it checked | real check OK over 83 rows |

Mutants for round 3's guards (`mutants_r3.log`): eight red. Two needed a second pass: `floor_off` was green until a fixture reached the floor (copies that agree on a 25-cell patch are reported "too few to tell"), and the first `cog_unchecked` mutation was malformed and crashed instead of failing (rewritten to skip the COG entry; red on the stale COG copy).

The enumeration, corrected: the copies are raw `.laz` → raw DTM/DSM/orthophoto → COG tree → prod → S3 → API. Ties: row ↔ laz by count, date and size; laz ↔ raw DTM by `check_dtm` at fit time; raw ↔ COG tree and raw ↔ prod by grid and five data-bearing windows with a floor on the cells compared; prod ↔ items by the path-key join and its refusals; prod ↔ S3 ↔ API by the pipeline's sync, register, verify and the live presence check. Each tie reads content or an identity the producer cannot keep, and each was shown to fire on the state it separates.

Round 4 (`review-round4.md`) found that enumeration short one copy: the item JSONs are written from the table at a build and never read back, so a row changed afterwards (a re-fit without a re-stitch: a new default, a newer LidarBC delivery) leaves its items stale with every gate green until a release, and the re-stitch recipe's "publish again" cannot complete, because deleting the prod dir deletes item JSONs the collection still links (`links_check` refuses; measured on a mirror). Fixed the way the repo already treats a registry change:

| finding | fix | proof |
|---|---|---|
| table ↔ items was a build-time tie only | `--check` reads every item JSON under a dataset back against its row (`item_fields`, the join restated since `item_create.py` cannot be imported under uv): a fitted row's exact values, nothing otherwise. `dataset_publish.sh` runs it first, so a row changed since the last release holds every publish until the next one, as #38's rename does; `catalogue_release.sh` runs it after its rebuild, so the arm reads what the release wrote and a stale cloud or raster still stops it before the sync | on the real prod tree (items built before #41) it reports exactly the 46 fitted datasets; on the mirror rebuilt from the table, OK in 17 s, which also holds the restated join to what `item_create.py` writes; selftest: fields on an item whose row is not fitted, and a fitted row changed after its item was built, both reported; `items_blind` mutant |
| the re-stitch recipe said "publish again" | the recipe says release (steps 2–3 again, then `catalogue_release.sh`, as for a retraction); a re-fit is a registry change (step 1 of "Releasing a registry change"); the `--check` remedies say so; NEWS and the recipe say the first publish after #41 waits for the release, as after #38 | |
| the collar fixture's patch held 900 distinct cells, under the 1000 floor, passing only through window overlap | patch 40 × 40 (1600) | selftest |
| `cloud_date` reads as 31 December of the year before (ODM writes day 0) | said in `cloud_header`'s docstring: compared, never read as a date | |
| the two Maps Made Easy `ortho.tif` were not compared | `RASTERS` includes it | real check covers them |

The chain, final: raw `.laz` →(count, date, size)→ table row →(`check_dtm` at the fit)→ raw DTM; raw rasters →(grid + data-bearing windows, floor)→ COG tree and prod; table row →(`item_fields` read back)→ prod items; prod →(sync, `stacs verify` by digest, the live presence check)→ S3 and the API. `stacs verify` compares every published body with the API's by digest, so the live values are the prod items' and the new arm closes the last proxy. Every tie was shown to fire on the state it separates.

## Errors Encountered

| Error | Resolution |
|-------|------------|
| `--trial` crashed with `KeyError: 'model'` printing progress for a dataset with no fit (its one row is status only) | the progress line branches on `"model" in r`; `--trial` resumes, skipping datasets already in the grid |
| `open` mask refused 16 datasets as `dsm_dtm_grids_differ`: the published DSM and DTM differ by a column or a centimetre of origin, and the check was exact affine equality | each raster sampled on its own grid, no shared grid assumed; selftest writes the DSM a column wider and 1 cm west, the restored refusal goes red |
| `python3` (3.14) numpy has no `median` for the comparison scripts | `uv run --no-project --with numpy` |
| the selftest's `check_blind` mutant crashed (IndexError on a shorter drift list) instead of failing | the check filters the list instead of indexing it, so a missing drift reads as a failed check |
