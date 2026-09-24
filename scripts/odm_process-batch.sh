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
#   caffeinate -s scripts/odm_process-batch.sh [--split N] <project-dir> [<project-dir>...]
#
# --split N: for large datasets (>~300 images) process in submodels of ~N images
# (100 m overlap, merged at the end) so memory stays bounded by the submodel,
# not the whole flight. Typical: --split 250. See scripts/config/README.md.
#
# ODM params mirror the repo standard (ngr::ngr_spk_odm defaults + dem-res 5).
set -u

SPLIT_OPTS=""
if [ "${1:-}" = "--split" ]; then
  [ -n "${2:-}" ] || { echo "ERROR: --split needs a submodel size (e.g. --split 250)" >&2; exit 1; }
  SPLIT_OPTS="--split $2 --split-overlap 100"
  shift 2
fi

[ $# -ge 1 ] || { echo "usage: $(basename "$0") [--split N] project-dir [project-dir ...]" >&2; exit 1; }

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

  # ODM finds any video in images/ and extracts frames from it, then processes
  # those frames as survey stills. They come off the drone at 1920x1080 beside
  # 8064x6048 stills, and ODM computes GSD across every camera then clamps ortho
  # AND dem resolution so neither is finer than that GSD — so one clip coarsens
  # all three products. Measured on wedzin_gosnell_confluence (#27): 4 frames
  # from a single .MP4 put ortho, DTM and DSM at 6.57 cm/px instead of 5.00.
  # Nothing reports it — every frame reconstructs, the stats look clean, and the
  # ortho is simply lower resolution than it should be.
  #
  # Move the clip aside rather than deleting it; the flight still owns it.
  vids=$(find "$proj/images" -maxdepth 1 -type f \
           \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.avi' -o -iname '*.mkv' \))
  if [ -n "$vids" ]; then
    mkdir -p "$proj/video"
    printf '%s\n' "$vids" | while IFS= read -r v; do
      mv -n "$v" "$proj/video/" && echo "    video moved out of images/: $(basename "$v")"
    done
    # .SRT telemetry and .LRF proxies belong with the clip, not the survey set
    find "$proj/images" -maxdepth 1 -type f \( -iname '*.srt' -o -iname '*.lrf' \) \
      -exec mv -n {} "$proj/video/" \;
  fi

  # frames.json is ODM's own manifest of what it extracted on a previous run;
  # with the video gone those frames must go too or they are ingested again.
  if [ -f "$proj/images/frames.json" ]; then
    python3 -c '
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
manifest = d / "frames.json"
for name in json.loads(manifest.read_text()):
    (d / name).unlink(missing_ok=True)
manifest.unlink()
' "$proj/images" && echo "    removed frames ODM had extracted from video"
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
    $SPLIT_OPTS \
    > "$proj/odm_process.log" 2>&1
  ec=$?
  echo "=== ODM exit $ec: $name $(date '+%Y-%m-%d %H:%M:%S')"
  if [ $ec -ne 0 ]; then
    echo "    (log tail:)"; tail -3 "$proj/odm_process.log" | sed 's/^/    /'
  fi
done
echo "=== batch done $(date '+%Y-%m-%d %H:%M:%S')"
