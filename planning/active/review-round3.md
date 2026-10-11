# Review round 3 (#38)

Branch diff `5bae813...HEAD`, reviewed 2026-10-10. Nothing in the repo was modified except this file. Probes ran in a scratchpad copy, plus read-only calls to fwapg and the live STAC search.

## Findings

- **[fragile]** scripts/item_create.py:163-165, inside the loop at :343-351 (rebuild) and :380-396 (additive). The new `registry_problems` refusal fires per tif, inside the loop. By then `item.save_object` has already rewritten every earlier item's JSON in the prod tree, and `collection.json` is left unsaved.
  - **Proven with a mock in a copy:** with two tifs and the second row coded `MORR` with a blank name, `--rebuild` exits `REFUSED`. The first item's JSON has been written and `collection.json` is byte-unchanged.
  - **Why it matters after the #38 transition:** once the tree holds no `nge:` items, `tree_undeclared` no longer blocks. A `dataset_publish.sh` for some other dataset then passes `links_check`, because the paths are the same. Its final `aws s3 sync "$PROD" … --delete` and `stacs register --mode drift` publish the half-rebuilt items: unreleased registry edits go live under the old version stamp.
  - **Not caught by the release live check:** it only checks prefixes and the two required keys.
  - **Partly pre-existing:** an exception in `footprint` or `validate` mid-loop has always done this. This diff adds the first predictable, data-driven trigger.
  - **Fix:** run `registry_problems` over every registry row that will be built before the loop writes anything, as `registry_conflicts` already does in `main()`.

Nothing else found that fails. Every assumption below was measured, and every one holds on today's atlas and registry.

## Mechanism

R1 and R2 come from the same belief: that the code ↔ name pairing is a **bijection**. The atlas only guarantees that code → name is a **function**. Each code is unique and has exactly one name; names are not unique.

- R1's gap followed from that belief. A name-consistent row was taken as correct whatever its code.
- R2's by-name check stated the belief outright, and Salmon River refuted it.

Behind both is a second fact. `item_create.py` never consults the atlas. Its guards can only check the registry against itself, which stands in for the real property ("this name is the atlas's name for this code"). Each guard therefore encodes a belief about what the atlas guarantees. Those beliefs have to be measured across all 246 groups, not reasoned from one example.

## Measurements

Taken 2026-10-10.

**Atlas** (`fwa_watershed_groups_poly`, every row; `properties=` set and the geometry reduced to centroids):
- 246 features, 246 distinct codes. No code has two names.
- Exactly one shared name: Salmon River (SALM and SALR).
- No duplicate names that differ only by case.
- No leading or trailing whitespace or double spaces. All codes are 4 upper-case letters, all names ASCII, and no name contains `,`, `"` or a newline.

**API filter behaviour:**
- `watershed_group_code=MORR` returns 1 feature.
- `=morr` and `=MOR` return 0, so the filter is exact and case-sensitive.
- A misspelled parameter (`watershed_group_codez=MORR`) is silently ignored and returns all 246 features.

**Registry** (`data/sites.csv`):
- 85 rows, CRLF line endings, no BOM, no duplicate keys.
- Every code is in the atlas, and every name equals the atlas name exactly.
- One row has no code (`kootenay/regent/2025/20250616`, `published=false`), and its name is blank.
- `registry_conflicts` returns `[]` and `registry_problems` returns `[]` on every row.
- No published row has a blank `stream_name`.

**Live search:** 245 items, no `next` link. Properties carry only `title`, `datetime`, `proj:*` and `nge:*`; assets carry only `href`, `type` and `roles`. The API injects no prefixed keys of its own.

## Mechanism enumeration

Each place this mechanism reaches, the assumption it rests on, and whether that assumption is measured.

- **`registry_problems`** (item_create.py:97): assumes every atlas code has a non-blank name, so a code with no name is always an error; and that a name with no code is always an error. **Measured fact:** 246 of 246 codes have a name. The no-code half holds by the registry's design.
- **`registry_conflicts`** by code (item_create.py:112): assumes the atlas maps each code to exactly one name, so two names under one registry code is always an error. **Measured fact:** 246 distinct codes, none with two names. It compares names verbatim after `strip()`. That is safe because the atlas has no whitespace or case variants and the registry matches the atlas byte for byte.
  - **Untested belief:** codes are grouped case-sensitively, so a hand-typed `morr` would not be grouped with `MORR`. No such row exists, and the fill script refuses `morr` (0 features). A row that skips the fill script would get past `item_create`.
  - **Accepted gap, measured as still present:** a lone changed row, or several rows changed to the same new code with the same stale name, passes.
- **Removed by-name check** (R2): would have assumed atlas names are unique. **Measured false:** SALM and SALR are both Salmon River. Correctly removed.
- **`atlas_name()`** (sites_fill-wsg_name.py:32):
  - (a) The filter is exact. **Measured.**
  - (b) One feature per code. **Measured.**
  - (c) The `== code` re-filter in the script protects against an ignored filter. **Measured:** an ignored parameter returns all 246, and the re-filter still yields the right single name. That path downloads full polygons for every group; a bounded single code is about 0.3 to 0.5 MB, up to 7 s against a 30 s timeout.
  - (d) The default page is at least 246. **Measured:** 246 are returned without `limit`.
- **One-name-per-code refusal** (`len(names) == 1`, sites_fill-wsg_name.py:39): assumes the atlas gives each code one name. **Measured fact.** The more-than-one branch is unreachable today and fails toward refusal. An unknown code fails toward refusal too, before anything is written.
- **Fill script read/write shape:** assumes CRLF, no BOM and unquoted cells. **Measured** on the current file. The byte-identical warm and cold rerun was verified in an earlier round.
- **Release live check** (catalogue_release.sh:83-112): rests on nothing from the atlas or registry pairing, because it never compares the name with the code. It assumes:
  - `FIELD_PREFIXES` is a top-level literal set. **Measured:** system Python 3.14 reads it. If it ever stops being one, the read raises `StopIteration` and the script exits 1, which fails loud.
  - The API serves properties verbatim. **Measured** on the live items.
  - 245 items fit under `limit=1000`. **Measured.**
  - It requires `newgraph:region` and `uav:stream_name` but not `fwa:watershed_group_code`. That is correct: the only row without a code is unpublished.
- **Selftest fixtures:** BULK = Bulkley River, MORR = Morice River and SALM / SALR = Salmon River are all **measured** against the atlas. The conflict fixture encodes code → name as a function, and the Salmon fixture encodes non-unique names; both are measured facts.
  - **Fixture gap:** no fixture has a row that refuses after an earlier row has been built. That is why the finding above is invisible to the selftest.
