# Task: Fit each flight to LidarBC: our UAV elevations are off by the drone's GPS altitude (#41)

Every UAV DTM and DSM in `imagery-uav-bc-prod` sits at the drone's GPS altitude. Against the LidarBC 1 m DEM, 51 ODM flights are off vertically by a median of 9 m (−107 to +97 m) and horizontally by a median of 3.5 m (up to 19 m); the published `odm_dem/dtm.tif` matches its point cloud to the centimetre, so the rasters carry the same error. No flight used ground control. A shift plus a tilt, fitted robustly to LidarBC ground, brings the misfit to a median of 0.82 m NMAD: 29 of 51 within 1 m, 12 within 0.5 m (`research/uav_pointclouds.md`, #44).

## Context

- Prod tree holds **81 published datasets** (245 items). The raw tree has an ODM cloud (`odm_georeferencing/odm_georeferenced_model.laz`) for 80; `skeena/bulkley/2025/buck_buc7` has none (it is #31's duplicate flight).
- The research run (`research/uav_pointclouds/uav_lidarbc_offsets.csv`): 51 ODM datasets fitted, none hit the ±20 m search bound, 6 have misfit > 2 m, one has < 1 M points. So the probe's model promotes as is; the script adds the gate, the table, the trials and the item join.
- Neither conda env (`titiler`, `dff`) has laspy. The probes carry PEP 723 headers and `uv` 0.12.5 is installed, so the new script runs as `uv run scripts/dataset_align-lidarbc.py`.
- The STAC Accuracy extension (v1.0.0-beta.1, Proposal) has x/y bias fields but no vertical bias, tilt or reference, which is why it was not chosen.

## Decided at the plan gate (2026-10-15)

| decision | choice |
|---|---|
| what the catalogue carries | the fitted transform as item fields; rasters untouched |
| prefix | new `alignment:`, added to `FIELD_PREFIXES`; no schema until a second catalogue writes it (crate rule) |
| flights with no LidarBC (31) | table row `no_reference`; no item fields; README says why |
| PR #44 | merged first (merge commit, no tag, no NEWS line: nothing published), then this branch off main |
| which items | all three of a dataset (ortho, DTM, DSM) carry the same fields: the flight was placed once, and the horizontal shift applies to the ortho too |
| publishing | nothing by this PR; the fields go live with the next `catalogue_release.sh`, like #38's rename |

**Fields** (model: `z_uav − z_dem(X + dx, Y + dy) = surface(X − Xc, Y − Yc)`, as the probe fits it):

| field | holds |
|---|---|
| `alignment:reference` | the LidarBC delivery the fit used, e.g. `093/093g/2024` (collection `stac-elevation-bc`) |
| `alignment:shift_x_m`, `alignment:shift_y_m` | add to the published coordinates to land on LidarBC |
| `alignment:offset_m` | the vertical correction at the dataset centre (`surface[0]`) |
| `alignment:tilt_m_per_100m` | magnitude of the tilt, for reading and filtering |
| `alignment:surface` | the fitted coefficients, per 100 m about `centre`: `[a, b, c]` (plane) or six (quadratic); `z_corrected = z − surface(x − Xc, y − Yc)` |
| `alignment:centre` | `[Xc, Yc]` in the item's `proj:` CRS |
| `alignment:misfit_m` | NMAD of the residual over the ground points compared (the plan said held-out; dropped 2026-10-16, see findings: a spatial split biased the search and a random one tests nothing at 10^5 points) |
| `alignment:points` | points compared |
| `alignment:model` | `plane` or `quadratic` (settled in Phase 2) |

Sign convention is stated once, in the README, and the NEWS entry repeats it.

## Phase 1: The script and its gate — `scripts/dataset_align-lidarbc.py`
- [x] `--selftest` first: a synthetic 1 m DEM (sloped, bumpy) and a synthetic cloud sampled from it with a known shift, offset, tilt, noise and 10% outliers; assert the fit recovers the shift within 0.25 m, the offset within 0.1 m and the tilt within 0.1 m/100 m; assert a cloud with < 2000 overlapping points, and one whose shift lies beyond the search window, are refused with no numbers written; assert the table round-trips (read-back shape = write shape). No network, no laz. Then restore each defect and confirm the gate goes red (11 guards red; also a flat site, a half-covered flight, a mask leaving too few points, `--check`)
- [x] Promote the probe (`research/uav_pointclouds/uav_lidar_align.py`) into one process over the published datasets: enumerate from the prod tree (`odm_dem/dtm.tif`), read the raw tree's laz (class 2, or all points when unclassified), find LidarBC DEM tiles by bbox from `https://images.a11s.one/search` (`stac-elevation-bc`, newest delivery year, every tile), assert the cloud's CRS is the raster's, fit as the probe does (coarse ±20 m / 1 m, fine ±1 m / 0.25 m; trim |r| > 3 NMAD, refit). Windowed `/vsicurl/` reads and a timeout on every fetch, as the probe and `sites_fill-wsg_name.py` do
- [x] `data/alignment_lidarbc.csv`: one row per published dataset, keyed `(region, watershed, year, item)` like `sites.csv`; columns `status` (`fitted` / `no_reference` / `no_cloud` / `refused:<reason>`), `reference`, `dem_ids`, `model`, `mask`, `shift_x_m`, `shift_y_m`, `offset_m`, `tilt_m_per_100m`, `surface`, `centre_x`, `centre_y`, `dz_raw_m`, `misfit_m`, `points`, `ground`, `run_date`. A refused row carries no numbers. Written by the script only (as built: `ground` dropped since only class 2 is fitted; `reference_crs`, `shift_spread_m`, `misfit_masked_m`, `coverage`, `outlier_frac`, `cloud_points`, `cloud_date` added, per the plan review)
- [x] Selection like `dataset_publish.sh`: `dataset_align-lidarbc.py [<project-dir>...]`, default every published dataset; a run merges its rows into the table by key, so a new dataset is added without refitting the rest; `--out` for trials
- [x] Run over all 83 (81 plus the two ortho-only datasets); compare the ODM rows with the research table: raw offsets identical to 0.03 m, misfits within 0.18 m, 0.79 against 0.82 m median; the shift differences and the two runs it took are in `findings.md`

## Phase 2: The two trials (scope 2)
- [ ] ~~Held-out scoring for every model: fit on a random half of the compared points, report NMAD on the other half, so the quadratic's three extra terms have to earn their keep~~ Dropped 2026-10-16 (findings): every arm is scored on every point compared instead, which is the same ground for all of them, and three extra parameters cannot overfit 10^5 points
- [ ] `--model plane|quadratic` and `--mask none|slope|slope+open` (slope: LidarBC DEM slope under a threshold, so banks where horizontal error reads as vertical misfit drop out; open: UAV DSM − DTM < 0.5 m at the point, from the dataset's own prod rasters, so ground the cameras saw under no canopy). `--trial` evaluates all six cells per dataset in one pass (load each cloud and DEM once) and writes the grid
- [ ] Run the grid over the 51 ODM datasets on LidarBC, into `research/uav_pointclouds/trials/`; a table of median, quartiles, count within 1 m and 0.5 m per cell; the winner (lowest median misfit over the same points, ties to the simpler) becomes the default; the trial table goes into `research/uav_pointclouds.md` (revised in place, Verified date updated) and the archive README's Measurement section
- [ ] Regenerate `data/alignment_lidarbc.csv` with the settled defaults; report the misfit distribution against the research figure (acceptance: median ≤ 0.82 m)

## Phase 3: Items — `scripts/item_create.py`
- [x] `--selftest` first: a `fitted` row yields exactly the `alignment:` fields above; a `no_reference` or refused row yields none; a published dataset absent from the table is refused; the prefix guard accepts `alignment:` and still refuses `nge:`. Restore each defect, gate goes red (4 mutants red; a fitted row with `nan` or `Infinity` is refused too)
- [x] `load_alignment()` beside `load_registry()`, `alignment_props(row)` beside `registry_props()`, `alignment` in `FIELD_PREFIXES`; `build_item()` adds the fields to all three items of a fitted dataset; the "no row" refusal runs with the registry checks, before the build loop (so a refusal writes nothing). `dataset_publish.sh` asks for the row before the COG conversion
- [x] `catalogue_release.sh` live check: a live item carries `alignment:reference` exactly when its dataset's row is fitted (the dataset read off the asset href; the table is the one source)
- [x] Offline verification as in #38: mirror the prod tree into the scratchpad (symlinked tifs, copied JSONs), `--rebuild --base <mirror> --version 0.0.0-test`, then `scripts/stacs.sh validate` and `audit --expect`; assert every fitted dataset's three items carry identical `alignment:` values and no other item carries any (validate 246/0, audit OK; against a control rebuild with no fitted row the builds differ only in the `alignment:` fields)

## Phase 4: Docs and release notes
- [ ] `README.Rmd`: an "Elevations" paragraph — UAV elevations are GPS-referenced (no ground control); measured against LidarBC, the vertical offset's median and range and the misfit after the fit, every number derived from `data/alignment_lidarbc.csv` at writing time; the sign convention and how to apply the fields; that flights off LidarBC carry none. The fields join the item-properties table with an rstac filter example (`alignment:misfit_m < 1`). Re-render `README.md` and `index.html` (the `build` chunk)
- [ ] `scripts/config/README.md`: recipe step 2b — `uv run scripts/dataset_align-lidarbc.py <project-dir>` after QC and before `dataset_publish.sh` (`item_create.py` refuses a published dataset with no row); registry section names the table. `CLAUDE.md` script list line
- [ ] `NEWS.md`: an entry for the release that will carry the fields, naming each, the sign convention, and that nothing changes until that release
- [ ] Edit the #41 body to the decided field list and decisions (bodies get edited, not appended)

## Validation
- [ ] `uv run scripts/dataset_align-lidarbc.py --selftest` and `conda run -n titiler python scripts/item_create.py --selftest` pass, and fail with each guard's defect restored
- [ ] `/code-check` clean (once over the branch with `/code-check branch`)
- [ ] PWF checkboxes match landed work
- [ ] `/planning-archive` on completion; the archive README carries Measurement (misfit distribution, trial grid) and Evidence (`research/uav_pointclouds/trials/`, `data/alignment_lidarbc.csv`)

## Verification, end to end

1. Both selftests green, and red with each defect restored (listed per guard in `findings.md`).
2. The production table: 81 rows; `fitted` count ≥ 51 (every research dataset) and the ODM rows agree with the research table.
3. Trial grid table in the research doc; the default is the measured winner.
4. Mirror rebuild validates and audits clean; field coverage asserted by script over the mirror.
5. Live checks run only at the next release (not in this PR).
