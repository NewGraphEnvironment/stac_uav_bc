# Code-check round 1 — #48 collection rename (branch `48-rename-the-collection-to-stac-imagery-ua` vs origin/main, three-dot)

Reviewed: the full diff plus the full contents of every changed file, `scripts/catalogue_release.sh`
for context, the stacs v0.1.0 source under the scratchpad, and the checklist (code-check.md,
code-check-shell.md, code-check-python.md in full; code-check-r.md and code-check-spatial.md by
heading, since the diff carries no R or spatial code: the README.Rmd chunks changed only a string
literal). Probes ran on copies under the scratchpad, never on the checkout; pgstac's behaviour was
read from the v0.9.8 migration SQL fetched from upstream (`pgstac.0.9.8.sql`, lines cited below).

## Findings

- **[fragile]** `scripts/config/item_unregister.sh:37` (`PERFORM pgstac.delete_item('$id');`) —
  from the cutover until the drop, the window this branch designs, both collections serve the same
  245 item ids (legal: `items` is `PARTITION BY LIST (collection)` with no global unique on `id`,
  pgstac.0.9.8.sql:2033-2043). pgstac 0.9.8's `delete_item(_id text, _collection text DEFAULT NULL)`
  runs `DELETE FROM items WHERE id = _id AND (_collection IS NULL OR collection=_collection)
  RETURNING * INTO STRICT out` (lines 2324-2330). Called with one argument it matches two rows,
  `STRICT` raises `TOO_MANY_ROWS`, the DO block's `EXCEPTION WHEN OTHERS` swallows it (and the
  subtransaction rolls the delete back), and the script prints `not deleted (missing?)` — the wrong
  reason — and exits 0. So every retraction, re-stitch and dataset rename in
  `scripts/config/README.md` is inert during the window, and nothing in NEWS or the recipe says to
  wait; the only later signal is the release's `stacs verify` reporting the id orphaned, far from the
  cause. The branch already reads `CID` from `stacs.toml` into this script for the verify line: pass
  it, `PERFORM pgstac.delete_item('$id', '$CID');`, which is correct before, during and after the
  window (the old collection is frozen and goes with the drop, so its copy need not be touched).

- **[fragile]** `scripts/config/collection_unregister.sh:118-126` (the `--yes` guard) — the
  "never delete first" check compares item counts (`LIVE_COUNT -ge COUNT`) and the only id the
  script refuses by name is the toml's. The database it runs against serves five collections
  (`findings.md`: airphoto 10,100, elevation 102,460, floodplains 23, pointcloud 174,282), and
  `--yes stac-floodplains-bc` passes every guard: 245 >= 23, the live id answers 200, the id is
  well-formed. The guard's stated property — the live collection holds what the one about to go holds
  — is id containment, which separates the old id (245 of 245 ids present in the live collection)
  from every sibling catalogue (0 of N); the count is a proxy for it (code-check.md, "A proxy is not
  the property"). One query replaces the compare: the number of target ids absent from the live
  collection, which must read 0,
  `select count(*) from pgstac.items t where t.collection = '<target>' and not exists (select 1 from
  pgstac.items l where l.collection = '<live>' and l.id = t.id);` (through `numeric`, so an
  unreadable answer still refuses), plus a branch for it in the selftest's `pg_query` stub. The
  stac_dem_bc precedent (`scripts/collection_unregister.sh` there) had no such guard at all, so this
  is a tightening of a new guard, not a regression — reported because the refusal text claims the
  property and the check tests a stand-in, on the one script that destroys a collection on a shared
  production database.

- **[fragile]** `scripts/config/collection_unregister.sh:146-225` (`--selftest`) — three of the
  guards the header advertises are not exercised, measured by restoring each defect in a copy and
  running the selftest (code-check.md, "Restore the bug and prove the guard fires"):

  | mutation (copy under the scratchpad) | selftest |
  |---|---|
  | configured-id guard removed | red, 1 case (as `findings.md` says) |
  | live-status (`= 200`) guard removed | red, 1 case |
  | live-count (`-ge`) guard removed | red, 1 case |
  | post-delete read-back `if [ "$AFTER_ITEMS" != "0" ] \|\| [ "$AFTER_ROWS" != "0" ]` → `if false` | **green, 11 ok** |
  | post-delete API check `if [ "$STATUS" != "404" ]` → `if false` | **green, 11 ok** |
  | `numeric` dropped from `LIVE_COUNT` | **green, 11 ok** (it still refuses, by `[`'s exit 2, under a message reading "holds  item(s)") |

  The stub answers 0 / 0 / 404 after any `delete_collection` it has logged, so no case can see a
  delete that did not take. Add a case whose stubs keep answering 245 / 1 / 200 after the delete
  statement, expecting rc 1, `still reads items=245` and `deletes=1`; and one where the live count
  answers text under `--yes`, expecting `could not read`.

- **[fragile]** `scripts/config/collection_unregister.sh:50,121,137` (`api_status`) — `curl -s -o
  /dev/null -w '%{http_code}'` prints `000` and exits non-zero on a transport failure (DNS, the 30 s
  `--max-time`), and `LIVE_STATUS=$(api_status …)` / `STATUS=$(api_status …)` are plain assignments,
  so `set -e` ends the script on that exit with no message. Before the delete that is a silent
  refusal (safe direction, but the operator sees nothing). After the delete it exits between
  `deleting …` and `OK — deleted …`, so the one irreversible step gets no confirmation and no recovery
  line, and a re-run reports "nothing to do". `api_status() { curl … || echo 000; }` keeps the
  comparison and its message on both paths (the 404 arm then reports `HTTP 000, not 404`).

## Checked, no issue

- `scripts/item_create.py`: `--selftest` green in the titiler env; the stamp with `collection.id =
  cid` dropped fails 4 checks and with both lines dropped fails 6 (copies), matching
  `findings.md`. `set_root()` replaces the file's root link with a title-less `Link.root`, so the
  stamped title reaches the collection's root link and every item link title (pystac falls back to
  the target's title; the mirror rebuild's 0 old-id files confirm it). The additive refusal runs
  before `links_check` and before any write; `--rebuild` never consults the tree's id, by design.
- `scripts/dataset_publish.sh:51-60`: quoted heredoc, `sys.exit(msg)` is exit 1 under `set -e`,
  sits after `--check` and before the COG step as the comment says.
- stacs v0.1.0 scopes every `/search` to `collections: [<toml id>]` (`verify.py:100-131,
  149-180`) and `register --mode drift` loads a 404 collection first and re-compares the whole
  catalogue when the collection state is not `same` (`register.py:535-560`), so the old collection's
  rows are never orphans to `verify`, and the release's `n_items` check reads the new id only.
- pgstac 0.9.8 `delete_collection(_id)` is `DELETE FROM collections … RETURNING * INTO STRICT`
  (line 905-911) and `items_collections_fk` is `ON DELETE CASCADE DEFERRABLE` (line 2050), so the
  header's cascade claim and the read-back's `items 0, row 0` expectation hold.
- `collection_unregister.sh` parses under `/bin/bash` 3.2.57 and its selftest passes there; one
  `trap … EXIT`, `mktemp` with six X's, allowlists before any SQL interpolation, `|| true` on the
  count substitutions with `numeric` behind them, `${1:-}` under `set -u`.
- `data/sites.csv`: the eight rows match NEWS; each of the eight datasets has 3 tifs and 3 item
  JSONs in the prod tree, so "15 items" and "9 items" are right; CRLF kept (accepted).
- `item_unregister.sh`: `read -r HOST DB API CID` with four space-free tokens; a failed python under
  `set -e` ends the script before the usage line.
- `python3` on this machine's PATH is 3.14.7 and `/usr/bin/python3` is 3.9.6 (no `tomllib`); the
  new blocks inherit the repo's existing dependence on a PATH python3 >= 3.11 (`item_unregister.sh`,
  `catalogue_release.sh` already do), and `collection_unregister.sh` refuses cleanly on the import
  error. Not flagged.
- No secrets in the diff; `stacs.toml` carries none; the host IP was already committed.
