#!/bin/bash
# The pinned stacs CLI (#35): registration and verification for this catalogue.
#
#   scripts/stacs.sh verify   --config stacs.toml --out-dir <dir>
#   scripts/stacs.sh register --config stacs.toml --mode drift
#
# stacs is not installed into any env here. uvx builds it, isolated and cached, from
# the tag below, so the pin lives in this one line and cannot collide with another
# repo's install. Bump it here and nowhere else. Needs uv (brew install uv).
set -euo pipefail
STACS_REF=v0.1.0
exec uvx --from "git+https://github.com/NewGraphEnvironment/stacs@${STACS_REF}" stacs "$@"
