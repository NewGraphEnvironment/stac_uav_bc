# Findings — Generate flight plans from boundaries we define (#26)

## Parameters for this run (user, 2026-09-26)

- **350 m AGL**, relative to takeoff point
- **10 m/s**
- **ff04** delineation only (ff02/ff06 stay reachable as a parameter)
- Launch: Peacock Creek confluence, `-126.79270, 54.36067`
- 3 batteries

## The `fly` dependency #26 assumes does not exist

fly#70 is **OPEN** — nothing landed. `fly` has no spacing, transect, sidelap, waypoint, KMZ or DJI
code anywhere in `R/`. `fly_footprint()` takes no height or focal argument; its `format_size` route
always yields a **square** footprint, wrong for a 4:3 sensor. `fly_coverage()`/`fly_overlap()`
*measure* an existing photo set — there is no inverse returning spacing. `fly_select()` is greedy
set-cover over existing points with no path, battery or ordering cost.

So v1 does not depend on `fly`. Geometry is taken from fly#70's body and cited, kept in one
module-level block, to be superseded when #70 lands.

## Sensor geometry, confirmed against real flights

fly#70 derives the Mini 4 Pro as 8064 × 6048 on a 9.68 × 7.26 mm sensor (1.2004 µm pitch) at
6.72 mm focal.

| | 300 m | 350 m (ours) |
|---|---|---|
| GSD | 5.36 cm/px | 6.25 cm/px |
| footprint | 432 × 324 m | 504 × 378 m |
| transect spacing @80/80 | 86.4 m | 100.8 m |
| along-track photo spacing | 64.8 m | 75.6 m |

**The check:** 300 m predicts 64.8 m photo spacing; the median segment length across all five real
KMZ missions is **64.9 m**. A competing derivation from the rounded 24 mm equivalent gives 1.250 µm
and would predict 67.5 m — ruled out.

## Fixture set

Five Map Pilot exports in `~/Downloads`. Each is a zip of `wpmz/template.kml` (871-byte stub) and
`wpmz/waylines.wpml`.

| file | height | autoSpeed | distance | waypoints | photos |
|---|---|---|---|---|---|
| `myKMZ-1.kmz` | 300 | 10 | 12651 m | 195 | 147 |
| `myKMZ-2.kmz` | 300 | 10 | 12097 m | 195 | 159 |
| `myKMZ-3.kmz` | 300 | 10 | 3221 m | 37 | 28 |
| `20260722_morr_jet_lwd01.kmz` | 300 | **26** | 17406 m | 194 | 165 |
| `20220722_morr_braid04-2.kmz` | 300 | 10 | 306 m | 7 | 5 |

Constant across all five: `executeHeightMode=relativeToStartPoint`, `finishAction=goHome`,
`gimbalPitchRotateAngle=-85`, `globalTransitionalSpeed=9.5`, `droneEnumValue=68`, median segment
64.9 m.

## Two traps that would silently corrupt a budget model

1. **`wpml:duration` is 200.324 in all five files** — a constant Map Pilot writes regardless of
   mission. Not a duration. Compute time from distance and speed.
2. **`morr_jet_lwd01` requests 26 m/s** (`autoFlightSpeed 26`, `waypointSpeed 26.00` on 193 of 194
   waypoints), above the Mini 4 Pro's maximum. #26 says this mission is "24.2 min @12 m/s, over
   budget" *and* that a model reproduces it at "606 s actual". Those cannot both describe one flight,
   so neither figure can be trusted as calibration.

## Ground truth #26 does not use

`20260722_morr_jet_lwd01.kmz` (bbox -127.16375,54.17880 → -127.13959,54.19210) is the mission that
produced published dataset **`wedzin_lwd001`** (bbox -127.15482,54.17923 → -127.13600,54.19012,
flown 2026-07-22 10:46:11→11:03:06, 1015 s elapsed, 97 images).

#26's proposed validation — "regenerate from its own recovered boundary" — is circular and
impossible, since the boundary never survives export (#26's own Problem section). Validate against
the real image GPS positions instead.

`myKMZ-1/2/3` sit at -127.37 to -127.43, 54.11-54.13 with **no published flight there** — planned
but unflown, or flown and unpublished.

## Floodplain source

`floodplain.gpkg` (12.4 MB, reads over `/vsicurl/`, no download) on either MORR item — both carry
the same delineation, only the species scenario differs.

Layers: `co_ff02`, `co_ff04`, `co_ff06`, `ch_ff02`, `ch_ff04`, `ch_ff06`, plus
`co_ff04_by_gnis_name` (33 features), `co_ff04_by_blue_line_key` (340),
`ch_ff06_by_blue_line_key`, `layer_styles`.

Nearest the launch point in `co_ff04_by_gnis_name`:

| gnis_name | ff04 area | distance from launch |
|---|---|---|
| Peacock Creek | 187.3 ha | 3 m |
| Morice River | 5598.4 ha | 223 m |
| Knapper Creek | 81.4 ha | 4765 m |

MORR ff04 total is 357.69 km²; three batteries covers ~0.6% of it, so this is about picking the
right 200 ha, not covering the group.

## Errors Encountered

| Error | Resolution |
|-------|------------|
