# Progress — Generate flight plans from boundaries we define (#26)

## Session 2026-09-26

- Plan-mode exploration — two Explore agents (`fly` API surface; this repo's script conventions)
- Established `fly` provides nothing for flight planning and fly#70 is still open — v1 does not
  depend on it
- Validated fly#70's sensor geometry against the five real KMZ missions: predicted 64.8 m photo
  spacing vs 64.9 m measured
- Found two fixture traps (`wpml:duration` is a constant; `morr_jet_lwd01` requests an impossible
  26 m/s) and the `morr_jet_lwd01` ↔ `wedzin_lwd001` ground-truth pairing
- Located the ff04 floodplain polygon: `floodplain.gpkg` over `/vsicurl/`, queryable by gnis name
- Phases approved by user
- Created branch `26-generate-flight-plans-from-boundaries-we` off main
- Next: Phase 1, the WPML writer

### Phase 1 — WPML writer (done)

- `scripts/flight_wpml.py`: reader + writer, action groups preserved verbatim on read
- All five fixtures re-emit **byte-for-byte exactly** (628 waypoints total)
- Found and fixed: Map Pilot's files end at `</kml>` with **no trailing newline**
- Found and fixed a defect in the gate itself: `splitlines()` discards the trailing-newline
  difference, so the detector fired while the explainer printed nothing. Added an arm that
  reports the trailing bytes when every line matches
- Gate proven both directions: trailing-byte difference caught and explained; a 1 m coordinate
  mutation caught at the exact line
