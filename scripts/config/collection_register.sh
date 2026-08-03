#!/bin/bash
# Register (upsert) a STAC collection JSON into the API database (pgstac) on the
# geoserv droplet. Companion to item_register.sh — same pypgstac transport.
#
# Usage:
#   scripts/config/collection_register.sh /path/to/collection.json
#
# Upsert is idempotent: re-registering an existing collection updates it in place.
set -euo pipefail

HOST=root@146.190.12.8   # geoserv droplet (hostname geopro)
DB=stac                  # imagery-uav-bc-prod lives in the default stac db

[ $# -eq 1 ] || { echo "usage: $(basename "$0") collection.json" >&2; exit 1; }

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])), separators=(",", ":")))' "$1" > "$TMP"

echo "registering collection $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$1") to $DB db on $HOST"
ssh "$HOST" "
  set -e
  cat > /tmp/stac_collection.ndjson
  . /opt/geoserv/.env
  export PATH=/root/.local/bin:\$PATH
  cd /opt/geoserv/scripts
  uv run pypgstac load collections /tmp/stac_collection.ndjson \
    --dsn \"postgresql://stac:\${POSTGRES_PASSWORD}@localhost:5432/$DB\" \
    --method upsert
  rm /tmp/stac_collection.ndjson
" < "$TMP"
echo "OK — verify: curl -s https://images.a11s.one/collections/<collection-id>"
