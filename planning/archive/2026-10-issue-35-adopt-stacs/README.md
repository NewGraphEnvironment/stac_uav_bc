## Outcome

Registration and verification moved to [`stacs`](https://github.com/NewGraphEnvironment/stacs),
pinned at `v0.1.0` through `scripts/stacs.sh` (uvx, one pin line). The catalogue is declared in
`stacs.toml`. `catalogue_release.sh` and `dataset_publish.sh` now run `stacs register --mode drift`
and `stacs verify`, and the release gate is `stacs validate` + `stacs audit --expect <link count>`.
`item_register.sh`, `collection_register.sh` and `item_validate.py` are deleted. `item_unregister.sh`
stays (stacs is upsert-only) and reads its host and db from `stacs.toml`.

Exploration found a pre-existing defect that blocked the switch. Every published item link was
`<bucket>/<id>/<id>.json`, a key S3 never held (403). pystac's `Collection.add_item()` overwrites
the item's self href with its default layout, and it also pulled the published S3
`collection.json` in as the root. `item_create.py` now keeps the tree path, roots the collection
on itself, and refuses to write a `collection.json` whose item links do not resolve under the prod
tree or link an id twice.

What was learned:
- Replacing a bespoke check with stacs' check silently narrows what gets checked. stacs sees only
  what `collection.json` links. The old checks looked at what the operator asked for, or at the
  disk. Code-check round 2 found one consequence and round 3 named the mechanism; the loop ended
  by enumerating stacs' 11 content refusals against the local gates that precede the sync.
- Two shell wrappers in this environment (`ls` adds colour codes, `diff` runs `git diff`) silently
  broke fixtures and comparisons.

## Measurement

- The prod tree, rebuilt with the fix at `--version 1.0.3`: 246 JSONs changed in `links` only, with
  0 body diffs. Rebuilt again with `set_root`, the output was byte-identical. HEAD requests for all
  245 new item hrefs on S3 returned 200.
- Read-only live verify, with the fixed `collection.json` served on loopback and bodies fetched
  from S3: **IN SYNC 245/245**, collection `same`, in 4 s. The drift dryrun found 0 to register.
- Positive control: one item body edited, then served. Result: `changed: 1`, naming exactly that id.
- Not exercised: the remote pypgstac load. The v1.0.4 release will load the collection only (links
  are outside the digest), so the first item upsert will be the next `dataset_publish.sh`, or
  `--mode ids` on one id.

## Evidence

Measurements and named commands are in `findings.md`. Reviews are in `review-*.md` in this directory.

Closed by: PR (see `git log --grep '#35'`)
