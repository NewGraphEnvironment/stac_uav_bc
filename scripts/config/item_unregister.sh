#!/bin/bash
# Unregister (delete) STAC items from the API database (pgstac) on the geoserv
# droplet. Registration is stacs (scripts/stacs.sh), which is upsert-only, so
# deletion stays here and goes through pgstac SQL (delete_item).
#
# Usage:
#   scripts/config/item_unregister.sh <item-id> [<item-id>...]
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
t = tomllib.load(open(sys.argv[1], "rb"))["transport"]
print(t["host"], t["db"])' "$REPO/stacs.toml")
HOST=${CFG% *}
DB=${CFG#* }
[ -n "$HOST" ] && [ -n "$DB" ] && [ "$HOST" != "$DB" ] \
  || { echo "ERROR: could not read [transport] host/db from $REPO/stacs.toml" >&2; exit 1; }

[ $# -ge 1 ] || { echo "usage: $(basename "$0") item-id [item-id ...]" >&2; exit 1; }

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
for id in "$@"; do
  case "$id" in
    *[!A-Za-z0-9_-]*) echo "ERROR: suspicious item id: $id" >&2; exit 1 ;;
  esac
  cat >> "$TMP" << SQL
DO \$\$
BEGIN
  PERFORM pgstac.delete_item('$id');
  RAISE NOTICE 'deleted: $id';
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'not deleted (missing?): $id';
END
\$\$;
SQL
done

echo "unregistering $# item(s) from $DB db on $HOST"
ssh "$HOST" "docker exec -i geoserv-db psql -U stac -d $DB -v ON_ERROR_STOP=1" < "$TMP"
echo "OK — verify 404: curl -s -o /dev/null -w '%{http_code}' https://images.a11s.one/collections/imagery-uav-bc-prod/items/<item-id>"
