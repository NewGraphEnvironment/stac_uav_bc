# Review round 1 — branch 38-move-the-nge-item-fields-to-standard-or (#38)

Reviewer: code-check round 1, 2026-10-10. Scope: `git diff 5bae813...HEAD` (scripts, CLAUDE.md, README.Rmd, data/sites.csv).

## Findings

- **[fragile]** scripts/item_create.py:97-104 (`registry_problems`) — the guard only catches a code with a **blank** name, but its own comment names the other half of the problem: "a row whose code was ... changed without it would publish fwa:watershed_group_code with no name (or a stale one) and nothing else would notice". A changed code with the old name left in place passes this guard, passes `--selftest`, and is published as a mismatched `fwa:watershed_group_code` / `fwa:watershed_group_name` pair; the release's live check does not look at the pair either. Only a manual run of `sites_fill-wsg_name.py` reports it. Probe: `registry_problems({**row, "watershed_group_code": "MORR"})` with `watershed_group_name: "Bulkley River"` returns `[]`. An offline check would cover most real edits: refuse a registry where one code maps to two names, or one name to two codes. Today all 17 codes map 1:1 (measured), so the check would pass on the current registry and fire whenever an edited row's code is shared with any other row. Or narrow the comment so it no longer claims stale names are covered. This is low severity: the documented recipe says to run the fill script after a code change.

## Checked and found sound (no action)

- `catalogue_release.sh` live check, extracted and run against the real live `/search` response (read-only): it refuses today's 245 `nge:` items (rc=1), and it passes (rc=0) on the same response with the keys renamed. The `ast` read of `FIELD_PREFIXES` works under system python3. A missing or annotated assignment raises `StopIteration`, so the check fails closed. The embedded code has no `$`, backtick or `"`, so bash quoting is safe.
- Live API: the search response carries no prefixed keys besides `nge:` and `proj:`, so the asset/property stray check will not false-fire on server-injected fields. Queryables are open (`additionalProperties: true`), so CQL2 filtering on the new names will work once released (a `nge:wsg_code = MORR` filter returns 57 today).
- `--selftest` passes in the titiler env.
- `sites_fill-wsg_name.py`: on a copy, the warm path (`--write` on the current registry) changes 0 rows and is byte-identical. The cold path (base-commit registry without the column, `--write`) reproduces the committed `data/sites.csv` byte-for-byte, CRLF included. An unknown code or an ignored API filter fails closed (`None` → refused before writing).
- Prod tree: 245 tifs and 245 item JSONs plus `collection.json`. There are no non-item JSONs and no `.aux.json`. Neither `published=false` row has a directory in the prod tree, so after one `--rebuild` every JSON is rewritten and the additive refusal in `tree_undeclared` lifts. An old-id leftover would be caught by the release's `audit --expect`.
- A rebuild that stops partway on a new refusal leaves some `nge:` JSONs in the tree. That keeps the additive refusal active, and `set -e` stops the release before sync, so it fails closed.
- Org-wide code search (`gh api search/code`) for `nge:stream_name`, `nge:wsg_code`, `nge:region`, `nge:site_id` and `nge:alias` finds no consumer outside this repo, only a planning note in rolex.
- No other script reads or writes `sites.csv` by column position (`stream_resolve.py` only prints).

## Verdict

One fragile finding (the stale-name scope of `registry_problems`). Nothing else found.
