#!/usr/bin/env bash
# Reproducible build of the Clipper simulation-only NautilusTrader wheel
# (Phase 0 proof 0A, check 1). Usage: build_engine.sh <work-dir>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${1:?work dir}
TAG=v2.0.0rc9
COMMIT=da6b57aefdd62b44f675e434ffcfefca7f4025dd
EVID=$HERE/../evidence/build
mkdir -p "$WORK" "$EVID"
SRC=$WORK/nt-build
if [[ ! -d $SRC ]]; then
  git clone --quiet --depth 1 --branch "$TAG" https://github.com/nautechsystems/nautilus_trader.git "$SRC"
fi
cd "$SRC"
test "$(git rev-parse HEAD)" = "$COMMIT" || { echo "tag $TAG does not resolve to $COMMIT" >&2; exit 1; }
git reset --quiet --hard "$COMMIT" && git clean -qfdx
git apply --check "$HERE/clipper-sim-only.patch"
git apply "$HERE/clipper-sim-only.patch"
"$HERE/prune.sh" | tee "$EVID/prune.log"
git status --short > "$EVID/source-changes.txt"

# Build tooling: uv-managed CPython 3.13 (python-build-standalone) + pinned maturin
uv python install 3.13 >/dev/null
BV=$WORK/build-venv
[[ -d $BV ]] || uv venv --quiet --python 3.13 "$BV"
uv pip install --quiet --python "$BV/bin/python" "maturin==1.15.0" patchelf

{
  echo "tag=$TAG commit=$COMMIT"
  echo "rustup_toolchain=$(rustup show active-toolchain)"
  rustc --version; cargo --version
  "$BV/bin/maturin" --version
  "$BV/bin/python" -c 'import sys,sqlite3;print("python",sys.version.split()[0],"sqlite",sqlite3.sqlite_version)'
  uv --version; cc --version | sed -n 1p; ldd --version | sed -n 1p
} > "$EVID/toolchain.txt" 2>&1

FEATURES="extension-module,arrow,high-precision,mimalloc,tracing-bridge,adapter-sandbox,adapter-databento"
# Feature graph with exactly the flags the wheel build uses (pyproject: no-default-features + FEATURES)
cargo tree --locked -p nautilus-pyo3 -e features --no-default-features --features "$FEATURES" \
  > "$EVID/cargo-tree-features.txt"
cargo tree --locked -p nautilus-pyo3 -e normal --no-default-features --features "$FEATURES" --prefix none \
  | sed 's/ (\*)//' | sort -u > "$EVID/cargo-tree-crates.txt"

cargo tree --locked -p nautilus-pyo3 -e normal --no-default-features --features "$FEATURES" -f '{p} [{f}]' --prefix none \
  | sed 's/ (\*)//' | sort -u > "$EVID/cargo-tree-enabled-features.txt"

START=$(date +%s)
( cd python && PATH="$BV/bin:$PATH" VIRTUAL_ENV= CARGO_TARGET_DIR="$WORK/target" \
    "$BV/bin/maturin" build --release --locked --out "$WORK/dist" ) 2>&1 | tee "$WORK/maturin-build.log" | tail -5
END=$(date +%s)
echo "build_seconds=$((END-START))" > "$EVID/build-duration.txt"
grep -E 'Building|features|Built wheel' "$WORK/maturin-build.log" > "$EVID/maturin-summary.txt" || true
WHL=$(ls -t "$WORK"/dist/nautilus_trader-2.0.0rc9-*.whl | sed -n 1p)
sha256sum "$WHL" | sed "s#$WORK/dist/##" > "$EVID/wheel.sha256"
python3 -I -c 'import sys,zipfile;[print(n) for n in sorted(zipfile.ZipFile(sys.argv[1]).namelist())]' "$WHL" > "$EVID/wheel-manifest.txt"
echo "$WHL"
