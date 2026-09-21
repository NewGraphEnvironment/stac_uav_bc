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

# n_items was printed but never asserted, so a release that dropped or stranded
# items still said RELEASE COMPLETE. Opt in with EXPECT_ITEMS=<n> (#22).
if [ -n "${EXPECT_ITEMS:-}" ]; then
  [ "$n_items" -eq "$EXPECT_ITEMS" ] \
    || { echo "RELEASE INCOMPLETE: $n_items items live, expected $EXPECT_ITEMS" >&2; exit 1; }
  echo "    item count OK: $n_items"
fi

# A registry miss is silent: item_create.py falls back to the directory name as
# title and emits no nge: properties at all. Count checks cannot see it, so
# assert every live item actually joined its sites.csv row (#22).
#
# Check nge:stream_name as well as nge:region, because registry_props drops any
# column that is blank after strip: a row that joins fine but has an empty
# stream_name still titles from the directory name while carrying nge:region.
# stream_name is the property the title actually reads, so it is the one that
# has to be present.
curl -s -X POST "https://images.a11s.one/search" -H "Content-Type: application/json" \
  -d '{"collections":["imagery-uav-bc-prod"],"limit":1000}' | python3 -c "
import json, sys
feats = json.load(sys.stdin)['features']
need = {'nge:region', 'nge:stream_name'}
orphans = [f['id'] for f in feats if not need <= f.get('properties', {}).keys()]
if orphans:
    print('RELEASE INCOMPLETE: %d item(s) missing nge: properties -- registry miss or blank '
          'stream_name; the title fell back to the directory name:' % len(orphans), file=sys.stderr)
    for i in orphans[:10]:
        print('   ', i, file=sys.stderr)
    sys.exit(1)
print('    registry coverage OK: %d/%d items carry nge:region + nge:stream_name' % (len(feats), len(feats)))
" || exit 1

echo "RELEASE COMPLETE: v$VERSION"
