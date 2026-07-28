#!/bin/bash
# Batch OpenDroneMap processing over project dirs (each containing images/).
# Companion to odm_process.R (interactive R log) — this is the callable runner.
#
# - Skips projects that already have odm_orthophoto/ (resume-safe: re-run after
#   an interruption and it picks up where it left off)
# - Cleans partial ODM state left by an interrupted run before starting
# - Runs sequentially; logs to <project>/odm_process.log
#
# Usage (caffeinate keeps the machine awake for the duration):
#   caffeinate -s scripts/odm_process-batch.sh <project-dir> [<project-dir>...]
#
# ODM params mirror the repo standard (ngr::ngr_spk_odm defaults + dem-res 5).
set -u

[ $# -ge 1 ] || { echo "usage: $(basename "$0") project-dir [project-dir ...]" >&2; exit 1; }

for proj in "$@"; do
  proj=${proj%/}
  if [ ! -d "$proj/images" ]; then
    echo "SKIP (no images/): $proj"
    continue
  fi
  if [ -d "$proj/odm_orthophoto" ]; then
    echo "SKIP (already processed): $proj"
    continue
  fi

  # partial state from an interrupted run confuses ODM — start clean
  rm -rf "$proj"/opensfm "$proj"/odm_* "$proj"/benchmark.txt \
         "$proj"/images.json "$proj"/img_list.txt "$proj"/cameras.json

  parent=$(dirname "$proj")
  name=$(basename "$proj")
  echo "=== ODM start: $name $(date '+%Y-%m-%d %H:%M:%S')"
  docker run --rm \
    -v "$parent":/datasets \
    opendronemap/odm \
    --project-path /datasets/ "$name" \
    --dtm --dsm --pc-quality low --dem-resolution 5 \
    > "$proj/odm_process.log" 2>&1
  ec=$?
  echo "=== ODM exit $ec: $name $(date '+%Y-%m-%d %H:%M:%S')"
  if [ $ec -ne 0 ]; then
    echo "    (log tail:)"; tail -3 "$proj/odm_process.log" | sed 's/^/    /'
  fi
done
echo "=== batch done $(date '+%Y-%m-%d %H:%M:%S')"
