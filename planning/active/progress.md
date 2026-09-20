# Progress — Process, publish and register two new 2026 flights (#22)

## Session 2026-09-20

- Explored the pipeline: `item_create.py` registry join + title construction + `--rebuild` semantics, `dataset_publish.sh` / `catalogue_release.sh` sync behaviour
- Identified the two new flights and established the parsnip one is a repeat of a published site (8 m from the 2026-07-14 original)
- Settled three decisions on #22 and rewrote the issue body so plan-init runs clean: alias-in-title, fix the `1996663` typo on both sides, release as v1.0.2
- Cleared the #18 retraction dependency gate (no external references to the parsnip URLs)
- Created branch `22-process-publish-and-register-two-new-202` off main
- Scaffolded PWF baseline with approved phases
- Next: Phase 2 dir renames, then start the ODM stitch in background while Phases 0/1/3 proceed

## Session 2026-09-20 (cont.) — released v1.0.2

- Stitch: pedley 10 min (33/33, 0.131 px, 1.66 cm GSD), parsnip post 40 min (83/84, 0.108 px,
  4.84 cm GSD). The parsnip miss was a 723 m climb-out frame shot 2.5 min before a survey flown
  entirely at 1001 m — correctly excluded, so 83/83 of the real flight.
- Published both; 6 items live, no in-band errors.
- Released v1.0.2: rebuild 236 items from 236 tifs, validate 237, register, tag pushed to origin.
- Unregistered the 3 old `1996663` ids AFTER the rebuild had the renamed ids live (#18 ordering).
- Verified: v1.0.2 live, 236 items, registry coverage 236/236, 0 stale ids, old ids 404 / new 200,
  old S3 prefix empty, parsnip `stream_name` untouched.
- The pair now titles distinctly:
  `Tributary to Parsnip River (moose pre-replacement) — 2026 orthophoto` /
  `… (moose post-replacement) — …`. Exactly 6 of 236 items carry a parenthesised alias, matching
  the 6 that carry `nge:alias` — so no unaliased title moved.
- Next: archive PWF, open the PR.
