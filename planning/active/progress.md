# Progress — Rename the collection to stac-imagery-uav-bc (#48)

## Session 2026-10-16

- Plan-mode exploration — phases approved by Al; cutover runs in this session; his saved
  `data/sites.csv` edits ride in v2.0.0
- Created branch `48-rename-the-collection-to-stac-imagery-ua` off main
- Scaffolded PWF baseline from issue #48 with approved phases
- Phase 0 baseline verify of the old id: IN SYNC 245 (19:50Z), log under `evidence/`
- Next: Phase 0 (commit sites.csv, record findings, file the viewer.html issue), then Phase 1
- Phase 0: committed Al's eight `sites.csv` stream-name corrections (booleans, CRLF and trailing
  newline restored so the diff is the eight rows); `item_create.py --selftest` PASS
- Phase 1: `stacs.toml` names `stac-imagery-uav-bc`; `item_create.py` stamps id + title from it on
  `--rebuild` and refuses a mismatched tree in additive mode (selftest + stamp-dropped mutant red
  on 4 checks); `dataset_publish.sh` asks before the COG step. Mirror rebuild: 0 files name the
  old id, 246 the new; validate 246/0; audit OK on the new id; diff vs prod as predicted. Log under
  `evidence/20261016_mirror_rebuild_new_id.log`
- Phase 2: `scripts/config/collection_unregister.sh` (report mode, `--yes`, `--selftest` with 11
  stubbed cases; guard-dropped mutant red on the configured-id case; real report mode: old id 245,
  nothing deleted, configured id refused); `item_unregister.sh` verify line from `stacs.toml`;
  config README gotcha + "Renaming the collection" recipe; CLAUDE.md line
- Phase 3: README.Rmd (new id in the prose and the three searches, QGIS note, figure caption,
  scripts table), qmd and research doc, NEWS v2.0.0 entry (rename, #38 pairs, registry
  corrections, #41). README.md and index.html render after the cutover
- Draft PR #50 opened (phases 4–6 pending); round 1 of `/code-check branch` spawned 20:05Z
- Round 1 (4 findings, all fixed, see findings): delete_item gets the collection; containment guard; sticky-stub selftest cases (15); api_status 000
