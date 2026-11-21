"""Lab: load every DDL file of docs/design/ into one database, in one dependency order. Not product code.

The combined loader of the catalog review (check 12), used by the final simulation:

1. 00_stubs.sql drops and rebuilds schemas nativeflows and types with the domains, without the stub tables that a DDL file now
   defines (user_account: DS-15; document: DS-05-platform; material_document and its lines: DS-22-09-42).
2. The extensions btree_gist (ADR-0007) and pg_trgm (ADR-0002) live in schema nativeflows, the schema the DDL runs in, so the
   gist and trigram operator classes resolve with search_path = nativeflows. An extension already installed in another schema
   of the database is moved into nativeflows (dropping nativeflows later drops it with the schema).
3. All DDL files are split into statements and ordered in one pass, as load_ds06.py does: every CREATE TABLE in
   dependency order (REFERENCES and PARTITION OF), then every other statement in file order. The files are taken in
   the order of FILE_ORDER, then any other design/*.sql file by name. A table defined twice is an error.
4. SET search_path = nativeflows, then each statement runs, in transactions of LOAD_BATCH statements after the stubs' own
   (one transaction for all of them exceeds max_locks_per_transaction at about 300 tables); a failure names
   the file and line.

Guard: a line whose code ends in ';' followed by a trailing comment is refused. load_ds06.py splits statements at lines
ending in ';', and such a line silently merges two statements there (lab finding L-13).

Usage:  python3 load_all.py <dsn> <docs dir>      prints the number of tables in schema nativeflows
Module: from load_all import load_all; load_all(dsn, docs_dir) -> int

Reloading: the tables already in schema nativeflows are dropped in batches of DROP_BATCH, each in its own transaction, before
the stubs drop the schema, so no transaction needs more locks than max_locks_per_transaction allows.

After the DDL, the lab-only stand-in for the command layer of S2 schema phase B runs: lab.id_default_shim_sql() gives
id the default uuidv7() on the tables that gained it in phase B, whose fixtures insert without an id (lab README).

Tables of DS-05-platform.sql get FORCE ROW LEVEL SECURITY; a role without BYPASSRLS (or not the superuser) must set
nativeflows.company_id before it reads or writes them (ADR-0017 rule 19).
"""
import glob
import os
import re
import sys

import psycopg

FILE_ORDER = ("DS-20-master-data.sql", "DS-06-universal-journal.sql", "DS-15-access.sql", "DS-35-crm.sql",
              "DS-56-product-configuration.sql", "DS-43-54-planning-production.sql",
              "DS-22-09-42-commercial-inventory.sql", "DS-05-platform.sql")
EXTENSIONS = ("btree_gist", "pg_trgm")
DROP_BATCH = 40
LOAD_BATCH = 150
LAB = os.path.join("reviews", "2026-11-14-design-validation", "lab")


def split_statements(text, name):
    """Split SQL text into (statement, first line number) pairs. Respects quotes, dollar quotes and comments; a statement
    keeps its comments. Returns the statements and the lines that end in ';' followed by a trailing comment."""
    out, buf, start, line = [], [], None, 1
    i, n, state, tag = 0, len(text), None, None
    trailing = []
    while i < n:
        ch = text[i]
        if state is None:
            if ch == "-" and text.startswith("--", i):
                j = text.find("\n", i)
                j = n if j < 0 else j
                before = text[text.rfind("\n", 0, i) + 1:i]
                if before.rstrip().endswith(";") and before.strip() != ";":
                    trailing.append(f"{name}:{line}")
                buf.append(text[i:j]); i = j
                continue
            if ch == "/" and text.startswith("/*", i):
                j = text.find("*/", i + 2)
                j = n if j < 0 else j + 2
                line += text.count("\n", i, j); buf.append(text[i:j]); i = j
                continue
            if ch == "'":
                state = "'"
            elif ch == "$":
                m = re.match(r"\$[A-Za-z_]*\$", text[i:])
                if m:
                    state, tag = "$", m.group(0)
                    if start is None:
                        start = line
                    buf.append(tag); i += len(tag)
                    continue
            elif ch == ";":
                buf.append(ch)
                stmt = "".join(buf).strip()
                if stmt != ";":
                    out.append((stmt, start if start is not None else line))
                buf, start = [], None
                i += 1
                continue
            if start is None and not ch.isspace():
                start = line
        elif state == "'":
            if ch == "'":
                state = None
        elif state == "$":
            if text.startswith(tag, i):
                buf.append(tag); i += len(tag); state = None
                continue
        if ch == "\n":
            line += 1
        buf.append(ch)
        i += 1
    rest = "".join(buf).strip()
    if rest and not all(l.strip().startswith("--") or not l.strip() for l in rest.splitlines()):
        raise SystemExit(f"{name}: text after the last ';' at line {start}")
    return out, trailing


def code_only(stmt):
    """The statement without comments and string literals, for dependency matching."""
    s = re.sub(r"--[^\n]*", "", stmt)
    s = re.sub(r"\$([A-Za-z_]*)\$.*?\$\1\$", "", s, flags=re.S)
    return re.sub(r"'(?:[^']|'')*'", "''", s)


def table_name(stmt):
    m = re.match(r"(?:--[^\n]*\n|\s)*CREATE TABLE (\w+)", stmt)
    return m.group(1) if m else None


def ddl_files(docs_dir):
    design = os.path.join(docs_dir, "design")
    present = {os.path.basename(p) for p in glob.glob(os.path.join(design, "*.sql"))}
    missing = [f for f in FILE_ORDER if f not in present]
    if missing:
        raise SystemExit("missing DDL files: " + ", ".join(missing))
    return [os.path.join(design, f) for f in FILE_ORDER] + sorted(os.path.join(design, f) for f in present - set(FILE_ORDER))


def build(docs_dir):
    """Returns (stub statements, ordered DDL statements as (sql, where)), without touching a database."""
    tables, others, guard = {}, [], []
    for path in ddl_files(docs_dir):
        name = os.path.basename(path)
        stmts, trailing = split_statements(open(path, encoding="utf-8").read(), name)
        guard += trailing
        for stmt, line in stmts:
            t = table_name(stmt)
            where = f"{name}:{line}"
            if t:
                if t in tables:
                    raise SystemExit(f"table {t} defined twice: {tables[t][1]} and {where}")
                tables[t] = (stmt, where)
            else:
                others.append((stmt, where))
    if guard:
        raise SystemExit("trailing comment after ';' (load_ds06.py would merge two statements): " + ", ".join(guard))
    stub_path = os.path.join(docs_dir, LAB, "00_stubs.sql")
    stub_stmts, _ = split_statements(open(stub_path, encoding="utf-8").read(), "00_stubs.sql")
    stubs = [s for s, _ in stub_stmts if table_name(s) not in tables]
    stub_tables = {table_name(s) for s in stubs} - {None}
    deps = {}
    for t, (stmt, _) in tables.items():
        code = code_only(stmt)
        refs = set(re.findall(r"REFERENCES (\w+)", code)) | set(re.findall(r"PARTITION OF (\w+)", code))
        deps[t] = sorted(r for r in refs if r in tables and r != t)
        unknown = sorted(r for r in refs if r not in tables and r not in stub_tables)
        if unknown:
            raise SystemExit(f"{t} refers to tables no file or stub defines: {', '.join(unknown)}")
    order, seen = [], set()

    def visit(t, stack=()):
        if t in seen:
            return
        if t in stack:
            raise SystemExit("cycle " + " -> ".join(stack + (t,)))
        for d in deps[t]:
            visit(d, stack + (t,))
        seen.add(t)
        order.append(t)
    for t in tables:
        visit(t)
    return stubs, [tables[t] for t in order] + others


def drop_in_batches(cx):
    """Drop the tables of schema nativeflows in batches, each in its own transaction (partitions go with their parent)."""
    names = [r[0] for r in cx.execute("select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
                                      " where n.nspname = 'nativeflows' and c.relkind in ('r', 'p') and not c.relispartition"
                                      " order by c.relname").fetchall()]
    for i in range(0, len(names), DROP_BATCH):
        with cx.transaction():
            cx.execute("DROP TABLE IF EXISTS " + ", ".join(f"nativeflows.{n}" for n in names[i:i + DROP_BATCH]) + " CASCADE")


def load_all(dsn, docs_dir):
    """Load stubs, extensions and every DDL file of docs_dir/design into the database at dsn; returns the table count."""
    docs_dir = os.path.abspath(os.path.expanduser(docs_dir))
    stubs, ordered = build(docs_dir)
    with psycopg.connect(dsn, autocommit=True) as cx:      # autocommit: each transaction() block is a real transaction
        drop_in_batches(cx)
        with cx.transaction():                             # its own transaction: dropping a loaded schema takes many locks
            for s in stubs:
                cx.execute(s)
        with cx.transaction():
            for ext in EXTENSIONS:
                row = cx.execute("select n.nspname from pg_extension e join pg_namespace n on n.oid = e.extnamespace"
                                 " where e.extname = %s", (ext,)).fetchone()
                if row is None:
                    cx.execute(f"CREATE EXTENSION {ext} SCHEMA nativeflows")
                elif row[0] != "nativeflows":
                    print(f"note: extension {ext} moved from schema {row[0]} to nativeflows", file=sys.stderr)
                    cx.execute(f"ALTER EXTENSION {ext} SET SCHEMA nativeflows")
        for i in range(0, len(ordered), LOAD_BATCH):
            with cx.transaction():
                cx.execute("SET LOCAL search_path = nativeflows")
                for stmt, where in ordered[i:i + LOAD_BATCH]:
                    try:
                        cx.execute(stmt)
                    except psycopg.Error as e:
                        raise SystemExit(f"{where}: {str(e).splitlines()[0]}") from None
        with cx.transaction():                             # lab-only id default of S2 schema phase B (lab.py, README)
            from lab import id_default_shim_sql
            cx.execute(id_default_shim_sql())
        return cx.execute("select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace"
                          " where n.nspname = 'nativeflows' and c.relkind in ('r', 'p')").fetchone()[0]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: load_all.py <dsn> <docs dir>")
    print(f"{load_all(sys.argv[1], sys.argv[2])} tables in schema nativeflows")
