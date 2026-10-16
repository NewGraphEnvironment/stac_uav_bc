#!/bin/bash
# Unregister (delete) a STAC collection, and every item in it, from the API database
# (pgstac) on the geoserv droplet. THE ONE SCRIPT HERE THAT DESTROYS A COLLECTION.
#
# It exists for a rename (#48): once the new collection is registered and verified and
# every consumer names it, the old collection's rows come out. Registration (stacs) is
# upsert-only, so nothing in the routine path can call this; deletion goes through pgstac
# SQL (delete_collection), as item_unregister.sh goes through delete_item.
#
# What this costs if you get it wrong. pgstac.items.collection is ON DELETE CASCADE, so
# the collection row goes with every item in it: the mechanism that took the API to zero
# items on 2026-08-29. There is no undo. The collection stacs.toml names is recovered by
# scripts/catalogue_release.sh (the bucket holds its bodies); a collection the release no
# longer publishes, such as the old id after a rename, has no recovery, so this script
# refuses the configured id and asks before deleting anything else.
#
# Usage:
#   scripts/config/collection_unregister.sh [--config <stacs.toml>] <collection-id>        # reports, deletes nothing
#   scripts/config/collection_unregister.sh [--config <stacs.toml>] --yes <collection-id>  # deletes
#   scripts/config/collection_unregister.sh --selftest                                     # the guards, no ssh
#
# Guards, each refusing toward not deleting:
#   - the id stacs.toml names is never a target (the live collection)
#   - --yes refuses unless the API serves the configured collection and every item id in
#     the target has an item in it: the new collection is live and holds what the old one
#     holds before the old one goes, never the reverse (a count would also pass a sibling
#     catalogue on the shared database; id containment passes only the renamed one)
#   - an id outside [A-Za-z0-9_-] or a db outside [A-Za-z0-9_] refuses (both reach SQL)
#   - a count that does not read as a number refuses
# An absent collection is "nothing to do" (exit 0); a row with no items is said as such.
# After --yes it re-reads both counts and the API, and exits 1 unless items 0, row 0, 404.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CONFIG="$REPO/stacs.toml"

usage() {
  echo "usage: $(basename "$0") [--config stacs.toml] [--yes] <collection-id> | --selftest" >&2
  exit 1
}
refuse() { echo "REFUSED: $*" >&2; exit 1; }
numeric() {  # what, value
  case "$2" in ''|*[!0-9]*) refuse "could not read $1 (got: '$2'); not deleting" ;; esac
}

# The three calls that leave this machine. The selftest redefines them.
pg_query() {  # SQL on stdin -> rows on stdout
  ssh "$HOST" "docker exec -i geoserv-db psql -U stac -d $DB -tA -v ON_ERROR_STOP=1"
}
ssh_probe() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" true 2>/dev/null; }
# curl prints 000 and exits non-zero on a transport failure; without the fallback the
# assignment ends the script under set -e with no message, after the delete as well as before.
api_status() { curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$1" || echo 000; }

count_items() {
  printf "select count(*) from pgstac.items where collection = '%s';\n" "$1" | pg_query | tr -d '[:space:]'
}
count_rows() {
  printf "select count(*) from pgstac.collections where id = '%s';\n" "$1" | pg_query | tr -d '[:space:]'
}
count_missing() {  # target, live: target item ids with no item of that id in live
  printf "select count(*) from pgstac.items t where t.collection = '%s' and not exists (select 1 from pgstac.items l where l.collection = '%s' and l.id = t.id);\n" "$1" "$2" \
    | pg_query | tr -d '[:space:]'
}

main() {
  local CONFIRM=0 CONFIG_ARG=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --config) [ $# -ge 2 ] || usage; CONFIG="$2"; CONFIG_ARG="--config $2 "; shift 2 ;;
      --yes) CONFIRM=1; shift ;;
      -*) usage ;;
      *) break ;;
    esac
  done
  [ $# -eq 1 ] || usage
  local TARGET="$1"
  # Interpolated into SQL, so allowlisted rather than escaped.
  case "$TARGET" in ''|*[!A-Za-z0-9_-]*) refuse "suspicious collection id: '$TARGET'" ;; esac

  # Host, db, api and the live collection id are the write path's own (#35).
  local CFG
  CFG=$(python3 -c '
import sys, tomllib
t = tomllib.load(open(sys.argv[1], "rb"))
c, tr = t["catalogue"], t["transport"]
print(tr["host"], tr["db"], c["api"].rstrip("/"), c["collection_id"])' "$CONFIG") \
    || refuse "could not read [transport] host, db and [catalogue] api, collection_id from $CONFIG"
  read -r HOST DB API LIVE_ID <<< "$CFG"
  [ -n "$HOST" ] && [ -n "$DB" ] && [ -n "$API" ] && [ -n "$LIVE_ID" ] \
    || refuse "a blank setting in $CONFIG (host='$HOST' db='$DB' api='$API' collection_id='$LIVE_ID')"
  case "$DB" in *[!A-Za-z0-9_]*) refuse "suspicious database name: '$DB'" ;; esac
  [ "$TARGET" != "$LIVE_ID" ] \
    || refuse "$TARGET is the collection $CONFIG names, the live one; this script drops only a collection the release no longer publishes"

  ssh_probe || refuse "cannot reach $HOST"
  # Counted before asking, so the number in front of the operator is the real one.
  local COUNT ROWS
  COUNT=$(count_items "$TARGET" || true); numeric "the item count of $TARGET" "$COUNT"
  ROWS=$(count_rows "$TARGET" || true);   numeric "the collection row count of $TARGET" "$ROWS"

  echo "collection : $TARGET"
  echo "database   : $DB on $HOST"
  echo "config     : $CONFIG (live collection: $LIVE_ID)"
  if [ "$ROWS" -eq 0 ]; then
    # A collection that is already absent is not an error, and not a deletion either.
    [ "$COUNT" -eq 0 ] \
      || refuse "$COUNT item(s) name $TARGET but it has no collection row; pgstac is inconsistent, look before deleting"
    echo "items      : 0"
    echo "nothing to do: no such collection registered"
    return 0
  fi
  if [ "$COUNT" -gt 0 ]; then
    echo "items      : $COUNT  <-- destroyed with the collection row"
  else
    echo "items      : 0 (the collection row exists with no items)"
  fi
  if [ "$CONFIRM" -ne 1 ]; then
    echo
    echo "Nothing deleted. Re-run with --yes to destroy the above:"
    echo "  $0 ${CONFIG_ARG}--yes $TARGET"
    return 0
  fi

  # Never delete first, as a check rather than a rule: the configured collection is
  # served, and holds an item for every item id the one about to go holds. A count would
  # pass any smaller sibling on the shared database; containment passes the renamed one.
  local LIVE_STATUS MISSING
  LIVE_STATUS=$(api_status "$API/collections/$LIVE_ID")
  [ "$LIVE_STATUS" = "200" ] \
    || refuse "$API/collections/$LIVE_ID answers HTTP $LIVE_STATUS, not 200: register the live collection before dropping $TARGET"
  MISSING=$(count_missing "$TARGET" "$LIVE_ID" || true)
  numeric "the count of $TARGET item ids absent from $LIVE_ID" "$MISSING"
  [ "$MISSING" -eq 0 ] \
    || refuse "$MISSING of $TARGET's $COUNT item id(s) have no item in $LIVE_ID: the live collection does not hold what $TARGET holds"

  echo "deleting $TARGET ($COUNT items) ..."
  printf "select pgstac.delete_collection('%s');\n" "$TARGET" | pg_query > /dev/null
  local AFTER_ITEMS AFTER_ROWS STATUS
  AFTER_ITEMS=$(count_items "$TARGET" || true)
  AFTER_ROWS=$(count_rows "$TARGET" || true)
  if [ "$AFTER_ITEMS" != "0" ] || [ "$AFTER_ROWS" != "0" ]; then
    echo "ERROR: after delete_collection, $TARGET still reads items=$AFTER_ITEMS rows=$AFTER_ROWS" >&2
    return 1
  fi
  STATUS=$(api_status "$API/collections/$TARGET")
  if [ "$STATUS" != "404" ]; then
    echo "ERROR: $API/collections/$TARGET answers HTTP $STATUS, not 404" >&2
    return 1
  fi
  echo "OK — deleted $TARGET ($COUNT items); $API/collections/$TARGET answers 404"
  echo "No recovery for $TARGET: the bucket publishes $LIVE_ID (scripts/catalogue_release.sh)."
}

selftest() {
  local td
  td=$(mktemp -d "${TMPDIR:-/tmp}/collection_unregister.XXXXXX")
  # Expanded now: the trap runs after this function's locals are gone.
  trap "rm -rf '$td'" EXIT
  cat > "$td/stacs.toml" <<'TOML'
[catalogue]
api = "https://api.example"
collection_id = "stac-live-bc"
[transport]
host = "root@example"
db = "stac"
TOML
  LOG="$td/sql.log"
  # Stubs: nothing leaves this machine. pg_query answers from the SQL it is given and
  # records every statement; once a delete_collection has been seen, the target is gone,
  # unless STUB_STICKY says the delete did not take (rows stay) or STUB_STICKY_API says
  # the API still serves it, so the read-back guards have a case that can fail them.
  ssh_probe() { :; }
  deleted() { [ "$STUB_STICKY" -eq 0 ] && grep -q delete_collection "$LOG"; }
  pg_query() {
    local sql; sql=$(cat); echo "$sql" >> "$LOG"
    case "$sql" in
      *delete_collection*) echo "" ;;
      *"not exists"*) echo "$STUB_MISSING" ;;
      *"collection = '$STUB_LIVE'"*) echo "$STUB_LIVE_COUNT" ;;
      *"collection = '"*) if deleted; then echo 0; else echo "$STUB_COUNT"; fi ;;
      *"collections where id = '"*) if deleted; then echo 0; else echo "$STUB_ROWS"; fi ;;
      *) echo "" ;;
    esac
  }
  api_status() {
    case "$1" in
      */collections/"$STUB_LIVE") echo "$STUB_LIVE_STATUS" ;;
      *) if [ "$STUB_STICKY_API" -eq 0 ] && grep -q delete_collection "$LOG"; then echo 404; else echo 200; fi ;;
    esac
  }
  local fails=0
  run() {  # name, want_rc, want_text, want_deletes, args...
    local name=$1 want_rc=$2 want=$3 want_del=$4; shift 4
    : > "$LOG"
    local out rc dels
    out=$(main --config "$td/stacs.toml" "$@" 2>&1) && rc=0 || rc=$?
    dels=$(grep -c delete_collection "$LOG" || true)
    if [ "$rc" -ne "$want_rc" ] || ! printf '%s' "$out" | grep -qF -- "$want" || [ "$dels" -ne "$want_del" ]; then
      echo "  FAIL: $name (rc=$rc want $want_rc; deletes=$dels want $want_del; want text: $want)"
      printf '%s\n' "$out" | sed 's/^/        /'
      fails=$((fails + 1))
    else
      echo "  ok: $name"
    fi
  }
  STUB_LIVE=stac-live-bc; STUB_LIVE_COUNT=245; STUB_LIVE_STATUS=200; STUB_COUNT=245; STUB_ROWS=1
  STUB_MISSING=0; STUB_STICKY=0; STUB_STICKY_API=0
  run "a suspicious id refuses" 1 "suspicious collection id" 0 "bad;id"
  run "the configured (live) id refuses" 1 "is the collection" 0 "stac-live-bc"
  run "report mode deletes nothing" 0 "Nothing deleted" 0 "stac-old-bc"
  STUB_COUNT=0
  run "a row with no items is said" 0 "exists with no items" 0 "stac-old-bc"
  STUB_COUNT="ERROR: relation"
  run "an unreadable count refuses" 1 "could not read" 0 "stac-old-bc"
  STUB_COUNT=245
  STUB_ROWS=0; STUB_COUNT=0
  run "an absent collection is nothing to do" 0 "nothing to do" 0 "stac-old-bc"
  STUB_ROWS=0; STUB_COUNT=3
  run "items with no collection row refuse" 1 "inconsistent" 0 "stac-old-bc"
  STUB_ROWS=1; STUB_COUNT=245
  STUB_LIVE_STATUS=404
  run "--yes refuses while the live collection is not served" 1 "not 200" 0 --yes "stac-old-bc"
  STUB_LIVE_STATUS=000
  run "--yes refuses when the API cannot be reached" 1 "HTTP 000, not 200" 0 --yes "stac-old-bc"
  STUB_LIVE_STATUS=200; STUB_MISSING=3
  run "--yes refuses while the live collection lacks target ids" 1 "have no item in" 0 --yes "stac-old-bc"
  STUB_MISSING="ERROR: relation"
  run "--yes refuses an unreadable containment count" 1 "could not read" 0 --yes "stac-old-bc"
  STUB_MISSING=0
  run "--yes deletes once and reads back 0, 0, 404" 0 "OK — deleted" 1 --yes "stac-old-bc"
  STUB_STICKY=1
  run "a delete that did not take is reported" 1 "still reads items=245" 1 --yes "stac-old-bc"
  STUB_STICKY=0; STUB_STICKY_API=1
  run "an API still serving the target after the delete is reported" 1 "not 404" 1 --yes "stac-old-bc"
  STUB_STICKY_API=0
  printf '[catalogue]\napi = "https://api.example"\ncollection_id = "stac-live-bc"\n[transport]\nhost = "root@example"\ndb = "stac; drop"\n' > "$td/bad.toml"
  : > "$LOG"
  if (main --config "$td/bad.toml" "stac-old-bc") > /dev/null 2>&1; then
    echo "  FAIL: a suspicious database name passed"; fails=$((fails + 1))
  else
    echo "  ok: a suspicious database name refuses"
  fi
  if [ "$fails" -gt 0 ]; then
    echo "COLLECTION_UNREGISTER SELFTEST FAILED: $fails case(s)" >&2
    return 1
  fi
  echo "COLLECTION_UNREGISTER SELFTEST PASS: id, config, live-collection and read-back guards"
}

if [ "${1:-}" = "--selftest" ]; then
  selftest
  exit $?
fi
main "$@"
