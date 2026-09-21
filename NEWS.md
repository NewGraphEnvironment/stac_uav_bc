# stac_uav_bc

## v1.0.2 (2026-09-20)

Two new 2026 datasets, plus the catalogue's first before/after pair at one crossing (#22).

- **New:** Pedley Creek (cottonwood 2026, PSCIS 198285) — first dataset in the Cottonwood River
  watershed group (`COTR`), and the first to extend the collection bbox south
- **New:** Tributary to Parsnip River post-replacement (parsnip 2026, PSCIS 199663) — reflown
  2026-09-15 after the culvert replacement; pairs with the 2026-07-14 pre-replacement flight
- Catalogue at 236 items

**Two consumer-visible changes** — both affect existing saved queries:

- `mackenzie/parsnip/2026/1996663_parsnip_trib_chco_11000` is now
  `…/199663_parsnip_trib_chco_11000`. The old directory name carried an extra `6`; `199663` is the
  real `aggregated_crossings_id` and `1996663` does not exist in bcfishpass. **The three old item
  ids are retired and their URLs no longer resolve** — nothing external referenced them
  (checked per #18 before retracting).
- `nge:alias` on that dataset moves from `moose` to `moose pre-replacement`, and the new flight
  carries `moose post-replacement`. **A saved `rstac`/QGIS filter on `nge:alias == 'moose'` will no
  longer match.** The alias is now what distinguishes repeat flights of one site.

Also in this release:

- Item titles include the alias when a row has one: `"<stream> (<alias>) — <year> <product>"`.
  Without it, the two parsnip flights would both read "Tributary to Parsnip River — 2026 orthophoto",
  since they share a stream name and a year. Rows without an alias title exactly as before.
- Collection `extent.spatial` is now recomputed on publish and on rebuild. It never was before, and
  the advertised bbox had drifted badly: **21 items across 7 datasets already fell outside it**,
  including everything in kootenay (Parker Creek at 49.21°N, Hadow Creek at 50.74°N) and four
  mackenzie peace/pine datasets north of 55.6°N. A bbox-filtered `rstac` or QGIS search against the
  collection extent silently missed all of them. The corrected bbox spans
  `[-127.741, 49.209, -114.529, 56.078]`, up from `[-127.741, 53.830, -121.741, 55.314]`.
- `catalogue_release.sh` asserts rather than announces: optional `EXPECT_ITEMS=<n>` checks the live
  count, and every live item is checked for `nge:region` + `nge:stream_name` so a silent registry
  miss — which titles an item from its directory name — fails the release instead of shipping.
- Recipes for repeat flights and for renaming a published dataset added to `scripts/config/README.md`.
  A prefix rename on S3 must be an `aws s3 mv`; left to `sync --delete` it re-uploads the whole
  dataset (4.34 GB here) with no progress output.

## v1.0.1 (2026-08-05)

- Retraction flow: `scripts/config/item_unregister.sh` (pgstac delete over SSH, idempotent) and the `published=false` lifecycle documented in the recipe (#18)
- First retraction: mis-filed `fraser/nechacko/2024/199256_kenneth_hwy16` removed from API + S3 (Kenneth Creek is in Morkill; replacement published at `fraser/morkill/2024/199256_kenneth_hwy16`; Fraser 2023 report updated to the new URLs first)
- New datasets since v1.0.0: Peacock Creek (morice 2025), Tributary to Waterfall Creek (bulkley 2025), Kenneth Creek morkill copy — catalog at 230 items

## v1.0.0 (2026-08-03)

First versioned release of the catalogue — 224 items across fraser, skeena, mackenzie, and kootenay.

- `data/sites.csv` is now the source of truth for site metadata (#16): stream names (up to three per flight), FWA watershed group codes, bcfishpass `aggregated_crossings_id`, aliases, and per-site notes. The catalogue is a reproducible build artifact: `scripts/catalogue_release.sh` rebuilds, validates, syncs, registers, and verifies in one command.
- Items carry `title` and queryable `nge:` properties (`region`, `watershed_group`, `wsg_code`, `site_id`, `stream_name`, `alias`, `project`) — filter with e.g. `rstac` on `nge:wsg_code == 'MORR'`.
- Item geometries are true valid-data footprints (`gdal_footprint`), replacing rectangular bboxes that overstated corridor flights 2-3x; report maps can now pull honest outlines via spatial search.
- Items carry flight capture datetimes (#9, since 2026-07); collection stamped with the STAC Version Extension.
- Script naming converged with stac_dem_bc (`item_create.py`, `item_validate.py`, `item_register.sh`, `collection_register.sh`, `dataset_publish.sh`, `catalogue_release.sh`).

Known imperfections shipping deliberately (fixes are v1.1.0's job and the release-system test): 11 stream names are nearest-stream guesses, two bulkley tokenizer artifacts (`Groot05 Creek`, `Rd Creek`), four crossing ids awaiting db verification — all flagged in `name_source`/`notes` columns of `data/sites.csv`.
