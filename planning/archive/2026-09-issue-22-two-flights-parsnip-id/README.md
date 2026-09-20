## Outcome

Published two new 2026 flights — Pedley Creek (cottonwood, the catalogue's first `COTR` dataset) and
the Parsnip post-replacement flight — and corrected a crossing-id typo on an already-published
dataset, which turned a routine additive release into a retraction + republish. Released as v1.0.2 at
236 items. The parsnip pair is the catalogue's first before/after at one crossing, which exposed that
item titles are built from stream name + year alone and so would have been identical for both
flights; `nge:alias` now feeds the title, and the two read `(moose pre-replacement)` /
`(moose post-replacement)`.

The durable lesson is that three separate silent-failure modes were sitting in the publish path, none
of which announces itself. `aws s3 sync` has no rename detection, so a renamed prefix is a delete plus
a full re-upload — 4.34 GB here, under `--only-show-errors`. `item_create.py --rebuild` never unlinks
a JSON whose id no longer matches, so a rename strands stale items that then sync to S3. And a
registry miss makes `item_create.py` fall back to the directory name as the title while emitting no
`nge:` properties at all — an item that looks fine and is wrong. The first two are now documented as a
renaming recipe in `scripts/config/README.md`; the third is now a release gate.

A Plan-subagent review of the task plan (per `conventions/planning.md`) found six issues, each
verified against the live system before acting — including one that would have destroyed the
in-flight ODM run, since `odm_process-batch.sh` skips only on `odm_orthophoto/` and an interrupted run
falls into its `rm -rf`. Worth noting the review was spawned *after* the baseline commit rather than
before it, contrary to the convention; it still caught everything, but earlier would have been cheaper.

## Measurement

- **Stitch** — pedley 10 min, 33/33 reconstructed, 0.131 px reprojection error, 1.66 cm GSD.
  Parsnip post 40 min, 83/84, 0.108 px, 4.84 cm GSD. The parsnip "miss" was a frame shot at 723 m
  altitude 2.5 min before a survey flown entirely at 1001 m — a climb-out shot, correctly excluded,
  so 83/83 of the real flight. 50 min total against a ~56 min benchmark for the 135-image original.
- **Catalogue** — 230 → 236 items. Mid-release it is transiently 239 (236 rebuilt + 3 stale not yet
  unregistered), which is why `EXPECT_ITEMS=236` could not be asserted on a release that also
  retracts; the `nge:` coverage guard ran instead (239/239) and 236 was asserted after the unregister.
- **Spatial extent, the pre-existing bug** — the advertised collection bbox had **21 items across 7
  datasets outside it** before pedley existed. Every kootenay dataset (Parker Creek 49.21°N, Hadow
  Creek 50.74°N) and four mackenzie peace/pine datasets above 55.6°N were unreachable by a
  bbox-filtered `rstac`/QGIS search, and had been since publication. `[-127.741, 53.830, -121.741,
  55.314]` → `[-127.741, 49.209, -114.529, 56.078]`. The review framed this as "pedley would be
  excluded"; pedley was only the first case anyone would trip over.
- **S3 rename** — 6 objects / 4.34 GB moved server-side at ~1.5 GiB/s, versus a delete-and-re-upload
  of the same volume over a home link had `sync --delete` been left to reconcile it.
- **Registry convention** — the id-prefix rule was exceptionless across all 81 prior rows (47
  id-set/prefixed, 34 id-empty/unprefixed). `pedley` was about to become the sole violation with a
  resolved id and no prefix; renamed to `198285_pedley_lake_creek_rd` after the stitch, at zero
  recompute, since ODM outputs are self-contained GeoTIFFs.
- **Alias blast radius** — exactly 6 of 236 live items carry a parenthesised alias, matching the 6
  carrying `nge:alias`, so no unaliased title moved.
- **Database facts** (local `fwapg`, no tunnel needed) — pedley: COTR, PSCIS 198285 "Pedley Creek",
  9.6 m. Parsnip: PARS, PSCIS 199663 "Tributary to Colbourne Creek", 77 m. `1996663` absent from the
  crossings table, confirming the typo.

## Evidence

Release and publish logs were session-scratch, not committed. Reproducible state is in the tag
`v1.0.2`, `NEWS.md`, and the live API (`https://images.a11s.one/collections/imagery-uav-bc-prod`).

## Carried forward

- **#23** — every `item` link in the published `collection.json` is dead (230/230 at the time, flat
  `<id>/<id>.json` rather than the dataset path). Pre-existing, unrelated, filed separately.
- **v1.1.0** — the parsnip `stream_name` remains the pending guess "Tributary to Parsnip River"
  though PSCIS says "Tributary to Colbourne Creek". Correcting only the new row would have split the
  pair across two stream names; both rows' notes flag it so v1.1.0 fixes them together.
- `odm_process-batch.sh` passes no `--platform` to `docker run`. Unreproduced; noted, not filed.

Closed by: PR #24
