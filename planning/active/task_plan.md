# Task: Adopt stacs for registration and verification (#35)

## Problem

`scripts/config/item_register.sh` and `collection_register.sh` are an early copy of the
registration layer now packaged as `stacs` (NewGraphEnvironment/stacs#1), and carry defects
the packaged version fixed:

- the database password is in pypgstac's argv on the STAC host
  (`--dsn "postgresql://stac:${POSTGRES_PASSWORD}@..."`), visible in `ps` there
- a fixed remote temp path (`/tmp/stac_items.ndjson`), so two runs collide
- no receiving-side line count, so a truncated transfer loads a short file and reports OK
- no check that the API serves what was sent

**Blocker found in plan-mode exploration:** every `rel: item` href in the published
`collection.json` (and every item's `self` link) is `<bucket>/<id>/<id>.json`, which S3 answers
403 (no such key); the files live at their tree path. `collection.add_item()` overwrites the self
href `build_item` sets (pystac 1.12.0 best-practice layout). stacs fetches item bodies through those
links, so this is fixed first and ships as release v1.0.4 at merge (v1.1.0 is reserved).

Decisions: pin stacs `v0.1.0` (issue; matches stac_dem_bc), run via `uvx`; host stays
`root@146.190.12.8`.

## Phase 1: Fix the item links (blocker)
- [x] `item_create.py`: keep `build_item`'s tree-path self href after `collection.add_item()`, in both rebuild and additive modes, so collection item links and item self links name the file that gets synced
- [x] Gate in `item_create.py`: after saving, every `rel: item` href in `collection.json` must map under `--s3-url` to a file that exists under `--base`; otherwise exit non-zero naming the first few broken links. This also refuses an additive run on a collection that still carries old broken links
- [x] Rebuild the prod tree in place with `--version 1.0.3` (no sync, no version change). Then check that all 245 links resolve locally, and HEAD-probe all 245 S3 tree paths for 200 (the item JSONs are already there)

## Phase 2: Pin stacs and declare the catalogue
- [x] `scripts/stacs.sh`: a pinned launcher, `exec uvx --from "git+https://github.com/NewGraphEnvironment/stacs@v0.1.0" stacs "$@"`, so the pin lives in one place; `scripts/stacs.sh --version` → `stacs 0.1.0`
- [x] `stacs.toml` at the repo root:
  - `[catalogue]`: api `https://images.a11s.one`, collection_id `imagery-uav-bc-prod`, bucket_url `https://imagery-uav-bc.s3.amazonaws.com`
  - `[assets]`: `require = "image"` (no forbid; nothing has been retired)
  - `[transport]`: host `root@146.190.12.8`, db `stac`, env_file `/opt/geoserv/.env`, workdir `/opt/geoserv/scripts`, path_prepend `/root/.local/bin`, pg `localhost:5432` as `stac`, `password_env = "POSTGRES_PASSWORD"`, `pypgstac = ["uv","run","pypgstac"]`
- [x] Prove the config is wired, not just present, on scratch copies:
  - `stacs audit` passes the prod items
  - it fails when one middle-sorted item names another collection
  - it fails when one item lacks `image`
  - a `password = "x"` line is refused
- [x] `config/item_unregister.sh` reads `host` and `db` from `stacs.toml` (python3 `tomllib`) instead of its own literals, so the delete path cannot drift from the write path

## Phase 3: Switch the callers, delete the old layer
- [x] `catalogue_release.sh`:
  - validate gate becomes `find … ! -name collection.json | scripts/stacs.sh validate`, plus a one-line pystac validation of `collection.json` (stacs validates items only), plus `stacs audit --config stacs.toml --expect <n item links>`
  - register becomes `scripts/stacs.sh register --config stacs.toml --mode drift` (collection first, then items, then read-back)
  - then `stacs verify`
  - keep the repo-specific version, `EXPECT_ITEMS` and `nge:` coverage checks
- [x] `dataset_publish.sh`:
  - item and collection registration becomes `stacs register --mode drift`
  - the per-item curl 200 loop becomes `stacs verify` (body digests, both directions)
  - drop `API` if it becomes unused
- [x] Delete `config/item_register.sh`, `config/collection_register.sh`, `scripts/item_validate.py`. Keep `item_unregister.sh` (stacs is upsert-only)
- [x] `item_create.py` header and the "register with:" hint point at `stacs`

## Phase 4: Docs
- [x] `scripts/config/README.md`:
  - release, retraction, rename and add-imagery recipes
  - the single-purpose tools list now names `scripts/stacs.sh verify|register|load`
  - a note on the link fix
- [x] `README.md` / `README.Rmd` scripts table row; `CLAUDE.md` architecture bullets (the stacs launcher, `stacs.toml`, the deleted scripts)
- [x] `NEWS.md` Unreleased entry: stacs adoption, the broken-links fix (consumer-visible for anyone walking the static catalogue), the deleted scripts. The version is left to `/gh-pr-merge`

## Phase 5: Live check (read-only)
- [x] Serve the rebuilt local `collection.json` on loopback, then run `scripts/stacs.sh verify --config stacs.toml --bucket-url http://127.0.0.1:<port>`. The fixed links fetch the real published bodies from S3, which are compared by digest with the live API. Expect IN SYNC 245/245 with the collection `same` (links are excluded from digests). Logged.
- [x] `register --mode drift` cannot run before the release: the S3 `collection.json` still carries the broken links. Record that the first live write is the v1.0.4 `catalogue_release.sh` run after merge
- [x] Findings: timings, results, what was not exercised

## Plan review fixes (review-plan.md)
- [x] `item_create.py`: `collection.set_root(collection)` (no S3 read); additive mode checks links before writing
- [x] Release gate: collection.json validated by `stacs validate` via stdin; conda one-liner dropped
- [x] `catalogue_release.sh` reads API + collection id from `stacs.toml`
- [x] `dataset_publish.sh` header: verify is catalogue-wide; rename recipe: unregister before publish/release

## Validation
- [x] Tests pass (item_create gate, stacs audit wiring, live verify)
- [ ] `/code-check` clean on each commit
- [ ] PWF checkboxes match landed work
- [ ] `/planning-archive` on completion

## After merge (outside the PR mandate)
