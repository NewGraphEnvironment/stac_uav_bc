# Code-check round 6 — branch `41-fit-each-flight-to-lidarbc-our-uav-eleva` vs `main` (merge-base ec6dd31)

Reviewed 2026-10-16 (UTC), fresh eyes over the whole diff through `82ac3f3` plus the full
contents of every changed code and doc file, against the repo's code-check conventions
(general, shell, R, spatial, Python) in full. Scope as briefed: round 5's three fixes first,
then the whole diff once more. Every probe ran read-only on the repo and the production trees
(both selftests, `--check` on prod and on the mirror, a name-derivation sweep over both trees)
or on copies of the mirror under `scratchpad/review/work/r6/`; nothing under `~/Projects/gis/`
was written and no publish or release script was run. `git status` clean at `82ac3f3` before
and after.

## Findings

No bug, security issue or data-loss path in a shipped code path. Round 5's three fixes hold
as written and were exercised mechanically (below). Three minor notes, none blocking, in
order of weight.

- **[fragile, minor]** `scripts/dataset_align-lidarbc.py:594-600` (the items arm's `items`
  set) against `scripts/item_create.py:443-446` (`--rebuild` builds an item for every
  `*.tif` that is not `.original.tif`) — the legitimate item names are derived from the
  literal `RASTERS` tuple, while the writer derives them from the tifs present. The two
  agree on every raster in prod and in the mirror today (measured: 83 datasets, 245 JSONs,
  245 names each way, 0 disagreements, the two root-level `ortho.tif` items included), and
  `dataset_publish.sh` can only add the three ODM products, so the only route to a
  disagreement is a hand-placed fourth raster under a dataset dir: the next release's
  rebuild writes its item and `--check` then reports that legitimate item as "not an item
  of this dataset's rasters: delete it", and the raster loop never compares it with the raw
  tree. Latent, loud, and the remedy is wrong only for a product nothing produces. The
  derivation that cannot drift is the writer's own: walk `pdir.rglob("*.tif")` (skipping
  `.original.tif`) and name each `"-".join(k + rel.parent.parts + (rel.stem,))`, and let the
  raster loop iterate the same set (`code-check.md`, "A guard's scope, escape hatches, and
  remedies": a literal set used as a filter covers whatever the data holds today).

- **[minor]** `scripts/dataset_align-lidarbc.py:601-604` — a hidden JSON under a dataset
  dir (`._<id>.json`, a dot-JSON) is reported as a leftover to delete (measured on a mirror
  copy), while both `aws s3 sync` calls exclude `*/.*` and `.*`, so such a file can never
  ship. The refusal is loud and the remedy (delete it) is harmless, so this is only the
  `stac_floodplains_bc#61` shape at its cheapest: a guard saying "this would reach the
  catalogue" without reading the shipper's exclusions. Prod holds no dot-JSON today (26
  dotfiles, none `.json`). Skip names beginning with `.` in the walk, or leave it, since a
  junk file under prod is worth deleting anyway.

- **[minor, doc]** `scripts/config/README.md:67` ("run steps 1–3 again") — step 1 is
  `odm_process-batch.sh`, which prints `SKIP (already processed)` and does nothing for a
  project that already has `odm_orthophoto/` (`scripts/odm_process-batch.sh:35-38`). Taken
  literally, the re-stitch recipe deletes the COG and prod copies, never re-stitches, refits
  the old cloud (same row), releases, and republishes the old rasters: nothing wrong ships
  and the SKIP line prints, so it costs a wasted release rather than a defect. The paragraph
  is new on this branch and should say to clear the project's ODM outputs (or run ODM by hand
  with the same `docker run`, per CLAUDE.md's resume rule) before step 1.

## Round 5's fixes, re-read against the code and the trees

- **(a) The items arm's derived names.** `item_create.py` names an item
  `"-".join(parts[:-1] + (stem,))` over the tif's path relative to the prod root and saves it
  beside the tif; the fitter names it `"-".join(k + tif.parent.parts + (tif.stem,))` and
  expects it at `pdir / tif.parent`. For `odm_dem/dtm.tif`, `odm_dem/dsm.tif` and
  `odm_orthophoto/odm_orthophoto.tif` the two are the same string at the same path. For the
  Maps Made Easy `ortho.tif`, `Path("ortho.tif").parent.parts` is `()` and
  `pdir / Path(".") / name` is `pdir / name` (measured), so the expected JSON sits at the
  dataset root beside `ortho.tif`, which is where `item_create.py` writes it. A direct sweep
  (`work/r6/names_probe.py`) over the real prod tree and over the mirror compared, per dataset
  dir, the JSONs present with both derivations: **0 of 83 datasets disagree**, 245 = 245 = 245.
  Membership is tested before the JSON is opened, so a malformed stray is reported rather
  than crashing the check. `--check --base <mirror2>`: `ALIGN CHECK OK: 83 rows` (16 s).
  `--check` on prod: 47 lines, **46** `does not carry the row's alignment: fields` (items
  built before #41), **0** `not an item`, 0 raster, 0 cloud lines, rc 1 — so no legitimate
  item in prod is misreported as a leftover. On a mirror copy, three planted leftovers were
  each reported with the delete remedy and nothing else: an `_OLD-ortho.json` at the root of
  a Maps Made Easy dataset (its legitimate `…-ortho.json` beside `ortho.tif` was not named),
  a `stray.json` in a nested `odm_dem/sub/` dir the walk reaches, and the dot-JSON above.
  One line per dataset with a `break` is fine: a leftover and a stale item in one dataset
  surface over two runs, each with the right remedy.

- **(b) The re-stitch recipe, run on a mirror copy** (`work/r6/restitch`, prod tifs
  symlinked, JSONs real): delete `skeena/bulkley/2025/bulkley_br5` (a fitted dataset;
  3 links in `collection.json`) → `item_create.py --rebuild --base <copy>`: `REBUILD: 242
  items from 242 tifs … 242 links; links OK` (39 s) → `--check --base <copy>`: OK (the
  dataset has no prod tif, so no "no row" line; its raw laz still matches its row) → put the
  three tifs back as the publish's COG copy would → `item_create.py <3 tifs> --base <copy>`
  (additive): `links_check` passes (the dropped links no longer name the deleted JSONs), the
  three ids are not in `existing`, `BUILT` ×3, `collection saved (245 item links)`, links OK
  → `--check --base <copy>`: OK. The rebuilt DTM item's ten `alignment:` fields equal the
  pre-deletion copy's (same row). So the local legs complete in the order the paragraph
  gives; the remote legs are the pre-existing pipeline's: `sync --delete` drops the
  dataset's objects at the release, `item_unregister.sh` (or `stacs verify` reporting the
  three ids orphaned, as the paragraph says) clears the API, and step 4's per-dataset sync,
  `register --mode drift` and `verify` put it back. The one gap is the step-1 skip in the
  third note.

- **(c) `CLAUDE.md:19`** now reads "`dataset_publish.sh` runs it first, `catalogue_release.sh`
  after its rebuild", which is what `scripts/dataset_publish.sh:47` and
  `scripts/catalogue_release.sh:34` do. `scripts/config/README.md:34` and `:72` say the
  same.

## The whole diff, once more

- Both gates on the branch tree: `conda run -n titiler python scripts/item_create.py
  --selftest` → `ITEM SELFTEST PASS`; `uv run scripts/dataset_align-lidarbc.py --selftest`
  → `ALIGN SELFTEST PASS` (66 s).
- `check_table`: the raster loop runs over `(COG, prod) × RASTERS` for every row before the
  cloud check; a row whose dataset dir is gone is skipped on every arm except the cloud one;
  a dataset in prod with no row is its own line. `item_fields` and `alignment_props` were
  compared over all 83 rows by round 5; the table is unchanged since.
- `item_create.py`: `alignment_props()` refuses an unreadable or non-finite fitted row
  before any write; the no-row refusal runs before the build loop in both modes and reads
  `published` as `build_item()` does; `FIELD_PREFIXES` carries `alignment`.
- Shell: both `uv run … --check || exit 1` lines are plain commands under `set -euo
  pipefail`; the embedded `python3 -c` programs carry no `"`, `` ` ``, `$` or `\`; the
  page-full guards are `sys.exit`; no `conda run` output is piped; no new absolute path
  beyond the ones the scripts already hardcode.
- Prod inventory for the claims above: 245 tifs (81 × dtm, dsm, odm_orthophoto; 2 × ortho),
  0 `.original.tif`, 246 JSONs (245 items + `collection.json`), 0 dot-JSONs; COG tree 242
  tifs, 0 `.original.tif`.
- Docs: README/NEWS/research numbers are the ones rounds 1–2 re-derived from the committed
  table, which round 5 confirmed unchanged; the round 5 commit touched only the fitter, the
  config README, CLAUDE.md and `planning/`.
- Probes and logs: `scratchpad/review/work/r6/` (`names_probe.py`, `check_prod.log`,
  `restitch_rebuild.log`, the `leftover` and `restitch` mirror copies).
