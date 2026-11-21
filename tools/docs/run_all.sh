#!/usr/bin/env bash
# Regenerate the rule index (committed) and the units, markers and dossiers (outside the repo), then run the tests.
# Usage: tools/docs/run_all.sh [OUT_DIR]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-$HOME/Projects/NativeFlows-lab/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
OUT="${1:-$HOME/Projects/NativeFlows-lab/fable/s3-out}"
mkdir -p "$OUT"
"$PY" "$HERE/build_index.py" > "$OUT/index-summary.txt"
"$PY" "$HERE/extract_rules.py" --out "$OUT/units.jsonl" --markers-out "$OUT/conflict-markers.jsonl" > "$OUT/extract-summary.txt"
"$PY" "$HERE/build_dossiers.py" --out "$OUT/dossiers" --quiet
(cd "$HERE" && "$PY" -m unittest discover tests)
echo "ok: index docs/design/generated/rule-index.csv; units, markers, summaries and dossiers in $OUT"
