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
- Next: Phase 2 when the trial lands (settle the model, regenerate the table if it changes), then Phase 4's numbers
