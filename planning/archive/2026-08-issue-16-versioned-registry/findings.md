# Findings — Versioned CSV-driven registry (#16)

## Issue context

## Problem

Item metadata (stream names, watershed groups, site ids, footprints) currently lives implicitly in directory names and rectangular bboxes. There is no versioned source of truth, no changelog, and updates require local knowledge of the pipeline.

## Design: versioned, CSV-driven registry

**`data/sites.csv` is the source of truth; the STAC catalog is a build artifact.** The build is a pure function of (sites.csv, COGs on S3):

1. Item properties from sites.csv: `title`, `nge:region`, `nge:watershed_group`, `nge:wsg_code`, `nge:site_id`, `nge:stream_name` (+ `_02`/`_03`), `nge:alias`, `nge:project`
2. Item geometry from `gdal_footprint` on the COG (true data outline; current geometries are 5-vertex bboxes that overstate corridor flights 2-3x) — bbox stays as the standard bbox field
3. Full rebuild every release (~5 min for 224 items; no incremental complexity), idempotent end to end
4. Version stamping: STAC Version Extension `version` property on the collection, sourced from the git tag; release notes in `NEWS.md`; tags per release (fits the existing gh-pr-merge release bookkeeping)

Workflow per release: edit sites.csv → PR/commit → rebuild → NEWS entry + tag → register.

## Automation: adopt the stac_dem_bc pattern

`stac_dem_bc/.github/workflows/update.yml` is the established system: GitHub-hosted runner, AWS auth via OIDC role (provisioned in rtj, trust scoped to main), items built in CI reading COGs remotely (`/vsicurl/` — footprints and datetime tags read only headers/overviews), pystac validation as a gate, sync to S3, caches committed back to main. pgstac registration remains a separate server-side step there, and the same split applies here.

Phasing:

- **Phase 1 (now, local):** wire sites.csv + footprints into `scripts/stac_create_item.py`, backfill all items, adopt NEWS.md + version stamp + first tag. Blocked on: sites.csv review, crossing-id verification (tunnel), footprint approval.
- **Phase 2 (CI):** `update.yml` triggered on push to `data/sites.csv` + `workflow_dispatch`, using a `role_gha_stac_uav_bc` OIDC role (rtj issue to follow, modeled on rtj#184). Registration stays a one-command manual step (`scripts/config/stac_register_item.sh`).
- **Phase 3 (optional):** server-side re-registration on change (e.g. geoserv cron checking the collection etag) — infrastructure repo territory; only worth it if manual registration proves a bottleneck.

## Acceptance

- Editing a stream name in sites.csv and cutting a release updates the live catalog with a traceable version, in one command (Phase 1) or automatically on merge (Phase 2)
- `rstac` can filter by `nge:watershed_group` / `nge:wsg_code` / `nge:site_id`
- Item geometries are true footprints; report maps can pull outlines via spatial search

