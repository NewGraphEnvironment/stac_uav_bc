# Progress — Versioned CSV-driven registry (#16)

## Session 2026-08-03

- Plan-mode comparison of stac_uav_bc vs stac_dem_bc script systems — convergence phases approved by user
- rtj#200 filed (OIDC role for Phase 4 CI)
- Created branch `16-versioned-csv-driven-registry-sites-csv` off main
- Scaffolded PWF baseline from issue #16 with approved phases
- Next: Phase 1 (renames + sites.csv/footprint wiring)

- Phase 1 complete: renames landed, item_create.py registry+footprint+rebuild+version, item_validate.py; full rebuild tested (224 items, 224 links, 225 valid)
- Phase 2 complete: catalogue_release.sh, NEWS.md v1.0.0 entry, sites.csv committed, recipe README registry section
- Phase 5 complete: stac_dem_bc#27 (adopt registration + versioning), soul#62 (stac-catalog convention candidate)
- Phase 3: v1.0.0 tagged + released. Live: version 1.0.0, 224 items, query ext verified (morice=42 items, MORR=45 incl. 3 cross-boundary sites, alias moose resolves), footprint geometries serving. Merge + archive pending PR.

## Archive hand-off 2026-08-05

- Phases 1-3, 5 complete; v1.0.0 merged (PR #17), issue #16 closed
- OPEN: Phase 4 (CI update.yml on stac_dem_bc pattern) — blocked on rtj#200 OIDC role; pick up there
