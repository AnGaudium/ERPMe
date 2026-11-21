#!/usr/bin/env bash
# Regenerate the rule index (committed), then the units, markers, summaries and dossiers, then run the tests.
# Usage: tools/docs/run_all.sh [--out DIR]
# Without --out the outputs go to a new temporary directory (printed at the end), so a run never overwrites a shared
# folder (S3 review S12).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-$HOME/Projects/NativeFlows-lab/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    *) echo "usage: $0 [--out DIR]" >&2; exit 2 ;;
  esac
done
[ -n "$OUT" ] || OUT="$(mktemp -d -t nativeflows-s3-XXXXXX)"
mkdir -p "$OUT"
"$PY" "$HERE/build_index.py" > "$OUT/index-summary.txt"
"$PY" "$HERE/extract_rules.py" --out "$OUT/units.jsonl" --markers-out "$OUT/conflict-markers.jsonl" > "$OUT/extract-summary.txt"
"$PY" "$HERE/build_dossiers.py" --out "$OUT/dossiers" --quiet
(cd "$HERE" && "$PY" -m unittest discover tests)
echo "ok: index docs/design/generated/rule-index.csv; units, markers, summaries and dossiers in $OUT"
