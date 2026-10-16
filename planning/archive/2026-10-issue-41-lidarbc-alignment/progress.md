# Progress — Fit each flight to LidarBC: our UAV elevations are off by the drone's GPS altitude (#41)

## Session 2026-10-15

- Plan-mode exploration — phases approved by user; the four stored-data forks (what the catalogue carries, the prefix, the 31 flights off LidarBC, the order against #44) all took the recommended option
- Merged #44 (research doc and probes) by merge commit, untagged
- Created branch `41-fit-each-flight-to-lidarbc-our-uav-eleva` off main
- Scaffolded PWF baseline from issue #41 with approved phases
- A Plan reviewer was spawned during plan mode; its findings fold in when they land

## Session 2026-10-16

- Plan review landed (30 findings); 17 adopted before the first full run (findings.md)
- `scripts/dataset_align-lidarbc.py` written: selftest green; 11 guard mutants red, nearest-cell sampling green (not a guard)
- `scripts/item_create.py` join: selftest green; 4 mutants red
- First full run (checkerboard held-out): 37 fitted, 12 refused; probe showed the checkerboard biased the search (findings.md); dropped, fit on every point
- Second run with the spread cut lifted: 47 fitted, reproduces the research (0.79 vs 0.82 m); cut set to 2 m from the measured gap
- Offline mirror rebuild against a no-fit control: validate 246/0, audit OK, fields only where fitted and identical across a dataset's items
- Production run (plane, 2 m cut): 45 fitted, 4 refused, 31 no_reference, 3 no_cloud; `--check` OK
- Phase 1 committed (script, table); Phase 3 committed (item join, release and publish gates)
- The trial grid runs (resumed after a print bug on a refused dataset's row)
- Trial grid landed (1 h 50 min): the quadratic wins by 0.225 m on 42 of 44; the masks are a tie; 16 datasets re-run after the `open` mask's exact-grid refusal was replaced by per-raster sampling (the re-run reproduced the first pass)
- Default set to `quadratic`/`none`; selftest green, 12 guards red again (and a 13th for the grid refusal); production table regenerated (46 fitted, median 0.42 m); `--check` OK; mirror rebuild validated, audited and checked against the control
- Phase 4 docs filled from the table (`fill_numbers.py`), README re-rendered, issue body edited
- Phase 2 and Phase 4 committed
- `/code-check branch`: six rounds (7b122ef, 134202d, a711b19, 242f0b4, 82ac3f3, and the round-6 commit). Rounds 2–4 each found a defect inside the previous round's fix, all the same mechanism (a tie between two adjacent copies through a proxy that left the next copy open); `--check` now ties the table to the raw cloud (count, date, size), every published and COG-tree raster to the raw tree (data-bearing windows with a floor), and every item to its row, and both publish scripts run it. The chain was enumerated and checked by two rounds; round 6 found nothing real
- Next: `/planning-archive`, `/gh-pr-push`
