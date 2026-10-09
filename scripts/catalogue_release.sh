#!/bin/bash
# Release the catalogue: full rebuild from data/sites.csv -> validate -> S3 ->
# register -> verify. One command per release; idempotent end to end (#16).
# Registration and verification are stacs, configured by stacs.toml (#35).
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
STACS="$REPO/scripts/stacs.sh"
CONFIG="$REPO/stacs.toml"
# The checks below read the same API and collection stacs does.
API=$(python3 -c 'import sys, tomllib; c = tomllib.load(open(sys.argv[1], "rb"))["catalogue"]; print(c["api"].rstrip("/") + "/collections/" + c["collection_id"])' "$CONFIG")

VERSION="${1:-$(git -C "$REPO" describe --tags --abbrev=0 | sed 's/^v//')}"
echo "=== catalogue release v$VERSION"

echo "=== rebuild items from sites.csv"
conda run -n titiler python "$REPO/scripts/item_create.py" --rebuild --version "$VERSION"

echo "=== validate + audit (gate)"
# Paths on stdin, because --dir does not recurse and the prod tree is nested. Given
# on stdin, collection.json is validated too (--dir would skip it).
find "$PROD" -name "*.json" | sort | "$STACS" validate
# --expect is the collection's own link count, so an item JSON the rebuild did not
# link (the old-id file a rename leaves behind) fails here instead of being synced.
n_links=$(python3 -c 'import json,sys; print(sum(l["rel"] == "item" for l in json.load(open(sys.argv[1]))["links"]))' "$PROD/collection.json")
find "$PROD" -name "*.json" -not -name "collection.json" | sort \
  | "$STACS" audit --config "$CONFIG" --expect "$n_links"

echo "=== sync JSONs to S3"
aws s3 sync "$PROD" "$BUCKET" --delete --exclude "*/.*" --exclude ".*" --profile "$PROFILE" --only-show-errors
echo "    sync OK"

echo "=== register (stacs: collection first, then whatever the API lacks or serves stale)"
"$STACS" register --config "$CONFIG" --mode drift

echo "=== verify (stacs: id sets both ways, every body by digest)"
VERIFY_DIR=$(mktemp -d "${TMPDIR:-/tmp}/stacs_verify.XXXXXX")
# stacs prints at most 5 ids per drift class; the full lists (orphaned.txt is
# what item_unregister.sh needs after a rename) are in VERIFY_DIR.
"$STACS" verify --config "$CONFIG" --out-dir "$VERIFY_DIR" \
  || { echo "full id lists: $VERIFY_DIR" >&2; exit 1; }

echo "=== verify (this catalogue: version stamp, registry coverage)"
live_version=$(curl -s "$API" | python3 -c "import json,sys; print(json.load(sys.stdin).get('version','MISSING'))")
n_items=$(curl -s -X POST "${API%/collections/*}/search" -H "Content-Type: application/json" \
  -d "{\"collections\":[\"${API##*/}\"],\"limit\":1000}" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['features']))")
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
curl -s -X POST "${API%/collections/*}/search" -H "Content-Type: application/json" \
  -d "{\"collections\":[\"${API##*/}\"],\"limit\":1000}" | python3 -c "
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
