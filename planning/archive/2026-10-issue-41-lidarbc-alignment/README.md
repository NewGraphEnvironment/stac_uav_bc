# #41 — Fit each flight to LidarBC: our UAV elevations are off by the drone's GPS altitude

## Outcome

Every published dataset is now fitted to the LidarBC 1 m DEM by `scripts/dataset_align-lidarbc.py`
(a horizontal shift and a quadratic correction surface, Huber-fitted to ODM's class-2 ground,
the shift searched twice on disjoint samples and refused when the two disagree), one row per
dataset in `data/alignment_lidarbc.csv`, and `item_create.py` carries a fitted row on all three
items of the dataset as `alignment:` fields; the rasters are published as they are. The model was
settled by a trial of every model × mask on every dataset: the quadratic halves the plane's misfit
and the masks are a tie. The branch review (six rounds) turned `--check` into the tie between the
table and everything downstream of it: the raw cloud (count, date, size), every published and
COG-tree raster (grid and data-bearing windows against the raw tree), and every item (read back
against its row); `dataset_publish.sh` runs it first and `catalogue_release.sh` after its rebuild,
so a re-stitch or a re-fit is a release, never a publish. What was learned: a held-out spatial
split biases the shift search on a GPS-only reconstruction (dropped); the published DSM and DTM
of 16 datasets sit on grids a column or a centimetre apart; and a guard between two copies of an
artifact, built through a proxy, closes the pair in front of it and leaves the next copy open,
which is why the review ran until the chain of copies was enumerated and checked twice. The
durable verdict is in [`research/uav_pointclouds.md`](../../../research/uav_pointclouds.md)
("Alignment in the pipeline"). Nothing is published by the PR: the fields go live with the next
`catalogue_release.sh`, which also carries #38, and until then `--check` holds every publish.

## Measurement

Over the 83 published datasets: 46 fitted, 3 refused (two shift searches 2.6 and 5.6 m apart; one
delivery covering 27 %), 31 with no LidarBC under them, 3 with no ODM cloud. Raw vertical offset
of the fitted: median 8.3 m in size (signed +5.8; −97 to +92 m); horizontal shift median 3.2 m
(up to 12.4 m). Misfit (NMAD over every ground point compared) after the quadratic fit: median
**0.42 m** (quartiles 0.32–0.69), 42 of 46 within 1 m, 26 within 0.5 m, against the research's
0.82 m with a plane; the plane run of the pipeline reproduced the research on the same datasets
(0.79 m, same 28 and 12 within 1 and 0.5 m, raw offsets within 0.03 m). The trial: the quadratic
lowers the plane's misfit on 42 of 44 datasets by a median of 0.225 m (0.78 → 0.42); the slope,
open and slope+open masks move the quadratic's median by 0.000, −0.006 and −0.006 m, so the
default is quadratic with no mask. The one dataset a mask rescues (`197912_roberthatch`, 0.15 m
with `open`) is refused in the table. Wrong turns kept: the first full run fitted on a 50 m
checkerboard and scored on the other half, which biased the search (`sandstone_mcdonell` 0.56 m
on the fit's own sample, 2.65 m on every point) and was dropped; a 1 m spread cut refused ten
flat sites, and the cut was set to 2 m from the measured gap of the plane run (the quadratic's
spreads are not as cleanly split: 1.95 m fitted, 2.6 m refused); the `open` mask was first refused
on 16 datasets by an exact-grid check. The review's measurements: on `bulkley_dickson` the raster
windows drawn over the bounding box compared 0 valid cells and passed a copy raised 1 m; drawn
where the data is, 20 480 cells, and the copy is reported; the fewest cells compared over all 243
published rasters is 16 314. `--check` over both trees and 245 items: 17 s.

## Evidence

`data/alignment_lidarbc.csv` (the table), `research/uav_pointclouds/trials/grid.csv` (every model ×
mask per dataset), `findings.md` and `review-round*.md` here (the runs, the probe tables, the gates
with each defect restored, the review rounds and the chain they enumerated).

Closed by: the PR from branch `41-fit-each-flight-to-lidarbc-our-uav-eleva` (final review commit
1f382c8, archive commit after it). #41 itself closes at the release that publishes the fields.
