"""Lab helpers (not product code)."""
import os, uuid, psycopg
DSN = os.environ.get("ERPME_LAB_DSN", "host=127.0.0.1 port=5561 dbname=erpme_lab user=lab") + " options=-csearch_path=erpme"
def new(): return uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.UUID(bytes=uuid.uuid4().bytes)
def conn(): return psycopg.connect(DSN)
RESULTS = []
def expect(name, fn, should_fail, match=None):
    c = conn()
    try:
        with c.transaction():
            fn(c)
        ok = not should_fail
        detail = "succeeded"
    except Exception as e:
        msg = str(e).splitlines()[0]
        ok = should_fail and (match is None or match in msg)
        detail = "failed: " + msg
    finally:
        c.close()
    RESULTS.append((ok, name, detail)); print(("PASS " if ok else "FAIL ") + name + " -- " + detail)
