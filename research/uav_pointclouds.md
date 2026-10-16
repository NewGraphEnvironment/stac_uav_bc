# UAV point clouds: what we have, how far off they sit, and where the value is

**Verified:** 2026-10-16 · **Issues:** spawned #41 (alignment), #42 (COPC publishing), #43 (change
detection); added in #44 · **Produced by:** the probes in
[`uav_pointclouds/`](uav_pointclouds/) (each says what it reads), run over the raw imagery tree;
per-flight numbers in [`uav_pointclouds/uav_lidarbc_offsets.csv`](uav_pointclouds/uav_lidarbc_offsets.csv)

The question was whether our UAV point clouds are worth putting in a STAC, whether they line up with
LidarBC, and whether any of it supports change-over-time analysis. Short answers: the clouds are cheap
to publish but are not where the value starts; they do **not** line up with LidarBC as they stand, and
neither do the DTMs and DSMs already in this catalogue; a simple fit against LidarBC brings about half
of them within a metre, which is enough for large changes and not for small ones.

## What we have

| | ODM (`odm_georeferencing/odm_georeferenced_model.laz`) | Maps Made Easy (`mme/*.las`) |
|---|---|---|
| files | 83, one per processed flight (4 more are `--split` submodels) | 15, older flights processed outside ODM |
| format | LAS 1.2, point format 3, RGB | LAS 1.2, point format 2, RGB |
| classes | 1, 2, 3, 6 (ODM's own classifier; one file has class 1 only) | none (all class 0) |
| density, points over bbox area | median 52 pts/m², 2.5–256 | median 96 pts/m², 42–441 |
| CRS | WGS 84 / UTM 9N, 10N, 11N; **no vertical CRS** | same |

About 12 GB and 1.3 billion points in all. ODM runs at `--pc-quality low` (`odm_process-batch.sh`).
**No flight used ground control**: all 80 `odm_report/stats.json` report `has_gcp: false`, and no
`gcp_list.txt` exists in the tree, so each cloud is placed by the drone's own GPS. Photogrammetry gives
one surface per point, so nothing sees under canopy; in dense forest ODM's class 2 can only be the
lowest surface the cameras saw.

52 of the 83 ODM clouds, and 9 of the 15 Maps Made Easy clouds, fall on a LidarBC 1 m DEM (searched by
bounding box in `stac-elevation-bc`). The 31 that do not are mostly in the Morice (all of 2021, 2023
and the 2026 Wedzin Kwa reaches) and the upper Parsnip (2022–2024).

## How far off they sit

For each cloud on a LidarBC DEM (the newest delivery under it), ground points were compared with the
DEM (`uav_lidar_align.py`). The model is the cheapest one that could explain a GPS-only
reconstruction: a horizontal shift, a vertical offset and a tilt, fitted robustly.

![Vertical offsets of 51 ODM flights from LidarBC, and the misfit after shift and after shift + tilt](uav_pointclouds/uav_lidarbc_offsets.png)

51 ODM flights with classified ground:

| | median | middle half | range |
|---|---|---|---|
| vertical offset, as georeferenced | +6.3 m | +1.9 to +33 m | **−107 to +97 m** |
| horizontal shift that fits best | 3.5 m | 1.9–5.8 m | 0–19 m |
| tilt | 1.2 m per 100 m | 0.45–2.4 | 0–7.2 |
| misfit (NMAD), shift only | 1.6 m | 0.94–2.9 | 0.46–15 |
| misfit (NMAD), shift + tilt | **0.82 m** | 0.52–1.4 | 0.34–6.7 |

- **The vertical offsets are not a datum problem.** The geoid separation at these sites is −8 to −15 m
  (CGG2013a), while the offsets run past ±100 m and differ between flights of the same reach. They are
  the drone's GPS altitude, which ODM takes as given.
- **The published DTMs and DSMs carry the same offsets.** Sampled at 20,000 ground points each,
  `odm_dem/dtm.tif` on the bucket matches its cloud to 0.00 m at `195290_gibson_hwy16` (cloud −37 m
  from LidarBC) and `bulkley_bul38` (+46 m). Anyone reading an elevation off one of our UAV DTMs is
  reading a number that is off by a median of 9 m.
- **After shift + tilt, 29 of 51 flights fit within 1 m and 12 within 0.5 m.** The misfit is an upper
  bound on the alignment error: it also holds real change since the LiDAR (flown 2018–2025, the UAV
  2020–2026) and vegetation that ODM classed as ground. Six flights stay above 2 m: the three 2026
  flights over a kilometre long in the Parsnip and upper Peace, at under 9 pts/m², and three 2025
  flights in the Bulkley.
- The Maps Made Easy clouds fit worse (median 3.3 m) only because they are unclassified, so the
  comparison includes vegetation. 13 of the 15 sit in a dataset directory ODM also processed, and the
  two placements differ by up to 51 m vertically (`195290_gibson_hwy16`: ODM −37 m, Maps Made Easy
  +14 m).

## Change over time: one pair, tested

The only UAV-to-UAV pair flown close together is the Parsnip crossing `199663` ("moose"), flown
2026-07-14 before its replacement and 2026-09-15 after, with LidarBC 2025 under both
(`moose_change.py`, `moose_detrend.py`; 0.5 m DSMs from the clouds).

| post minus pre | median | 5th–95th percentile |
|---|---|---|
| as georeferenced | +49 m | +25 to +71 m |
| each flight fitted to LidarBC (shift + tilt) | +0.5 m | −8.6 to +7.7 m |

![post − pre after shift + tilt: a bowl](uav_pointclouds/moose_ddsm_aligned.png)

Fitted to LidarBC, the difference is still a **bowl**: centre up, edges down, about 12 m across 1.6 km.
That is the doming a GPS-only, nadir-only photogrammetric block is known for, and no rigid model
removes it. The post flight alone was tilted 4.4 m per 100 m, and its horizontal shift is not well
determined: two fits on different point samples gave 18.8/8.0 m and 16.5/9.3 m. A robust quadratic fitted to the
difference itself takes most of the bowl out:

![post − pre after a quadratic detrend between the flights](uav_pointclouds/moose_ddsm_detrended.png)

What is left: open ground is smooth to about ±0.5 m, forest is ±2 m noise (crowns seen from slightly
different positions), and every road and bank shows a paired red/blue edge, which is 1–2 m of
horizontal misregistration. The residual misfit is 2.5 m NMAD. **Culvert-scale change (a metre or two
over a few tens of metres) cannot be separated from that with these flights.**

## Where the value is

Ranked by value for the effort, cheapest first.

1. **Fix the absolute elevations we already publish.** Every UAV DTM and DSM in `imagery-uav-bc-prod`
   is off by the flight's GPS error. Measuring each flight's shift + tilt against LidarBC is a script
   that already runs (here, 15 minutes for 61 clouds), and recording it on the items, or publishing
   corrected rasters, turns a misleading elevation into a useful one for the 29 flights that fit
   within a metre. The 31 off LidarBC need another reference or ground control.
2. **LiDAR then UAV, where the change is large.** Every flight on LidarBC is already a two-epoch pair:
   the LiDAR (2018–2019 in the Bulkley, 2024–2025 in the Fraser and Parsnip) and the UAV years later.
   With about 0.8 m misfit after alignment, changes of 2 m or more on open ground are measurable: bank
   retreat, channel migration across gravel bars, wood jams, fill at a crossing. This needs one test
   on a reach where something moved before it is worth building.
3. **Publish the clouds as COPC.** Low effort (83 files, 4.8 GB) and useful to look at in 3D, and it
   makes 1 and 2 reproducible from the catalogue. On its own it adds little analysis: the clouds are
   low-density, single-return and, until 1 is done, in the wrong place.
4. **UAV to UAV change: not with the flights we have.** The moose pair shows the limit: metres of
   relative error that a smooth model only partly removes. It needs either ground control (a few
   checkerboards surveyed with a GNSS receiver) or an RTK/PPK drone, which would put each flight within
   centimetres without any of the fitting above. That is a field decision, not a processing one.

## What is not known yet

- How much of each flight's misfit is real change since the LiDAR rather than alignment error. A
  stable-surface mask (roads, the LiDAR's own ground in open areas) would split the two.
- Whether a quadratic per flight against LidarBC removes the doming as well as it does between the
  moose flights. It is the next model to try in the alignment issue.
- Whether `--pc-quality medium` or `high` changes any of this. It would raise density, not fix
  placement.
