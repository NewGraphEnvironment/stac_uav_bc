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
- Round 2 (5 findings, 2 inside round 1's fixes, all fixed): api_status 000 (not 000000); item_unregister.sh --collection + the drop's refusal names the ids; direction-aware stub; verdict flag under bash 3.2; private repo names out of the planning files
- Round 3 (mechanism: guards keyed on a surrogate; 2 findings + 1 wording, fixed): item_unregister.sh option loop and -* refusal (ssh-shim measured); row-count numeric case under --yes; NEWS: /search on the old id answers 200 with no features. Loop ended by enumeration: 19 guard mutants red, every $(...) guarded
- Phase 4: cutover RELEASE COMPLETE v2.0.0 (20:58Z); hand checks 245/245, tile 200; README rendered from the new collection; issue body rewritten; 13 sweep PRs opened (21:00Z)
- Phase 5: 13 PRs open and MERGEABLE/CLEAN; template gate 245 on the new id; gh pr merge refused by the auto-mode classifier (merge without review): Al merges, then Phase 6
- Phase 6 (2026-10-17): Al merged the remaining PRs (last at 00:50Z); gate re-measured in the
  foreground (13 MERGED, clone-and-grep clean outside rendered output/logs/archives, the second
  talk repo's branch already changed, QGIS m4 332/0 + m1 141/0); drop: report 245 → `--yes`
  deleted 245, API 404 (00:53Z); after: new id 2.0.0, verify IN SYNC 245, nothing to do, tile 200,
  rstac 245; drop date into NEWS and the issue body. Next: `/planning-archive`, PR #50 ready,
  merge, release commit + tag v2.0.0 on main, close #38 #41 #48
