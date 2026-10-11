# Findings — Move the nge: item fields to standard or descriptive names (#38)

## Issue context

**If we do it:** each field an item carries says what it is. Clients that know the standard extension read the standard fields, and a reader does not have to know that `nge` means New Graph Environment. **If we never do:** the fields stay readable only to people who know the initials.

Decided for the catalogue family in NewGraphEnvironment/stac_pointcloud_bc#12 (2026-10-10):
- A field with a standard home uses it.
- Otherwise its prefix names what it describes.
- `nge:` stays only where New Graph Environment itself is the subject.

Each custom prefix gets a JSON Schema in crate, which items list in `stac_extensions` (NewGraphEnvironment/crate#23 is the umbrella; `lidarbc` and `las` are done there). **Prefer a standard field.** A custom prefix earns a crate schema only when more than one catalogue writes it, or something outside NGE reads it (`crate/pkgdown/assets/stac/README.md`), because every schema is permanent and every field change is a new version. Provenance that only this catalogue writes goes in `processing:*` or a `derived_from` link.

Once the mapping below is settled, file one crate issue for the custom prefixes that remain and link it from crate#23. This catalogue's rebuild waits on that crate deploy. Validate against copies of the schemas checked into this repo, as stac_pointcloud_bc#2 does, not against the live URLs. The [processing extension](https://github.com/stac-extensions/processing) (v1.2.0) defines `processing:datetime`, `processing:version`, `processing:software` (a name → version map) and `processing:lineage`.

## Fields (main, 2026-10-10)

The mapping below is a proposal. Check each row against what the field holds before renaming it.

| field | proposed | note |
|---|---|---|
| `nge:stream_name`, `nge:stream_name_03` | an `fwa:` prefix (BC Freshwater Atlas) | names from the atlas |
| `nge:watershed_group`, `nge:wsg_code` | `fwa:watershed_group_name`, `fwa:watershed_group_code` | the atlas's own column names |
| `nge:site_id` | `bcfishpass:aggregated_crossings_id` | it holds bcfishpass's crossing id (`scripts/item_create.py`) |
| `nge:region`, `nge:project`, `nge:alias` | stay `nge:`, or a project prefix | NGE's own project registry; NGE is the subject |

## When

Renaming changes every published item, so it rides with this catalogue's next full rebuild, not a release of its own. NEWS names each old → new pair, because a saved filter on an old name stops matching.



## Exploration (2026-10-10)

- Writer: `registry_props()` in `scripts/item_create.py`; reader: `build_item()` (title from stream_name + alias); release gate `scripts/catalogue_release.sh` checks `nge:region` + `nge:stream_name` live.
- Built items carry only `proj:` besides `nge:` (rio_stac `with_proj=True`); `stac_extensions` lists projection v1.1.0 only.
- `sites.csv` (85 rows): `watershed` is the tree slug (`peace_arm`, `upper_arrow_lake`), not the FWA name, so the issue's `fwa:watershed_group_name` for it was wrong. `watershed_group_code` is FWA's, one row blank. `project` blank in all rows.
- Stream names by `name_source`: pscis 24, bcfishpass or FWA 54 (bcfishpass_gnis 18, fwa_bbox 7, fwa_nearest_* 24, bulkley-rule 5), guess_* 5, user 1, blank 1. Not atlas names, hence `uav:` rather than `fwa:`.
- fwapg REST: `https://features.hillcrestgeo.ca/fwa/collections/whse_basemapping.fwa_watershed_groups_poly/items.json?watershed_group_code=BULK&properties=watershed_group_code,watershed_group_name` returns `Bulkley River`.
- Org code search for each `nge:` key: no code reader outside this repo (rolex planning text only).
- Precedent: stac_airphoto_bc#47 declares prefixes in `FIELD_PREFIXES` (prefix → schema URL or None) and refuses undeclared ones in `stac_validate.py`.
- Decision drift vs family: user chose `newgraph:` over `nge:` for NGE-as-subject fields. The family text (stac_pointcloud_bc#12, crate#23, sibling issue bodies) says "`nge:` stays"; flag, do not edit.
- v1.1.0 is reserved for Al's release-loop test (sites.csv corrections he makes himself); the rename should ride with it rather than cut its own tag.

## Superseded in the issue context above

The issue text quoted above says each custom prefix gets a crate schema and that this catalogue's rebuild waits on a crate deploy. Decided otherwise at the plan gate: no prefix here meets crate's two-writers-or-outside-reader rule, so none gets a schema yet and the release waits on nothing in crate. The #38 body now says so.

## Plan review (Plan agent, 2026-10-10; delivered as reply text, read-only agent)

No blockers. Dispositions:

| finding | disposition |
|---|---|
| G1 build_item / additive guard wiring not in selftest | Phase 4 red runs: mutant with `proj` undeclared refuses at the first mirror item; additive run on real prod refused, prod JSONs unmodified (0 modified in last 2 h) |
| G2 code without name passes silently | `registry_problems()` refuses at build; selftest + mutant + mirror run with a blanked name all confirm |
| G3 prefix set restated in release check | already avoided: release check reads `FIELD_PREFIXES` via `ast`; comment now says the live check confirms, not gates |
| G4 refusal message omits tag + NEWS | message now names NEWS → tag → `catalogue_release.sh`; same note in `scripts/config/README.md` |
| G5 index.html not rendered; table must be static; filter eval=FALSE | table static, example `eval=FALSE` already; index.html now rendered too |
| O1 tif copied before refusal | refusal message and config README say the release publishes it, so its sites.csv row must exist |
| O2 publish blocked until release; do not tag on merge | PR body + report |
| O3 docs ahead of API | README + config README say `nge:` names until the release that ships #38; NEWS pairs also recorded in the v1.1.0 memory |
| A1/A2 mirror safety | `--base` explicit, 0 symlinked JSONs, 0 prod JSONs modified |
| A4 title check fragile | replaced by AC1 |
| AC1/AC2 diff mirror vs prod with mapping undone | 245 items, 0 differences in any key (geometry, datetime, proj, assets, links); collection differs only in `version`, links equal |
| S1 findings stale on crate | section above |
| S2 dict instead of set | declined: no schema URLs exist yet; becomes a dict when the first crate schema does |
| S3 CLAUDE.md no-op; publish header | CLAUDE.md now lists the fill script + guard; `dataset_publish.sh` header names the refusal |

## Errors Encountered

| Error | Resolution |
|-------|------------|
| `diff - file` in this shell printed git-diff usage (shell `diff` is a git wrapper) | `command cmp -s` for byte comparison |
