# Code review round 2 — #35 (branch 35-adopt-stacs-for-registration-and-verific, 2b858a7...HEAD)

## Findings

- **[severity: fragile]** scripts/dataset_publish.sh:140 — `PUBLISH COMPLETE: ${#rels[@]} dataset(s) live`
  is now printed for a dataset that produced no item. When a project's `data/sites.csv` row is
  `published=false`, `item_create.py` prints `SKIP (published=false …)`, `build_item` returns `None`,
  nothing is linked, `stacs register --mode drift` has nothing new and `stacs verify` reads IN SYNC
  (it checks only what `collection.json` links). The old tail built `jsons` from
  `find "$PROD/$rel" -name '*.json'`, so this case ended with an empty array under `set -u` and the
  script died (accidentally, but it did not report success). Now it reports the dataset live when it
  is not. The realistic path is re-running `dataset_publish.sh` on a dataset retracted per the
  retraction recipe. That also re-uploads its COGs to the public bucket (step 3 undone), but the
  re-upload predates this branch; only the success message is new. Narrow, and it is a message, not
  a write. Fix: count the item JSONs `item_create.py` wrote for `rels`, or derive "live" from the ids
  `stacs verify` saw, and fail if any `rel` has none.

Nothing else found. Checked against the full current files and stacs v0.1.0's source
(`git show v0.1.0:src/stacs/{cli,register,validate,catalogue}.py` in the scratch clone):

- `item_create.py` `collection.set_root(collection)`: pystac's `Catalog.set_root` only re-roots
  resolved child/item targets and caches self; the root href serialised for items is still the
  collection's self href (the S3 URL), so output is unchanged and the S3 read is gone (matches the
  byte-identical rebuild recorded in review-plan #2). `collection_add` restores the tree self href
  after `add_item`; asset hrefs are absolute, so the re-basing in `set_self_href` is a no-op.
- `links_check` before writing in additive mode exits (via `sys.exit`, propagated by `conda run`)
  before any item or collection write; the existing-id set still reads the basename, which is the id
  in both the old and the new layout. A collection with zero item links is refused, which is correct
  for this catalogue (245 links).
- `catalogue_release.sh` API derivation: measured `${API%/collections/*}` = `https://images.a11s.one`,
  `${API##*/}` = `imagery-uav-bc-prod`, and the `/search` body parses as JSON. A missing toml key or
  file fails the `API=$(…)` assignment under `set -e`. `find … | sort | "$STACS" validate` under
  `pipefail`: stacs validates collection.json too (`validate_dict` on every path), refuses empty
  input, and `exec uvx` passes stdin. Audit `--expect` matches how stacs counts item links.
- `"$STACS" verify … || { echo …; exit 1; }`: the left side is exempt from `set -e` only to reach
  the block, which exits 1 on both drift (rc 1) and config error (rc 2); `mktemp -d` failure aborts
  the assignment. stacs writes `missing/orphaned/changed.txt` before computing rc, so the printed
  directory holds the lists when verify fails. `register --mode drift` does not fail on orphans, so
  a rename's orphans reach the verify step and its message, as the README says.
- Rename recipe ordering is consistent with the code: unregister-before-release avoids the verify
  failure, a skipped step 2 trips the audit count, and a publish-path rename is refused by the
  additive `links_check` (the old link names a deleted file).
- `item_unregister.sh`: host/db parse rejects a single-token output; id regex still guards the SQL
  heredoc; `-d $DB` comes from the repo's own toml.
- No live reference to the deleted scripts outside NEWS history and `planning/`.
