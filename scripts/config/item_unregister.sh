#!/bin/bash
# Unregister (delete) STAC items from the API database (pgstac) on the geoserv
# droplet. Registration is stacs (scripts/stacs.sh), which is upsert-only, so
# deletion stays here and goes through pgstac SQL (delete_item).
#
# Usage:
#   scripts/config/item_unregister.sh [--collection <id>] <item-id> [<item-id>...]
#
# Deletes from the collection stacs.toml names. While an old collection still serves
# the same ids (a rename's window, #48), pass --collection <old-id> to remove its copy
# too; collection_unregister.sh names the ids that need it.
#
# Idempotent: an id that is not registered warns and continues (exit 0).
# This removes items from the API only — S3 objects and prod-tree files are
# handled separately; see the retraction recipe in README.md (#18).
set -euo pipefail

# Host and db are the write path's own: read from stacs.toml, so a host move
# cannot leave the delete path pointing at the old machine (#35).
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CFG=$(python3 -c '
import sys, tomllib
t = tomllib.load(open(sys.argv[1], "rb"))
tr, c = t["transport"], t["catalogue"]
print(tr["host"], tr["db"], c["api"].rstrip("/"), c["collection_id"])' "$REPO/stacs.toml")
read -r HOST DB API CID <<< "$CFG"
[ -n "$HOST" ] && [ -n "$DB" ] && [ -n "$API" ] && [ -n "$CID" ] \
  || { echo "ERROR: could not read [transport] host/db and [catalogue] api/collection_id from $REPO/stacs.toml" >&2; exit 1; }

COLL="$CID"
if [ "${1:-}" = "--collection" ]; then
  [ $# -ge 2 ] || { echo "usage: $(basename "$0") [--collection <id>] item-id [item-id ...]" >&2; exit 1; }
  COLL="$2"; shift 2
fi
case "$COLL" in
  ''|*[!A-Za-z0-9_-]*) echo "ERROR: suspicious collection id: '$COLL'" >&2; exit 1 ;;
esac
[ $# -ge 1 ] || { echo "usage: $(basename "$0") [--collection <id>] item-id [item-id ...]" >&2; exit 1; }

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
for id in "$@"; do
  case "$id" in
    *[!A-Za-z0-9_-]*) echo "ERROR: suspicious item id: $id" >&2; exit 1 ;;
  esac
  # The collection is passed: pgstac's delete_item deletes RETURNING ... INTO STRICT, so
  # while two collections hold the same id (a rename's window, #48) the one-argument
  # form matches two rows, raises, and the EXCEPTION arm reports it as missing.
  cat >> "$TMP" << SQL
DO \$\$
BEGIN
  PERFORM pgstac.delete_item('$id', '$COLL');
  RAISE NOTICE 'deleted: $id';
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'not deleted (missing?): $id';
END
\$\$;
SQL
done

echo "unregistering $# item(s) from collection $COLL in $DB db on $HOST"
ssh "$HOST" "docker exec -i geoserv-db psql -U stac -d $DB -v ON_ERROR_STOP=1" < "$TMP"
echo "OK — verify 404: curl -s -o /dev/null -w '%{http_code}' $API/collections/$COLL/items/<item-id>"
