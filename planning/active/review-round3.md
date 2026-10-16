# Code-check round 3 — #48 collection rename (branch `48-rename-the-collection-to-stac-imagery-ua` at 981003e vs origin/main, three-dot)

Reviewed: the full diff and the full contents of every changed file, `scripts/catalogue_release.sh`
for context, and the checklist in full (code-check.md, code-check-shell.md, code-check-python.md;
code-check-r.md and code-check-spatial.md by heading, since the diff carries no R or spatial code:
the README.Rmd chunk edits are string literals). The prompt's copies of the four scripts were
compared byte for byte with the checkout (`/usr/bin/diff`; the shell's `diff` is a function wrapping
`git diff`). Every probe ran on copies under the scratchpad (`probe3/`); the two live checks were
read-only `curl`s. Measured 2026-10-16 20:41–20:55Z, `/bin/bash` 3.2.57, python3 3.14.7, curl 8.7.1.

## The mechanism behind rounds 1 and 2

Every defect the two rounds found was a guard, a stub or a message **keyed on a surrogate for the
state it was supposed to decide on**, picked because it was what the author had to hand, and the
surrogate agrees with the property on every input the steady state produces and parts company on
exactly the state the script exists for:

| defect | surrogate | property | where they part |
|---|---|---|---|
| `delete_item('<id>')` | the item id identifies the row | (id, collection) does | two collections holding the same ids: the window |
| `--yes` count guard | `live >= target` | every target id has an item in live | a smaller sibling catalogue |
| stub 0/0/404 after any delete | "a `delete_collection` line is in the log" | the delete took | a delete that did not take |
| stub `*"not exists"*` | "the SQL contains `not exists`" | the containment runs target → live | a swapped call |
| `api_status` under `set -e` | curl's exit | curl's printed code | a transport failure |
| `\|\| echo 000` | "non-zero exit means nothing printed" | curl prints `000` and exits non-zero | the same failure |
| selftest verdict | the shell's exit status | the PASS/FAIL line | bash 3.2's armed EXIT trap |
| the two round-1 fixes | each modelled the window alone | the window with both in it | a retraction during the window |

In the checklist's words: "A proxy is not the property", and the reason the selftest kept
certifying each one is "A fixture that cannot reach the failure mode": **the stub answers from the
request's text** (which SQL substring, which URL suffix, whether a delete was logged) **rather than
from a modelled database state**, so any guard whose correctness depends on a state the stub never
models can be deleted with the suite green. That is the test that terminates this class: enumerate
every state a guard reads and ask whether the stub can produce the state in which the guard is the
only thing standing between the operator and the delete. The enumeration is below; it found one
such guard (finding 2) and one sibling of round 1's first finding on the other script (finding 1).

## Findings

- **[fragile]** `scripts/config/item_unregister.sh:31,44` — `--collection` is recognised only as
  the first argument, and the item-id allowlist `[A-Za-z0-9_-]` admits option-shaped tokens, so a
  misplaced or misspelt flag is silently an item id and the real ids are deleted **from the live
  collection**. Measured through an `ssh` shim (nothing left the machine):
  `item_unregister.sh id1 --collection imagery-uav-bc-prod` sends
  `delete_item('id1', 'stac-imagery-uav-bc')`, `delete_item('--collection', …)`,
  `delete_item('imagery-uav-bc-prod', …)`, prints `unregistering 3 item(s) from collection
  stac-imagery-uav-bc` and exits 0; the two phantom ids come back as psql `not deleted (missing?)`
  warnings, which is the script's documented idempotent path. The operation this branch created the
  flag for is the one that meets it: `collection_unregister.sh`'s refusal tells the operator to run
  `item_unregister.sh --collection <old-id> <item-id>...` to clear a retracted id from the old
  collection, so the ids in hand are ones that may still be live (a retraction whose first
  `item_unregister.sh` run was skipped, or any id typed from the refusal's list by mistake), and a
  one-character slip (`--colection`, measured: accepted as an item id) deletes them from the live
  collection with exit 0 and the drop still refused. `collection_unregister.sh` already refuses
  `-*` in its own argument loop (measured: `--yes -bad` prints usage); this script does not. Remedy,
  one line beside the existing case: refuse any id beginning with `-` (`-*) usage`), or parse
  `--collection` anywhere in the argument list. Same shape as round 1's first finding — the
  identity the SQL is given is narrower than the operator's intent — on the sibling script.

- **[fragile]** `scripts/config/collection_unregister.sh:109` with the selftest at `:201-215,
  237-253` — the `numeric` guard on the collection-row count is the one guard in `main` whose
  deletion leaves the selftest green, and it is load-bearing for `--yes`. Mutation table, each mutant
  a fresh copy with one edit (asserted to match once), run under `/bin/bash --selftest`:

  | mutant | selftest |
  |---|---|
  | `numeric` on `ROWS` dropped (line 109) | **green, 16 ok** |
  | `ssh_probe \|\| refuse` dropped (line 105) | green, 16 ok (benign, see below) |
  | unbound `$NEVER_SET_VAR` inside `selftest()` | red: `ended before its verdict`, rc 1 (round 2's fix holds on 3.2) |
  | `count_missing` arguments swapped | red, 3 cases |
  | `[ "$MISSING" -ne 0 ]` → `-lt 0` | red, 1 |
  | configured-id refusal dropped | red, 1 |
  | post-delete read-back `if false` | red, 1 |
  | post-delete 404 check `if false` | red, 1 |
  | `numeric` on `COUNT` dropped | red, 1 |
  | `numeric` on `MISSING` dropped | red, 1 |
  | live-status `= 200` refusal dropped | red, 2 |
  | the delete statement replaced by `:` | red, 4 |
  | items-with-no-row refusal dropped | red, 1 |
  | db allowlist dropped | red, 1 |
  | target allowlist dropped | red, 1 |

  Why the ROWS guard matters: with it gone, an unreadable row count (`ROWS=""` from a transport
  blip on that one read, or psql error text) reaches `if [ "$ROWS" -eq 0 ]`, `[` exits 2 on a
  non-integer, `if` reads that as false, and `--yes` carries on through the containment guard to
  the delete. Measured by adding one case to the mutant (`STUB_ROWS="ERROR: relation"` under
  `--yes`, expecting `could not read` and 0 deletes): the mutant **deletes** (`deletes=1 want 0`,
  rc 0), and the pristine script passes the same case. The stub never sets `STUB_ROWS` to text
  (every case uses 0 or 1), so the state the guard refuses is one the fixture cannot produce — the
  mechanism above, one guard over from the three round 1 added cases for. The code is correct; the
  gate the task plan's Phase 4 pre-flight relies on cannot see this guard go. Remedy: the three lines
  above, placed beside line 244 (`STUB_COUNT="ERROR: relation"`), which go red on the mutant and
  green on HEAD as measured. The post-delete reads (lines 155-157) have the same unmodelled state
  and fail the safe way: an empty `AFTER_ITEMS` reads as `!= "0"`, exit 1, under a message claiming
  the delete did not take (`still reads items= rows=`); misleading, not dangerous, since a re-run
  then reports "nothing to do".

- **[fragile, low]** `NEWS.md:22-24` — "after the drop the old id answers 404" is true of
  `GET /collections/imagery-uav-bc-prod` and false of the path the README's own examples take.
  Measured on the live API with the not-yet-registered new id as the stand-in for an unknown
  collection: `/collections/stac-imagery-uav-bc` → 404, but `POST /search
  {"collections":["stac-imagery-uav-bc"]}` → **200, `FeatureCollection`, 0 features**. So a
  consumer who keeps `collections = "imagery-uav-bc-prod"` in an `rstac::stac_search()` (the
  README's three examples, the seven report repos' one line each) gets an empty result after the
  drop, not an error — the flooded#51 row in `code-check.md`, which cost a session exactly this way
  after `stac-dem-bc` was dropped. The sentence tells that reader to expect a 404 and go looking for
  one. One clause fixes it: "the old id answers 404 on `/collections`, and a search naming it
  returns no items".

## Enumeration (what the mechanism reaches in this diff, and whether each is covered)

**Every `$(...)` assignment whose command can fail.** `collection_unregister.sh`: `REPO=` (37; a
failed `cd` ends the script under `set -e`, no trap armed yet, loud); `CFG=` (92-97, `|| refuse`,
loud); `COUNT=` (108, `|| true` then `numeric`, case 5, mutant red); `ROWS=` (109, `|| true` then
`numeric`, **no case, mutant green: finding 2**); `LIVE_STATUS=` (138, `api_status` cannot fail:
measured `000` on an unresolvable host, `404` on the live API); `MISSING=` (141, `numeric`, case
12, red); `AFTER_ITEMS=`/`AFTER_ROWS=` (155-156, no `numeric`, `!= "0"` fails toward abort);
`STATUS=` (161, as `LIVE_STATUS`); `SELFTEST_TD=` (183, `set -e` before the trap is armed, loud);
`sql=$(cat)` and `out=$(main …) && rc=0 || rc=$?` (harness); `dels=$(grep -c … || true)` (228, the
right shape: `0` printed once; a missing log gives `""` and `[ -ne ]` errors loudly).
`item_unregister.sh`: `CFG=` (20-24, `set -e`, no trap yet, loud); `TMP=$(mktemp)` (40, same).
`dataset_publish.sh`: the new block is a heredoc python, `sys.exit(msg)` is 1, a missing file is a
traceback, both end the script before the COG step. `catalogue_release.sh`: unchanged.

**Every guard, the selftest case that fails it, and the mutant's colour** — the table in finding 2.
Sixteen guards in `main`; fourteen have a red case; `ssh_probe` (105) has none and its deletion is
benign (the next `pg_query` read then refuses through `numeric`; only the `cannot reach` message
is lost); the ROWS `numeric` has none and its deletion is not benign.

**Every stub answer and what it is keyed on.** `ssh_probe` → `:` (keyed on nothing). `pg_query`
(201-215): `*delete_collection*` → `""` (function name in the SQL); `*"select t.id"*` → two ids
(printed only); `*"t.collection = '<live>'"*` → `STUB_MISSING_REVERSED` (the live id in the target
position); `*"t.collection = '"*"l.collection = '<live>'"*` → `STUB_MISSING` (the live id in the
live position; a swapped call cannot reach it, mutant red on 3); `*"collection = '"*` → `STUB_COUNT`
or `0` once a delete is logged and `STUB_STICKY=0`; `*"collections where id = '"*` → `STUB_ROWS` or
`0` likewise; else `""`. `api_status` (216-221): URL ending `/collections/<live>` →
`STUB_LIVE_STATUS`; anything else → `404` once a delete is logged and `STUB_STICKY_API=0`, else
`200`. `deleted()` (200): `STUB_STICKY=0` and `delete_collection` in the log. States the stubs never
produce: text for `STUB_ROWS` (finding 2), an unreadable post-delete read, an unreachable host. The
pattern order was checked for every SQL `main` sends: `count_items` and `count_rows` cannot match
the two containment arms (no `t.`/`l.` alias), `count_rows` cannot match `*"collection = '"*`
(`collections where id = '` has no `collection = '` substring), and a target id that extends the
live id (`stac-live-bc2`) cannot match `*"t.collection = 'stac-live-bc'"*` because the closing
quote is part of the pattern.

**Every path two scripts share.** (1) The toml read: five readers of `[catalogue] collection_id`
(`item_create.py`, `dataset_publish.sh`, `catalogue_release.sh`, both unregister scripts), one
file, so consistent by construction; `collection_unregister.sh` allowlists `TARGET` and `DB` but
interpolates `LIVE_ID` into SQL unchecked, where `item_unregister.sh` allowlists `COLL` (which
defaults to the same toml id) — the toml is committed, so not flagged. (2) The ssh + `docker exec
… psql -U stac -d $DB` line: both scripts hardcode the container and the user while the toml
carries `pg_user`; pre-existing in `item_unregister.sh` and copied, not flagged. (3) The id
allowlist `[A-Za-z0-9_-]`: identical in both; `collection_unregister.sh`'s argument loop refuses
`-*` first and `item_unregister.sh` has no such arm — **finding 1**. (4) The drop's refusal names
`item_unregister.sh --collection <old-id> <item-id>...` as its remedy: run verbatim through the
shim with two real ids it sends `delete_item('<id>', 'imagery-uav-bc-prod')` for each, which is
what clears the containment count; `scripts/config/README.md:55,137` and the usage line agree on
the flag-first form. (5) `dataset_publish.sh`'s pre-check and `item_create.py`'s
`collection_id_check` read the same two artifacts with the same predicate, so they cannot disagree.
(6) The verify-404 line `item_unregister.sh` prints and the 404 check `collection_unregister.sh`
runs build the same URL shape from the same toml `api`.

## Checked, no issue

- `scripts/item_create.py`: `--selftest` PASS on the copy in the titiler env; the stamp runs after
  `set_root()` and before any item is built, the additive refusal before `links_check` and any
  write; `catalogue_release.sh`'s `ast` read of `FIELD_PREFIXES` evaluates `literal_eval` only on
  the matching assignment, so the two new module-level assignments above it are not parsed.
- `scripts/dataset_align-lidarbc.py` (`--check` runs between the rebuild and the sync) keys on
  `stac-elevation-bc` only (`:80`); nothing there reads this catalogue's id.
- `collection_unregister.sh`: parses and passes under `/bin/bash` 3.2 (16 ok); `api_status`
  measured `000` (3 chars) on an unresolvable host; an option-shaped target prints usage; the
  containment guard is refused in the right direction on the stub's asymmetric case (3 missing vs
  0 reversed) and ignores the reverse (case 11).
- Both repos named in the planning files that exist on GitHub are PUBLIC (`restoration_wedzin_kwa_2024`,
  `stac_dem_bc`, `stac_floodplains_bc`, `stac_pointcloud_bc`); the infrastructure, talk and evidence
  repos are referred to generically. Round 2's fix held.
- The old id outside `planning/`, NEWS and the README source survives only in ignored files
  (`README.html`, `.Rhistory`, `.Rproj.user`; `git ls-files` lists none, `check-ignore` names the
  rules); `README.md` and `index.html` render after the cutover by design.
- `data/sites.csv`, the #38 table and the "15 items / 9 items" counts: unchanged since round 2,
  which measured them.
- No secrets in the diff; `stacs.toml` carries none; the host IP was already committed.
