## Outcome

Item properties move off `nge:` to prefixes that say what each field describes: `newgraph:region`, `newgraph:alias` and `newgraph:project` (New Graph is the subject); `uav:stream_name`, `_02` and `_03` (the registry's pick, from PSCIS, bcfishpass, the atlas or a guess); `fwa:watershed_group_code`, plus a new `fwa:watershed_group_name` (the atlas's own name, from a new `data/sites.csv` column filled by `scripts/sites_fill-wsg_name.py`); and `bcfishpass:aggregated_crossings_id`. `nge:watershed_group` is dropped: it held the tree's directory slug, which is in the item id.

`item_create.py` declares `FIELD_PREFIXES` and refuses any other. It refuses a registry whose code and name disagree, and it builds every item before saving any. Additive mode refuses while the prod tree still holds `nge:` items. `dataset_publish.sh` audits the whole tree before any upload. Nothing was published: the rename rides with the next full `catalogue_release.sh` (v1.1.0), whose NEWS entry must list the old → new pairs.

What was learned:

- Two of the issue's proposed rows did not survive a check against the data. `nge:watershed_group` was a slug, not an atlas name, and the stream names come from mixed sources (24 PSCIS, 54 bcfishpass or atlas, 5 guesses, 1 by hand).
- **Atlas watershed group names are not unique.** `SALM` and `SALR` are both "Salmon River". Code → name is a function, not a bijection, and a guard written on the bijection belief would have blocked every build (code-check round 2).
- `newgraph:` replaced the family's "`nge:` stays where NGE is the subject". That is the user's call at the plan gate, and it is still to be reflected in crate#23 and stac_pointcloud_bc#12.

## Measurement

- **Offline mirror of the prod tree** (real directories, 245 symlinked tifs, copied JSONs):
  - The rebuild gives 245 items. With the rename undone, each equals its prod JSON in every key: geometry, datetime, `proj:*`, assets and links.
  - `collection.json` differs only in `version`.
  - `stacs validate`: 246 validated, 0 invalid. `audit --expect 245`: OK.
- **Fill script:** 17 codes and 84 rows filled. The diff is column-only (87 lines, 0 mismatches), and a re-run reports 0 changes.
- **Atlas:** 246 groups, 246 unique codes, one repeated name (round 3).
- **Release live check,** run against the live API: 245 `nge:` items, refused. A clean synthetic input passes, and a synthetic stray `nge:alias` is refused.
- **Guards, each with its defect restored:** the selftest goes red for each, a late refusal leaves the mirror byte-identical, and a stray JSON fails the new publish audit.
- **Review:** 1 plan review and 4 code-check rounds, 6 reviewer agents in all. Rounds 2 and 3 each found a defect inside the previous fix. The loop ended by enumeration: round 3 mapped what the atlas guarantees, and round 4 listed every exit against every write.

Closed by: PR for #38 (branch `38-move-the-nge-item-fields-to-standard-or`)
