#!/usr/bin/env bash
# Reproduce Phase 0 proof 0A end to end on the reference machine (Linux x86-64, systemd user
# session, Rust via rustup, uv). Disposable: everything heavy goes under WORK (default: a temp dir).
#   ./reproduce.sh [WORK]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${1:-$(mktemp -d -t clipper-0a-XXXXXX)}
echo "work dir: $WORK"

# 1. Restricted engine build from tag v2.0.0rc9 + Clipper patch (check 1 build evidence)
"$HERE/build/build_engine.sh" "$WORK"
WHL=$(ls -t "$WORK"/dist/nautilus_trader-2.0.0rc9-*.whl | sed -n 1p)

# 2. Runtime prefix: uv-managed CPython 3.13 (python-build-standalone) with ONLY the restricted wheel
rm -rf "$WORK/runtime"
uv venv --quiet --python 3.13 "$WORK/runtime"
uv pip install --quiet --python "$WORK/runtime/bin/python" --no-deps "$WHL"

# 3. Optional stock comparison environment (PyPI rc9 wheel) for the artifact baseline
uv venv --quiet --python 3.13 "$WORK/stock-venv"
uv pip install --quiet --python "$WORK/stock-venv/bin/python" --only-binary :all: nautilus_trader==2.0.0rc9

# 4. Checks 1-4 (each case in its own systemd --user scope for memory.peak), then the report
cd "$HERE/harness"
"$WORK/runtime/bin/python" run_suite.py --python "$WORK/runtime/bin/python" \
  --stock-python "$WORK/stock-venv/bin/python" --work "$WORK" --evidence "$WORK/evidence-run"
python3 make_report.py "$WORK/evidence-run/results.json" "$HERE/evidence"
echo "evidence: $HERE/evidence/summary.md"
