# Code review round 3 — #35 (branch 35-adopt-stacs-for-registration-and-verific, 2b858a7...HEAD)

## Mechanism

The shared assumption behind the plan-review, round-1 and round-2 findings is this: **the
catalogue's own record (`collection.json`'s item links, or the published copy on S3) stands in
for the intended state.** pystac took the published S3 `collection.json` as root instead of the
one being built. Item hrefs were whatever `add_item()` wrote rather than where the files are.
stacs `verify` reads only what the published collection links, so the old per-dataset check (what
the operator asked to publish) disappeared with the curl loop. The candidate mechanism in the brief
is right. A replacement that reads the catalogue's self-description cannot see a gap between that
description and the operator's arguments or the prod tree on disk.

It reaches five boundaries. Each is checked below:

| boundary | what now holds it | closed? |
|---|---|---|
| operator's args ↔ collection links (publish) | b0676ed: each `rel` has ≥1 link | yes for presence; see Finding 1 for the link-uniqueness side |
| prod tree on disk ↔ collection links (release) | `item_create.links_check` (links ⊆ files) + `audit --expect n_links` (count) + audit's repeated-id check | yes: subset + equal count + no repeated id = set equality |
| local prod ↔ S3 | `aws s3 sync` alone (size/mtime) | not verified, but this was true before too; see the notes at the end |
| S3 (published) ↔ API | `stacs verify`: ids both ways, bodies by digest, collection state | yes, and stronger than before |
| sites.csv ↔ live items | release registry-coverage check (unchanged) + opt-in `EXPECT_ITEMS` | unchanged by this branch |

## Enumeration (removed/replaced check → replacement → anything now passing that used to fail)

1. **`item_validate.py`** (pystac `from_dict().validate()` on `collection.json` and every
   `type: Feature` JSON under PROD; zero found means fail) → `find PROD -name '*.json' | stacs
   validate`. stacs runs `validate_dict` on every path, collection included, and refuses empty input.
   **Nothing newly passes.** The new check is stricter in two ways. It validates the body as written
   rather than pystac's upgraded re-serialisation. It also validates every `*.json`, where the old
   one silently skipped JSONs that were not STAC.
2. **`item_register.sh`** (release: every JSON on disk; publish: every JSON under each `rel`) →
   `stacs register --mode drift`, which registers from the published collection's links. Before,
   an unlinked JSON on disk was *registered*: the old-id file a rename leaves, or a retracted
   dataset's leftover. Now the release fails on it through `audit --expect`, and the publish ignores
   it (correctly). **Nothing newly passes.**
3. **`collection_register.sh`** (always upsert) → drift loads the collection when its state is not
   `same` or there are items to send. The release's live-version assertion still catches a
   collection that did not land. **Nothing newly passes.**
4. **The `dataset_publish.sh` per-item `curl $API/items/$id` = 200 loop** (ids from `find
   $PROD/$rel`) → `stacs verify` (catalogue-wide) + b0676ed (each `rel` linked).
   - An unlinked JSON under a `rel` now passes where it used to be registered and checked. Only
     stale files fall in that class, so ignoring them is correct.
   - "≥1 link per rel" is weaker than "every product linked", but I found no path that links only
     some of a dataset's products. `build_item` skips per registry row, so all three products go
     together. A `footprint` failure aborts the whole `item_create.py` run before
     `collection.json` is saved. An `already in collection` SKIP means the product is already
     linked. The old loop had the same blind spot, since it only checked JSONs that existed.
   - A retracted row whose link is still in `collection.json` (retraction step 1 done, step 5
     not) passes the check, because the additive SKIP fires before the `published` test. The old
     loop passed it too. This predates the branch.
5. **The release's own API checks** (version stamp, `EXPECT_ITEMS`, nge: coverage) are kept. `API`
   is now derived from `stacs.toml`. I measured that `${API%/collections/*}` and `${API##*/}`
   reproduce the old literals (rounds 1 and 2).
6. **`item_unregister.sh`'s hardcoded host/db** → read from `stacs.toml`. It fails loudly if the
   file or a key is missing. The id regex still guards the SQL.

b0676ed itself, measured in scratch under `/bin/bash` 3.2.57 with `set -euo pipefail`:
- The quoted heredoc is fine. The `rels` array is never empty: `$# ≥ 1`, and each loop pass
  either appends or exits. A Python exit 1 aborts the script under `set -e`.
- The substring `/{rel}/` passes `mackenzie/pine/2026/6971_pine` and fails both `…/6971_pin` and
  `…/6971_pine_x`, because of the trailing slash.
- A suffix-only rel (`pine/2026/6971_pine`) also passes. A rel cannot be one: it is always the
  full path below `$ROOT`, and the three-tif presence check rejects a directory that is not a
  dataset.
- A percent-encoded href would fail the check, which is the loud direction. The hrefs are not
  encoded in any case.

## Findings

- **[severity: fragile]** scripts/item_create.py:206 + 213, reached from scripts/dataset_publish.sh:38–75.
  Passing one dataset twice writes a duplicate item link. The second spelling can be `dir` and
  `dir/` (normalised by `${proj%/}`), or an overlapping glob plus an explicit path. `existing` is
  computed once, before the loop, and never updated. The second occurrence of each tif therefore
  rebuilds the item, and `collection_add` appends a second link with the same href.
  - Measured in conda `titiler` with pystac 1.12.0: two `add_item` calls for one id/href give two
    identical `rel: item` links. pystac does not dedupe.
  - `links_check` passes, because both links resolve. b0676ed passes too.
  - The final `aws s3 sync` then **publishes** that `collection.json`. After that, `stacs register
    --mode drift` refuses at `collection_item_links` ("links id … more than once").
  - That refusal is loud and happens before any write, but the bad `collection.json` is now both
    local and on S3. Every later `dataset_publish.sh` keeps the duplicate: additive mode never
    rewrites existing links, and `links_check` still passes. So every later publish fails at
    register until a full `--rebuild` release clears it.
  - The duplicate-link bug predates the branch. What is new is the consequence: the old flow
    registered from disk and never read links, so a duplicate was cosmetic. Now it blocks
    publishing, and it is caught only after the sync.
  - Same mechanism as above: the new gate (`links_check`) and stacs apply different predicates
    to one link list. `links_check` asks "does each link resolve"; stacs also requires "one link
    per id". Fix: add the id to `existing` after each create (or dedupe `args.tifs`), and make
    `links_check` refuse a repeated href/basename. Then the gate that runs before the sync enforces
    everything stacs enforces after it.

## Notes (not findings)

- **Local prod ↔ S3 is trusted to `aws s3 sync`.** The old flow registered from local files, so
  the API matched local and S3 could lag. The new flow registers from S3, so the API matches S3 and
  local could lag. A rebuild rewrites every JSON with a newer mtime, so sync uploads them all. The
  release's live-version assertion also catches a `collection.json` that was not uploaded. I see no
  realistic path to a stale S3 item, and S3 agreeing with the API is the better invariant for
  consumers.
- `catalogue_release.sh`'s own `/search` checks read one page at `limit: 1000` without paging.
  This predates the branch and is fine at 245 items. stacs pages correctly.
