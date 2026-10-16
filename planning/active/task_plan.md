# Task: Rename the collection to stac-imagery-uav-bc (#48)

`imagery-uav-bc-prod` is the one collection on the API outside the `stac-<product>-bc` pattern
(`stac-airphoto-bc`, `stac-elevation-bc`, `stac-floodplains-bc`, `stac-pointcloud-bc`), and #42
adds `stac-pointcloud-uav-bc` beside it. The `-prod` suffix names a stage no other collection has.
Renaming is cheap here (245 items) and has a precedent: stac_dem_bc renamed `stac-dem-bc` to
`stac-elevation-bc` on 2026-09-01 (its #34, v2.0.0, 102,460 items, no downtime).

New id `stac-imagery-uav-bc`; item ids, bucket, hrefs and the `image` asset key unchanged; ships
as v2.0.0 with #38 and #41. Order: register the new collection, verify it, keep the old one live
through the consumer sweep, then drop it with a new `collection_unregister.sh`. Never delete first.

Decided with Al at the plan gate (2026-10-16): this session runs the cutover, and his saved
`data/sites.csv` edits ride in v2.0.0. The collection title follows the sibling pattern
(`UAV Imagery from British Columbia - stac-imagery-uav-bc`), one field beyond the issue's
"nothing else".

## Phase 0: Baseline, before anything moves

- [x] `scripts/stacs.sh verify --config stacs.toml --out-dir <dir>` on the old id prints
      `IN SYNC: 245` (before `stacs.toml` changes; path in `findings.md`), so "the rename lost
      items" and "already behind" stay distinguishable
- [x] Commit Al's `data/sites.csv` edits: `published` back to lower case, CRLF and the trailing
      newline restored (the file's convention; `item_create.py` reads either), leaving the eight
      stream-name corrections as the diff; `item_create.py --selftest` green
- [x] Record in `findings.md`: the live title in both places, the 320 cached searches (0 with
      metadata), the GitHub hit list, items by collection (245), the tile route measured
- [ ] File the `scripts/viewer.html` pre-2.0 titiler route as its own issue (side finding)

## Phase 1: The id has one source: `stacs.toml` → `item_create.py`

- [x] `stacs.toml`: `collection_id = "stac-imagery-uav-bc"`; header says `item_create.py` stamps it
      on `--rebuild` and refuses a tree that disagrees (no longer "change them together")
- [x] `item_create.py`: read `[catalogue] collection_id` from `stacs.toml` (tomllib); on `--rebuild`
      set `collection.id` and `collection.title` (`COLLECTION_TITLE = "UAV Imagery from British
      Columbia - {id}"`) before any item is built; additive mode refuses when the tree's
      `collection.json` id differs from the toml's, naming the release recipe; header comment
      names the new id
- [x] `dataset_publish.sh`: the same toml-vs-tree id check beside the alignment pre-check
      (`:62-69`), before the COG conversion spends its minutes
- [x] `--selftest`: the toml read, a rebuild-style stamp on a temp collection (id, title, root link
      title, an item's `collection` and link titles), the additive refusal; restore-the-bug: drop
      the stamp, selftest red (4 checks; a first version let the refusal's `sys.exit` mask them)
- [x] Offline mirror of the prod tree (symlinked tifs, copied JSONs, as #38 did):
      `--rebuild --base <mirror> --version 2.0.0`, then `grep -rl imagery-uav-bc-prod <mirror>`
      returns nothing and 246 files name the new id; items differ from prod only in `collection`,
      the three link titles (and link order), the `alignment:` fields #41 added, the #38 field
      renames and the registry fields Al's edits changed (15 titles); `stacs validate`
      246/0 invalid and `audit --config stacs.toml --expect 245` OK; prod untouched

## Phase 2: `collection_unregister.sh`, the drop path (written now, run in Phase 6)

- [x] `scripts/config/collection_unregister.sh [--config <toml>] <id>` reports (item count,
      collection row, which toml and id it read) and deletes nothing; `--yes <id>` runs
      `pgstac.delete_collection` over the same ssh/psql path as `item_unregister.sh`; host and db
      from `stacs.toml`; header states the cascade cost and that the old id has no recovery after
      the cutover (the new id's is `catalogue_release.sh`)
- [x] Guards: id and db allowlists (`[A-Za-z0-9_-]`, `[A-Za-z0-9_]`); refuses the id the toml names;
      `--yes` refuses unless `<api>/collections/<toml id>` answers 200 and every target item id has
      an item in the live collection (round 1: a count would pass a smaller sibling); ssh
      reachability probe (`BatchMode`); an unreadable count refuses, toward not deleting; an
      absent collection is "nothing to do", exit 0, and a row with no items is said as such; the
      count printed is read before asking; a curl transport failure reports `000` (round 1)
- [x] After `--yes`: re-read both counts (items 0, row 0) and curl the old id for 404, exit
      non-zero on anything else; `item_unregister.sh`'s verify line reads api and collection id from
      `stacs.toml` (no literal); it passes the collection to `delete_item` (round 1: the
      one-argument form raises on two rows during the window) and takes `--collection <id>` for
      the old copy (round 2), which the drop's refusal names beside the missing ids
- [x] `--selftest`: the three remote calls sit behind functions the selftest redefines with stubs
      (canned counts, every SQL logged, the containment query answered from its own text); 21
      cases after three review rounds; the mutation table (`findings.md`, Enumeration) has one
      mutant per guard site, 19 of them, every one red on a named case. Report mode against the
      real database: old id 245 items, nothing deleted; the configured id refused.
      `item_unregister.sh` refuses any option-shaped token as an id (round 3), measured through
      an ssh shim
- [x] `scripts/config/README.md`: the "collection deletion is server-side" gotcha names the script;
      a "Renaming the collection" recipe (register new → verify → sweep → drop; the safe
      invocation in the version window) beside the dataset-rename recipe; `CLAUDE.md`'s
      `scripts/config/` line names the script

## Phase 3: Docs, NEWS, README source (the render waits for Phase 4)

- [x] `README.Rmd`: the prose at line 75 and the three `collections =` → new id; QGIS section: a
      saved connection re-adds the collection (listed by its new title) after the rename, layers
      keep working; `fig/a11sone01.png` captioned as the pre-rename picker; the scripts table
      names `collection_unregister.sh`
- [x] `stac_create_collection.qmd:50` → new id, with a note that `--rebuild` stamps it from
      `stacs.toml`; `research/uav_pointclouds.md:102` → new id
- [x] `NEWS.md` Unreleased becomes the v2.0.0 entry (heading dated at the release): the rename
      first (old → new id and title; unchanged: item ids, bucket, hrefs, `image`; what a consumer
      changes: `collections =`, QGIS re-add, anything reading an item's `collection` field; the
      static S3 catalogue names the new id from the release date, the API serves both until the
      drop date, the old frozen at 1.0.4; the drop date filled in Phase 6), then #38's old → new
      field pairs, then the registry corrections from Al's edits (five renames: 15 items retitled;
      three second streams: 9 items), then #41's text
- [x] `/code-check branch` (three rounds: 4, 5 and 2 findings, rounds 2 and 3 each inside the
      previous round's fixes; ended by enumeration, 19 guard mutants all red); PR #50 open as
      draft with Phases 4–6 listed as pending

## Phase 4: Cutover: register the new collection, old stays live

- [x] Pre-flight: tree clean and committed; `item_create.py --selftest`,
      `dataset_align-lidarbc.py --selftest`, `collection_unregister.sh --selftest` green;
      `git fetch` and re-read `origin/main` (20:56Z)
- [x] `EXPECT_ITEMS=245 scripts/catalogue_release.sh 2.0.0` from the branch: rebuild → `--check` →
      validate + audit → sync → `stacs register --mode drift` (collection first, then 245) →
      `stacs verify` IN SYNC → version 2.0.0, 245 items, registry, field and alignment coverage OK
      (`RELEASE COMPLETE: v2.0.0`, 20:56:51Z to 20:58:24Z; `evidence/20261016_catalogue_release_2.0.0.log`)
- [x] Verify by hand, saved to `findings.md`: `/collections/stac-imagery-uav-bc` serves the new
      title and 245 via search; the old id still serves 245 at 1.0.4; pgstac items by collection
      245 + 245; an rstac query from R against the new id returns 245 features; the tile:
      `/stac/WebMercatorQuad/tilejson.json?url=<new-collection item URL>&assets=image`, then one
      tile at its minzoom, HTTP 200 `image/png`, 693 bytes
- [x] Render `README.Rmd` with `update_query = TRUE` (regenerates `data/stac_result.rds` from the
      new collection: the client gate, 245 features), then README.md and index.html; commit
- [x] Edit the issue body: the title deviation; the 320 cached searches are the API's query cache,
      not mosaics, left as the 988 `stac-dem-bc` rows were; `restoration_wedzin_kwa_2024` added
      to the sweep; the static-catalogue flip date; what `/search` answers after the drop

## Phase 5: The consumer sweep (one PR per repo; merged after Phase 4, before Phase 6)

- [x] `git fetch` every cloned consumer first; clone `stac_floodplains_bc` and `stac_pointcloud_bc`
      (branches cut from each repo's `origin/main` in scratch worktrees)
- [x] the report template repo first: `0400-results.Rmd:156` (PR #239)
- [x] Seven reports, one line each: `0400-results.Rmd` (fraser_2023 #162, peace_2024 #42,
      skeena_2024 #49), `0740-appendix-uav-imagery.Rmd` (fraser_2025 #40, peace_2025 #51,
      skeena_2025 #22); `docs/*.html` is rendered output and changes at the report's next render
- [x] `restoration_wedzin_kwa_2024` #163: `2042-Appendix-uav-imagery.Rmd:11`, `scripts/functions.R:582`
- [x] the two talk repos: the four UAV scripts of the 2026 Terrace talk; the first repo's PR #5;
      the second repo holds them only on Al's in-flight feature branch (his to change; the lines
      are the same four `collections =` / `stac_items(` literals plus three comments)
- [x] the infrastructure repo PR #398: register-all list (both the uav line and the stale
      `stac-dem-bc` line → `stac-elevation-bc`), geoserv README counts, the endpoints doc, the two
      unregister comment lines; logs untouched
- [x] Sibling READMEs: `stac_dem_bc` #65, `stac_floodplains_bc` #97 (+ `scripts/item_unregister.sh`),
      `stac_pointcloud_bc` #29, `README.Rmd`, `README.md` and the rendered `index.html` where tracked
- [x] Each PR body says the old id serves until the drop and what `/search` answers after it; no
      repo configures an R&D cross-reference; public repos get no private pointers
- [x] Gate: the template's `0400-results.Rmd` query lines run against the new id return 245
      features, equal to the old id's 245 measured before the drop
- [ ] The thirteen PRs merged (all MERGEABLE/CLEAN at 21:03Z; the auto-mode classifier refused
      `gh pr merge` as a merge without review, so Al merges them)
- [ ] QGIS count on each other machine that holds projects (hand Al the one-liner; this machine:
      0 of 301 name the id); each machine's number recorded before the drop

## Phase 6: Drop the old collection, release

- [ ] Every sweep PR merged; every machine's QGIS count recorded (non-zero → the infrastructure
      repo's project surgeries, before the drop); `gh api search/code` for the old id returns only
      archives, logs and the evidence repo's dumps plus the by-design carve-out (NEWS, the config README recipe,
      planning), and a clone-and-grep of each consumer repo, open template branches included, agrees
- [ ] `scripts/config/collection_unregister.sh imagery-uav-bc-prod` reports **245** (anything else
      means something still writes to it); then `--yes`, which prints items 0, row 0, API 404
- [ ] New id serves 245; `stacs verify` IN SYNC; `collection_unregister.sh imagery-uav-bc-prod`
      says "nothing to do"; drop date into NEWS and the issue body
- [ ] `/planning-archive` (README with Measurement and Evidence); merge; release commit on main:
      NEWS heading `## v2.0.0 (<date>)`, `git tag v2.0.0`, then `curl $API | jq .version` reads
      2.0.0 and `stacs verify` IN SYNC; close #38, #41, #48

## Validation

- [x] Selftests pass (`item_create.py`, `collection_unregister.sh`, `dataset_align-lidarbc.py`)
- [x] `/code-check` clean (once over the branch: three rounds, ended by enumeration)
- [ ] PWF checkboxes match landed work
- [ ] `/planning-archive` on completion
