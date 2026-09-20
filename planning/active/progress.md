# Progress — Process, publish and register two new 2026 flights (#22)

## Session 2026-09-20

- Explored the pipeline: `item_create.py` registry join + title construction + `--rebuild` semantics, `dataset_publish.sh` / `catalogue_release.sh` sync behaviour
- Identified the two new flights and established the parsnip one is a repeat of a published site (8 m from the 2026-07-14 original)
- Settled three decisions on #22 and rewrote the issue body so plan-init runs clean: alias-in-title, fix the `1996663` typo on both sides, release as v1.0.2
- Cleared the #18 retraction dependency gate (no external references to the parsnip URLs)
- Created branch `22-process-publish-and-register-two-new-202` off main
- Scaffolded PWF baseline with approved phases
- Next: Phase 2 dir renames, then start the ODM stitch in background while Phases 0/1/3 proceed
