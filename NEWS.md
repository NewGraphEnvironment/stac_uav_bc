# stac_uav_bc

## v1.0.0 (2026-08-03)

First versioned release of the catalogue — 224 items across fraser, skeena, mackenzie, and kootenay.

- `data/sites.csv` is now the source of truth for site metadata (#16): stream names (up to three per flight), FWA watershed group codes, bcfishpass `aggregated_crossings_id`, aliases, and per-site notes. The catalogue is a reproducible build artifact: `scripts/catalogue_release.sh` rebuilds, validates, syncs, registers, and verifies in one command.
- Items carry `title` and queryable `nge:` properties (`region`, `watershed_group`, `wsg_code`, `site_id`, `stream_name`, `alias`, `project`) — filter with e.g. `rstac` on `nge:wsg_code == 'MORR'`.
- Item geometries are true valid-data footprints (`gdal_footprint`), replacing rectangular bboxes that overstated corridor flights 2-3x; report maps can now pull honest outlines via spatial search.
- Items carry flight capture datetimes (#9, since 2026-07); collection stamped with the STAC Version Extension.
- Script naming converged with stac_dem_bc (`item_create.py`, `item_validate.py`, `item_register.sh`, `collection_register.sh`, `dataset_publish.sh`, `catalogue_release.sh`).

Known imperfections shipping deliberately (fixes are v1.1.0's job and the release-system test): 11 stream names are nearest-stream guesses, two bulkley tokenizer artifacts (`Groot05 Creek`, `Rd Creek`), four crossing ids awaiting db verification — all flagged in `name_source`/`notes` columns of `data/sites.csv`.
