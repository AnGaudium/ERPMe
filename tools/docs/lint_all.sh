#!/usr/bin/env bash
# Lint every compiled spec in docs/compiled/ against the rule index, one doc_lint.py run per module.
#
# Usage: tools/docs/lint_all.sh
# Env overrides (defaults are the real paths): DOCS_DIR (docs/compiled), INDEX (docs/design/generated/rule-index.csv),
#   ADR_DIR (docs/adr), LINT (tools/docs/doc_lint.py), PYTHON.
#
# Files are named <module>.md or <module>-<n>.md (chunks). The front matter `Module:` must equal the file-name module.
# Per module: doc_lint.py <all files> --module <m> (--index-commit left default), plus a DRIFT CHECK: the last commit
# that touched an ADR file affecting the module (source_file of the index rows whose primary_module or modules contains
# the module) must be an ancestor of, or equal to, the `Generated from index:` commit of the spec. Otherwise an ADR
# changed after the spec was generated and the spec is stale.
#
# Coverage: every module of ADR-0022 rule 2, except `process` and the modules in DOCS_DIR/SKIP.txt, must have a spec.
# SKIP.txt: one module per line, then a reason; `#` starts a comment. For modules that own no rule (zero primary rules
# in the index), such as: api db errors i18n ids sdk.
#
# Output: one line per module (PASS or FAIL, then the first line of the lint), then the full lint output of every
# failing module. Exit 1 when any module fails or a required module has no spec; 2 on bad setup.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DOCS_DIR="${DOCS_DIR:-$REPO/docs/compiled}"
INDEX="${INDEX:-$REPO/docs/design/generated/rule-index.csv}"
ADR_DIR="${ADR_DIR:-$REPO/docs/adr}"
LINT="${LINT:-$HERE/doc_lint.py}"
PY="${PYTHON:-$HOME/Projects/NativeFlows-lab/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
[ -d "$DOCS_DIR" ] || { echo "no spec folder: $DOCS_DIR" >&2; exit 2; }
[ -f "$INDEX" ] || { echo "no index: $INDEX" >&2; exit 2; }
ADR22="$(ls "$ADR_DIR"/0022-*.md 2>/dev/null | head -1 || true)"
[ -n "$ADR22" ] || { echo "no ADR-0022 in $ADR_DIR" >&2; exit 2; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Group files by module and confirm the front matter module: "<module> <file>" lines; problems to $TMP/problems.
"$PY" - "$DOCS_DIR" > "$TMP/groups" 2> "$TMP/problems" <<'PYE'
import os, re, sys
d = sys.argv[1]
for f in sorted(os.listdir(d)):
    m = re.fullmatch(r"([a-z][a-z0-9_]*?)(?:-(\d+))?\.md", f)
    if not m or f == "CONFLICTS.md":
        continue
    head = open(os.path.join(d, f), encoding="utf-8").read(3000)
    fm = re.search(r"^Module:\s*([A-Za-z0-9_]+)", head, re.M)
    if not fm or fm.group(1) != m.group(1):
        print(f"BADMODULE {m.group(1)} {f}: front matter Module `{fm.group(1) if fm else 'missing'}` differs from the file name module", file=sys.stderr)
    print(m.group(1), os.path.join(d, f))
PYE

# Required modules: backticked module names that start an item in the ADR-0022 rule 2 table.
"$PY" - "$ADR22" > "$TMP/required" <<'PYE'
import re, sys
out = []
for line in open(sys.argv[1], encoding="utf-8"):
    m = re.match(r"\s*\|\s*\d\s*·[^|]*\|(.*)\|\s*$", line)
    if not m:
        continue
    cell, depth, item_start = m.group(1), 0, True
    i = 0
    while i < len(cell):
        c = cell[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and c == "`":
            j = cell.index("`", i + 1)
            if item_start and re.fullmatch(r"[a-z_][a-z0-9_]*", cell[i + 1:j]):
                out.append(cell[i + 1:j])
            item_start = False
            i = j
        elif depth == 0 and c == ",":
            item_start = True
        i += 1
print("\n".join(sorted(set(out))))
PYE

fail=0
if [ -s "$TMP/problems" ]; then sed 's/^BADMODULE [^ ]* //' "$TMP/problems"; fail=1; fi

declare -A SKIP=()
if [ -f "$DOCS_DIR/SKIP.txt" ]; then
  while read -r m _; do case "$m" in ''|'#'*) ;; *) SKIP[$m]=1 ;; esac; done < "$DOCS_DIR/SKIP.txt"
fi

: > "$TMP/fails"
have=""
for m in $(cut -d' ' -f1 "$TMP/groups" | sort -u); do
  have="$have $m"
  files=$(awk -v m="$m" '$1==m{print $2}' "$TMP/groups")
  out="$TMP/lint-$m.txt"
  extra=""; [ "$m" = process ] && extra="--allow-process"
  rc=0
  # shellcheck disable=SC2086
  "$PY" "$LINT" $files --module "$m" $extra > "$out" 2>&1 || rc=$?
  drift=""
  "$PY" - "$INDEX" "$ADR_DIR" "$m" $files > "$TMP/adrs-$m" 2> "$TMP/drift-$m" <<'PYE' || true
import csv, os, re, sys
index, adr_dir, mod = sys.argv[1:4]
commits = set()
for f in sys.argv[4:]:
    t = re.search(r"Generated from index:\s*([0-9a-f]{7,40})", open(f, encoding="utf-8").read(3000))
    commits.add(t.group(1) if t else "")
if len(commits) != 1 or "" in commits:
    print(f"`Generated from index:` missing or different across the files of {mod}: {sorted(commits)}", file=sys.stderr); sys.exit(1)
print("COMMIT", commits.pop())
seen = set()
for r in csv.DictReader(open(index, encoding="utf-8")):
    if mod in r["primary_module"].split(";") or mod in r["modules"].split(";"):
        seen.add(os.path.join(adr_dir, os.path.basename(r["source_file"])))
for p in sorted(seen):
    print(p)
PYE
  if [ -s "$TMP/drift-$m" ]; then
    drift="$(cat "$TMP/drift-$m")"
  else
    idx="$(sed -n 's/^COMMIT //p' "$TMP/adrs-$m")"
    mapfile -t adrs < <(grep -v '^COMMIT ' "$TMP/adrs-$m" || true)
    if ! git -C "$ADR_DIR" cat-file -e "$idx^{commit}" 2>/dev/null; then
      drift="index commit $idx of the spec is not a commit of this repository"
    elif [ "${#adrs[@]}" -gt 0 ]; then
      last="$(git -C "$ADR_DIR" log -1 --format=%h -- "${adrs[@]}")"
      if [ -n "$last" ] && ! git -C "$ADR_DIR" merge-base --is-ancestor "$last" "$idx"; then
        drift="DRIFT: an ADR affecting $m changed in commit $last, after the index commit $idx the spec was generated from; regenerate the spec"
      fi
    fi
  fi
  if grep -q "^BADMODULE $m " "$TMP/problems"; then drift="${drift:+$drift; }front matter Module differs from the file name"; fi
  first="$(head -1 "$out")"
  if [ "$rc" -eq 0 ] && [ -z "$drift" ]; then
    echo "PASS $m: $first"
  else
    echo "FAIL $m: ${first:-no lint output (exit $rc)}${drift:+ | $drift}"
    echo "$m" >> "$TMP/fails"
    [ -n "$drift" ] && echo "$drift" >> "$out"
    fail=1
  fi
done

while read -r m; do
  [ -n "$m" ] && [ "$m" != process ] && [ -z "${SKIP[$m]:-}" ] || continue
  case " $have " in *" $m "*) ;; *) echo "FAIL $m: no spec in $DOCS_DIR (and not in SKIP.txt)"; fail=1 ;; esac
done < "$TMP/required"

for m in $(cat "$TMP/fails"); do
  echo; echo "=== full lint output: $m ==="; cat "$TMP/lint-$m.txt"
done
exit "$fail"
