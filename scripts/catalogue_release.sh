#!/bin/bash
# Release the catalogue: full rebuild from data/sites.csv -> validate -> S3 ->
# register -> verify. One command per release; idempotent end to end (#16).
#
# Usage:
#   scripts/catalogue_release.sh [version]
#
# version defaults to the latest git tag — tag first, then release:
#   git tag v1.1.0 && scripts/catalogue_release.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PROD=/Users/airvine/Projects/gis/uav_imagery/stac/prod/imagery_uav_bc
BUCKET=s3://imagery-uav-bc
PROFILE=airvine
API=https://images.a11s.one/collections/imagery-uav-bc-prod

VERSION="${1:-$(git -C "$REPO" describe --tags --abbrev=0 | sed 's/^v//')}"
echo "=== catalogue release v$VERSION"

echo "=== rebuild items from sites.csv"
conda run -n titiler python "$REPO/scripts/item_create.py" --rebuild --version "$VERSION"

echo "=== validate (gate)"
conda run -n titiler python "$REPO/scripts/item_validate.py"

echo "=== sync JSONs to S3"
aws s3 sync "$PROD" "$BUCKET" --delete --exclude "*/.*" --exclude ".*" --profile "$PROFILE" --only-show-errors
echo "    sync OK"

echo "=== register items (bulk upsert)"
find "$PROD" -name "*.json" -not -name "collection.json" | sort | xargs "$REPO/scripts/config/item_register.sh"

echo "=== register collection"
"$REPO/scripts/config/collection_register.sh" "$PROD/collection.json"

echo "=== verify"
live_version=$(curl -s "$API" | python3 -c "import json,sys; print(json.load(sys.stdin).get('version','MISSING'))")
n_items=$(curl -s -X POST "https://images.a11s.one/search" -H "Content-Type: application/json" \
  -d '{"collections":["imagery-uav-bc-prod"],"limit":1000}' | python3 -c "import json,sys; print(len(json.load(sys.stdin)['features']))")
echo "live collection version: $live_version | items: $n_items"
[ "$live_version" = "$VERSION" ] || { echo "RELEASE INCOMPLETE: live version != $VERSION" >&2; exit 1; }
echo "RELEASE COMPLETE: v$VERSION"
