#!/bin/bash
# Register STAC item JSONs into the API database (pgstac) on the geoserv droplet.
#
# The public API at images.a11s.one is read-only (transactions extension off,
# POST returns 405 — deliberate), so items are loaded with pypgstac, which the
# server build installs on the droplet host for exactly this purpose.
#
# Usage:
#   scripts/config/item_register.sh item1.json [item2.json ...]
#
# Upsert is idempotent: re-registering an existing item is harmless.
# Raw-SQL fallback if pypgstac is ever unavailable:
#   SELECT pgstac.upsert_item('<item json>'::jsonb);
#   piped into: docker exec -i geoserv-db psql -U stac -d stac
set -euo pipefail

HOST=root@146.190.12.8   # geoserv droplet (hostname geopro)
DB=stac                  # imagery-uav-bc-prod lives in the default stac db

[ $# -ge 1 ] || { echo "usage: $(basename "$0") item.json [item.json ...]" >&2; exit 1; }

# compact each item to one line (ndjson) for pypgstac
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
python3 - "$@" > "$TMP" <<'PYEOF'
import json, sys
for f in sys.argv[1:]:
    print(json.dumps(json.load(open(f)), separators=(",", ":")))
PYEOF

echo "registering $(wc -l < "$TMP" | tr -d ' ') item(s) to $DB db on $HOST"
ssh "$HOST" "
  set -e
  cat > /tmp/stac_items.ndjson
  . /opt/geoserv/.env
  export PATH=/root/.local/bin:\$PATH
  cd /opt/geoserv/scripts
  uv run pypgstac load items /tmp/stac_items.ndjson \
    --dsn \"postgresql://stac:\${POSTGRES_PASSWORD}@localhost:5432/$DB\" \
    --method upsert
  rm /tmp/stac_items.ndjson
" < "$TMP"
echo "OK — verify: curl -s https://images.a11s.one/collections/imagery-uav-bc-prod/items/<item-id>"
