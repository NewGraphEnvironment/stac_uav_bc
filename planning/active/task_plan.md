# Task: Retraction flow: item_unregister.sh + published=false lifecycle (#18)

Build the catalog's retraction path and execute the first retraction (mis-filed nechacko kenneth copy) as a v1.0.1 patch release. Replacement (fraser/morkill) is live; Fraser 2023 report verified serving morkill URLs — zero dependents remain on the old URL.


### Phase 0 — Hand off the #16 PWF

- [x] `/planning-archive` the completed #16 PWF (issue closed; its open Phase 4 / CI workflow is tracked by rtj#200 and noted in the archived plan + progress hand-off)

### Phase 1 — `item_unregister.sh`

- [x] `scripts/config/item_unregister.sh <item-id>...` — deletes items from pgstac over SSH (`pgstac.delete_item`), sibling to `item_register.sh`; idempotent (missing id → warning, not failure)
- [x] Round-trip test on one live item: unregister → verify 404 on API → re-register via `item_register.sh` → verify 200 (proves both tools, changes nothing net)

### Phase 2 — Retract the nechacko kenneth copy (order matters)

- [x] `data/sites.csv`: flip nechacko kenneth row to `published=false`, note the retraction date + replacement path
- [x] Remove the dataset from the prod tree and the `imagery_uav_bc` COG tree (prevents stale JSONs re-syncing; raw source images under `uav_imagery/fraser/nechacko/` are left for the user to keep or delete)
- [x] `aws s3 rm --recursive` the `fraser/nechacko/2024/199256_kenneth_hwy16/` prefix (6 objects: 3 tifs + 3 item JSONs)
- [x] `item_unregister.sh` the 3 nechacko item ids
- [x] Release v1.0.1: NEWS entry, tag, `catalogue_release.sh` (rebuild drops the collection links; verify live version 1.0.1, 230 items)
- [x] Verify: 3 nechacko ids 404 via API; morkill ids still 200; S3 prefix empty

### Phase 3 — Document + close

- [x] `scripts/config/README.md`: retraction recipe (flip `published=false` → remove trees/S3 → `item_unregister.sh` → release)
- [ ] PR via `/gh-pr-push` (closes #18), merge, `/planning-archive`


## Validation

- [x] Round-trip test passes before any real deletion
- [x] /code-check clean per commit; PWF checkboxes match landed work
- [x] /planning-archive on completion
