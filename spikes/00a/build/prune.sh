#!/usr/bin/env bash
# Part 4 of the Clipper simulation-only patch (ADR-002, D13): remove the Python
# packages of every adapter that is not compiled in. Run from the upstream
# source root after applying clipper-sim-only.patch.
set -euo pipefail
KEEP=(databento sandbox)
cd python/nautilus_trader/adapters
for d in */; do
  d=${d%/}
  if [[ " ${KEEP[*]} " != *" $d "* ]]; then
    echo "prune: python/nautilus_trader/adapters/$d"
    rm -rf -- "$d"
  fi
done
