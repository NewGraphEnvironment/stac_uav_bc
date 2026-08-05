# Progress — Retraction flow (#18)

## Session 2026-08-05

- Phases approved via plan mode (v1.0.1 patch vehicle; round-trip test gate before deletion)
- Archived #16 PWF (Phase 4 → rtj#200)
- Created branch `18-retraction-flow-item-unregister-sh-publi`
- Next: Phase 1 (item_unregister.sh + round-trip)
- Phase 1: item_unregister.sh built; round-trip test passed (200→404→idempotent warn→200)
- Phase 2: nechacko kenneth retracted (CSV flip, trees, S3 6 objects, 3 API items); v1.0.1 released — live version 1.0.1, 230 items, nechacko 404 / morkill 200
- Phase 3: retraction recipe documented; PR next
- PR #19 merged (0c933a2), tag v1.0.1 reachable from main, pages green. Archiving.
