# #48 — Rename the collection to `stac-imagery-uav-bc`

## Outcome

The collection is `stac-imagery-uav-bc`, product first like its four siblings on the API, with
the title `UAV Imagery from British Columbia - stac-imagery-uav-bc`; item ids, the bucket, every
asset href and the `image` asset key are unchanged. The id now has one source, `stacs.toml`:
`item_create.py --rebuild` stamps it and the title into `collection.json`, from where pystac
carries them into every item's `collection` field and link titles, and both `dataset_publish.sh`
and an additive `item_create.py` refuse a prod tree that names another id. The rename shipped as
v2.0.0 with #38's field rename, #41's `alignment:` fields and eight registry corrections, in the
order the issue fixed and stac_dem_bc's #34 had used: `catalogue_release.sh 2.0.0` registered the
new collection beside the old one (stacs never deletes), both served 245 items through the
consumer sweep (thirteen PRs across the report template, seven reports, a talk repo, the
infrastructure repo and the three sibling catalogues, plus four scripts on a feature branch), and
the new `scripts/config/collection_unregister.sh` then dropped the old one: it reports before it
deletes, refuses the id `stacs.toml` names, and refuses `--yes` unless the live collection is
served and holds an item for every item id the target holds. What was learned: during the window
pgstac's one-argument `delete_item` matches a row in each collection and silently deletes
nothing, so `item_unregister.sh` now passes the collection; a count guard would pass a sibling
catalogue on the shared database, where id containment passes only the renamed one; after the
drop `/collections/<old id>` answers 404 but a `/search` naming it answers 200 with no features,
so a consumer left behind sees an empty table, not an error; and GitHub's code-search index lags
a merge by minutes, so the clone-and-grep is the proof and the search only the net. The durable
recipe is `scripts/config/README.md`, "Renaming the collection"; the titiler 2.0 route the viewer
still calls is #49.

## Measurement

Baseline 2026-10-16: `imagery-uav-bc-prod` 245 items at 1.0.4, `stacs verify` IN SYNC; the old id
sat in 246 catalogue files (the collection's title and every item's three link titles). The
offline mirror rebuild named it in 0 files and the new id in 246. Cutover 20:58Z: RELEASE
COMPLETE v2.0.0, 245 registered, both collections 245 on the API and in pgstac, one tile 200
`image/png` (693 bytes) from a new-collection item, rstac from R 245 features. The sweep: 59
GitHub code-search hits on default branches (two pages) plus a local grep, thirteen PRs merged
between 2026-10-16 and 2026-10-17 00:50Z; QGIS projects naming the id: 0 of 332 on m4, 0 of 141
on m1 (`.qgs` only there); pgstac's `searches` cache held 320 bodies naming the old id, none a
titiler mosaic (0 with `metadata`), left in place like the 988 `stac-dem-bc` rows from 2026-09.
The branch review ran three rounds (4, 5 and 2 findings; rounds 2 and 3 each inside the previous
round's fixes) and ended by enumeration: 19 guard mutants, all red. Drop 2026-10-17 00:53Z: report
245, `--yes` deleted 245, API 404; after it, the new id at 2.0.0, IN SYNC 245/245, pgstac 245
under the new id and no old row, report mode "nothing to do", tile 200, rstac 245, `/search` on
the old id 200 with 0 features. Wrong turns kept: the first `--yes` guard compared counts
(`live >= target`), which the 23-item floodplains collection showed would pass a sibling, so it
became containment, probed on the real database (245 old ids absent from the unregistered new
collection, 23 of 23 floodplains ids absent from the old); the one-argument `delete_item` was
found by reading the function off the host, not by a failing run, since its `EXCEPTION` arm
reported "not deleted (missing?)" with exit 0; and the `|| echo 000` fallback on the API probe
would have printed `000000`.

## Evidence

`planning/archive/2026-10-issue-48-rename-collection-stac-imagery-uav-bc/evidence/2026101*` (the
baseline verify, the mirror rebuild, the 2.0.0 release, the README render, the drop) and
`review-round*.md` beside them.

Closed by: PR #50 (release commit and tag v2.0.0 on main after it).
