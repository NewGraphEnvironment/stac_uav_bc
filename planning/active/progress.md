# Progress — Adopt stacs for registration and verification (#35)

## Session 2026-10-09

- Plan-mode exploration — phases approved by user ("go all phases to pr")
- Created branch `35-adopt-stacs-for-registration-and-verific` off main
- Scaffolded PWF baseline from issue #35 with approved phases
- Next: start Phase 1
- Phase 1: link fix + gate in item_create.py; prod tree rebuilt (links only, 245/245 resolve on S3)
- Phase 2: scripts/stacs.sh (v0.1.0 via uvx), stacs.toml, wiring proven by mutation; item_unregister.sh reads host/db from stacs.toml
- Phase 3: release/publish scripts on stacs; item_register.sh, collection_register.sh, item_validate.py deleted
- Phase 4: docs — config README (stacs section, recipes), README table, CLAUDE.md, NEWS Unreleased
- Phase 5: loopback verify IN SYNC 245/245, drift dryrun 0, positive control, ssh probe; plan review (11 findings) folded in — review-plan.md
