# Task: Versioned CSV-driven registry: sites.csv as source of truth, footprint geometries, CI rebuild (#16)

Item metadata lives implicitly in directory names with bbox-only geometries; no versioned source of truth or changelog. data/sites.csv becomes the source of truth, the catalog a reproducible versioned build artifact, converging script conventions with stac_dem_bc across the ecosystem.


### Phase 1 — Converge naming; wire sites.csv + footprints

- [x] Renames (git mv; update references in READMEs, CLAUDE.md, recipe):
      `stac_create_item.py`→`item_create.py` · `stac_register_item.sh`→`item_register.sh` · `stac_register_collection.sh`→`collection_register.sh` · `stac_publish.sh`→`dataset_publish.sh`
- [x] `item_create.py`: load `data/sites.csv` keyed on path parts `(region, watershed, year, item)`; skip `published=false`; stamp `title` + `nge:region`, `nge:watershed_group`, `nge:wsg_code`, `nge:site_id`, `nge:stream_name`(+`_02`/`_03`), `nge:alias`, `nge:project` (empty cells omitted)
- [x] Item geometry via `gdal_footprint -ovr 2 -simplify 10 -t_srs EPSG:4326` (proven <1 s/ortho, 54–112 vertices); `bbox` stays raster extent
- [x] `--rebuild` mode: regenerate every item JSON in the prod tree (~5 min full rebuild, no incremental complexity)
- [x] Collection version stamp: STAC Version Extension, value from latest git tag
- [x] New `item_validate.py` (adopt stac_dem_bc's explicit QA gate): pystac-validate all items, nonzero exit on failure

### Phase 2 — Release plumbing

- [ ] `catalogue_release.sh` — one command: `item_create.py --rebuild` → `item_validate.py` → `aws s3 sync` (JSONs) → `item_register.sh` (bulk upsert) → `collection_register.sh` → API verify
- [ ] `NEWS.md` v1.0.0 entry; commit `data/sites.csv`
- [ ] README + `scripts/config/README.md`: registry/release workflow, renamed script references

### Phase 3 — Release v1.0.0

- [ ] Run `catalogue_release.sh`; tag `v1.0.0`
- [ ] Verify: `rstac` filter `nge:watershed_group == 'morice'` → 12 datasets; API geometry vertex count > 5; viewer spot-check
- [ ] PR via `/gh-pr-push`, merge, `/planning-archive`

### Phase 4 — CI rebuild (blocked on rtj#200 OIDC role)

- [ ] `.github/workflows/update.yml` modeled on stac_dem_bc: push to `data/sites.csv` + `workflow_dispatch`; dataset enumeration **from sites.csv** (`published=true`); COG reads via `/vsicurl/` (headers/overviews only — no local tifs in CI); `item_validate.py` gate; `aws s3 sync`
- [ ] Registration stays a documented manual step, matching the stac_dem_bc split

### Phase 5 — Ecosystem convergence issues

- [ ] stac_dem_bc issue: adopt client-side registration scripts (`item_register.sh`/`collection_register.sh` pattern) + versioned-registry release pattern where applicable
- [ ] soul issue: capture converged stac-repo conventions (script names, registry pattern, registration split, release workflow) as a convention candidate so future stac repos start from it; note stac_airphoto_bc / stac_orthophoto_bc / floodplains for later audit against it


## Validation

- [ ] catalogue_release.sh idempotent (second run = no-op)
- [ ] /code-check clean on each commit
- [ ] PWF checkboxes match landed work
- [ ] /planning-archive on completion
