# Plan review — #35 (Plan agent, 2026-10-09, returned after Phases 1–4 had landed)

Read-only agent; findings returned as reply text and written here. Each was probed before acting.

| # | Category | Finding | Disposition |
|---|---|---|---|
| 1 | Acceptance | v1.0.4 release will not exercise the item-load path: links are outside the digest, so drift loads only the collection | **Accepted.** Phase 5 adds `register --mode drift --dryrun` via loopback (0 to register) and an ssh BatchMode probe of the host (ok). First live item upsert = next `dataset_publish.sh`, or a one-id `--mode ids` after the release (PR body) |
| 2 | Gap | `from_file` leaves root unresolved (S3 URL); `add_item` → `get_root()` downloads the bucket's collection.json and roots everything on it | **Confirmed** by spying `read_text_from_href`: one S3 read during `get_root()`, none after `set_root(collection)`. Fixed; re-rebuild byte-identical (246/246) |
| 3 | Ordering | links gate runs after writing in additive mode | **Fixed**: additive mode checks existing links before writing. Test: stale link → exit 1, JSON count 2→2, collection.json md5 unchanged |
| 4 | Assumption | `stacs validate` on stdin validates collection.json too | **Confirmed** (a collection with `extent` removed → INVALID, exit 1). Conda one-liner dropped; `find "$PROD" -name '*.json'` feeds both |
| 5 | Gap | `audit --expect <n links>` checks nothing new | **Rejected.** `--rebuild` never deletes an old-id JSON (README rename gotcha). That file carries a different id, so only the count sees it; Phase 3 mutation: `expected 245 item(s), audited 246`, exit 1 |
| 6 | Gap | verify fails on orphans catalogue-wide; header + rename ordering | **Fixed**: `dataset_publish.sh` header says so; rename recipe says unregister **before** publish/release (the header's `item_register.sh` mention was already gone in Phase 3) |
| 7 | Gap | api/bucket/collection id duplicated outside stacs.toml | **Partly fixed**: `catalogue_release.sh` derives `API` and the `/search` collection from `stacs.toml`. `BUCKET` (`s3://` form for aws) and `item_create.py --s3-url` remain; a mismatch fails loudly (links gate / stacs collection-id refusal) |
| 8 | Assumption | `item_unregister.sh` needs python3 ≥3.11 for tomllib | Noted. Fails loudly (`ModuleNotFoundError` under `set -e`) before touching anything |
| 9 | Assumption | `uvx --from git+…@tag` ignores stacs' `uv.lock` | Noted; same as stac_dem_bc. Low risk |
| 10 | Acceptance | "Tests pass" names no suite | **Accepted**: findings.md records each gate as a named command with expected output |
| 11 | Scope | local prod tree ahead of S3 by links | Noted; the release sync closes it |
