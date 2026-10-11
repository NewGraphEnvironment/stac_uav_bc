# Progress — Move the nge: item fields to standard or descriptive names (#38)

## Session 2026-10-10

- Plan-mode exploration — phases approved by user (naming forks answered at the gate: `uav:` stream names, `newgraph:` region/alias/project, `fwa:watershed_group_name` from a new sites.csv column)
- Created branch `38-move-the-nge-item-fields-to-standard-or` off main
- Scaffolded PWF baseline from issue #38 with approved phases
- Next: start Phase 1
- Phase 1: #38 body rewritten with the decided mapping; `scripts/sites_fill-wsg_name.py` filled `watershed_group_name` for 84 rows from 17 codes (1 row, `kootenay/regent/2025/20250616`, has no code). Diff verified column-only (87 lines, 0 mismatches after removing the field); a second run reports 0 changes.
- Phase 2: `item_create.py` writes the new names (`REGISTRY_FIELDS`), declares `FIELD_PREFIXES`, refuses an undeclared prefix per item and, in additive mode, refuses a prod tree still holding pre-#38 items. `--selftest` passes; 8 restored defects (old stream/alias keys, `nge` declared, blank carried, assets unchecked, collection.json not skipped, title on old alias) each turn it red.
