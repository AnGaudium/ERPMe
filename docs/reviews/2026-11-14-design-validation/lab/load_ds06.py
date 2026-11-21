"""Lab: order DS-06 statements by table dependency and prepend stubs. Not product code."""
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
# split into statements, respecting $$ bodies
stmts, buf, in_dollar = [], [], False
for line in src.splitlines(keepends=True):
    if line.strip().startswith("--") and not in_dollar:
        continue
    buf.append(line)
    if line.count("$$") % 2 == 1:
        in_dollar = not in_dollar
    if not in_dollar and line.rstrip().endswith(";"):
        stmts.append("".join(buf)); buf = []
tables, others = {}, []
for s in stmts:
    m = re.match(r"\s*CREATE TABLE (\w+)", s)
    if m:
        tables[m.group(1)] = s
    else:
        others.append(s)
deps = {t: {r for r in re.findall(r"(?:REFERENCES|PARTITION OF) (\w+)", s) if r in tables and r != t} for t, s in tables.items()}
order, seen = [], set()
def visit(t, stack=()):
    if t in seen: return
    if t in stack: raise SystemExit("cycle " + " -> ".join(stack + (t,)))
    for d in sorted(deps[t]): visit(d, stack + (t,))
    seen.add(t); order.append(t)
for t in tables: visit(t)
external = sorted({r for s in tables.values() for r in re.findall(r"REFERENCES (\w+)", s)} - set(tables))
print("-- external:", ", ".join(external), file=sys.stderr)
print("-- order:", ", ".join(order), file=sys.stderr)
out = [tables[t] for t in order] + others
sys.stdout.write("".join(out))
from lab import id_default_shim_sql  # noqa: E402  the lab-only id default of S2 schema phase B (lab.py, README)
sys.stdout.write("\n" + id_default_shim_sql())
