# Findings — Rename the collection to stac-imagery-uav-bc (#48)

## Issue context

## Problem

`imagery-uav-bc-prod` is the one collection on the API outside the `stac-<product>-bc` pattern
(`stac-airphoto-bc`, `stac-elevation-bc`, `stac-floodplains-bc`, `stac-pointcloud-bc`), and #42
adds `stac-pointcloud-uav-bc` beside it. The `-prod` suffix names a stage no other collection
has. Renaming is cheap here (245 items) and has a precedent: stac_dem_bc renamed `stac-dem-bc`
to `stac-elevation-bc` on 2026-09-01 (its #34, v2.0.0, 102,460 items, no downtime).

## Decided (2026-10-16)

- **New id: `stac-imagery-uav-bc`.** Product first like its siblings, the same stem as the
  bucket (`imagery-uav-bc`) and the local trees (`imagery_uav_bc`), and it pairs with
  `stac-pointcloud-uav-bc`.
- **Unchanged:** item ids, the S3 bucket, every asset href and download link, the asset key
  `image`. The release rewrites the `collection` field of each item and the `id` of
  `collection.json`, nothing else, so the rewrite rides on a normal `catalogue_release.sh`.
- **One break, one release.** Ships in the same release as #38's field rename and #41's
  `alignment:` fields, as **v2.0.0**; v1.1.0 is not cut. Consumers absorb one break, which is
  why stac_dem_bc's #34 waited for its #31 deferrals. The NEWS entry names the old and new
  collection id beside #38's old → new field pairs.
- **Order, which is the whole design.** Register the new collection; verify it (id set equality
  in both directions, a real client query, one tile rendered from the API); then leave the old
  collection live, serving v1.0.4, until the consumer sweep below has landed; then drop it with
  a new `scripts/config/collection_unregister.sh` (pgstac `delete_collection`, driven the way
  `item_unregister.sh` drives `delete_item`), and confirm the old id 404s. pgstac keys items per
  collection, so both can serve the same 245 ids meanwhile. Never delete first: that order took
  the API to zero items once.
- **The consumer sweep**, measured 2026-10-16 (57 hits on GitHub default branches; 301 QGIS
  projects on one machine):
  - this repo: `stacs.toml`, `item_create.py`, the verify line in `item_unregister.sh`,
    `README.Rmd` (the rstac and QGIS examples; README.md and index.html re-rendered),
    `stac_create_collection.qmd`, `research/uav_pointclouds.md`.
  - the fish passage report repos (seven) and their template: one `collections =` line each,
    read by rstac at render time. Their published pages only echo the code, so nothing already
    online breaks; a re-render does until the line changes. The template first, since every
    new report starts from it.
  - two talk repos, four scripts each.
  - the sibling catalogue READMEs (stac_dem_bc, stac_floodplains_bc, stac_pointcloud_bc), which
    name it as a sister collection, and one script line in stac_floodplains_bc.
  - the website (`newgraphenvironment.github.io`, checked 2026-10-16 at 2d6e4ce): nothing outside
    its planning archives names the collection id. Its drone-imagery section links the catalogue's
    own page, the viewer, the source repo and the API host, none of which change.
  - the internal infrastructure repo: the droplet's register-all list (so a rebuild registers
    the new id), its unregister script, the endpoints doc.
  - **QGIS projects.** On this machine none of the 301 names the collection id: the 77 that
    reference the catalogue do so through the asset hrefs, which do not change. Repeat that
    count on every machine that holds projects before the drop. Any project that does name it
    is corrected by the infrastructure repo's project surgeries, not by hand.
  - registered searches in pgstac (titiler mosaics) naming the old collection: list them, and
    re-register under the new id or drop.
  - planning archives, logs and evidence dumps: history, untouched.
- **Outside readers** with the README's rstac example or a saved QGIS search are the part that
  cannot be counted. The old id 404s after the drop, and the README and NEWS carry the new one.
  QGIS layers keep working, since a layer holds the asset href; the collection has to be
  re-added in the browser.

## Scope

1. This repo: the six files above, the NEWS entry, `collection_unregister.sh` with its
   selftest, the README re-rendered.
2. The v2.0.0 release registers the new collection; verify as above.
3. The sweep: one PR per consumer repo, the template first; the QGIS count on each machine.
4. Drop the old collection; verify the 404; a GitHub code search for the old id returns only
   archives, logs and evidence, and a clone-and-grep of each consumer repo above agrees. The
   search is the net, not the proof: on 2026-10-16 it missed a default-branch file that a
   clone and grep found.

## Acceptance

- `images.a11s.one/collections/stac-imagery-uav-bc` serves 245 items, `stacs verify` in sync,
  one tile renders through the API from an item in it.
- The old id 404s, and nothing outside planning archives, logs and evidence names it.
- A report re-rendered from the template queries the new collection and gets its items.

## Plan-mode exploration (2026-10-16)

### Where the id lives, and the mechanism

- `stacs.toml` `[catalogue] collection_id` and the prod tree's `collection.json` `id` both carry
  it. `item_create.py` reads the id from `collection.json` (`:441`) and writes it into every item
  (`collection=collection.id`, `:232`). Nothing today changes the tree's id. The release checks the
  tree against the toml before the sync (`stacs audit --config` at `catalogue_release.sh:43-44`
  compares every body's `collection` with the toml id; `dataset_publish.sh:124-125` likewise), so a
  release with a stale tree fails before any upload, and cannot pass without a stamp. Decided:
  `--rebuild` stamps id and title from `stacs.toml`; additive mode and `dataset_publish.sh`
  refuse a tree that disagrees.
- The title is `"UAV Imagery from British Columbia - imagery-uav-bc-prod"` in `collection.json`
  and in each item's root, parent and collection link titles: all 246 prod files name the old id.
  Siblings keep `<description> - <id>` (live titles: `Elevation models from British Columbia -
  stac-elevation-bc`, `Point clouds from British Columbia - stac-pointcloud-bc`), so the new
  title is `"UAV Imagery from British Columbia - stac-imagery-uav-bc"`.
- pystac 1.12.0 in the titiler env (Python 3.11.11, tomllib present): setting `collection.id`
  and `collection.title` before building items puts the new id in each item's `collection` and
  the new title in all three link titles and the collection's root link (probe
  `scratchpad/pystac_title_probe.py`, 2026-10-16).

### stacs v0.1.0 on the cutover (source read at the tag)

- `register` refuses when `stacs.toml`'s id differs from the published `collection.json`
  (`register.py:391-398`); `ndjson_write` refuses an item body naming another collection
  (`:160-168`); `drift` treats an unknown collection as missing (an unknown id answers 200 with
  zero features), loads the collection first, then every missing item, then re-compares the whole
  catalogue (`:543-553`). Nothing deletes. `aws s3 sync --delete` removes only keys absent from
  the tree, and all 246 keys survive the rebuild. pgstac hydrates items against its own
  `collections` row, not S3.
- So Phases 1 to 5 cannot delete or empty the old collection. But from the cutover's sync on, S3
  holds only new-id bodies: pgstac's `imagery-uav-bc-prod` rows are the last copy, and the drop
  has no undo. The new id's recovery is `catalogue_release.sh`.
- Version window: the live collection carries 2.0.0 from the cutover while the last tag is
  v1.0.4. `catalogue_release.sh` defaults its version to the tag, so in the window the only safe
  invocation is `scripts/catalogue_release.sh 2.0.0` from the branch.

### Live state, 2026-10-16

- `/collections`: `imagery-uav-bc-prod` (title above, version 1.0.4), `stac-airphoto-bc`,
  `stac-elevation-bc`, `stac-floodplains-bc` (2.0.0), `stac-pointcloud-bc` (0.4.0). Old id serves
  245 via search; new id 404.
- pgstac 0.9.8 on the host: `delete_collection(_id text)` and `delete_item(_id, _collection)`
  exist. Items by collection: imagery-uav-bc-prod 245, stac-airphoto-bc 10,100, stac-elevation-bc
  102,460, stac-floodplains-bc 23, stac-pointcloud-bc 174,282.
- `pgstac.searches`: 3,888 rows; 320 name the old id (308 alone, 5 with another collection); 0 of
  them carry `metadata`, so none is a titiler mosaic registration. They are the API's cache of
  `/search` bodies (bbox + limit 10, QGIS browsing). 988 rows still name `stac-dem-bc`, dropped
  2026-09-01. Decided: leave them.
- titiler is 2.0.0a2 (GDAL 3.12.1): routes carry the tile matrix set.
  `/stac/WebMercatorQuad/tilejson.json?url=<API item URL>&assets=image` reads the item from the
  API; one tile at its minzoom (16/9518/20790 for
  `skeena-zymoetz-2024-8530_sandstone_mcdonell-odm_dem-dsm`) returned `200 image/png`, 693 bytes.
  `/cog/tilejson.json` (the route `scripts/viewer.html` uses) answers `{"detail":"Not Found"}`;
  `/cog/WebMercatorQuad/tilejson.json` is 200. Side finding for its own issue.

### Baseline (Phase 0)

- `scripts/stacs.sh verify --config stacs.toml` on the old id, 2026-10-16 19:50:16Z to 19:50:20Z:
  `IN SYNC: 245 published, all registered with the published body, no orphans`, collection
  `same`. Log: `planning/active/evidence/20261016_verify_baseline_old_id.log`.

### Consumers (GitHub code search, 59 hits over 2 pages, plus local grep)

| repo | files naming the old id | action |
|---|---|---|
| fish_passage_template_reporting | `0400-results.Rmd:156` | PR, first |
| fish_passage_{fraser_2023,peace_2024,skeena_2024}_reporting | `0400-results.Rmd` | PR each |
| fish_passage_{fraser_2025,peace_2025,skeena_2025}_reporting | `0740-appendix-uav-imagery.Rmd` (+ rendered `docs/app-uav.html`) | PR each; html at next render |
| restoration_wedzin_kwa_2024 (not in the issue) | `2042-Appendix-uav-imagery.Rmd:11`, `scripts/functions.R:582` (+ `docs/app-uav-imagery.html`) | PR |
| spoke, logic (private; logic outside the search index) | `talks/2026-terrace-cop/scripts/{airphoto_pair-site,uav_crop-site,uav_logjam-morice,uav_panels-compare}.R` | PR each; `_site`, `_freeze`, `logic/.../ledger.md:93` (figure provenance) untouched |
| rtj | `scripts/geoserv/stac_register-all.sh:31` (list also still has `stac-dem-bc` at `:28`), `scripts/geoserv/README.md:47-49`, `docs/stac-endpoints.md:12`, comment lines in `scripts/geoserv/stac_unregister.sh:10` and `modules/droplet/scripts/config/stac_unregister.sh:4`; logs | PR; logs untouched |
| stac_dem_bc | `README.Rmd:174`, `README.md` (origin/main; the local clone is behind) | PR |
| stac_floodplains_bc | `README.Rmd`, `README.md`, `scripts/item_unregister.sh` | PR (not cloned here) |
| stac_pointcloud_bc | `README.Rmd`, `README.md` | PR (not cloned here) |
| sred | `evidence/fy2025_2026/dumps/*/logs.csv` | evidence, untouched |
| a second template checkout on a branch (`fish_passage_template_reporting_issue-165`) | `0400-results.Rmd` | the final grep covers open template branches |

Local checkouts (2026-10-16): logic on `5-scaffold-the-terrace-cop-presentation-se` with 2 dirty
files; restoration_wedzin_kwa_2024 on `cabin-sites-source`, 1 dirty; template main, 1 dirty;
peace_2025 main, 4 dirty; the rest on main and clean. QGIS projects on this machine: 0 of 301
name the id (issue measurement).

### Precedent: stac_dem_bc #34 (archive read from its git history, a89d136)

Registered the new collection beside the old (102,460 ids in both, `3ead514`), gated the drop on
a real client query, dropped with `collection_unregister.sh --yes` after the report mode printed
the expected count. Lessons carried here: a half-done rename is invisible to set equality
(homogeneity is the property, which stacs's audit now checks); the title in both places; the
drop is irreversible once S3 holds the new bodies; print a recovery line.

### Al's `data/sites.csv` edits (saved 2026-10-16, uncommitted at branch creation)

Eight stream-name corrections: `125000_parsnip_trib_arctic` (case), `125179_missinka_trib`
("Tributary to Missinka River"), `bulkley_dickson_BR1-2021_BR2-2021` ("Bulkley River",
name_source cleared), `buck_bob_buc78` (+ "Bob Creek"), `maxan_foxy_confluence` (+ "Foxy Creek"),
`198000_mcbride_nanikafsr` (+ "McBride Lake"), `8478_mcdonell_trib` ("Tributary to McDonell
Lake"), `8525_coal_trib` ("Tributary to Coal Creek"). The spreadsheet save also upper-cased every
`published` cell, wrote LF line endings where the committed file has CRLF, and dropped the trailing
newline; all three normalised back in the Phase 0 commit (`item_create.py` lower-cases
`published` and `csv.DictReader` reads either), so the diff is the eight rows. The two `199663`
rows keep "Tributary to Parsnip River" as Al saved them.

### Plan review (one Plan agent, 2026-10-16, synchronous)

No blocker. Folded in: the audit-before-sync correction; title asserted in the selftest and
proved by the mirror grep; the toml-vs-tree pre-check in `dataset_publish.sh`; the drop script's
ssh probe, db allowlist, no-items distinction, recovery line, post-delete re-read of both counts
and the 404 check, an API-derived never-delete-first guard, a `--config` parameter for the
selftest stub; NEWS facts (title, `collection` field, both collections in the window, the static
catalogue flipping at the release date, drop date); `fig/a11sone01.png` caption; consumer fetch
before edit; rtj's stale `stac-dem-bc` line; open template branches in the final grep; the tile
check through titiler's `/stac` route; the template query measured as 245; the by-design
carve-out for NEWS and the recipe; QGIS counts recorded before the drop; no full release re-run
after the tag.

## Phase 1 and 2 measurements (2026-10-16)

- `item_create.py --selftest` PASS; with the stamp dropped (`collection.id = cid` removed) it
  fails 4 checks. A first version of the selftest let the additive refusal's `sys.exit` end the
  run before printing them: the final check is now caught and reported as a failure.
- Additive mode against the real prod tree (old id) with the new toml: REFUSED before any
  write (0 prod JSONs modified). The publish pre-check block refuses the same way.
- Mirror rebuild (`--rebuild --base <mirror> --version 2.0.0`, 245 tifs symlinked, 246 JSONs
  copied): 0 files name the old id, 246 the new; `stacs validate` 246 validated, 0 invalid;
  `stacs audit --config stacs.toml --expect 245` OK against `stac-imagery-uav-bc`. Diff against
  prod, by key: `collection` on 245 items; collection.json `id`, `title`, `version`; the root,
  parent and collection link titles on every item (hrefs identical, link order differs); the #38
  renames (`nge:*` gone, `newgraph:`, `uav:`, `fwa:`, `bcfishpass:` present); `alignment:*` on
  the fitted datasets' items (1,518 field differences); `title` on 15 items and `uav:stream_name*`
  on the rows Al corrected (the 6 `nge:alias` / `newgraph:alias` differences are the key rename on
  the moose pair, not a value change). Log: `evidence/20261016_mirror_rebuild_new_id.log`.
- `collection_unregister.sh --selftest`: 11 cases PASS; with the configured-id guard removed,
  that one case fails. Report mode on the real database: `imagery-uav-bc-prod` 245 items,
  nothing deleted; `stac-imagery-uav-bc` refused as the configured collection.

### QGIS projects, this machine (2026-10-16 20:08Z)

332 `.qgs`/`.qgz` files under `~` (Library, Trash, node_modules and `.git` pruned; `.qgz`
read through `unzip -p`): **0 name `imagery-uav-bc-prod`**. The issue's count was 301 of a
narrower tree. Other machines: Al's counts, before the drop.

## Code-check rounds (branch mode)

### Round 1 (spawned 20:05Z, delivered 20:16Z; `review-round1.md`)

Four findings, all fixed; the first was the sharpest.

- `item_unregister.sh` called `pgstac.delete_item('<id>')` with one argument. During the window
  both collections hold the same 245 ids, and the function deletes `RETURNING * INTO STRICT`
  (read off the host, pgstac 0.9.8), so two rows raise, the DO block's `EXCEPTION` arm swallows
  it, and the script prints "not deleted (missing?)" with exit 0. Every retraction and re-stitch
  recipe would have been inert until the drop. Fixed: the collection id from `stacs.toml` is
  passed, so it deletes from the live collection only.
- The `--yes` guard compared counts (`live >= target`), which a smaller sibling on the shared
  database would pass. Replaced by id containment: the number of target item ids with no item in
  the live collection must read 0. Probed on the real database: 245 of the old id's items are
  absent from the (unregistered) new collection today, and 23 of 23 floodplains items are absent
  from the old one, so the guard refuses both.
- The selftest could not see a delete that did not take (the stub answered 0/0/404 after any
  logged delete): three mutants stayed green. Added sticky stubs and four cases (unreachable API,
  unreadable containment count, rows that survive the delete, an API that still serves the
  target). Now 15 cases; five mutants (read-back, 404 check, `numeric` on the containment count,
  the configured-id guard, the containment compare) each go red on exactly one case.
- `api_status` let curl's transport failure end the script under `set -e` with no message, after
  the delete as well as before; it now prints `000` and the comparison reports it.

## Errors Encountered

| Error | Resolution |
|-------|------------|
| titiler `/cog/tilejson.json` and `/stac/tilejson.json` answer 404 | titiler 2.0.0a2 needs the tile matrix set in the path: `/stac/WebMercatorQuad/tilejson.json` |
