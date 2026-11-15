"""Build the erpme_sim schema from the eight design DDL files (simulation helper, not product code).

Recipe (until docs/reviews/2026-11-14-design-validation/lab/load_all.py exists; it is used when present):
  lab/00_stubs.sql without the stub tables a DDL file defines (user_account, document, material_document,
  material_document_line); CREATE EXTENSION pg_trgm after SET search_path = erpme; the eight files concatenated
  and ordered by lab/load_ds06.py; SET search_path = erpme. Then sim_stubs.sql (tables with no DDL yet).
"""
import os, re, subprocess, sys, tempfile

DOCS = os.path.expanduser(os.environ.get("ERPME_DOCS", "~/Projects/ERPMe/docs"))
DESIGN = os.path.join(DOCS, "design")
LAB = os.path.join(DOCS, "reviews/2026-11-14-design-validation/lab")
HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["DS-05-platform.sql", "DS-06-universal-journal.sql", "DS-15-access.sql", "DS-20-master-data.sql",
         "DS-22-09-42-commercial-inventory.sql", "DS-35-crm.sql", "DS-43-54-planning-production.sql",
         "DS-56-product-configuration.sql"]
DEFINED_STUBS = ["user_account", "document", "material_document", "material_document_line"]


def build_sql():
    stubs = open(os.path.join(LAB, "00_stubs.sql"), encoding="utf-8").read()
    removed = []
    for t in DEFINED_STUBS:
        pat = re.compile(r"^CREATE TABLE %s \(.*?\);\n" % t, re.M | re.S)
        stubs, n = pat.subn("", stubs)
        if n:
            removed.append(t)
    stubs = stubs.replace("SET search_path = erpme;\n", "SET search_path = erpme;\nCREATE EXTENSION IF NOT EXISTS pg_trgm;\n", 1)
    src = "".join(open(os.path.join(DESIGN, f), encoding="utf-8").read() + "\n" for f in FILES)
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as tf:
        tf.write(src)
    p = subprocess.run([sys.executable, os.path.join(LAB, "load_ds06.py"), tf.name], capture_output=True, text=True)
    os.unlink(tf.name)
    if p.returncode:
        raise SystemExit("load_ds06.py failed: " + p.stderr[:500])
    external = next((l.split(":", 1)[1].strip() for l in p.stderr.splitlines() if l.startswith("-- external:")), "")
    sim_stubs = open(os.path.join(HERE, "sim_stubs.sql"), encoding="utf-8").read()
    remaining = sorted(set(re.findall(r"CREATE TABLE (\w+)", stubs)))
    info = {"recipe": "00_stubs.sql (minus %s) + pg_trgm + load_ds06.py order of %d files" % (", ".join(removed), len(FILES)),
            "design_files": ["docs/design/" + f for f in FILES], "lab_stub_tables": remaining,
            "external_refs": [e.strip() for e in external.split(",") if e.strip()],
            "sim_stub_tables": sorted(set(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+)", sim_stubs)))}
    return [stubs, "SET search_path = erpme;\n" + p.stdout, sim_stubs], info


def load(cx, dsn=None):
    """Prefer the repo's combined loader (lab/load_all.py); fall back to the recipe above when it is absent."""
    sim_stubs = open(os.path.join(HERE, "sim_stubs.sql"), encoding="utf-8").read()
    if os.path.isfile(os.path.join(LAB, "load_all.py")):
        sys.path.insert(0, LAB)
        from load_all import load_all
        n = load_all(dsn or os.environ.get("ERPME_SIM_DSN", "host=127.0.0.1 port=5561 dbname=erpme_sim user=lab password=lab"), DOCS)
        cx.execute(sim_stubs)
        stubs = open(os.path.join(LAB, "00_stubs.sql"), encoding="utf-8").read()
        defined = {r[0] for r in cx.execute("select table_name from information_schema.tables where table_schema='erpme'")}
        stub_tables = sorted(t for t in set(re.findall(r"CREATE TABLE (\w+)", stubs)) if t in defined and t not in DEFINED_STUBS)
        return {"recipe": "docs/reviews/2026-11-14-design-validation/lab/load_all.py (all design/*.sql in one dependency order, %d tables) + sim_stubs.sql" % n,
                "design_files": ["docs/design/" + os.path.basename(f) for f in sorted(__import__("glob").glob(os.path.join(DESIGN, "*.sql")))],
                "lab_stub_tables": stub_tables,
                "sim_stub_tables": sorted(set(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+)", sim_stubs)))}
    parts, info = build_sql()
    for sql in parts:
        cx.execute(sql)
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    with open(os.path.join(HERE, "build", "schema.sql"), "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(parts))
    return info


if __name__ == "__main__":
    import psycopg
    dsn = os.environ.get("ERPME_SIM_DSN", "host=127.0.0.1 port=5561 dbname=erpme_sim user=lab password=lab")
    cx = psycopg.connect(dsn); cx.autocommit = True
    info = load(cx)
    n = cx.execute("select count(*) from information_schema.tables where table_schema='erpme'").fetchone()[0]
    print(info); print("tables in erpme:", n)
