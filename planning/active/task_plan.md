# Task: Move the nge: item fields to standard or descriptive names (#38)

**If we do it:** each field an item carries says what it is. Clients that know the standard extension read the standard fields, and a reader does not have to know that `nge` means New Graph Environment. **If we never do:** the fields stay readable only to people who know the initials.

## Decided mapping (2026-10-10, plan gate)

| was | now | source |
|---|---|---|
| `nge:region` | `newgraph:region` | NGE's own regional split; may ride between catalogues |
| `nge:alias` | `newgraph:alias` | NGE's name for the site |
| `nge:project` | `newgraph:project` | NGE's project (blank in all 85 rows, so not written today) |
| `nge:stream_name`, `_02`, `_03` | `uav:stream_name`, `_02`, `_03` | this catalogue's registry judgment (PSCIS, bcfishpass, FWA, guess, user) |
| `nge:wsg_code` | `fwa:watershed_group_code` | the atlas column |
| `nge:watershed_group` (slug) | dropped; new `fwa:watershed_group_name` | the atlas name, from a new sites.csv column; the slug stays in the item id |
| `nge:site_id` | `bcfishpass:aggregated_crossings_id` | bcfishpass's id |

No crate schema or crate issue yet: only this catalogue writes these prefixes (crate `pkgdown/assets/stac/README.md` rule). Prefixes are declared locally, with no schema URL.

## Phase 1: Settle the mapping and add the registry column
- [x] Edit the #38 body: replace the "proposal" table with the decided mapping above, including the reasons the `fwa:watershed_group_name` and `fwa:` stream-name rows changed
- [x] `scripts/sites_fill-wsg_name.py`: fill `watershed_group_name` from `watershed_group_code` through the fwapg REST collection `whse_basemapping.fwa_watershed_groups_poly` (probed: BULK → "Bulkley River"). It makes one fetch per distinct code from inside one process, sets `--max-time`, prints by default and writes only with `--write`, and refuses a code the atlas does not know. The written CSV must keep its column order, quoting and line endings (diff limited to the new column)
- [x] Add the `watershed_group_name` column after `watershed_group_code` and fill it. Report the one row with a blank code
- [x] Document the column in the `scripts/config/README.md` registry paragraph and the add-imagery recipe

## Phase 2: Item builder (`scripts/item_create.py`)
- [x] `--selftest` gate first, following `flight_coverage.py --selftest`. It runs on fixture rows with no network and no tifs, and asserts:
  - the full old→new mapping
  - blank cells are omitted
  - the title reads `uav:stream_name` and `newgraph:alias`
  - the prefix guard refuses `nge:x` and any undeclared prefix
  - additive mode refuses a tree whose items carry an undeclared prefix

  Then restore each defect and confirm the gate goes red.
- [x] Rewrite the `registry_props()` mapping, update `build_item()`'s `props.get(...)` reads, and add `FIELD_PREFIXES = {proj, fwa, bcfishpass, uav, newgraph}`
- [x] Guard in `build_item()`: refuse any property whose prefix is not declared
- [x] Additive mode refuses when existing item JSONs in the prod tree carry an undeclared prefix (i.e. `nge:`). The message points to `catalogue_release.sh`. Without this, `dataset_publish.sh` would publish renamed items beside `nge:` ones

## Phase 3: Release gate and reader docs
- [x] `scripts/catalogue_release.sh` registry-coverage check: require `newgraph:region` and `uav:stream_name`, and fail if any live item carries a property outside the declared prefixes, so a stray `nge:` key fails the release
- [x] `README.Rmd`: an item-properties table listing each field, what it holds and its source, and how to filter on it with rstac. Re-render `README.md`
- [x] Update `scripts/config/README.md:36` ("queryable `nge:` properties") and any `CLAUDE.md` line that names the fields

## Phase 4: Verify offline (nothing published)
- [x] Mirror the prod tree into the scratchpad: real directories, symlinked tifs, copied JSONs. Run `item_create.py --rebuild --base <mirror> --version 0.0.0-test`, then `stacs.sh validate` and `audit --expect <links>` on the mirror
- [x] On the mirror, assert:
  - zero `nge:` keys
  - every item carries `newgraph:region` and `uav:stream_name`
  - `fwa:watershed_group_name` is present wherever the code is
  - titles are unchanged from the live items, compared by id
- [x] Confirm that additive mode against the real prod tree, which still holds `nge:` items, refuses without writing anything

## Validation
- [x] `item_create.py --selftest` passes, and fails with each guard's defect restored
- [x] `/code-check` clean (once over the branch with `/code-check branch`)
- [ ] PWF checkboxes match landed work
- [ ] `/planning-archive` on completion; PR body lists every old → new pair so the NEWS entry can carry them

