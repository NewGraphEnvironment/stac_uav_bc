# Task: Process, publish and register two new 2026 flights: cottonwood/pedley and parsnip post-replacement (#22)

Two flights landed in `/Users/airvine/Projects/gis/uav_imagery` on 2026-09-20 as raw JPG sets with no ODM output. They need the full add-imagery path: registry rows -> stitch -> QC -> publish -> release.

Neither is a mechanical add. **Cottonwood is a new watershed group** — no `cottonwood` row in `data/sites.csv`, its FWA code nowhere in the registry, and `pedley` carries no crossing-id prefix. **The parsnip flight is a repeat of a published site** — the original (2026-07-14, 135 images) sits 8 m away at 55.001328, -122.758852, so this is a before/after culvert-replacement pair, both in year 2026.

Decisions are settled in the issue body (alias-in-title, fix the `1996663` typo on both sides, release as v1.0.2). Nothing here needs re-litigating.

Branch: `22-process-publish-and-register-two-new-202`

## Phase 0 — Establish registry facts (read-only; the only open unknowns)

- [ ] Resolve the Cottonwood FWA watershed group code for 53.383799, -122.555596 against fwapg/bcfishpass (`/db-newgraph`)
- [ ] Resolve `pedley`: `aggregated_crossings_id` and gazetted stream name if a crossing exists; otherwise an explicit `guess_*`/`user` `name_source` plus note, per the `wedzin_*` row pattern
- [ ] Confirm `199663` is the correct aggregated id for the parsnip crossing
- [ ] Record values and the queries used in `findings.md`

## Phase 1 — Alias in the item title

- [ ] `scripts/item_create.py:94` — when `nge:alias` is set, title becomes `"{stream} ({alias}) — {year} {product}"`
- [ ] Verify against the 3 parsnip items; confirm unaliased items are byte-identical

## Phase 2 — Correct the parsnip id (`1996663` -> `199663`)

Order matters — stale JSONs go before any sync.

- [ ] Record the dependency-gate evidence in `findings.md` (#18 requires it before retracting)
- [ ] Rename the dataset dir in all three trees: raw `uav_imagery/`, COG `imagery_uav_bc/`, prod `stac/prod/imagery_uav_bc/`
- [ ] Delete the 3 stale `...-1996663_...json` files from the renamed prod dir
- [ ] Rename the new dir to `199663_parsnip_trib_chco_11000_post_replacement`
- [ ] `data/sites.csv:17`: `item` -> `199663_parsnip_trib_chco_11000`, `alias` -> `moose pre-replacement`, note the id correction; **leave `stream_name` alone** (v1.1.0's job)
- [ ] `scripts/config/item_unregister.sh` the 3 old ids; confirm 404 via API

## Phase 3 — Registry rows for the two new flights

- [ ] `fraser,cottonwood,<WSG>,2026,pedley,...` using Phase 0 values
- [ ] `mackenzie,parsnip,PARS,2026,199663_parsnip_trib_chco_11000_post_replacement,199663,...`, alias `moose post-replacement`
- [ ] Confirm each `(region, watershed, year, item)` key matches its directory path exactly — a mismatch publishes silently wrong

## Phase 4 — Stitch

- [ ] `caffeinate -s scripts/odm_process-batch.sh <pedley> <parsnip post-replacement>` (no `--split`)
- [ ] If interrupted: resume with the identical command, never re-point the batch script at an in-flight dir

## Phase 5 — QC gate (human)

- [ ] `odm_report/stats.json` per dataset: all images reconstructed, reprojection error ~1-2 px
- [ ] Eyeball each ortho preview

## Phase 6 — Publish

- [ ] `scripts/dataset_publish.sh <pedley> <parsnip post-replacement>`
- [ ] Confirm the 6 new items return 200, and the parsnip pair's titles carry their aliases

## Phase 7 — Release v1.0.2

- [ ] `NEWS.md`: two new datasets, the parsnip id correction, the alias-in-title change
- [ ] `git tag v1.0.2`; `scripts/catalogue_release.sh`
- [ ] Verify live version `1.0.2`, 236 items, pre/post titles now differ

## Phase 8 — Document and close

- [ ] `scripts/config/README.md`: the repeat-flight convention (alias disambiguates the title)
- [ ] `/planning-archive`, then `/gh-pr-push` (closes #22)

## Validation

- [ ] `/code-check` clean on each commit
- [ ] PWF checkboxes match landed work
- [ ] Old `1996663` ids 404; new `199663` ids 200; old S3 prefix gone
- [ ] Catalogue at 236 items, live version 1.0.2
- [ ] Parsnip row `stream_name` untouched, so v1.1.0 still has its test
- [ ] `/planning-archive` on completion
