#!/bin/bash
# Publish ODM-processed projects to the STAC — run AFTER visual QC of the ortho.
#
# Per project: COG convert + validate → prod tree → create items (flight
# datetimes) → S3 upload; then once per invocation: refresh the collection
# temporal extent, final sync, register items + collection, verify via the API.
# Orchestrates the existing tools (stac_create_item.py, stac_register_item.sh,
# stac_register_collection.sh); see scripts/config/README.md for the recipe.
#
# Idempotent: existing COGs, items, uploads, and registrations are skipped or
# upserted, so re-running after an interruption is safe and cheap.
#
# Usage:
#   scripts/stac_publish.sh <project-dir> [<project-dir>...]
# project-dir is a dataset dir under the imagery root, e.g.
#   /Users/airvine/Projects/gis/uav_imagery/mackenzie/pine/2026/6971_pine_oxbox_hwy97S
set -euo pipefail

ROOT=/Users/airvine/Projects/gis/uav_imagery
COG_TREE=$ROOT/imagery_uav_bc
PROD=$ROOT/stac/prod/imagery_uav_bc
BUCKET=s3://imagery-uav-bc
PROFILE=airvine
API=https://images.a11s.one/collections/imagery-uav-bc-prod
REPO="$(cd "$(dirname "$0")/.." && pwd)"

TIFS="odm_orthophoto/odm_orthophoto.tif odm_dem/dtm.tif odm_dem/dsm.tif"

[ $# -ge 1 ] || { echo "usage: $(basename "$0") project-dir [project-dir ...]" >&2; exit 1; }

rels=()
new_tifs=()
for proj in "$@"; do
  proj=${proj%/}
  case "$proj" in
    "$ROOT"/*) ;;
    *) echo "ERROR: $proj is not under $ROOT" >&2; exit 1 ;;
  esac
  rel=${proj#"$ROOT"/}
  for t in $TIFS; do
    [ -f "$proj/$t" ] || { echo "ERROR: missing $proj/$t — run ODM first" >&2; exit 1; }
  done

  echo "=== COG: $rel"
  for t in $TIFS; do
    out="$COG_TREE/$rel/$t"
    if [ ! -f "$out" ]; then
      mkdir -p "$(dirname "$out")"
      conda run -n dff rio cogeo create "$proj/$t" "$out"
    fi
    conda run -n dff rio cogeo validate "$out" | tail -1
    mkdir -p "$PROD/$rel/$(dirname "$t")"
    cp -np "$out" "$PROD/$rel/$t"
    new_tifs+=("$rel/$t")
  done
  rels+=("$rel")
done

echo "=== create items"
conda run -n titiler python "$REPO/scripts/stac_create_item.py" "${new_tifs[@]}"

echo "=== upload (per-dataset sync: durable + skips what is already up)"
for rel in "${rels[@]}"; do
  aws s3 sync "$PROD/$rel" "$BUCKET/$rel" --profile "$PROFILE" --only-show-errors
  echo "  synced: $rel"
done

echo "=== refresh collection temporal extent"
python3 - "$PROD" <<'PYEOF'
import json, pathlib, sys
base = pathlib.Path(sys.argv[1])
dts = []
for p in base.rglob("*.json"):
    if p.name == "collection.json":
        continue
    d = json.loads(p.read_text())
    if d.get("type") == "Feature":
        dts.append(d["properties"]["datetime"])
pc = base / "collection.json"
c = json.loads(pc.read_text())
interval = [[min(dts), max(dts)]]
if c["extent"]["temporal"]["interval"] != interval:
    c["extent"]["temporal"]["interval"] = interval
    pc.write_text(json.dumps(c, indent=2))
    print("extent ->", interval)
else:
    print("extent unchanged")
PYEOF

echo "=== final sync (item JSONs + collection.json)"
aws s3 sync "$PROD" "$BUCKET" --delete --exclude "*/.*" --exclude ".*" --profile "$PROFILE" --only-show-errors

echo "=== register items"
jsons=()
for rel in "${rels[@]}"; do
  while IFS= read -r j; do jsons+=("$j"); done < <(find "$PROD/$rel" -name "*.json" | sort)
done
"$REPO/scripts/config/stac_register_item.sh" "${jsons[@]}"

echo "=== register collection"
"$REPO/scripts/config/stac_register_collection.sh" "$PROD/collection.json"

echo "=== verify via API"
fail=0
for j in "${jsons[@]}"; do
  id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$j")
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API/items/$id")
  if [ "$code" != "200" ]; then
    fail=$((fail+1)); echo "  MISSING ($code): $id"
  fi
done
if [ "$fail" -eq 0 ]; then
  echo "PUBLISH COMPLETE: ${#jsons[@]} items live across ${#rels[@]} dataset(s)"
else
  echo "PUBLISH INCOMPLETE: $fail item(s) not reachable via API" >&2
  exit 1
fi
