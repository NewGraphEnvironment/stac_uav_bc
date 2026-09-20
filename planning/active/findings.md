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

### Deliberate deviation on the post-replacement row's stream_name

The db says the PSCIS name for 199663 is **"Tributary to Colbourne Creek"**, corroborating the correction
already queued for v1.1.0. The new post-replacement row nonetheless carries **"Tributary to Parsnip River"**
— the same pending guess as its pre-replacement sibling — because:

- v1.0.2 was scoped as additive datasets with no registry corrections; the correction is v1.1.0's test
- writing the correct name on only the new row would split the pair, leaving the before/after flights
  under two different stream names until v1.1.0

Both rows' notes name the discrepancy so v1.1.0 corrects them together.
