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

## Errors Encountered

| Error | Resolution |
|-------|------------|
