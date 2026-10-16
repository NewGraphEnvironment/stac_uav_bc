# Branch review round 7: `alignment:applied` (#41, PR #45)

Reviewed 2026-10-16. Scope: the `alignment:applied` follow-up. It was handed over as an
uncommitted working-tree diff (`scratchpad/review/diff_applied.patch`, written 07:44 PDT) and
was committed as `65ff0e4` at 07:46 PDT while this review ran; the commit's diff equals the
patch byte for byte (index lines aside), so the findings apply to `65ff0e4`.

## Findings

- **[severity: fragile]** `README.Rmd:179`, `NEWS.md:22` (and the renders `README.md:43`,
  `index.html:3588`) — "`alignment:applied` is `false` on every item" / "`false` on every
  item" is a false quantifier. Measured on the prod tree against `data/alignment_lidarbc.csv`:
  245 items, of which 138 belong to the 46 fitted datasets and will carry the field; the
  other 107 (37 datasets: 31 `no_reference`, 3 refused, 3 `no_cloud`) carry no `alignment:`
  field at all, `applied` included. #46's own acceptance text has it right ("every other item
  either `false` with its fields or no fields"), and the README table row is right. A reader
  who filters `alignment:applied = false` expecting the whole catalogue gets 138 of 245. The
  sentence before each occurrence does say those datasets carry no fields, so the context
  qualifies it; the sentence itself does not. Wording only ("on every item that carries the
  fields", or "on every fitted dataset's items"); the Rmd fix needs a re-render into
  `README.md` and `index.html`, and `NEWS.md` is a separate copy.

Nothing else. Everything below was checked and holds.

## The chain, walked for the new field

table (no column; a constant) -> `item_create.py` -> prod items -> `--check` -> S3 -> API

| link | what carries `applied` | blind? |
|---|---|---|
| `alignment_props` (`item_create.py:161`) | writes `False` after the numeric join, before the finiteness check | no |
| prod items | pystac `save_object` -> `json.dumps` -> `"alignment:applied": false`; `json.load` -> `False`, `type` `bool` (probed) | no |
| `check_table` (`dataset_align-lidarbc.py:636-649`) | `have` = every `alignment:` key on the item, compared whole-dict to `item_fields(row)`, which restates `False` | no: an item without the key, or with `true`, `"false"`, `1`, `None`, is reported (probed) |
| `dataset_publish.sh` | runs `--check` before building, so the hold on pre-`applied` items is the documented one (`scripts/config/README.md:34`) | no |
| `catalogue_release.sh:35` | runs `--check` after the rebuild, so it reads the items this release wrote | no |
| `aws s3 sync` | size + mtime; the new key adds bytes and the rebuild sets a new mtime | no |
| `stacs verify` (v0.1.0, `verify.py:240-304`) | JCS digest of the whole body minus `links`, published S3 body against the API body; `_canonical` converts only `type(x) is int` beyond 2^53, so a bool is never folded into a number | no |
| `catalogue_release.sh:124-150` live arm | presence of `alignment:reference` only; does not look at `applied` | by itself yes, but it is a proxy over a link `stacs verify` already closes by digest; accepted design from round 4 |

No link is blind to the field.

## Probes

- **JSON round trip.** `json.dumps({"alignment:applied": False})` -> `false` -> `json.loads`
  -> `False`, `bool`; equal to `item_fields`' value.
- **`False == 0.0`.** `{"alignment:applied": 0} == {"alignment:applied": False}` is `True`, and
  so is `0.0`; `1`, `True`, `"false"` and `None` are unequal. So `check_table` would pass an
  item carrying `0` or `0.0`. No writer in the repo can produce one: the only item writer is
  `alignment_props` -> pystac -> `json.dumps`, which writes `false`, and stacs' canonicaliser
  keeps bools apart from ints. Not a finding today. Forward note for #46, which will read
  `applied` from a GDAL metadata tag (a string): if that reader ever writes `0`/`1`, `--check`
  will not see it; a string (`"true"`) it will.
- **Finiteness check** (`item_create.py:164`): `[v for v in props.values() if isinstance(v, float)]`
  skips the bool (`isinstance(False, float)` is `False`) and still lists every float; probed with
  a NaN beside the bool, the NaN is seen.
- **Selftest fixture order** (`dataset_align-lidarbc.py:946-957`): full fields -> clean; fields
  minus `applied` -> reported; full fields rewritten (line 954) -> then `misfit_m` changed ->
  reported. The item holds the pre-change row when the misfit check runs, which is what that
  check assumes.
- **Mutation, in copies under `scratchpad/review/round7/`.** Controls pass (`uv run` and
  `conda run -n titiler`). With the one `applied` assignment removed:
  `align_mutant.py --selftest` -> `ALIGN SELFTEST FAILED: 1 check(s): --check blind to an item
  built before alignment:applied existed`, rc 1; `item_mutant.py --selftest` -> `ITEM SELFTEST
  FAILED: 1 check(s): alignment_props: got {... no applied}, want {... 'alignment:applied': False}`,
  rc 1. Both guards fire.
- **Renders.** `README.md` carries the Rmd paragraph and table row verbatim (pandoc's `\#46`
  renders as `#46` in GFM). `index.html` carries both; its other change is the DT widget id
  (`htmlwidget-f06c05…` -> `htmlwidget-0d4953…`), and the two 84,216-char widget payloads are
  identical after masking the id, so no table data moved.
- **Docs against the issues.** `item_create.py:156-160` ("#46 … sets this true per dataset, read
  from the corrected raster; … the table has no column for it") matches #46 Scope 2 and Decided
  ("the tag is the one source; the table does not repeat it"). `dataset_align-lidarbc.py:606-607`
  matches. README table row "`true` (after #46): the fit was applied to the published raster"
  matches #46 "Replace, not add". `research/uav_pointclouds.md:126-127` ("#42 then publishes the
  clouds the same way") matches #42 Decided (placement by #46's transform; follows #46).
  `NEWS.md:22-23` matches. `scripts/config/README.md` has no `applied` mention and needs none
  until #46 changes a recipe.

## Checklist items applied

Serialization loses meaning silently (bool round trip: holds); a proxy is not the property
(the live arm, closed by verify's digest); restore the bug and prove the guard fires (both
mutants red); a fixture that cannot reach the failure mode (the stale fixture is the real
pre-`applied` item shape, the one the prod tree holds today); documents that share an
ancestor corroborate nothing (the "every item" sentence is one Rmd source rendered twice plus
a NEWS copy, which is the finding); regenerated binaries churn git (the widget id, confirmed
data-identical).
