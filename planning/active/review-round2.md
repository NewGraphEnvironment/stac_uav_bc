# Code-check round 2 — #48 collection rename (branch `48-rename-the-collection-to-stac-imagery-ua` at 04f3fbd vs origin/main, three-dot)

Reviewed: the full diff and the full contents of every changed file, `scripts/catalogue_release.sh`
for context, the stacs v0.1.0 source and the saved pgstac 0.9.8 SQL under the scratchpad, and the
checklist: code-check.md (mechanisms, standalone rules, security), code-check-shell.md and
code-check-python.md in full; code-check-r.md and code-check-spatial.md by heading, since the diff
carries no R or spatial code (the README.Rmd chunk edits are string literals). Round 1's four fixes
were read as closely as the rest. Every probe ran on copies under the scratchpad
(`probe2/`); the live checks were read-only (report mode, two `SELECT count(*)`), nothing on the
host was written. Measured 2026-10-16 20:05–20:31Z.

## Findings

- **[fragile]** `scripts/config/collection_unregister.sh:53` (`api_status`) — the round-1 fix
  doubles the code it was meant to supply. `curl -s -o /dev/null -w '%{http_code}'` writes `000`
  on a transport failure **and** exits non-zero, so `|| echo 000` appends a second one. Measured
  (curl 8.7.1, an unresolvable host): the function returns `000000` (6 chars); bare curl prints
  `000` with rc 6. Before the delete it still refuses, under `answers HTTP 000000, not 200`
  (cosmetic). After the delete (line 146) a transport blip reports the one irreversible step as
  `answers HTTP 000000, not 404`, exit 1, and the recovery line never prints. The selftest case
  at line 225 (`HTTP 000, not 200`) is fed by the stub (`STUB_LIVE_STATUS=000`), so it pins a
  message the real function cannot produce, and the real function is never exercised. This is
  `code-check-shell.md`'s "`grep -c` prints the count AND exits 1 — never `|| echo 0` inside the
  substitution" one tool over, and round 1 prescribed this exact text. Remedy: `|| true` (curl's
  own `000` survives: measured `000 rc=6`), or assign then default:
  `c=$(curl …) || c=000; printf '%s' "${c:-000}"`. The timeout variant (`--max-time`, rc 28) was
  not measured here (the probe was refused); on a timeout after the headers arrive `%{http_code}`
  can be `200` with rc 28, which the same `|| echo` turns into `200000`.

- **[fragile]** `scripts/config/collection_unregister.sh:132-135` with
  `scripts/config/item_unregister.sh:39` — round 1's two fixes interact. `item_unregister.sh` now
  deletes from the live collection only (correct), so from the cutover until the drop a
  retraction, a re-stitch or a dataset rename leaves the retired id in the old collection and
  absent from the live one. The containment guard then refuses `--yes` for the old id:
  `1 of imagery-uav-bc-prod's 245 item id(s) have no item in stac-imagery-uav-bc`. That refusal
  is the safe direction, but it has no escape hatch and names no remedy; `item_unregister.sh`
  cannot reach the old collection's copy (it reads the configured id only), and
  `scripts/config/README.md:131-134` says a count other than the whole catalogue "means something
  still writes to the old id", which is wrong for this case. So the operations round 1 made work
  during the window are also the ones that make the drop undroppable without hand SQL
  (`pgstac.delete_item('<id>', 'imagery-uav-bc-prod')`), against "recurring operations get repo
  scripts". The window is the consumer sweep (about fifteen repos plus QGIS counts on other
  machines), long enough for a retraction. Reasoned from the SQL (no retraction exists today):
  `t.collection = old AND NOT EXISTS (l in live WITH l.id = t.id)` counts exactly a retired id.
  Remedy, one of: the guard prints the missing ids and names the delete that clears them;
  `item_unregister.sh` takes `--collection <id>` (or deletes the id from every collection that
  holds it, one `delete_item(id, collection)` per collection, since the one-argument form raises
  on two rows); or the recipe says retractions wait for the drop. Side effect in the same window:
  the retraction recipe's step 3 removes the S3 objects while the old collection still serves the
  item, so the old id serves dangling hrefs until the drop (transient; the old id is deprecated).

- **[fragile]** `scripts/config/collection_unregister.sh:179` (the stub's `*"not exists"*` arm) —
  the selftest cannot see which way the containment runs. The stub answers `$STUB_MISSING`
  whatever the SQL's argument order, so a copy with the two arguments swapped
  (`count_missing "$LIVE_ID" "$TARGET"`: live ids absent from the target) passes all 15 cases
  (measured). The direction is the guard: measured live today, old→live reads **245** (refuses)
  and live→old reads **0** (would pass). The reversed guard passes precisely when the live
  collection holds fewer ids than the one about to go, which is the never-delete-first failure
  it exists to stop (today the `= 200` check would still catch it, since the new id 404s; after
  the cutover both directions read 0 until a retraction, and then only the correct direction
  refuses). Round 1's "five mutants each go red on exactly one case" did not include this one.
  Lines 180 and 207 (`*"collection = '$STUB_LIVE'"*`, `STUB_LIVE_COUNT`) are left over from the
  count guard and unreachable: `count_items` is never called on `LIVE_ID`, and the `not exists`
  arm matches first. Remedy: answer from the SQL's own text, e.g. `$STUB_MISSING` only when it
  matches `*"t.collection = 'stac-old-bc'"*"l.collection = '$STUB_LIVE'"*` and a different
  canned value otherwise, with one case where the two differ; delete the dead arm.

- **[fragile]** `scripts/config/collection_unregister.sh:155-159, 251-253` — the selftest arms
  `trap "rm -rf '$td'" EXIT` under `set -euo pipefail`, and on macOS `/bin/bash` 3.2 (the
  shebang) an armed EXIT trap turns an expansion error into exit **0**
  (`code-check-shell.md`, "On bash 3.2 an armed `EXIT` trap turns some fatal errors into exit 0").
  Measured on a copy with one `$NEVER_SET_VAR` read inside `selftest()` before the verdict:
  `unbound variable` on stderr, no PASS line, **rc 0** under `/bin/bash`; rc 1 under Homebrew
  bash 5.3.9. A crash inside a `run` case is caught (it runs in `$( )`; a copy with
  `STUB_STICKY_API` never initialised went red, rc 1), so the exposure is the function body
  outside `$(…)`: today nothing there reads an unset name, so this is latent, and it is the shape
  the next case added with a new `STUB_*` variable produces. The task plan's Phase 4 pre-flight
  gates on this selftest being "green". Remedy: `ok=0; trap 'rc=$?; rm -rf "$td"; [ "$ok" = 1 ]
  || exit $(( rc ? rc : 1 ))' EXIT`, `ok=1` on the line before the PASS echo; or gate the
  pre-flight on the PASS line, not the exit status. `item_unregister.sh:29` arms the same trap
  after its reads; its variables are all set and its failure paths are command failures (exit
  non-zero), so it is not exposed today.

- **[fragile, convention, low]** `planning/active/findings.md:146-158, 191`;
  `planning/active/task_plan.md:119, 124, 126, 142` — the repo is PUBLIC (`gh repo view`) and the
  committed planning files name private repos with their internal layout: the infrastructure repo
  (`the register-all list:31`, `the droplet's unregister script`),
  the talk site repo, the talk drafts repo (a branch name and dirty-file counts), the evidence repo
  (its dump logs) and the report template repo; all five
  measured PRIVATE. `CLAUDE.md:25` deliberately writes "our internal infrastructure repo" for the
  same repo, and `feature-workflow.md` ("Public-repo text describes the package, and points
  nowhere private") says a public repo's committed `planning/` is public and carries no private
  repo names. Not code and not a credential; a disclosure of repo names and paths. Remedy: say
  "the infrastructure repo's register-all list", "two talk repos", "the report template", as the
  Decided section of the same file already does, and keep the per-repo table where the sweep is
  tracked.

## Checked, no issue

- `scripts/item_create.py` is unchanged since round 1 (`04f3fbd` touched the two config scripts,
  docs and planning only); `--selftest` PASS on a copy in the titiler env. The stamp runs after
  `set_root()` and before any item is built; the additive refusal runs before `links_check` and
  before any write.
- `scripts/dataset_publish.sh:51-60`: the pre-check block run standalone against the real
  `stacs.toml` and the real prod `collection.json` refuses with the designed message, rc 1 (prod
  still names `imagery-uav-bc-prod`, title `… - imagery-uav-bc-prod`, version 1.0.4): a positive
  control for the guard's direction.
- `collection_unregister.sh`: selftest 15 of 15 under `/bin/bash` 3.2; `[ "$MISSING" -eq 0 ]` →
  `-ge 0` red on one case; live-id refusal removed red on one case; `bash -n` clean on all three
  shell scripts. Report mode against the real database: `imagery-uav-bc-prod` 245 items, nothing
  deleted, the configured id refused. `grep -c … || true` inside the `run` substitution is the
  right shape (prints `0` once).
- pgstac 0.9.8 (saved SQL): `delete_collection(_id)` is `DELETE … RETURNING * INTO STRICT`
  (905-911); `collection_delete_trigger` BEFORE DELETE drops `_items_<key>` with CASCADE (925-944)
  and `items_collections_fk` is `ON DELETE CASCADE` (2050), so the read-back's items 0 / row 0
  holds; `delete_item(_id text, _collection text DEFAULT NULL)` (2324-2330) matches the
  two-argument call.
- stacs v0.1.0 scopes every `/search` to the toml collection (`verify.py:104, 137, 174`) and
  `register --mode drift` loads an unregistered collection before its items, so the old
  collection's rows are never orphans to the release's verify.
- `data/sites.csv`: 86 rows × 15 fields, CRLF (accepted); the eight rows read as NEWS states;
  each of the eight datasets holds 3 item JSONs in prod, so 15 and 9 are right. `name_source`
  (cleared on three rows) has no consumer in the build.
- NEWS's #38 table matches `REGISTRY_FIELDS` and the keys a prod item carries today
  (`nge:region`, `nge:stream_name`, `nge:watershed_group`, `nge:wsg_code` measured on one item).
- No caller of `delete_item` / `delete_collection` outside the two config scripts; the old id
  survives outside `planning/` only in NEWS.md, README.Rmd, README.md and index.html (accepted).
- README.Rmd and NEWS: "re-add it in the browser" for QGIS is a claim about a third-party client
  not executed here; at worst over-prescriptive (a connection lists `/collections` live on
  refresh), not wrong in effect.
- No secrets in the diff; `stacs.toml` carries none; the host IP was already committed.
