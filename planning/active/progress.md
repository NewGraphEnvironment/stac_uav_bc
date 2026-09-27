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
