#!/bin/bash
# Publish ODM-processed projects to the STAC — run AFTER visual QC of the ortho.
#
# Per project: COG convert + validate → prod tree → create items (flight
# datetimes) → S3 upload; then once per invocation: refresh the collection
# temporal extent, final sync, register items + collection, verify via the API.
# Orchestrates the existing tools (item_create.py, item_register.sh,
# collection_register.sh); see scripts/config/README.md for the recipe.
#
# Idempotent: existing COGs, items, uploads, and registrations are skipped or
# upserted, so re-running after an interruption is safe and cheap.
#
# Usage:
#   scripts/dataset_publish.sh <project-dir> [<project-dir>...]
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
    # This gate was `conda run … validate "$out" | tail -1` and was inert two ways
    # over (#27). `conda run` captures its child's output and does not pass it
    # through a pipe, so nothing was ever printed; and `rio cogeo validate` exits
    # 0 whether the file is valid or not, so testing the status would not have
    # worked either. Every publish ran an unvalidated COG step that looked gated.
    #
    # --no-capture-output restores the text, and the verdict IS the text, so match
    # it — on the positive marker, since an unreadable file or a changed message
    # must not read as a pass.
    valid=$(conda run --no-capture-output -n dff rio cogeo validate "$out" 2>&1)
    case "$valid" in
      *"is a valid cloud optimized GeoTIFF"*) echo "    COG valid: $t" ;;
      *) printf '%s\n' "$valid" >&2
         echo "ERROR: $out is not a valid COG — not publishing" >&2; exit 1 ;;
    esac
    mkdir -p "$PROD/$rel/$(dirname "$t")"
    cp -np "$out" "$PROD/$rel/$t"
    new_tifs+=("$rel/$t")
  done
  rels+=("$rel")
done

echo "=== create items"
conda run -n titiler python "$REPO/scripts/item_create.py" "${new_tifs[@]}"

echo "=== upload (per-dataset sync: durable + skips what is already up)"
for rel in "${rels[@]}"; do
  aws s3 sync "$PROD/$rel" "$BUCKET/$rel" --profile "$PROFILE" --only-show-errors
  echo "  synced: $rel"
done

echo "=== refresh collection extent (spatial + temporal)"
python3 - "$PROD" <<'PYEOF'
import json, pathlib, sys
base = pathlib.Path(sys.argv[1])
dts, bboxes = [], []
for p in base.rglob("*.json"):
    if p.name == "collection.json":
        continue
    d = json.loads(p.read_text())
    if d.get("type") == "Feature":
        dts.append(d["properties"]["datetime"])
        if d.get("bbox"):
            bboxes.append(d["bbox"])
pc = base / "collection.json"
c = json.loads(pc.read_text())
changed = []

interval = [[min(dts), max(dts)]]
if c["extent"]["temporal"]["interval"] != interval:
    c["extent"]["temporal"]["interval"] = interval
    changed.append(f"temporal -> {interval}")

# Spatial was never recomputed, so the collection could advertise an extent that
# excluded its own items — a bbox-filtered search then silently misses them (#22).
if bboxes:
    bbox = [min(b[0] for b in bboxes), min(b[1] for b in bboxes),
            max(b[2] for b in bboxes), max(b[3] for b in bboxes)]
    if c["extent"]["spatial"]["bbox"] != [bbox]:
        c["extent"]["spatial"]["bbox"] = [bbox]
        changed.append(f"spatial -> {bbox}")

if changed:
    pc.write_text(json.dumps(c, indent=2))
    for line in changed:
        print("extent", line)
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
"$REPO/scripts/config/item_register.sh" "${jsons[@]}"

echo "=== register collection"
"$REPO/scripts/config/collection_register.sh" "$PROD/collection.json"

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
