# Findings — Process, publish and register two new 2026 flights (#22)

## The flights

| | `fraser/cottonwood/2026/pedley` | `mackenzie/parsnip/2026/1996663_parsnip_trib_chco_11000_post_replacement` |
|---|---|---|
| Images | 33 JPG | 84 JPG |
| Size | 1.3 GB | 3.6 GB |
| Flown | 2026-09-13 | 2026-09-15 |
| First-image GPS | 53.383799, -122.555596 | 55.001370, -122.758782 |
| ODM output | none at start | none at start |

GPS read from EXIF via PIL (`GPSLatitude`/`GPSLongitude`, converted from DMS).

## The parsnip flight is a repeat of a published site

The existing registry row (`data/sites.csv:17`) is the same crossing:

```
mackenzie,parsnip,PARS,2026,1996663_parsnip_trib_chco_11000,199663,Tributary to Parsnip River,,,moose,,true,guess_nearest_353m,...
```

Original flight: 2026-07-14, 135 images, first-image GPS 55.001328, -122.758852 — **8 m** from the new flight. Before/after culvert replacement pair, both in year 2026.

## Pipeline mechanics established by reading the code

- `scripts/item_create.py:86` — `row = registry.get(parts[:4])`. On a **miss** `row` is `None`, `props` is `{}`, and `stream` falls back to `parts[3]` (the directory name). No error, no warning. Publishing before the registry row lands produces an item that looks fine and is wrong. Registry rows must be committed first, with keys matching directory paths exactly.
- `scripts/item_create.py:94` — `props["title"] = f"{stream} — {parts[2]} {product}"`. Alias is not in the title, so the pre/post pair would both read "Tributary to Parsnip River — 2026 orthophoto".
- `scripts/item_create.py:145` — `--rebuild` walks the **prod tree** (`base.rglob("*.tif")`, skipping `*.original.tif`) and writes `<item.id>.json` beside each tif. It never removes JSONs whose id no longer matches, so a renamed directory strands stale old-id JSONs, which then sync to S3.
- `scripts/dataset_publish.sh:91` and `scripts/catalogue_release.sh:28` — both end in `aws s3 sync "$PROD" "$BUCKET" --delete`. The prod tree is authoritative for the bucket, so a prod-side rename cleans the old S3 prefix automatically. `item_unregister.sh` is still required: pgstac registration is not driven by the sync.
- Item id format: `<region>-<watershed>-<year>-<item>-<subdir>-<stem>`, e.g. `mackenzie-parsnip-2026-1996663_parsnip_trib_chco_11000-odm_dem-dsm`.
- Exactly **one** registry row carries an alias today (row 17, `moose`), so the alias-in-title change has a 3-item blast radius.
- Catalogue at 230 items; this work adds 6 (3 products x 2 datasets) -> 236.

## Retraction dependency gate (#18 requires this before retracting)

`grep -rl "1996663\|parsnip_trib_chco"` across `~/Projects/repo`, restricted to `*.Rmd|*.md|*.qmd|*.R|*.json|*.csv`:

- `stac_uav_bc/scripts/odm_process.R`, `stac_uav_bc/data/sites.csv` — this repo
- `fissr_explore/data/fiss_density_pts_channel_width.csv`
- `water-temp-bc/data/eccc/.../ts2_08FF001_20221216T150334.csv`
- `bc_climate_anomaly/ecoprovince_average_anomaly/...csv`

The three out-of-repo hits are coincidental matches of the digit string `1996663` inside unrelated numeric CSV data, not URL references. **No external dependents — clear to retract.**

## ODM runtime expectation

`benchmark.txt` from the original 135-image parsnip flight totals ~3365 s (~56 min): mvs_texturing 1119 s, openmvs 613 s, opensfm 548 s, odm_dem 547 s, the rest minor. The new flights are 33 and 84 images, so both together should land well under an hour. `--split` (the 10+ hour path) does not apply below ~300 images.

ODM also writes `*.original.tif` beside each output (~5 GB extra per flight); `item_create.py` skips them.

## Phase 0 — registry facts (resolved 2026-09-20)

Queried against the local `fwapg` Docker DB (`fresh-db`, port 5432) — no SSH tunnel needed, since
`whse_basemapping.fwa_watershed_groups_poly` and `fresh.crossings_vw_bcfp` are both present locally.

**Watershed groups** — point-in-polygon on `fwa_watershed_groups_poly`:

| site | code | name |
|---|---|---|
| pedley (53.383799, -122.555596) | **COTR** | Cottonwood River |
| parsnip post (55.001370, -122.758782) | **PARS** | Parsnip River |

**Crossings** — nearest on `fresh.crossings_vw_bcfp`:

| site | aggregated_crossings_id | source | stream | road | dist |
|---|---|---|---|---|---|
| pedley | **198285** | PSCIS | Pedley Creek (gnis + pscis agree) | Lake Creek Rd | 9.6 m |
| parsnip post | **199663** | PSCIS | Tributary to Colbourne Creek | Chco 11000 FSR | 77.1 m |

So `pedley` gets `name_source=pscis` with a real gazetted name — no guess needed.

**The `1996663` typo is confirmed.** Filtering `aggregated_crossings_id IN ('199663','1996663','198285')`
returns only `199663` and `198285`; `1996663` does not exist in the crossings table.

## Plan-agent review — three blockers, all confirmed and fixed

### B1 — the plan's ODM resume instruction would have destroyed an in-flight run

`odm_process-batch.sh:35` skips a project only when `odm_orthophoto/` exists, and that directory is
written near the *end* of a run. An interrupted run therefore falls through to the `rm -rf
"$proj"/opensfm "$proj"/odm_* …` at `:41`, wiping exactly the state being resumed — the CLAUDE.md
footgun verbatim. The original bullet said "resume with the identical command", and the identical
command *is* the batch script. Worse: both dirs run in one invocation, so a second batch call aimed
at the parsnip dir would have wiped pedley mid-flight. Fixed to spell out the `docker run` form.

### B2 — a silent 4.34 GB re-upload, avoided

`aws s3 sync` has no rename detection; it compares keys. With the prod dir renamed, the sync at
`dataset_publish.sh:91` would have deleted the three old-prefix TIFs and re-uploaded them from local —
956 MB + 1.22 GB + 2.16 GB = **4.34 GB** over the home link, under `--only-show-errors`, so with no
progress output at all. Verified against the live bucket before acting.

Fixed with a server-side move before any sync:

```
aws s3 mv --recursive --profile airvine \
  s3://imagery-uav-bc/mackenzie/parsnip/2026/1996663_parsnip_trib_chco_11000/ \
  s3://imagery-uav-bc/mackenzie/parsnip/2026/199663_parsnip_trib_chco_11000/
```

Ran at ~1.5 GiB/s in-region. Old prefix now empty; all 6 objects at the new prefix. The three stale
old-id JSONs came across with the move and will be removed by the later `sync --delete`, since they
no longer exist locally.

**Generalisable:** the README's renaming recipe now carries this — a prefix rename on S3 must be an
`aws s3 mv`, never left to `sync` to reconcile.

### B3 — the retraction was sequenced backwards against the #18 precedent

The unregister sat in Phase 2, but the renamed dataset is only re-registered by `catalogue_release.sh`
in Phase 7 — behind an unbounded human QC gate. That would have taken the pre-replacement site dark
for the whole interval. #18 deliberately did the reverse (publish the replacement, *then* retract,
minutes apart). Moved the unregister to sit immediately after the release.

### Deliberate deviation on the post-replacement row's stream_name

The db says the PSCIS name for 199663 is **"Tributary to Colbourne Creek"**, corroborating the correction
already queued for v1.1.0. The new post-replacement row nonetheless carries **"Tributary to Parsnip River"**
— the same pending guess as its pre-replacement sibling — because:

- v1.0.2 was scoped as additive datasets with no registry corrections; the correction is v1.1.0's test
- writing the correct name on only the new row would split the pair, leaving the before/after flights
  under two different stream names until v1.1.0

Both rows' notes name the discrepancy so v1.1.0 corrects them together.

## The spatial-extent bug was pre-existing and much larger than pedley

The review framed G1 as "pedley would fall outside the advertised bbox". Measuring against the prod
tree showed **21 items across 7 datasets already outside it** before pedley existed:

```
old bbox: [-127.741, 53.830, -121.741, 55.314]
new bbox: [-127.741, 49.209, -114.529, 56.078]

kootenay-elk-2021-parker                              @ 49.209 N, -114.552
kootenay-upper_arrow_lake-2024-arrow                  @ 50.742 N, -117.800
mackenzie-pine-2026-6971_pine_oxbox_hwy97S            @ 55.605 N
mackenzie-peace_arm-2026-16701333_carbon_trib…        @ 55.909 N
mackenzie-upper_peace-2026-23502870_track_ck…         @ 55.970 N
mackenzie-peace_arm-2026-16701523_table_ck…           @ 56.060 N
fraser-cottonwood-2026-198285_pedley_lake_creek_rd    @ 53.383 N   (the new one)
```

Every kootenay dataset in the catalogue was unreachable by a bbox-filtered search against the
collection extent, and had been since it was published. Pedley was simply the first case anyone was
going to trip over. Fixed for all of them by the same change.

## Release arithmetic — why EXPECT_ITEMS could not be used on this run

Live count read 236 immediately after publish, which *looks* like the target but was 233 real items
plus the 3 stale `1996663` registrations, with the 3 renamed ids not yet created. The release rebuild
took it to 239; only the unregister brought it to a correct 236. Asserting 236 during the release
would have failed on the right number at the wrong moment. The `nge:` coverage guard ran instead
(239/239), and 236 was asserted after the unregister.
