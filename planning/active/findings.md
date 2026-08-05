# Findings — Retraction flow (#18)

## Issue context

## Problem

The registry's `published=false` flag excludes datasets from rebuilds but does nothing to items already live — there is no retraction path. First real case: `fraser/nechacko/2024/199256_kenneth_hwy16` is mis-filed (Kenneth Creek is in MORK/Morkill; the correctly-filed `fraser/morkill` copy is now published). The nechacko copy must be retracted — but its viewer URL is embedded in the published Fraser 2023 report, so retraction is blocked until the report is rebuilt against the morkill URL.

## Proposed Solution

1. `scripts/config/item_unregister.sh <item-id>...` — delete items from pgstac over SSH (`pgstac.delete_item`), sibling to `item_register.sh`
2. Retraction recipe wired to the registry: flipping a row to `published=false` + release = items deleted from the API, S3 prefix removed, prod-tree dir removed, collection links rebuilt (already handled by `--rebuild`)
3. Apply to the kenneth nechacko copy **after** the Fraser 2023 report rebuild deploys (see report issue), ideally in the v1.1.0 release
4. Document in the recipe README

## Sequencing

- [x] Publish `fraser/morkill/2024/199256_kenneth_hwy16` (done — live)
- [x] Fraser 2023 report URL swap + rebuild deployed (PR fish_passage_fraser_2023_reporting#161, live-verified 2026-08-05)
- [ ] `item_unregister.sh` built
- [ ] Retract nechacko copy (items + S3 + prod tree), flip row `published=false`


