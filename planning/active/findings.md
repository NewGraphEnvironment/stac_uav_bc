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

## Errors Encountered

| Error | Resolution |
|-------|------------|
