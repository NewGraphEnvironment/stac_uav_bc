# Findings — Adopt stacs for registration and verification (#35)

## Issue context

## Problem

`scripts/config/item_register.sh` and `collection_register.sh` are an early copy of the
registration layer now packaged as `stacs` (NewGraphEnvironment/stacs#1), and carry defects
the packaged version fixed:

- the database password is in pypgstac's argv on the STAC host
  (`--dsn "postgresql://stac:${POSTGRES_PASSWORD}@..."`), visible in `ps` there
- a fixed remote temp path (`/tmp/stac_items.ndjson`), so two runs collide
- no receiving-side line count, so a truncated transfer loads a short file and reports OK
- no check that the API serves what was sent

## Work

- [ ] Pin `stacs` at `v0.1.0` once that tag exists
- [ ] Commit a `stacs.toml` for this collection (catalogue, `[assets]` rules if any,
      `[transport]` with `password_env` naming the host variable)
- [ ] Register with `stacs load collection ...` then `... | stacs load items ...`, or
      `stacs register --mode drift` once the catalogue is published; then `stacs verify`
- [ ] Delete `config/item_register.sh` and `config/collection_register.sh`; keep
      `item_unregister.sh` (a delete path; stacs is upsert-only) and item creation
- [ ] `item_validate.py` (49 lines) → `stacs validate` if it only runs pystac


## Exploration (plan mode, 2026-10-09)

- stacs tags `v0.1.0` and `v0.1.1` exist; 0.1.1 is docs + doctests only. stac_dem_bc pins v0.1.0
  (stac_dem_bc#49) and is the reference adoption: `stacs.toml` at root, transport values identical
  to this repo's (`/opt/geoserv/.env`, `/opt/geoserv/scripts`, `/root/.local/bin`, user `stac`,
  `POSTGRES_PASSWORD`, `uv run pypgstac`), host `root@geopro` there vs the IP here.
- This repo has no pyproject / environment.yml; Python runs from conda `titiler` (3.11). stacs needs
  >=3.11. `uvx --from git+…@v0.1.0` gives an isolated, pinned install with no env to manage.
- `stacs validate` and `audit --dir` are non-recursive (`os.listdir`) and skip `collection.json`;
  our tree is nested, so feed paths on stdin. `item_validate.py` also validated the collection;
  stacs does not, so that one check moves inline.
- Items carry exactly one asset, `image` → `[assets] require = "image"`.

## Broken static-catalogue links (pre-existing)

Probed 2026-10-09:
- `https://imagery-uav-bc.s3.amazonaws.com/<id>/<id>.json` (the collection's item href) → **403**
- the same item at its tree path `…/fraser/cottonwood/2026/198285_pedley_lake_creek_rd/odm_dem/<id>.json` → 200
- `collection.json` → 200; live API collection `version` 1.0.3; 245 item links

Cause, reproduced in conda `titiler` (pystac 1.12.0): an item with self href
`https://b.example/r/w/2026/site/odm_dem/x.json` passed to `Collection.add_item()` comes back with
`https://b.example/x/x.json`. `build_item` sets the right href; `add_item` replaces it.
The API is unaffected (pgstac rewrites links); anything walking the static catalogue, and stacs, is.

## Phase 1 measurements (2026-10-09)

- Synthetic tree (two 64x64 tifs, scratch): additive and rebuild both write tree-path item links and
  self links; `links OK`. Bug restored (`set_self_href` dropped) → `LINKS FAILED: 2/2`, exit 1.
  Additive run on a collection carrying one stale link → `LINKS FAILED: 1/3`, exit 1, names the link.
- Prod tree rebuilt in place, `--version 1.0.3`, 40 s: `245 items from 245 tifs`, `links OK: 245`.
  Diff against a pre-rebuild copy of all 246 JSONs: **246 differ in `links` only, 0 body diffs**.
- HEAD of all 245 new item hrefs on S3: **245 × 200** (the files were always there at the tree path).
- The prod tree is now ahead of the bucket by links only; the v1.0.4 release sync publishes it.

## Phase 2 measurements (2026-10-09)

- `scripts/stacs.sh --version` → `stacs 0.1.0` (uvx, 39 packages, cached after first build).
- Over the 245 rebuilt prod items: `stacs audit --config stacs.toml --expect 245` OK
  (`require=image forbid=-`); `stacs validate` (paths on stdin) `245 item(s), 0 invalid`.
- Mutations on scratch copies, the mutated item 120th of 245 in sort order:
  `collection` changed → `FAIL: 1 item(s) name another collection`, exit 1;
  `image` renamed `data` → `FAIL: 1 item(s) lack asset 'image'`, exit 1;
  `password = "x"` in `[transport]` → `unknown key(s) in [transport]: password`, exit 2.
- `item_unregister.sh` now resolves `root@146.190.12.8` / `stac` from `stacs.toml`; with the
  toml absent it exits 1 before doing anything.

## Phase 3 measurements (2026-10-09)

- `catalogue_release.sh`'s validate + audit block, extracted and run alone against the prod tree:
  245 valid, collection valid, audit OK, exit 0.
- Same block over a JSON-only copy with one extra `old-id-odm_dem-dtm.json` (the stale file a rename
  leaves; `item_create.py --rebuild` never deletes it): `FAIL: 1 id(s) appear more than once` and
  `expected 245 item(s), audited 246`, exit 1. `--expect` = the collection's own link count is what
  turns the README's rename gotcha into a gate.
- `dataset_publish.sh` now ends `stacs register --mode drift` → `stacs verify`. Its additive
  `item_create.py` run will refuse (links gate) until the v1.0.4 rebuild has replaced the old links,
  so the release goes first.

## Phase 5 live check (read-only, 2026-10-09 14:50 UTC)

Local `collection.json` (fixed links) served on loopback from one Python process
(`scratchpad/p5/drive.py`); item bodies fetched from S3 at the fixed tree paths; API live.

| command | result | wall |
|---|---|---|
| `scripts/stacs.sh verify --config stacs.toml --bucket-url http://127.0.0.1:<port> --out-dir …` | **IN SYNC** — 245 published, 245 registered, 0 missing / 0 orphaned / 0 changed, collection `same`; 245/245 fetched | 4 s |
| `scripts/stacs.sh register --config stacs.toml --mode drift --dryrun --bucket-url …` | `to register: 0`, `would upsert 0 item(s) (collection: same)` | 4 s |
| positive control: one item link pointed at a loopback copy with `title` edited | exit 1, `changed: 1`, `changed.txt` = exactly that id | — |
| `ssh -o BatchMode=yes root@146.190.12.8 'test -f /opt/geoserv/.env && test -d /opt/geoserv/scripts'` | `host-ok` | — |
| release gate + API checks (`catalogue_release.sh` blocks, `VERSION=1.0.3 EXPECT_ITEMS=245`) | 246 valid, audit OK, `live 1.0.3`, count 245, coverage 245/245, exit 0; `VERSION=9.9.9` → `RELEASE INCOMPLETE`, exit 1 | — |

**Not exercised:** the remote load (`env_file`, `uv run pypgstac`, `STACS_LOADED`). Drift cannot write
before the release (S3 `collection.json` still has the broken links), and after it the v1.0.4 drift
loads only the collection, because links are outside the digest. The first stacs **item** upsert is
the next `dataset_publish.sh`, or `--mode ids` on one id after the release.

Loopback note: a backgrounded `python3 -m http.server` + `sleep 1` probe raced the server's start and
read as "blocked"; serving from a thread in the driving process worked first time (unsandboxed).

## Errors Encountered

| Error | Resolution |
|-------|------------|
| `S=… && … && server &` — `&` backgrounded the whole list, `$S` empty in the parent | Assign on its own line, background only the server |
| `diff -rq` printed git-diff usage — `diff` is a shell wrapper for `git diff` here | Compare in Python (or `command diff`) |
| Mutation fixture picked `\x1b[00m…json` — `ls` is a colour alias in this shell, so the mutated copies were never written and the audit passed | `command ls`; check the fixture was mutated before reading a pass |

## /code-check branch — how the loop ended (2026-10-09)

Round 1 clean (+ a usability note applied). Round 2: one defect created by this branch's own Phase 3
change (dropped curl loop → a `published=false` dataset reported PUBLISH COMPLETE), fixed b0676ed.
Round 3 named the mechanism (checks that read the catalogue's own record cannot see where it
departs from the operator's request or the disk), enumerated all six removed/replaced checks, and
found one defect at the links gate this branch added: a dataset passed twice links its id twice,
which stacs refuses only **after** the sync, permanently until a rebuild. Fixed: `existing` is
updated per created id, and `links_check` refuses an id linked more than once. Tested: `T T` → one
link; an injected duplicate link → `LINKS FAILED: 1 id(s) linked more than once`, exit 1.

Terminated by enumeration, not a further round. Every refusal stacs v0.1.0 can raise from the
**content** of the published catalogue (`grep 'raise\|failures.append'` over `catalogue.py`,
`register.py`, `validate.py` at v0.1.0; 11 sites), and what stops each one before `aws s3 sync`:

| stacs refusal | stopped before sync by |
|---|---|
| catalogue.py:40 link not `.json` | construction (`item_create` writes `<id>.json`) + `links_check` file exists |
| :70 child link | construction (pystac `add_item` only) |
| :77 / :186 / register.py:421 id or href linked twice | `links_check` repeated-id gate (new, both modes) |
| :81 no item links | `links_check` |
| :194 body not JSON | written by pystac; release also `stacs validate` |
| :197 body names another id | construction (link and file name both `item.id`); release `audit` |
| register.py:392 collection id mismatch | the file is read and re-saved, id never set; release `audit` on items |
| register.py:448 body unreadable | `links_check` (file exists → synced to that key) |
| register.py:522 audit refused | release: same `stacs audit` before sync; publish: construction (`collection=collection.id`, `asset_name="image"`) |

The rest are config, transport or API-state errors (no catalogue content reaches them).
