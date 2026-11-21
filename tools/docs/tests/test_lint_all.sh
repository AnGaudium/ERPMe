#!/usr/bin/env bash
# Test of the drift check of lint_all.sh: a throwaway git repo, a stub linter. Usage: bash test_lint_all.sh [path/to/lint_all.sh]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${1:-$HERE/lint_all.sh}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cd "$T"; git init -q .; git config user.email t@t; git config user.name t
mkdir -p adr compiled
printf '# ADR-0022\n\n   | Layer | Modules |\n   | --- | --- |\n   | 3 · Core | `foo` (x), `bar` |\n' > adr/0022-conv.md
printf '# ADR-0099\nrule\n' > adr/0099-foo.md
printf 'id,kind,primary_module,modules,source_file\nADR-0099.R1,rule,foo,foo,docs/adr/0099-foo.md\n' > index.csv
printf 'bar no rule of its own\n' > compiled/SKIP.txt
git add -A; git commit -qm base
IDX="$(git rev-parse --short HEAD)"
printf 'Module: foo    Chunk: whole    Source ADRs: ADR-0099\nBuild step(s): 0    Generated from index: %s    Compiled by: t\n' "$IDX" > compiled/foo.md
echo 'print("LINT PASS findings=0")' > stub.py
git add -A; git commit -qm spec
run() { DOCS_DIR="$T/compiled" INDEX="$T/index.csv" ADR_DIR="$T/adr" LINT="$T/stub.py" PYTHON=python3 bash "$SCRIPT"; }
out="$(run)" || { echo "FAIL: clean state must pass"; echo "$out"; exit 1; }
echo "ok: passes before the ADR edit"
echo "changed" >> adr/0099-foo.md; git commit -qam "edit ADR after the index commit"
if out="$(run)"; then echo "FAIL: drift not detected"; echo "$out"; exit 1; fi
echo "$out" | grep -q DRIFT || { echo "FAIL: no DRIFT message"; echo "$out"; exit 1; }
echo "ok: fails after the ADR edit with a DRIFT message"
# a missing required module must fail
rm compiled/foo.md; git add -A; git commit -qm rm
if run >/dev/null; then echo "FAIL: missing spec not detected"; exit 1; fi
echo "ok: missing required spec fails"
echo "ALL TESTS PASSED"
