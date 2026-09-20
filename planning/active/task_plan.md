# Task: Process, publish and register two new 2026 flights: cottonwood/pedley and parsnip post-replacement (#22)

Two flights landed in `/Users/airvine/Projects/gis/uav_imagery` on 2026-09-20 as raw JPG sets with no ODM output. They need the full add-imagery path: registry rows -> stitch -> QC -> publish -> release.

Neither is a mechanical add. **Cottonwood is a new watershed group** — no `cottonwood` row in `data/sites.csv`, its FWA code nowhere in the registry, and `pedley` carries no crossing-id prefix. **The parsnip flight is a repeat of a published site** — the original (2026-07-14, 135 images) sits 8 m away at 55.001328, -122.758852, so this is a before/after culvert-replacement pair, both in year 2026.

Decisions are settled in the issue body (alias-in-title, fix the `1996663` typo on both sides, release as v1.0.2). Nothing here needs re-litigating.

Branch: `22-process-publish-and-register-two-new-202`

## Phase 0 — Establish registry facts (read-only; the only open unknowns)

- [x] Resolve the Cottonwood FWA watershed group code for 53.383799, -122.555596 against fwapg/bcfishpass (`/db-newgraph`)
- [x] Resolve `pedley`: `aggregated_crossings_id` and gazetted stream name if a crossing exists; otherwise an explicit `guess_*`/`user` `name_source` plus note, per the `wedzin_*` row pattern
- [x] Confirm `199663` is the correct aggregated id for the parsnip crossing
- [x] Record values and the queries used in `findings.md`

## Phase 1 — Alias in the item title

- [x] `scripts/item_create.py:94` — when `nge:alias` is set, title becomes `"{stream} ({alias}) — {year} {product}"`
- [x] Unit-check the title expression in isolation: aliased rows gain `(alias)`, unaliased are unchanged
- [ ] At release, snapshot the prod JSONs, run `--rebuild`, and diff — expect **only** the 3 renamed
      parsnip paths to move and no other item's title to change (the isolation check above does not
      prove this, and byte-identity also rests on gdal/pystac/rio_stac being unchanged since the
      2026-08-05 rebuild, which nothing pins)

## Phase 2 — Correct the parsnip id (`1996663` -> `199663`)

Order matters — stale JSONs go before any sync.

- [x] Record the dependency-gate evidence in `findings.md` (#18 requires it before retracting)
- [x] Rename the dataset dir in all three trees: raw `uav_imagery/`, COG `imagery_uav_bc/`, prod `stac/prod/imagery_uav_bc/`
- [x] Delete the 3 stale `...-1996663_...json` files from the renamed prod dir
- [x] Rename the new dir to `199663_parsnip_trib_chco_11000_post_replacement`
- [x] `data/sites.csv:17`: `item` -> `199663_parsnip_trib_chco_11000`, `alias` -> `moose pre-replacement`, note the id correction; **leave `stream_name` alone** (v1.1.0's job)
- [x] `aws s3 mv --recursive` the old S3 prefix to the new one — **server-side, before any sync.**
      `aws s3 sync` has no rename detection: it would have deleted 4.34 GB of TIFs at the old prefix
      and re-uploaded them from local under `--only-show-errors`, silently, over the home link.
- [ ] _(moved to Phase 7)_ the old-id unregister — doing it here would take the pre-replacement site
      dark from now until the release clears the unbounded human QC gate. #18 published the
      replacement first, then retracted, minutes apart.

## Phase 3 — Registry rows for the two new flights

- [x] `fraser,cottonwood,<WSG>,2026,pedley,...` using Phase 0 values
- [x] `mackenzie,parsnip,PARS,2026,199663_parsnip_trib_chco_11000_post_replacement,199663,...`, alias `moose post-replacement`
- [x] Confirm each `(region, watershed, year, item)` key matches its directory path exactly — a mismatch publishes silently wrong

## Phase 4 — Stitch

- [ ] `caffeinate -s scripts/odm_process-batch.sh <pedley> <parsnip post-replacement>` (no `--split`)
- [ ] **Never re-run the batch script to resume.** Its skip guard is `odm_orthophoto/`
      (`odm_process-batch.sh:35`), which an interrupted run has not written yet, so it falls through to
      the `rm -rf "$proj"/opensfm "$proj"/odm_* …` at `:41` and destroys the very state you meant to
      resume. Both dirs are in one invocation, so a second batch call aimed at the parsnip dir would
      wipe pedley. Resume with the `docker run` at `:47` directly:
      ```
      docker run --rm -v <parent-of-project-dir>:/datasets opendronemap/odm \
        --project-path /datasets/ <project-name> --dtm --dsm --pc-quality low --dem-resolution 5
      ```

## Phase 5 — QC gate (human)

**Never gate this on the batch script's exit code.** `odm_process-batch.sh` runs `set -u` only and
captures `ec=$?` at `:54` purely to echo it — the loop continues and the script's final `echo` returns
0 whether or not ODM failed. Gate on artifacts instead.

- [x] pedley — all 3 TIFs + `odm_report/stats.json` present; 33/33 reconstructed, 0.131 px, 1.66 cm GSD;
      the 32 error-matching log lines are all DEBUG pairwise match failures between non-overlapping frames
- [ ] parsnip post-replacement — same artifact + stats check
- [x] Eyeball pedley ortho (sent to user; crossing and riprap sharp, margin smearing is normal corridor edge)
- [ ] Eyeball parsnip ortho

## Phase 6 — Publish

- [ ] `scripts/dataset_publish.sh <pedley> <parsnip post-replacement>`
- [ ] Confirm the 6 new items return 200, and the parsnip pair's titles carry their aliases

## Phase 7 — Release v1.0.2

- [ ] `NEWS.md`: two new datasets, the parsnip id correction, the alias-in-title change
- [ ] `git tag v1.0.2`; `scripts/catalogue_release.sh` — the `--rebuild` writes the 3 renamed-parsnip
      items under their new ids and registers them
- [ ] **Immediately after**, `scripts/config/item_unregister.sh` the 3 old `...-1996663_...` ids, so the
      new ids are already live before the old ones go (#18 ordering); confirm 404
- [ ] `git push origin v1.0.2` — v1.0.0/v1.0.1 are on origin; a local-only tag strands the release marker
- [ ] Verify live version `1.0.2`, 236 items, pre/post titles now differ
- [ ] Verify the collection `extent.spatial.bbox` now contains pedley (53.3838 was below the old south
      edge of 53.8303 — nothing recomputed spatial before this change)

## Phase 8 — Document and close

- [ ] `scripts/config/README.md`: the repeat-flight convention (alias disambiguates the title)
- [ ] `/planning-archive`, then `/gh-pr-push` (closes #22)

## Validation

- [ ] `/code-check` clean on each commit
- [ ] PWF checkboxes match landed work
- [ ] Old `1996663` ids 404; new `199663` ids 200
- [x] Old S3 prefix empty — verified after the `aws s3 mv`, as an explicit step rather than an implied
      side effect of a later sync (#18 treats it the same way)
- [ ] `EXPECT_ITEMS=236 scripts/catalogue_release.sh` — the count is now asserted, not just printed,
      and every live item is checked for `nge:` properties so a silent registry miss fails the release
- [ ] Catalogue at 236 items, live version 1.0.2
- [ ] Parsnip row `stream_name` untouched, so v1.1.0 still has its test
- [ ] `/planning-archive` on completion
