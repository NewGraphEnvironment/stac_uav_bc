# Code review round 1 — #35 (branch 35-adopt-stacs-for-registration-and-verific, 2b858a7...HEAD)

## Clean

No issues found that could cause failures, security problems or data loss.

What was checked, against the full current files and stacs v0.1.0's source (`cli.py`, `validate.py`,
`catalogue.py`, `register.py`, read from a scratch copy checked out at the tag):

- `item_create.py`: `collection_add` restores the self href after `add_item()`, so the collection's
  item link (a resolved Link to the object, href read at save time) and the item's self link both
  carry the tree path. Asset hrefs are absolute, so `Item.set_self_href`'s asset re-basing is a no-op.
  `set_root(collection)` removes the S3 read. `links_check` runs before writing in additive mode and
  after saving in rebuild mode; an empty link list exits. Prod `collection.json` hrefs are absolute,
  none contain `%` or spaces, so `unquote()` here and stacs' `%20`-only decode agree.
- `catalogue_release.sh`: `stacs validate` refuses empty stdin and validates `collection.json` too;
  `audit` refuses zero items and checks `--expect`; `find` failure propagates under `pipefail`; `API`
  derivation from `stacs.toml` fails under `set -e` if the file or key is missing (python3 on PATH is
  3.14, so `tomllib` is present); `${API%/collections/*}` / `${API##*/}` give base and id. The verify
  out-dir is a fresh `mktemp -d`; stacs fetches into its own temp dir, so the "fetch dir must be empty"
  rule is not at stake.
- `dataset_publish.sh`: verify failure exits non-zero under `set -e`; arrays are non-empty when
  expanded (bash 3.2 safe); drift reads the bucket's `collection.json` after the final sync.
- `stacs.sh`: `exec uvx` passes stdin through (measured in findings); flags after the subcommand
  match the v0.1.0 parser (`verify --config --out-dir`, `register --config --mode drift`,
  `audit --config --expect`, `validate` with stdin).
- `stacs.toml`: every table/key is in stacs' `CONFIG_KEYS`; `pg_port` is an int; `pypgstac` a list.
- `item_unregister.sh`: a missing toml/key fails the `CFG=$(...)` assignment under `set -e`; the
  id regex still guards the SQL heredoc.
- Docs: no remaining references to the deleted scripts outside NEWS history and planning.

Non-blocking observation (not a defect): `catalogue_release.sh` and `dataset_publish.sh` pass a
`mktemp -d` `--out-dir` to `stacs verify` but never print its path, and stacs prints at most 5 ids per
drift class to stderr. After a rename of more than one dataset, the full orphan list needed for
`item_unregister.sh` is in a directory the operator is not told about; re-running `scripts/stacs.sh
verify --out-dir <dir>` by hand recovers it.
