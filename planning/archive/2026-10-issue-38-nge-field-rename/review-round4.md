# Code-check round 4 (#38) — focus: 3c929c9, refusals vs writes

Reviewed: `git diff 5bae813...HEAD` (HEAD 3c929c9), `scripts/item_create.py` in full,
`dataset_publish.sh`, `catalogue_release.sh`, `sites_fill-wsg_name.py`, doc diffs, `data/sites.csv`.
Probes (read-only): `--selftest` passes in the titiler env; the real registry (85 rows, 83
published) has no code/name half-pairs and no duplicate keys, so the moved
`registry_problems` refuses nothing today; prod tree holds 246 JSONs, all dict items or
`collection.json`, 245 non-`.original` tifs; `sites.csv` is CRLF throughout, as before.

## Findings

- **[severity: fragile, pre-existing shape, newly relevant]** scripts/catalogue_release.sh:26-35
  with scripts/item_create.py:379 — the release writes the prod tree (`--rebuild`) and only then
  runs its gate (`stacs validate` / `audit --expect`). If that gate refuses, the tree is left
  rebuilt with the new field names and the new version stamp, unsynced. The additive guard
  this branch adds (`tree_undeclared`, "release first") is then satisfied by that tree, so
  the next `dataset_publish.sh` goes ahead and its final `aws s3 sync --delete` + register
  publishes the whole rebuilt tree. That includes whatever the audit refused (for example
  the stray old-id JSON that `--expect` exists to catch). The release's own live checks
  (version, coverage, stray fields) never run. This is the R3 mechanism, a refusal after a
  write, one level up, in the shell rather than in item_create.py. Nothing in item_create.py
  can see it. Low severity: it needs a failed release followed by a publish with no rerun of
  the release. Narrowest guard: have dataset_publish.sh run the same `validate` +
  `audit --expect` over `$PROD` before its final sync. Or document that a failed release
  must be rerun to green before any publish.

No other issue. Specific questions from the brief:

- **registry_problems over every published row.** The check is independent of tifs, so a
  published row with no tif yet is checked only for its code/name pair, and passes when
  both or neither are set. The real registry passes. A half-pair on a row unrelated to the
  publish now blocks `dataset_publish.sh`. That is a loud refusal before any write, and the
  release would refuse it the same way, so it is consistent and not a bug. (`registry_conflicts`
  also counts `published=false` rows while `registry_problems` skips them. That is loud and
  the fill script fixes it. Not a bug.)
- **Consumers of the old per-item behaviour.** Nothing parses `CREATED:` (grep over the
  repo's `.sh`/`.py`/`.R`/`.qmd`/`.md`). `dataset_publish.sh` reads only the exit status and,
  afterwards, `collection.json`. `made` is now the list of saved dests, still used only for
  the closing hint. Nothing is broken.
- **Deferred saves vs anything reading item JSON earlier.** `build_item` and `collection_add`
  never read item JSON from disk. Links resolve to in-memory targets: `clear_items`,
  `add_item` and `update_extent_from_items` → `get_items` do no I/O, because `set_root(collection)`
  keeps the root in memory. An item's JSON depends only on itself and on the collection's
  self href and root, which do not change during the loop, so saving later gives the same
  bytes. `links_check` runs before any write (additive) or after every save (both modes),
  so it never ran between per-item saves. The additive `existing` set covers a repeat
  within one run without a file on disk.

## Exit-vs-write enumeration (scripts/item_create.py)

Writes: item `save_object` at 360 (rebuild) and 408 (additive); collection `save_object` at
367 (rebuild) and 410 (additive). `footprint()` writes only to a TemporaryDirectory.

| line | exit / raise | after a write? rebuild | after a write? additive |
|---|---|---|---|
| 321 | `--selftest` exit | no | no |
| 323 | args usage exit | no | no |
| 326 | `load_registry` raise (missing or garbled csv) | no | no |
| 331 | `published` `.strip()` on None (short row) raises | no | no |
| 334 | REFUSED registry_problems | no | no |
| 337 | REFUSED registry_conflicts | no | no |
| 339 | `Collection.from_file` raise | no | no |
| 160 | SKIP published=false (return, not exit) | n/a | n/a |
| 166-179 | rio_stac / `flight_datetime` / `footprint` (CalledProcessError) raise | no: all items still pending | no |
| 183 | REFUSED undeclared prefix | no | no |
| 184 | `item.validate()` raise | no | no |
| 376 → 205/211/217 | `links_check` pre-check exits | — | no: before any write |
| 382 | REFUSED stale `nge:` tree | — | no |
| 393 | `missing:` exit inside the loop | — | no: saves now come after the loop (was a partial write before 3c929c9) |
| 360 / 408 | `save_object` I/O error partway through the save loop | yes: partial items, collection not | yes: same |
| 365 | `update_extent_from_items` raise | **yes, after the item saves**, before the collection save. Not reachable in practice: rio_stac always sets bbox and datetime, and with 0 items nothing was saved | — |
| 366 | `git_version` raise (FileNotFoundError if no `git`; only when `--version` is omitted; the release always passes it) | **yes, after the item saves**. Not reachable from the scripts | — |
| 367 / 410 | collection `save_object` raise | yes: items saved, collection not | yes: same |
| 371 / 412 | `links_check` post-write exits | yes: accepted (#35); the caller stops before sync | yes: accepted |

Under 3c929c9 no refusal, meaning a guard that decides "no", can follow a write in either
mode. What follows a write is I/O failure in the save loops, plus two computations in
rebuild (365, 366) that could be moved above line 359 at no cost. Neither is reachable on a
normal run. The one remaining refusal-after-write is the shell-level case in Findings.
