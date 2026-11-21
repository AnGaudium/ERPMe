"""Scenario: the platform DDL of DS-05-platform.sql loaded with DS-15, DS-20, DS-35, DS-56 and DS-06.

Part A first loads the platform file together with the other two holistic drafts (DS-43-54 planning and production,
DS-22-09-42 commercial and inventory, which refers to document, document_line_tax and the cash tables of this file)
when they are found, and checks that no table is defined twice. It then loads the six files of this scenario in one
dependency order (load_ds06.py) after 00_stubs.sql without the stubs they now define (user_account: DS-15; document:
DS-05-platform), with the two material_document stubs moved into the ordered source because they refer to document.
It checks external references, company_id coverage, the installation tables, recorded_at on every table, forced
row-level security, identifier lengths and the company policy for a role without BYPASSRLS.
Parts B to K walk a small dataset through the keys and checks: a document with versions and the final-state guards,
a policy decision with an approval plan and two stage approvals, taint on versions and its clearance, a work item and
its claim, a change proposal executed, an agent run with steps and budgets, a bank line proposed then matched at Post,
the outbox, audit and denial records, attachments, taxes and posting intents.
Not covered: commands, the dispatcher, consumers, the matching cascade, stage eligibility (t12), invariants that span
modules (INV-82, INV-95's amount, INV-212 over usage rows), partition maintenance.

Run: python t15_platform_ddl.py
  NATIVEFLOWS_LAB_DSN must name a throwaway database (schemas nativeflows and types are dropped and rebuilt); PGPASSWORD its password.
  NATIVEFLOWS_DOCS points at the docs/ tree whose design files and lab stubs are loaded (default ~/Projects/NativeFlows/docs).
  NATIVEFLOWS_PLATFORM_DDL, NATIVEFLOWS_DS22 and NATIVEFLOWS_DS43 override the paths of the three drafts (default <docs>/design/<file>);
  the combined load of part A is skipped when DS-22-09-42 or DS-43-54 is not found.
"""
import hashlib, json, os, re, subprocess, sys, tempfile
from datetime import date, datetime, timedelta, timezone

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
LAB = os.path.join(DOCS, "reviews/2026-11-14-design-validation/lab")
DESIGN = os.path.join(DOCS, "design")
PLATFORM = os.environ.get("NATIVEFLOWS_PLATFORM_DDL", os.path.join(DESIGN, "DS-05-platform.sql"))
DS22 = os.environ.get("NATIVEFLOWS_DS22", os.path.join(DESIGN, "DS-22-09-42-commercial-inventory.sql"))
DS43 = os.environ.get("NATIVEFLOWS_DS43", os.path.join(DESIGN, "DS-43-54-planning-production.sql"))
sys.path.insert(0, LAB)
from lab import RESULTS, conn, erasure_marker, insert_aged, new, ins_system_account, ins_account, ins_fiscal_year, ins_posting_period, ins_area_state  # noqa: E402

RLS_ROLE = "nativeflows_lab_rls"


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def trial(name, fn, should_fail, match=None):
    """Run fn in a transaction, fire deferred checks, roll back. should_fail: expect an error containing match."""
    c = conn()
    c.autocommit = True
    try:
        c.execute("BEGIN")
        fn(c)
        c.execute("SET CONSTRAINTS ALL IMMEDIATE")
        ok, detail = not should_fail, "succeeded"
    except Exception as e:  # noqa: BLE001
        msg = str(e).splitlines()[0]
        ok, detail = should_fail and (match is None or match in msg), "failed: " + msg
    finally:
        try:
            c.execute("ROLLBACK")
        finally:
            c.close()
    check(name, ok, detail)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


NOW = datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)
TODAY = date(2026, 11, 15)

# ======================================================================= A: load
stubs = open(os.path.join(LAB, "00_stubs.sql"), encoding="utf-8").read()
USER_STUB = "CREATE TABLE user_account (id uuid PRIMARY KEY);\n"                  # DS-15 (as t12)
DOC_STUB = ("CREATE TABLE document (id uuid PRIMARY KEY, company_id uuid NOT NULL, document_type text NOT NULL, state text NOT NULL DEFAULT 'draft',\n"
            "  UNIQUE (company_id, id));\n")
MOVED = [
    "CREATE TABLE material_document (id uuid PRIMARY KEY, document_id uuid NOT NULL UNIQUE REFERENCES document(id));\n",
    "CREATE TABLE material_document_line (id uuid PRIMARY KEY, material_document_id uuid NOT NULL REFERENCES material_document(id));\n",
]
for line in [USER_STUB, DOC_STUB] + MOVED:
    assert stubs.count(line) == 1, line
    stubs = stubs.replace(line, "")
platform = open(PLATFORM, encoding="utf-8").read()
FILES = ("DS-20-master-data.sql", "DS-06-universal-journal.sql", "DS-15-access.sql", "DS-35-crm.sql", "DS-56-product-configuration.sql")
base = {f: open(os.path.join(DESIGN, f), encoding="utf-8").read() for f in FILES}
# The stubs of the DS-05 tables (fiscal_year, posting_period, posting_period_area_state, close_task, tax_code) serve the labs
# that load DS-06 without DS-05. Here the platform file defines them, so their stubs are dropped (each stub may span lines).
DEFINED = set(re.findall(r"^CREATE TABLE (\w+)", platform + "".join(base.values()), flags=re.M))
STUB_DEFS = {m.group(1): m.group(0) for m in re.finditer(r"^CREATE TABLE (\w+) \(.*?\);\n", stubs, flags=re.M | re.S)}
DS05_STUBS = {t_: d_ for t_, d_ in STUB_DEFS.items() if t_ in DEFINED}
for d_ in DS05_STUBS.values():
    stubs = stubs.replace(d_, "")
stubs += "CREATE EXTENSION IF NOT EXISTS pg_trgm;\n"     # DS-35 search keys (ADR-0022 rule 8)
STUB_TABLES = set(re.findall(r"CREATE TABLE (\w+)", stubs)) | {"material_document", "material_document_line"}


def order(text):
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as tf_:
        tf_.write(text)
    p_ = subprocess.run([sys.executable, os.path.join(LAB, "load_ds06.py"), tf_.name], capture_output=True, text=True)
    os.unlink(tf_.name)
    return p_


# A00: the three holistic drafts together. load_ds06.py keeps the last of two CREATE TABLEs of one name, so duplicates are counted first.
if os.path.isfile(DS22) and os.path.isfile(DS43):
    drafts = {"DS-43-54": open(DS43, encoding="utf-8").read(), "DS-22-09-42": open(DS22, encoding="utf-8").read(), "DS-05-platform": platform}
    seen, dup = {}, []
    for name, text in list(base.items()) + list(drafts.items()):
        for tname in re.findall(r"^CREATE TABLE (\w+)", text, flags=re.M):
            if tname in seen:
                dup.append(f"{tname} ({seen[tname]}, {name})")
            seen.setdefault(tname, name)
    check("A00a no table is defined twice across DS-15, DS-20, DS-35, DS-56, DS-06 and the three holistic drafts", dup == [], dup)
    p_all = order("".join(t_ + "\n" for t_ in base.values()) + "".join(t_ + "\n" for t_ in drafts.values()))
    try:
        c_all = conn()
        c_all.autocommit = True
        c_all.execute(stubs)                               # DS-22-09-42 defines material_document and its lines
        c_all.execute(p_all.stdout)
        c_all.close()
        ok_all, why = p_all.returncode == 0, p_all.stderr[:200] if p_all.returncode else ""
    except Exception as e:  # noqa: BLE001
        ok_all, why = False, str(e).splitlines()[0]
    check("A00b the platform file loads together with DS-43-54 and DS-22-09-42", ok_all, why)
else:
    print("note: DS-22-09-42 or DS-43-54 not found; the combined load A00 is skipped")
src = "".join(t_ + "\n" for t_ in base.values()) + "".join(MOVED) + platform
with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as tf:
    tf.write(src)
p = subprocess.run([sys.executable, os.path.join(LAB, "load_ds06.py"), tf.name], capture_output=True, text=True)
os.unlink(tf.name)
external = [l for l in p.stderr.splitlines() if l.startswith("-- external:")]
ext = set(external[0].split(":", 1)[1].replace(" ", "").split(",")) - {""} if external else set()   # empty once every reference is defined
check("A01 load_ds06.py orders DS-20, DS-06, DS-15, DS-35, DS-56 and the platform file in one dependency order (no cycle)",
      p.returncode == 0, p.stderr[:200] if p.returncode else "")
check("A01b the six files refer to no table outside themselves except the remaining lab stubs", ext <= STUB_TABLES, sorted(ext - STUB_TABLES))
X0 = conn()
X0.autocommit = True
X = X0.execute
from load_all import drop_in_batches  # noqa: E402
drop_in_batches(X0)   # the combined load of A00 left about 390 tables; one DROP SCHEMA of all of them exceeds max_locks_per_transaction (as load_all.py)
X(stubs)
X(p.stdout)
check("A02 the stubs keep no document or user_account table of their own, and the loaded document is the platform one",
      X("select count(*) from information_schema.columns where table_schema='nativeflows' and table_name='document'").fetchone()[0] > 10)


def stub_columns(text):
    body = text.split("(", 1)[1]
    out = {}
    for part in re.split(r",\s*(?![^()]*\))", body):
        m = re.match(r"\s*([a-z_][a-z0-9_]*)\s+(uuid|text\[\]|text|integer|bigint|boolean|date|timestamptz|jsonb)(?=\s|$)(.*)", part, flags=re.S)
        if m and m.group(1) not in ("unique", "foreign", "primary", "constraint"):
            out[m.group(1)] = (m.group(2), "NOT NULL" in m.group(3) or "PRIMARY KEY" in m.group(3))
    return out


TYPES = {"ARRAY": "text[]", "integer": "integer", "bigint": "bigint", "boolean": "boolean", "date": "date", "jsonb": "jsonb", "text": "text", "uuid": "uuid",
         "timestamp with time zone": "timestamptz"}
drift = []
for t_, d_ in sorted(DS05_STUBS.items()):
    real = {r_[0]: (TYPES.get(r_[1], r_[1]), r_[2] == "NO") for r_ in X(
        "select column_name, data_type, is_nullable from information_schema.columns where table_schema='nativeflows' and table_name=%s", (t_,))}
    if stub_columns(d_) != real:
        drift.append(t_)
check(f"A02b the {len(DS05_STUBS)} lab stubs of DS-05 tables have the design columns, types and NOT NULLs", len(DS05_STUBS) == 5 and drift == [],
      sorted(DS05_STUBS) if drift == [] else drift)

tables = re.findall(r"^CREATE TABLE (\w+) \(", platform, flags=re.M)   # default partitions (PARTITION OF) follow their parent; A09 checks them
# tax_code moved from the installation tables to the shared reference catalogs with tax_rate, and tax_matrix joined the
# installation tables (ADR-0041 rules 2-4 notes, S2 closure 2026-11-21): a design change, so A04 and A05 follow it.
INSTALLATION = {"event_subject", "event_consumer", "agent_type", "agent_type_version", "regime_setting", "tax_matrix"}
NULLABLE = {"outbox_event", "event_delivery", "audit_record", "audit_change", "audit_denial", "agent_budget_usage", "idempotency_record",
            "tax_code", "tax_rate", "tax_treatment_rule"}


def cols(t):
    return {r[0]: r[1] for r in X("select column_name, is_nullable from information_schema.columns where table_schema='nativeflows' and table_name=%s", (t,))}


missing = [t for t in tables if t not in INSTALLATION and "company_id" not in cols(t)]
check(f"A03 all {len(tables) - len(INSTALLATION)} company tables of the platform file carry company_id", missing == [], missing)
check("A04 the six installation tables carry no company_id", [t for t in INSTALLATION if "company_id" in cols(t)] == [])
bad_null = [t for t in tables if t not in INSTALLATION and (cols(t)["company_id"] == "YES") != (t in NULLABLE)]
check(f"A05 company_id is nullable exactly on the {len(NULLABLE)} tables with installation-scoped or package rows", bad_null == [], bad_null)
check("A06 every platform table has recorded_at", [t for t in tables if "recorded_at" not in cols(t)] == [])
not_forced = [t for t in tables if t not in INSTALLATION and not X(
    "select relrowsecurity and relforcerowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace where nspname='nativeflows' and relname=%s", (t,)).fetchone()[0]]
check("A07 every company table of the platform file has forced row-level security and a company policy",
      not_forced == [] and X("select count(distinct tablename) from pg_policies where schemaname='nativeflows' and policyname='company_policy' and tablename = any(%s)",
                             (tables,)).fetchone()[0] == len(tables) - len(INSTALLATION),
      not_forced)
names = re.findall(r"(?:CONSTRAINT|INDEX|TRIGGER|FUNCTION) (\w+)", platform)
check("A08 every constraint, index, trigger and function name of the file is at most 63 bytes (ADR-0004 rule 6)",
      [n for n in names if len(n.encode()) > 63] == [], max(names, key=len))
check("A09 the four partitioned tables have a default partition",
      X("select count(*) from pg_inherits i join pg_class c on c.oid=i.inhrelid where c.relname in ('outbox_event_default','audit_record_default','audit_change_default','agent_run_step_default')").fetchone()[0] == 4)

# ---------------------------------------------------------------- fixtures
I = {k: new() for k in """co co2 uOwner uAcc uChief uSales uOther b1 p1 p2 e1 pba sa acBank acCash acRev acBank2 fy per tc
rAcc rChief rOwner poolPo poolGen poolSales stStd stSen stGen stSales procStd procSen
rule ruleV atype runR1 runR2 wiRun tk""".split()}
t = str(I["co"])[-8:]
X("insert into currency (code, minor_unit) values ('VND',0),('USD',2) on conflict do nothing")
for k in ("uOwner", "uAcc", "uChief", "uSales", "uOther"):
    X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,%s,'en','x',now())",
      (I[k], (k + t).lower(), k))
for k, code in (("co", "C15-"), ("co2", "C15B-")):
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Sample Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','warehouse',%s,'vi')", (I[k], code + t, I["uOwner"]))
X("insert into branch (id, company_id, code, name) values (%s,%s,'B1','B1')", (I["b1"], I["co"]))
X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,'P1','Supplier (sample)','organization','VN'),"
  " (%s,%s,'E1','Employee (sample)','individual','VN')", (I["p1"], I["co"], I["e1"], I["co"]))
X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,'P2','Other co partner','organization','VN')", (I["p2"], I["co2"]))
X("insert into partner_bank_account (id, company_id, partner_id, bank_name, account_number, holder_name) values (%s,%s,%s,'Bank (sample)','0001','Supplier')",
  (I["pba"], I["co"], I["p1"]))
ins_system_account(X, I["sa"], "cash_in_bank" + t)
for k, code in (("acBank", "1121"), ("acCash", "1111"), ("acRev", "5111"), ("acBank2", "1122")):
    ins_account(X, I[k], I["co"], code, I["sa"], "VND")
ins_fiscal_year(X, I["fy"], I["co"], "2026", "2026-01-01", "2026-12-31")
ins_posting_period(X, I["per"], I["co"], I["fy"], 11, "2026-11-01", "2026-11-30")
ins_area_state(X, I["co"], I["per"], "general", "open")
X("""insert into transaction_key (id, code, name, determinants, required_system_accounts, required_control_kind, has_regime_alternatives, added_in, meaning)
     values (%s,%s,'Input tax','{tax_code}','{tax_receivable_input}',null,false,'0.1.0','lab fixture')""", (I["tk"], "input_tax" + t))
X("""insert into tax_code (id, localization_package, code, name, tax_kind, direction, calculation, sequence, transaction_key_id, deductibility, basis)
     values (%s,'l10n_xx',%s,'Input VAT 10%%','vat','purchase','percent',1,%s,'deductible','{"status": "unverified"}')""", (I["tc"], "VAT10_IN_" + t, I["tk"]))
for k, code in (("rAcc", "accountant"), ("rChief", "chief_accountant"), ("rOwner", "owner")):
    X("""insert into role (id, company_id, code, name, template_code, basis, registry_version, expansion_hash) values (%s,%s,%s,%s,%s,'{"kind":"template"}','lab','x')""",
      (I[k], I["co"], code, code, code))
for k, code in (("poolPo", "po"), ("poolGen", "general"), ("poolSales", "sales")):
    X("""insert into approval_pool (id, company_id, code, name, basis) values (%s,%s,%s,%s,'{"kind":"core_seed"}')""", (I[k], I["co"], code, code))
for k, pool, seq, code, rank in (("stStd", "poolPo", 1, "standard", 10), ("stSen", "poolPo", 2, "senior", 20),
                                 ("stGen", "poolGen", 1, "standard", 10), ("stSales", "poolSales", 1, "standard", 10)):
    X("insert into approval_stage (id, company_id, approval_pool_id, sequence, code, name, min_rank, required_approvals) values (%s,%s,%s,%s,%s,%s,%s,1)",
      (I[k], I["co"], I[pool], seq, code, code, rank))
    X("insert into approval_stage_member (company_id, approval_stage_id, member_kind, role_id) values (%s,%s,'role',%s)", (I["co"], I[k], I["rOwner"]))
for k, code, rank in (("procStd", "standard", 10), ("procSen", "senior", 20)):
    X("""insert into approval_procedure (id, company_id, code, name, rank, basis, recorded_at) values (%s,%s,%s,%s,%s,'{"kind":"core_seed"}',now())""",
      (I[k], I["co"], code, code, rank))
X("insert into policy_rule (id, company_id, code, recorded_at) values (%s,%s,'po_senior',now())", (I["rule"], I["co"]))
X("""insert into policy_rule_version (id, company_id, policy_rule_id, version, effective_from, action, document_type, amount_company_min, effect,
     approval_procedure_id, is_enabled, recorded_at) values (%s,%s,%s,1,'2026-01-01','submit','purchase_order',100000000,'require_approval',%s,true,now())""",
  (I["ruleV"], I["co"], I["rule"], I["procSen"]))
X("insert into agent_type (id, code, name, recorded_at) values (%s,'bank_matching','Bank matching',now())", (I["atype"],))
X("""insert into agent_type_version (id, agent_type_code, version, content_hash, behavior_hash, declaration, recorded_at)
     values (%s,'bank_matching','1.0.0',%s,%s,'{"steps":["read_description","record_suggestion"]}',now())""", (new(), "a" * 64, "b" * 64))
X("insert into agent_type_setting (id, company_id, agent_type_code, mode, workflow_owner_id, recorded_at) values (%s,%s,'bank_matching','shadow',%s,now())",
  (new(), I["co"], I["uChief"]))


def doc(cx, did, dtype, state="draft", by="uAcc", co="co", partner=None, number=None, posted_at=None, **kw):
    cx.execute("""insert into document (id, company_id, document_type, state, version, number, partner_id, created_by_user_id, posted_at,
                  origin_work_item_id, workflow_step, draft_ordinal, change_state, pending_version, reversal_of_id, recorded_at)
                  values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())""",
               (did, I[co], dtype, state, kw.get("version", 1), number, partner, I[by], posted_at, kw.get("wi"), kw.get("step"),
                kw.get("ordinal"), kw.get("change_state", "none"), kw.get("pending_version"), kw.get("reversal_of")))
    return did


def version(cx, did, v, content, actor_kind="human", actor="uAcc", tainted=False, run=None, origin=None, derived=None, co="co", at=None, vid=None):
    vid = vid or new()
    sql = """insert into document_version (id, company_id, document_id, version, content, version_hash, actor_kind, actor_id, on_behalf_of_id,
             agent_run_id, origin_agent_run_id, is_tainted, derived_from_version_id, recorded_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    params = (vid, I[co], did, v, json.dumps(content), sha(content), actor_kind, I[actor] if actor in I else actor,
              I[actor] if actor_kind == "human" else I["uChief"], run, origin, tainted, derived, at or NOW)
    if at:      # recorded_at is the system's time (ADR-0007 rule 9); a fixture that names its time of writing keeps it (lab-only insert_aged)
        insert_aged(cx.execute, "document_version", sql, params)
    else:
        cx.execute(sql, params)
    return vid


def run(cx, rid, tainted_at=None, state="running", outcome=None, wi=None, **kw):
    cx.execute("""insert into agent_run (id, company_id, agent_type_code, agent_type_version, seatmap_hash, mode, trigger_kind, work_item_id,
                  started_by_kind, on_behalf_of_id, scope_kind, subject_table, subject_id, tainted_at, taint_source_kind, budget, state, outcome,
                  started_at, ended_at, llm_call_count, cost_amount, reserved_amount, denial_count, recorded_at)
                  values (%s,%s,'bank_matching','1.0.0','h','live','work_item',%s,'system',%s,'subject','bank_statement_line',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())""",
               (rid, I["co"], wi, I["uChief"], new(), tainted_at, "outside_subject" if tainted_at else None,
                json.dumps(kw.get("budget", {"max_llm_calls": 4, "max_tool_calls": 8, "max_cost": "0.50", "max_rows_read": 500})),
                state, outcome, NOW, NOW if state in ("completed", "stopped", "canceled") else None,
                kw.get("calls", 0), kw.get("cost", 0), kw.get("reserved", 0), kw.get("denials", 0)))
    return rid


def work_item(cx, wid, kind="bank_line_unmatched", key=None, owner_kind="role", owner_role="accountant", state="open", **kw):
    cx.execute("""insert into work_item (id, company_id, kind, subject_table, subject_id, open_key, state, owner_kind, owner_user_id, owner_role,
                  owner_approval_stage_id, due_date, is_tainted, claimed_by_kind, claimed_by_id, claimed_at, claim_expires_at, resolution, resolved_at,
                  version, recorded_at) values (%s,%s,%s,'document',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,now())""",
               (wid, I["co"], kind, kw.get("subject", new()), key or str(wid), state, owner_kind, kw.get("owner_user"),
                owner_role if owner_kind == "role" else None, kw.get("stage"), TODAY + timedelta(days=2), kw.get("tainted", False),
                kw.get("claimed_by_kind"), kw.get("claimed_by_id"), NOW if kw.get("claimed_by_kind") else None, kw.get("expires"),
                kw.get("resolution"), NOW if state in ("done", "canceled") else None))
    return wid


# ---------------------------------------------------------------- A10: the company policy for a role without BYPASSRLS
d_rls = doc(X0, new(), "purchase_order")
doc(X0, new(), "purchase_order", co="co2", by="uOther")
if not X("select 1 from pg_roles where rolname=%s", (RLS_ROLE,)).fetchone():
    X(f"CREATE ROLE {RLS_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS")
X(f"GRANT USAGE ON SCHEMA nativeflows, types TO {RLS_ROLE}")
X(f"GRANT SELECT ON ALL TABLES IN SCHEMA nativeflows TO {RLS_ROLE}")


def rls_counts(cx):
    cx.execute(f"SET LOCAL ROLE {RLS_ROLE}")
    none_ = cx.execute("select count(*) from document").fetchone()[0]
    cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
    own = cx.execute("select count(*) from document").fetchone()[0]
    other = cx.execute("select count(*) from document where company_id=%s", (I["co2"],)).fetchone()[0]
    cx.execute("select set_config('nativeflows.company_id', 'installation', true)")
    inst = cx.execute("select count(*) from document").fetchone()[0]
    return none_, own, other, inst


c = conn()
c.autocommit = True
c.execute("BEGIN")
counts = rls_counts(c)
c.execute("ROLLBACK")
c.close()
check("A10 as a role without BYPASSRLS: no setting shows no document, the company setting shows its own only, installation shows none of the company rows",
      counts[0] == 0 and counts[1] >= 1 and counts[2] == 0 and counts[3] == 0, counts)

# A11 (S2 adversarial review N1): the role reproduced there updated another company's partner rows, which had no policy. Every
# company table of every design file now has the generated policies (t31 part Z checks the whole catalog).
X(f"GRANT UPDATE ON partner TO {RLS_ROLE}")


def other_company_partner_update(cx):
    cx.execute(f"SET LOCAL ROLE {RLS_ROLE}")
    cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co2"]),))
    n = cx.execute("update partner set name = name where company_id = %s", (I["co"],)).rowcount
    own = cx.execute("select count(*) from partner where company_id = %s", (I["co"],)).fetchone()[0]
    if n or own:
        raise RuntimeError(f"company 2 saw {own} and updated {n} partner rows of company 1")


trial("A11 as a role without BYPASSRLS under company 2, company 1's partner rows are neither visible nor updated (DS-20 has the policies)",
      other_company_partner_update, False)

# ======================================================================= B: documents and versions
D1 = doc(X0, new(), "purchase_order", partner=I["p1"])
V1 = version(X0, D1, 1, {"lines": [{"line_number": 1, "quantity": "10"}]})
V2 = version(X0, D1, 2, {"lines": [{"line_number": 1, "quantity": "12"}]})
X("update document set version=2 where id=%s", (D1,))
check("B01 a document with two versions; version content hashes differ", V1 != V2 and X("select count(distinct version_hash) from document_version where document_id=%s", (D1,)).fetchone()[0] == 2)
trial("B02 a second row for one (document, version) is refused", lambda cx: version(cx, D1, 2, {"x": 1}), True, "document_version_document_id_version_key")
trial("B03 a version hash that is not SHA-256 hex is refused", lambda cx: cx.execute(
    "insert into document_version (id, company_id, document_id, version, content, version_hash, actor_kind, actor_id, is_tainted, recorded_at) values (%s,%s,%s,9,'{}','abc','human',%s,false,now())",
    (new(), I["co"], D1, I["uAcc"])), True, "ck_document_version_version_hash")
trial("B04 a version of another company's document is refused (composite key)", lambda cx: version(cx, D1, 3, {"y": 1}, co="co2"), True, "fk")
trial("B05 versions are never updated (ADR-0009 rule 14)", lambda cx: cx.execute("update document_version set content='{}' where id=%s", (V1,)), True, "never updated")
trial("B06 a version is deleted only with its draft, under nativeflows.document_delete_id", lambda cx: (
    cx.execute("select set_config('nativeflows.document_delete_id', %s, true)", (str(D1),)),
    cx.execute("delete from document_version where document_id=%s", (D1,)), cx.execute("delete from document where id=%s", (D1,))), False)
trial("B07 without the setting a draft's versions cannot be deleted", lambda cx: cx.execute("delete from document_version where document_id=%s", (D1,)), True, "never updated or deleted")
trial("B08 INV-43: a pending version without a change state is refused", lambda cx: doc(cx, new(), "sales_order", pending_version=2), True, "ck_document_pending_version")
trial("B09 INV-43: a pending version not above the version in force is refused",
      lambda cx: doc(cx, new(), "sales_order", state="approved", change_state="drafting", pending_version=1), True, "ck_document_pending_version")
trial("B10 INV-44: a document in issuing has no number", lambda cx: doc(cx, new(), "sales_invoice", state="issuing", number="SI/1"), True, "ck_document_issuing_number")
trial("B11 numbers are unique per company and document type", lambda cx: (
    doc(cx, new(), "bank_payment", state="posted", number="BP/2026/000001", posted_at=NOW),
    doc(cx, new(), "bank_payment", state="posted", number="BP/2026/000001", posted_at=NOW)), True, "uq_document_company_id_document_type_number")
trial("B12 a posted document has posted_at", lambda cx: doc(cx, new(), "bank_payment", state="posted"), True, "ck_document_posted_at")
D_post = doc(X0, new(), "general_journal", state="posted", number="GJ/1", posted_at=NOW)
trial("B13 a posted document never changes (ADR-0009 rule 14)", lambda cx: cx.execute("update document set partner_id=%s where id=%s", (I["p1"], D_post)), True, "immutable")
trial("B14 Reverse may move posted to reversed and nothing else", lambda cx: cx.execute("update document set state='reversed' where id=%s", (D_post,)), False)
trial("B15 a document is reversed at most once", lambda cx: (
    doc(cx, new(), "general_journal", state="posted", number="GJ/2", posted_at=NOW, reversal_of=D_post),
    doc(cx, new(), "general_journal", state="posted", number="GJ/3", posted_at=NOW, reversal_of=D_post)), True, "uq_document_reversal_of_id")
trial("B16 only a draft is deleted", lambda cx: cx.execute("delete from document where id=%s", (D_post,)), True, "only a draft")
WI_D = work_item(X0, new(), kind="supplier_invoice_received")
trial("B17 ADR-0030 rule 11: a second agent draft for one work item, step and ordinal is refused", lambda cx: (
    doc(cx, new(), "purchase_invoice", wi=WI_D, step="purchase_invoice.draft", ordinal=1),
    doc(cx, new(), "purchase_invoice", wi=WI_D, step="purchase_invoice.draft", ordinal=1)), True, "ux_document_draft_key")
trial("B18 ... but a canceled draft frees its key", lambda cx: (
    doc(cx, new(), "purchase_invoice", state="canceled", wi=WI_D, step="purchase_invoice.draft", ordinal=1),
    doc(cx, new(), "purchase_invoice", wi=WI_D, step="purchase_invoice.draft", ordinal=1)), False)

# ======================================================================= C: policy decision with a plan, stage approvals
D2 = doc(X0, new(), "purchase_order", partner=I["p1"])
V21 = version(X0, D2, 1, {"lines": [{"line_number": 1, "amount": "150000000"}]})
PLAN = [{"id": str(I["stStd"]), "sequence": 1, "code": "standard", "min_rank": 10, "k": 1, "scope_binding": "document_scope", "escalation_role_id": None, "due_days": 2},
        {"id": str(I["stSen"]), "sequence": 2, "code": "senior", "min_rank": 20, "k": 1, "scope_binding": "document_scope", "escalation_role_id": None, "due_days": 2}]


def decision(cx, did, vid, outcome="approval_required", rank=20, proc="procSen", pool="poolPo", plan=PLAN, actor="uAcc", **kw):
    pid = kw.get("pid", new())
    cx.execute("""insert into policy_decision (id, company_id, document_id, document_version_id, action, actor_kind, actor_id, on_behalf_of_id, outcome,
                  policy_rule_id, policy_rule_version, matching_rules, approval_procedure_id, required_rank, human_post, policy_input_hash,
                  approval_pool_id, approval_plan, continues_policy_decision_id, is_confirmation_required, decided_at, recorded_at)
                  values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),now())""",
               (pid, I["co"], did, vid, kw.get("action", "submit"), kw.get("actor_kind", "human"), I[actor], None, outcome,
                I["rule"] if rank else None, 1 if rank else None, json.dumps([{"policy_rule_id": str(I["rule"]), "version": 1}] if rank else []),
                I[proc] if proc else None, rank, kw.get("human_post", False), "c" * 64, I[pool] if pool else None,
                json.dumps(plan) if plan is not None else None, kw.get("continues"), kw.get("confirm", False)))
    return pid


PD = decision(X0, D2, V21)
X("update document set state='pending_approval' where id=%s", (D2,))
check("C01 a policy decision at Submit stores rank 20, pool po and a two-stage plan (ADR-0055 rule 6)",
      X("select required_rank, jsonb_array_length(approval_plan) from policy_decision where id=%s", (PD,)).fetchone() == (20, 2))
trial("C02 INV-230: a rank without a plan is refused", lambda cx: decision(cx, D2, V21, plan=None), True, "ck_policy_decision_plan")
trial("C03 INV-230: a rank with an empty plan is refused", lambda cx: decision(cx, D2, V21, plan=[]), True, "ck_policy_decision_plan")
trial("C04 ADR-0043 rule 8: approval_required needs a rank and a procedure", lambda cx: decision(cx, D2, V21, rank=None, proc=None, pool=None, plan=None), True, "ck_policy_decision_rank")
trial("C05 ADR-0043 rule 8: human_only carries human_post", lambda cx: decision(cx, D2, V21, outcome="human_only", rank=None, proc=None, pool=None, plan=None), True, "ck_policy_decision_human_post")
trial("C06 confirmation only on an allowed outcome", lambda cx: decision(cx, D2, V21, outcome="human_only", rank=None, proc=None, pool=None, plan=None, human_post=True, confirm=True),
      True, "ck_policy_decision_confirmation")
trial("C07 a decision on a version of another document is refused (composite key to the version)", lambda cx: decision(cx, D_post, V21), True, "fk")


def approve(cx, actor, stage, pool="poolPo", pid=None, vid=None, did=None, decision_="approved", **kw):
    aid = new()
    cx.execute("""insert into approval (id, company_id, document_id, document_version_id, policy_decision_id, decision, reason, actor_kind, actor_id,
                  approval_stage_id, approval_pool_id, delegated_from_user_id, is_escalated, decided_at, recorded_at)
                  values (%s,%s,%s,%s,%s,%s,'ok',%s,%s,%s,%s,%s,%s,now(),now())""",
               (aid, I["co"], did or D2, vid or V21, pid or PD, decision_, kw.get("actor_kind", "human"), I[actor], I[stage] if stage else None,
                I[pool] if stage else None, kw.get("delegated"), kw.get("escalated", False)))
    return aid


A1 = approve(X0, "uChief", "stStd")
A2 = approve(X0, "uOwner", "stSen")
X("update document set state='approved' where id=%s", (D2,))
check("C08 two stage approvals, one per stage, by two people, satisfy the plan (ADR-0055 rules 8-9)",
      X("select count(distinct actor_id), count(distinct approval_stage_id) from approval where policy_decision_id=%s and decision='approved'", (PD,)).fetchone() == (2, 2))
trial("C09 agents never approve: actor_kind agent is refused (ADR-0017 rule 15)", lambda cx: approve(cx, "uSales", "stStd", actor_kind="agent"), True, "ck_approval_actor_kind")
trial("C10 a person counts once within a decision (ADR-0055 rule 7 condition 6)", lambda cx: approve(cx, "uChief", "stSen"), True, "ux_approval_policy_decision_id_actor_id")
trial("C11 an approval naming another pool than its decision's is refused (composite keys to the decision and the stage)",
      lambda cx: approve(cx, "uSales", "stStd", pool="poolSales"), True, "foreign key")


def stage_outside_plan(cx):
    sid = new()
    cx.execute("insert into approval_stage (id, company_id, approval_pool_id, sequence, code, name, min_rank, required_approvals) values (%s,%s,%s,3,'extra','extra',30,1)",
               (sid, I["co"], I["poolPo"]))
    I["stExtra"] = sid
    approve(cx, "uSales", "stExtra")


trial("C12 a stage of the pool but outside the plan is refused", stage_outside_plan, True, "approval_stage_not_in_plan")
trial("C13 a decision with a plan is not approved without a stage", lambda cx: approve(cx, "uSales", None), True, "approval_stage_not_in_plan")
trial("C14 escalation is not used together with a delegation (ADR-0055 rule 7)", lambda cx: approve(cx, "uSales", "stStd", delegated=I["uAcc"], escalated=True), True, "ck_approval_escalated")
trial("C15 an approval on a version its decision does not bind is refused", lambda cx: approve(cx, "uSales", "stStd", vid=V1, did=D1), True, "fk")
trial("C16 approvals are never updated", lambda cx: cx.execute("update approval set reason='changed' where id=%s", (A1,)), True, "never updated")
trial("C17 a rule allowing an agent without owner and maximum is refused (ADR-0043 rule 3)", lambda cx: cx.execute(
    """insert into policy_rule_version (id, company_id, policy_rule_id, version, effective_from, action, actor_kind, effect, recorded_at)
       values (%s,%s,%s,2,'2026-12-01','post','system','allow',now())""", (new(), I["co"], I["rule"])), True, "ck_policy_rule_version_loosening")
trial("C18a direct_master_data_change needs actor kind human (ADR-0043 rule 12)", lambda cx: cx.execute(
    """insert into policy_rule_version (id, company_id, policy_rule_id, version, effective_from, action, command_type, effect, recorded_at)
       values (%s,%s,%s,2,'2026-12-01','direct_master_data_change','UpdatePartnerBankAccount','deny',now())""", (new(), I["co"], I["rule"])),
      True, "ck_policy_rule_version_direct_change")
trial("C18 direct_master_data_change only denies, for humans (ADR-0043 rule 12)", lambda cx: cx.execute(
    """insert into policy_rule_version (id, company_id, policy_rule_id, version, effective_from, action, command_type, actor_kind, effect, recorded_at)
       values (%s,%s,%s,2,'2026-12-01','direct_master_data_change','UpdatePartnerBankAccount','human','allow',now())""", (new(), I["co"], I["rule"])),
      True, "ck_policy_rule_version_direct_change")
trial("C19 a boolean condition is null or true, never false (ADR-0043 rule 3)", lambda cx: cx.execute(
    """insert into policy_rule_version (id, company_id, policy_rule_id, version, effective_from, action, is_credit_exceeded, effect, approval_procedure_id, recorded_at)
       values (%s,%s,%s,2,'2026-12-01','submit',false,'require_approval',%s,now())""", (new(), I["co"], I["rule"], I["procStd"])), True, "ck_policy_rule_version_credit_exceeded")
trial("C20 a policy rule version changes only is_enabled and its shadow evidence", lambda cx: cx.execute(
    "update policy_rule_version set amount_company_min=0 where id=%s", (I["ruleV"],)), True, "append-only")
writers = sorted(r[0] for r in X("select user_account_id from document_actor(%s) where actor_role='writer'", (D2,)))
submitters = [r[0] for r in X("select user_account_id from document_actor(%s) where actor_role='submitter'", (D2,))]
check("C21 document_actor returns the writer and the submitter (platform review 17)", writers == [I["uAcc"]] and submitters == [I["uAcc"]], (writers, submitters))
trial("C22 auto-post confirmations are unique per decision", lambda cx: [cx.execute(
    "insert into auto_post_confirmation (id, company_id, policy_decision_id, confirmed_by_id, confirmed_at, recorded_at) values (%s,%s,%s,%s,now(),now())",
    (new(), I["co"], PD, I["uOwner"])) for _ in range(2)], True, "uq_auto_post_confirmation_policy_decision_id")

# ======================================================================= D: work items
WI1 = work_item(X0, new(), kind="approval_pending", key=str(D2), owner_kind="approval_stage", owner_role=None, stage=I["stStd"])
check("D01 an approval_pending item owned by its stage (ADR-0055 rule 12)", X("select owner_kind from work_item where id=%s", (WI1,)).fetchone()[0] == "approval_stage")
trial("D02 rule 4: a second open item with the same kind and key is refused", lambda cx: work_item(cx, new(), kind="approval_pending", key=str(D2), owner_kind="approval_stage", owner_role=None, stage=I["stSen"]),
      True, "ux_work_item_open_key")
X("update work_item set state='done', resolution='stage_completed', resolved_at=now() where id=%s", (WI1,))
WI2 = work_item(X0, new(), kind="approval_pending", key=str(D2), owner_kind="approval_stage", owner_role=None, stage=I["stSen"])
check("D03 once resolved, the next stage's item takes the same key", WI2 is not None)
check("D04 owner_role stores the symbolic rule: a template code (platform review 4)", X("select owner_role from work_item where id=%s", (work_item(X0, new(), owner_role="warehouse_keeper"),)).fetchone()[0] == "warehouse_keeper")
trial("D05 owner_role refuses role:<template>, which is the catalog's rule syntax, not the stored value", lambda cx: work_item(cx, new(), owner_role="role:accountant"), True, "ck_work_item_owner_role")
trial("D06 a role owner needs owner_role and nothing else", lambda cx: work_item(cx, new(), owner_kind="role", owner_role=None), True, "ck_work_item_owner")
trial("D07 a claimed item needs its claimer", lambda cx: work_item(cx, new(), state="claimed"), True, "ck_work_item_claim")
trial("D08 an agent claim needs an expiry (ADR-0042 rule 9)", lambda cx: work_item(cx, new(), state="claimed", claimed_by_kind="agent_run", claimed_by_id=new()), True, "ck_work_item_claim")
WI3 = work_item(X0, new(), tainted=True)
trial("D09 taint on an item never drops (ADR-0042 rule 5)", lambda cx: cx.execute("update work_item set is_tainted=false where id=%s", (WI3,)), True, "work item identity")
trial("D10 a resolved item stays resolved", lambda cx: cx.execute("update work_item set state='open', resolved_at=null, resolution=null where id=%s", (WI1,)), True, "work item identity")
NOTE = new()
X("insert into work_item_note (id, company_id, work_item_id, author_kind, author_id, body_text, recorded_at) values (%s,%s,%s,'user',%s,'checked',now())", (NOTE, I["co"], WI2, I["uOwner"]))
trial("D11 notes are append-only (ADR-0042 rule 3)", lambda cx: cx.execute("update work_item_note set body_text='x' where id=%s", (NOTE,)), True, "never updated")

# ======================================================================= E: agent runs, taint on versions, change proposal
WIR = work_item(X0, I["wiRun"], kind="bank_line_unmatched", tainted=True)
run(X0, I["runR1"], tainted_at=NOW - timedelta(minutes=5), wi=WIR)
CP = doc(X0, new(), "change_proposal")
trial("E01 INV-88: a version written by a tainted run must be tainted",
      lambda cx: version(cx, CP, 1, {"items": [1]}, actor_kind="agent", actor=new(), run=I["runR1"], tainted=False), True, "tainted run must be tainted")
CPV1 = version(X0, CP, 1, {"items": [{"command_type": "CreateBankMatchingRule"}]}, actor_kind="agent", actor=new(), run=I["runR1"], tainted=True)
trial("E02 INV-88 / EC-57: a person's edit of a tainted version stays tainted", lambda cx: version(cx, CP, 2, {"items": [2]}, actor="uChief"), True, "effectively tainted")
X("insert into taint_clearance (id, company_id, document_version_id, cleared_by_user_id, reason, cleared_at, recorded_at) values (%s,%s,%s,%s,'checked the token',%s,now())",
  (new(), I["co"], CPV1, I["uOther"], NOW + timedelta(minutes=1)))
CPV2 = version(X0, CP, 2, {"items": [{"command_type": "CreateBankMatchingRule", "payload": {"token": "ACME"}}]}, actor="uChief", at=NOW + timedelta(minutes=2))
X("update document set version=2 where id=%s", (CP,))
check("E03 after a clearance (ADR-0029 rule 8) the next version may be untainted", X("select is_tainted from document_version where id=%s", (CPV2,)).fetchone()[0] is False)
trial("E04 a version cleared later than it was used does not count", lambda cx: version(cx, doc(cx, new(), "change_proposal"), 1, {}, actor_kind="agent", actor=new(),
      run=I["runR1"], tainted=False, at=NOW - timedelta(minutes=10)), False)
trial("E05 a clearance is immutable and one per version", lambda cx: cx.execute(
    "insert into taint_clearance (id, company_id, document_version_id, cleared_by_user_id, reason, cleared_at, recorded_at) values (%s,%s,%s,%s,'again',now(),now())",
    (new(), I["co"], CPV1, I["uOwner"])), True, "uq_taint_clearance_document_version_id")
X("""insert into change_proposal (id, company_id, plan, plan_hash, evidence, reason, document_date, recorded_at) values (%s,%s,'{}',%s,'[]','rule from repeated payer',%s,now())""",
  (CP, I["co"], "d" * 64, TODAY))
for i_ in range(2):
    X("""insert into change_proposal_item (id, company_id, change_proposal_id, item_index, command_type, schema_version, payload, target_table, field_changes, recorded_at)
         values (%s,%s,%s,%s,'CreateBankMatchingRule',1,'{}','bank_matching_rule','[]',now())""", (new(), I["co"], CP, i_))
trial("E06 a change proposal item names a PascalCase command", lambda cx: cx.execute(
    """insert into change_proposal_item (id, company_id, change_proposal_id, item_index, command_type, schema_version, payload, target_table, field_changes, recorded_at)
       values (%s,%s,%s,5,'create_rule',1,'{}','x','[]',now())""", (new(), I["co"], CP)), True, "ck_change_proposal_item_command_type")
trial("E07 an expected version needs a target", lambda cx: cx.execute(
    """insert into change_proposal_item (id, company_id, change_proposal_id, item_index, command_type, schema_version, payload, target_table, expected_version, field_changes, recorded_at)
       values (%s,%s,%s,6,'UpdatePartner',1,'{}','partner',%s,'[]',now())""", (new(), I["co"], CP, "e" * 64)), True, "ck_change_proposal_item_target")
PDC = decision(X0, CP, CPV2, rank=10, proc="procStd", pool="poolGen", plan=[{"id": str(I["stGen"]), "sequence": 1, "code": "standard", "min_rank": 10, "k": 1}], actor="uChief")
approve(X0, "uOwner", "stGen", pool="poolGen", pid=PDC, vid=CPV2, did=CP)
X("update document set state='approved' where id=%s", (CP,))
AR = {}


def audit(cx, command="CreateBankMatchingRule", effect="master_data_change", draft_only=False, run_=None, aid=None, company="co", **kw):
    aid = aid or new()
    cx.execute("""insert into audit_record (id, company_id, business_date, command_type, schema_version, effect_class, is_human_only, is_proposal_bound,
                  is_draft_only, is_internal_only, actor_kind, actor_id, on_behalf_of_id, agent_run_id, reason, idempotency_key, causation_chain_id, causation_depth, recorded_at)
                  values (%s,%s,%s,%s,1,%s,false,true,%s,false,%s,%s,%s,%s,%s,%s,%s,0,now())""",
               (aid, I[company] if company else None, TODAY, command, effect, draft_only, kw.get("actor_kind", "system"), kw.get("actor", new()), I["uOwner"], run_,
                kw.get("reason"), kw.get("key"), new()))
    return aid


EX = new()
X("insert into change_proposal_execution (id, company_id, change_proposal_id, document_version_id, executed_at, recorded_at) values (%s,%s,%s,%s,now(),now())", (EX, I["co"], CP, CPV2))
for i_ in range(2):
    AR[i_] = audit(X0, key=f"change_proposal_executor:{EX}:1")
    X("insert into change_proposal_execution_item (company_id, change_proposal_execution_id, item_index, audit_record_id, recorded_at) values (%s,%s,%s,%s,now())", (I["co"], EX, i_, AR[i_]))
X("update document set state='closed' where id=%s", (CP,))
check("E08 the executed proposal has one execution with the audit row of each item, and is closed (ADR-0029 rule 3)",
      X("select count(*) from change_proposal_execution_item where change_proposal_execution_id=%s", (EX,)).fetchone()[0] == 2
      and X("select state from document where id=%s", (CP,)).fetchone()[0] == "closed")
trial("E09 a proposal is executed once", lambda cx: cx.execute(
    "insert into change_proposal_execution (id, company_id, change_proposal_id, document_version_id, executed_at, recorded_at) values (%s,%s,%s,%s,now(),now())",
    (new(), I["co"], CP, CPV2)), True, "uq_change_proposal_execution_change_proposal_id")
def execution_other_version(cx):
    cp2 = doc(cx, new(), "change_proposal")
    cx.execute("insert into change_proposal (id, company_id, plan, plan_hash, reason, document_date, recorded_at) values (%s,%s,'{}',%s,'r',%s,now())", (cp2, I["co"], "d" * 64, TODAY))
    cx.execute("insert into change_proposal_execution (id, company_id, change_proposal_id, document_version_id, executed_at, recorded_at) values (%s,%s,%s,%s,now(),now())",
               (new(), I["co"], cp2, V21))


trial("E10 an execution names a version of its own proposal", execution_other_version, True, "fk")
trial("E11 the items of a closed proposal are frozen (ADR-0009 rule 14)", lambda cx: cx.execute("delete from change_proposal_item where change_proposal_id=%s", (CP,)), True, "immutable")
trial("E12 executions are immutable", lambda cx: cx.execute("update change_proposal_execution set executed_at=now() where id=%s", (EX,)), True, "never updated")

# ======================================================================= F: agent run, steps and budgets
R2 = run(X0, I["runR2"], wi=WIR, tainted_at=NOW)
REQ = new()
X("""insert into agent_run_step (id, company_id, agent_run_id, ordinal, step_code, kind, seat, provider, model, template_code, template_version, request_hash,
     reserved_amount, request_body, recorded_at) values (%s,%s,%s,1,'bank_matching.read_description','llm_request','classification','anthropic','m','read_description','1.0.0',%s,0.02,'{"messages": [{"role": "user", "content": "Sample text"}]}',now())""",
  (REQ, I["co"], R2, "f" * 64))
X("""insert into agent_run_step (id, company_id, agent_run_id, ordinal, step_code, kind, request_step_id, seat, provider, model, response_body, cost_amount, recorded_at)
     values (%s,%s,%s,2,'bank_matching.read_description','llm_response',%s,'classification','anthropic','m','{}',0.01,now())""", (new(), I["co"], R2, REQ))
TREQ = new()
X("""insert into agent_run_step (id, company_id, agent_run_id, ordinal, step_code, kind, tool_name, schema_version, mode, recorded_at)
     values (%s,%s,%s,3,'bank_matching.suggest','tool_request','RecordBankLineSuggestion',1,'execute',now())""", (TREQ, I["co"], R2))
X("""insert into agent_run_step (id, company_id, agent_run_id, ordinal, step_code, kind, request_step_id, tool_name, schema_version, mode, recorded_at)
     values (%s,%s,%s,4,'bank_matching.suggest','tool_result',%s,'RecordBankLineSuggestion',1,'execute',now())""", (new(), I["co"], R2, TREQ))
X("update agent_run set state='completed', outcome='drafted', ended_at=now(), llm_call_count=1, tool_call_count=1, cost_amount=0.01 where id=%s", (R2,))
check("F01 a completed run with four steps (ADR-0050 rules 17-19)", X("select count(*) from agent_run_step where agent_run_id=%s", (R2,)).fetchone()[0] == 4
      and X("select state, outcome from agent_run where id=%s", (R2,)).fetchone() == ("completed", "drafted"))
trial("F02 a response row needs its request row", lambda cx: cx.execute(
    """insert into agent_run_step (id, company_id, agent_run_id, ordinal, step_code, kind, seat, provider, model, recorded_at)
       values (%s,%s,%s,5,'x','llm_response','s','anthropic','m',now())""", (new(), I["co"], R2)), True, "ck_agent_run_step_pairing")
trial("F03 a request body only on a request row", lambda cx: cx.execute(
    """insert into agent_run_step (id, company_id, agent_run_id, ordinal, step_code, kind, request_step_id, tool_name, request_body, recorded_at)
       values (%s,%s,%s,5,'x','tool_result',%s,'T','{}',now())""", (new(), I["co"], R2, TREQ)), True, "ck_agent_run_step_bodies")
trial("F04 steps are append-only; erasure may blank bodies", lambda cx: cx.execute("update agent_run_step set step_code='y' where id=%s", (REQ,)), True, "append-only")
trial("F05 ... with a valid erasure marker (an erasure command's idempotency record of this transaction) the bodies are blanked", lambda cx: (
    erasure_marker(cx.execute, company_id=I["co"]),
    cx.execute("update agent_run_step set request_body=null, erased_at=now() where id=%s", (REQ,))), False)
trial("F06 rule 17: a completed run cannot carry a stop outcome", lambda cx: run(cx, new(), state="completed", outcome="budget_exceeded", wi=WIR), True, "ck_agent_run_outcome")
trial("F07 the third denial stops a run; a fourth is never counted", lambda cx: run(cx, new(), wi=WIR, denials=4), True, "ck_agent_run_denial_count")
trial("F08 rule 23: calls above the start snapshot are refused", lambda cx: run(cx, new(), wi=WIR, calls=5), True, "ck_agent_run_within_budget")
trial("F09 rule 23: cost plus reservation above max_cost is refused", lambda cx: run(cx, new(), wi=WIR, cost=0.40, reserved=0.20), True, "ck_agent_run_within_budget")
trial("F10 INV-212: an ended run holds no reservation", lambda cx: run(cx, new(), wi=WIR, state="stopped", outcome="crashed", reserved=0.01), True, "ck_agent_run_reservation_settled")
trial("F11 tainted_at is never cleared (ADR-0050 rule 25)", lambda cx: cx.execute("update agent_run set tainted_at=null, taint_source_kind=null where id=%s", (R2,)), True, "append-only")
trial("F12 ... and set once from null", lambda cx: cx.execute("update agent_run set tainted_at=now(), taint_source_kind='untrusted_field' where id=%s", (I["runR1"],)), True, "append-only")
trial("F13 a live run needs a work item (ADR-0042 rule 11)", lambda cx: run(cx, new(), wi=None), True, "ck_agent_run_work_item")
# ADR-0078 rule 7: two budget tiers. The company row holds the daily cap; the per-type row counts usage with the company cap
# as its limit and no run limit, so it never binds before the company row (S2: F14 used to test a per-type limit of its own).
BU, BUT = new(), new()
X("insert into agent_budget_usage (id, scope_kind, company_id, business_date, limit_amount, recorded_at) values (%s,'company',%s,%s,5,now())",
  (BU, I["co"], TODAY))
X("insert into agent_budget_usage (id, scope_kind, company_id, agent_type_code, business_date, limit_amount, recorded_at) values (%s,'company_agent_type',%s,'bank_matching',%s,5,now())",
  (BUT, I["co"], TODAY))
trial("F14 a reservation within the company's daily cap passes on the company row and the per-type row, whose limit is the company cap (ADR-0078 rule 7)",
      lambda cx: cx.execute("update agent_budget_usage set reserved_amount = reserved_amount + 4 where id in (%s, %s)", (BU, BUT)), False)
trial("F15 a reservation that would pass the company's daily cap reserves nothing (rule 23 guard)", lambda cx: cx.execute(
    "update agent_budget_usage set reserved_amount = reserved_amount + 6 where id=%s", (BU,)), True, "ck_agent_budget_usage_guard")
trial("F16 one usage row per scope and date, an installation row without company", lambda cx: [cx.execute(
    "insert into agent_budget_usage (id, scope_kind, business_date, limit_amount, recorded_at) values (%s,'installation',%s,200,now())", (new(), TODAY)) for _ in range(2)],
      True, "uq_agent_budget_usage_key")
trial("F17 an assisted setting needs its promoted version (rule 14)", lambda cx: cx.execute(
    "update agent_type_setting set mode='assisted' where company_id=%s", (I["co"],)), True, "ck_agent_type_setting_promoted")
trial("F18 agent type versions are immutable", lambda cx: cx.execute("update agent_type_version set declaration='{}'"), True, "never updated")

# ======================================================================= G: money accounts, statement, proposal, match at Post
MA = new()
X("""insert into money_account (id, company_id, code, name, kind, currency, account_id, bank_name, bank_account_number, recorded_at)
     values (%s,%s,'BANK1','Bank (sample)','bank','VND',%s,'Bank (sample)','123456',now())""", (MA, I["co"], I["acBank"]))
MAC = new()
X("insert into money_account (id, company_id, code, name, kind, currency, account_id, recorded_at) values (%s,%s,'CASH1','Cash','cash','VND',%s,now())", (MAC, I["co"], I["acCash"]))
MA2 = new()
X("""insert into money_account (id, company_id, code, name, kind, currency, account_id, bank_name, bank_account_number, recorded_at)
     values (%s,%s,'BANK2','Bank 2 (sample)','bank','VND',%s,'Bank (sample)','654321',now())""", (MA2, I["co"], I["acBank2"]))
trial("G01 a cash account carries no bank fields (rule 2)", lambda cx: cx.execute(
    "insert into money_account (id, company_id, code, name, kind, currency, account_id, bank_name, recorded_at) values (%s,%s,'C2','C','cash','VND',%s,'B',now())",
    (new(), I["co"], I["acRev"])), True, "ck_money_account_bank")
trial("G02 one operational account serves one money account", lambda cx: cx.execute(
    "insert into money_account (id, company_id, code, name, kind, currency, account_id, recorded_at) values (%s,%s,'C3','C','cash','VND',%s,now())",
    (new(), I["co"], I["acCash"])), True, "uq_money_account_account_id")
ATT = new()
X("insert into attachment (id, company_id, sha256, media_type, byte_count, storage_key, data_label, source_kind, state, recorded_at) values (%s,%s,%s,'text/csv',100,'k','personal','upload','clean',now())",
  (ATT, I["co"], "1" * 64))
ST = new()
L1, L2 = new(), new()


def statement(cx, sid, closing, lines, number="S-1"):
    cx.execute("""insert into bank_statement (id, company_id, money_account_id, statement_number, period_start_date, period_end_date, transaction_opening_balance,
                  transaction_closing_balance, source_attachment_id, reader_code, imported_by_user_id, recorded_at)
                  values (%s,%s,%s,%s,'2026-11-01','2026-11-15',1000000,%s,%s,'generic_csv',%s,now())""", (sid, I["co"], MA, number, closing, ATT, I["uChief"]))
    for n, (lid, amount, ref) in enumerate(lines, 1):
        cx.execute("""insert into bank_statement_line (id, company_id, bank_statement_id, money_account_id, line_number, booking_date, value_date, transaction_amount,
                      bank_reference, description, recorded_at) values (%s,%s,%s,%s,%s,'2026-11-14','2026-11-14',%s,%s,'PAY INV-2026-0042 (sample)',now())""",
                   (lid, I["co"], sid, MA, n, amount, ref))


with conn() as cx:
    statement(cx, ST, 1000000 + 5500000 - 2200000, [(L1, 5500000, "FT001"), (L2, -2200000, "FT002")])
check("G03 a balanced statement with two lines commits (ADR-0048 rule 8)", X("select count(*) from bank_statement_line where bank_statement_id=%s", (ST,)).fetchone()[0] == 2)
trial("G04 an unbalanced statement is refused at commit (bank_statement_unbalanced)", lambda cx: statement(cx, new(), 999, [(new(), 5, "FT009")], number="S-2"), True, "bank_statement_unbalanced")
trial("G05 ADR-0030 rule 10: a second line with the same account, reference, value date and amount is refused", lambda cx: statement(
    cx, new(), 1000000 + 5500000, [(new(), 5500000, "FT001")], number="S-3"), True, "ux_bank_statement_line_natural_key")
trial("G06 ... without a reference no key applies; both lines are kept", lambda cx: statement(cx, new(), 1000000 + 10, [(new(), 5, None), (new(), 5, None)], number="S-4"), False)


def payment(cx, pid, ma=MA):
    doc(cx, pid, "bank_payment", partner=I["p1"])
    cx.execute("""insert into payment (id, company_id, document_type, money_account_id, transaction_currency, document_date, posting_date, value_date, partner_id,
                  partner_bank_account_id, bank_statement_line_id, recorded_at) values (%s,%s,'bank_payment',%s,'VND',%s,%s,%s,%s,%s,%s,now())""",
               (pid, I["co"], ma, TODAY, TODAY, TODAY, I["p1"], I["pba"], L2))
    cx.execute("""insert into payment_line (id, company_id, payment_id, line_number, line_kind, transaction_amount, evidence_method, recorded_at)
                  values (%s,%s,%s,1,'advance',2200000,'bank_transfer',now())""", (new(), I["co"], pid))
    return pid


PY = payment(X0, new())
trial("G07 a bank payment on a cash account is refused (money_account_kind_mismatch, held by the key)", lambda cx: (
    doc(cx, (d := new()), "bank_payment"), cx.execute(
        "insert into payment (id, company_id, document_type, money_account_id, transaction_currency, document_date, posting_date, value_date, recorded_at) values (%s,%s,'bank_payment',%s,'VND',%s,%s,%s,now())",
        (d, I["co"], MAC, TODAY, TODAY, TODAY))), True, "foreign key")
trial("G08 a payment header's type must be its document's", lambda cx: (
    doc(cx, (d := new()), "cash_receipt"), cx.execute(
        "insert into payment (id, company_id, document_type, money_account_id, transaction_currency, document_date, posting_date, value_date, recorded_at) values (%s,%s,'bank_receipt',%s,'VND',%s,%s,%s,now())",
        (d, I["co"], MA, TODAY, TODAY, TODAY))), True, "fk")
trial("G09 a settle line needs its open item, and evidence on settling lines (rule 3)", lambda cx: cx.execute(
    "insert into payment_line (id, company_id, payment_id, line_number, line_kind, transaction_amount, evidence_method, recorded_at) values (%s,%s,%s,2,'settle',1,'bank_transfer',now())",
    (new(), I["co"], PY)), True, "ck_payment_line_kind_columns")
trial("G10 third party only on a settle line with method third_party", lambda cx: cx.execute(
    "insert into payment_line (id, company_id, payment_id, line_number, line_kind, transaction_amount, evidence_method, is_paid_by_third_party, recorded_at) values (%s,%s,%s,2,'advance',1,'bank_transfer',true,now())",
    (new(), I["co"], PY)), True, "ck_payment_line_evidence")
trial("G11 the beneficiary account must belong to the payment's partner", lambda cx: (
    cx.execute("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,'P9','Other','organization','VN')", (pz := new(), I["co"])),
    cx.execute("update payment set partner_id=%s where id=%s", (pz, PY))), True, "fk_payment_partner_bank_account_id")
trial("G12a a line in state proposed names its proposed document (ADR-0048 rule 8 note; simulation review)", lambda cx: cx.execute(
    "update bank_statement_line set match_state='proposed' where id=%s", (L2,)), True, "ck_bank_statement_line_proposed")
X("update bank_statement_line set match_state='proposed', proposed_document_id=%s, proposal_score=90, match_basis='account_amount' where id=%s", (PY, L2))
check("G12 the cascade's proposal is recorded on the line, in state proposed, while the payment is a draft (flows review A9; ADR-0048 rule 9 note F1)",
      X("select match_state, proposal_score, match_basis from bank_statement_line where id=%s", (L2,)).fetchone() == ("proposed", 90, "account_amount"))
trial("G13 an LLM suggestion never carries a score (rule 9)", lambda cx: cx.execute(
    "update bank_statement_line set proposed_document_id=%s, proposal_score=50, match_basis='llm_suggestion' where id=%s", (PY, L1)), True, "ck_bank_statement_line_proposal")
trial("G13b ... it is a proposal without a score", lambda cx: cx.execute(
    "update bank_statement_line set proposed_document_id=%s, match_basis='llm_suggestion' where id=%s", (PY, L1)), False)
trial("G14 INV-95: a line is not matched to a draft", lambda cx: cx.execute(
    "update bank_statement_line set match_state='matched', matched_document_id=%s where id=%s", (PY, L2)), True, "bank_statement_line_not_posted")


def other_account_posted(cx):
    pid = payment(cx, new(), ma=MA2)
    cx.execute("update document set state='posted', number='BP/2026/000009', posted_at=now() where id=%s", (pid,))
    cx.execute("update bank_statement_line set match_state='matched', matched_document_id=%s where id=%s", (pid, L2))


trial("G14b INV-95: nor to a posted payment of another money account", other_account_posted, True, "another money account")
trial("G15 the statement text is append-only (untrusted, never edited)", lambda cx: cx.execute("update bank_statement_line set description='edited' where id=%s", (L2,)), True, "append-only")
X("update document set state='posted', number='BP/2026/000001', posted_at=now() where id=%s", (PY,))
X("update bank_statement_line set match_state='matched', matched_document_id=%s where id=%s", (PY, L2))
check("G16 after Post the line is matched to the payment; the proposal stays as its trace",
      X("select match_state, proposed_document_id = matched_document_id from bank_statement_line where id=%s", (L2,)).fetchone() == ("matched", True))
trial("G17 a posted payment's lines are frozen", lambda cx: cx.execute("update payment_line set description='x' where payment_id=%s", (PY,)), True, "immutable")
trial("G18 a suggestion records its run and purpose together (ADR-0051 rule 17)", lambda cx: cx.execute(
    "update bank_statement_line set suggested_reference_tokens='{INV-2026-0042}', suggested_purpose='invoice_payment' where id=%s", (L1,)), True, "ck_bank_statement_line_suggestion")
trial("G19 ... and with the run it is accepted", lambda cx: cx.execute(
    "update bank_statement_line set suggested_reference_tokens='{INV-2026-0042}', suggested_purpose='invoice_payment', suggestion_agent_run_id=%s where id=%s", (R2, L1)), False)

# ======================================================================= H: outbox, audit, denials, attachments
X("insert into event_consumer (consumer, kind, queue, is_paused, recorded_at) values ('cash_bank_matching','transactional','events',false,now()) on conflict do nothing")
EV = new()
X("""insert into outbox_event (id, company_id, event_type, schema_version, subject_table, subject_id, subject_sequence, payload, actor_kind, actor_id,
     business_date, command_type, causation_chain_id, causation_depth, recorded_at) values (%s,%s,'BankStatementImported',1,'bank_statement',%s,1,'{}','human',%s,%s,'ImportBankStatement',%s,0,now())""",
  (EV, I["co"], ST, I["uChief"], TODAY, new()))
X("insert into event_subject values (uuidv7(), 'bank_statement',%s,1,now())", (ST,))
X("""insert into event_delivery (id, consumer, event_id, subject_table, subject_id, subject_sequence, company_id, next_attempt_at, recorded_at)
     values (%s,'cash_bank_matching',%s,'bank_statement',%s,1,%s,now(),now())""", (new(), EV, ST, I["co"]))
check("H01 an event and its delivery are written (ADR-0013 rules 2, 6)", X("select count(*) from event_delivery where event_id=%s", (EV,)).fetchone()[0] == 1)
trial("H01a events are never updated (ADR-0013 rule 2; S2 schema review N6)", lambda cx: cx.execute("update outbox_event set payload='{\"x\": 1}' where id=%s", (EV,)), True, "never updated")
trial("H01b ... nor deleted row by row: retention drops whole partitions (ADR-0013 rule 15)", lambda cx: cx.execute("delete from outbox_event where id=%s", (EV,)), True, "never updated")
trial("H02 one delivery per consumer and event", lambda cx: cx.execute(
    "insert into event_delivery (id, consumer, event_id, subject_table, subject_id, subject_sequence, company_id, next_attempt_at, recorded_at) values (%s,'cash_bank_matching',%s,'bank_statement',%s,1,%s,now(),now())",
    (new(), EV, ST, I["co"])), True, "uq_event_delivery_consumer_event_id")
trial("H03 a running delivery has its lease", lambda cx: cx.execute(
    "insert into event_delivery (id, consumer, event_id, subject_table, subject_id, subject_sequence, state, next_attempt_at, recorded_at) values (%s,'cash_bank_matching',%s,'x',%s,1,'running',now(),now())",
    (new(), EV, new())), True, "ck_event_delivery_running")
trial("H04 a consumer name is snake_case of at most 48 characters", lambda cx: cx.execute(
    "insert into event_consumer (consumer, kind, queue, recorded_at) values (%s,'transactional','events',now())", ("c" * 49,)), True, "ck_event_consumer_consumer")
AUD = audit(X0, command="ApproveChangeProposal", effect="other", reason="looks right", actor_kind="human", actor=I["uOwner"])
trial("H05 audit records are append-only (ADR-0038 rule 4)", lambda cx: cx.execute("update audit_record set reason='x' where id=%s", (AUD,)), True, "append-only")
trial("H06 ... except that erasure masks reason under a valid erasure marker", lambda cx: (
    erasure_marker(cx.execute, company_id=I["co"]),
    cx.execute("update audit_record set reason='', erased_at=now() where id=%s", (AUD,))), False)   # an erasure result of ADR-0079 rule 6 (R2-N3)
trial("H07 ... and erasure changes nothing else", lambda cx: (
    erasure_marker(cx.execute, company_id=I["co"]),
    cx.execute("update audit_record set command_type='X' where id=%s", (AUD,))), True, "append-only")
trial("H08 a draft-only command is never of a posting effect class (ADR-0050 rule 26)", lambda cx: audit(cx, effect="posting", draft_only=True), True, "ck_audit_record_draft_only")
check("H09 audit records with installation scope have no company and live in the default partition",
      X("select tableoid::regclass::text from audit_record where id=%s", (audit(X0, company=None, effect="other"),)).fetchone()[0] == "audit_record_default")
WIN = datetime(2026, 11, 15, 9, 10, tzinfo=timezone.utc)


def denial(cx, run_=None, window=WIN, code="tainted_run_not_allowed"):
    cx.execute("""insert into audit_denial (id, company_id, command_type, mode, actor_kind, actor_id, agent_run_id, error_code, window_start, first_at, last_at, recorded_at)
                  values (%s,%s,'PostBankPayment','execute','agent',%s,%s,%s,%s,now(),now(),now())
                  on conflict (company_id, actor_kind, actor_id, agent_run_id, command_type, error_code, subject_table, subject_id, window_start)
                  do update set denial_count = audit_denial.denial_count + 1, last_at = excluded.last_at""",
               (new(), I["co"], I["runR2"], run_, code, window))


denial(X0, I["runR2"]); denial(X0, I["runR2"])
check("H10 denials coalesce per actor, run, type, code, subject and window (ADR-0038 rule 5)",
      X("select denial_count from audit_denial where agent_run_id=%s", (I["runR2"],)).fetchone()[0] == 2)
trial("H11 a denial count never goes down", lambda cx: cx.execute("update audit_denial set denial_count=1 where agent_run_id=%s", (I["runR2"],)), True, "only count up")
trial("H12 windows are 10 minutes", lambda cx: denial(cx, window=WIN + timedelta(minutes=3)), True, "ck_audit_denial_window")
trial("H13 the denial codes are the enumerated list (platform review 15)", lambda cx: denial(cx, code="not_found"), True, "ck_audit_denial_error_code")
trial("H14 a second attachment row for the same bytes in one company is refused (ADR-0027 rule 2)", lambda cx: cx.execute(
    "insert into attachment (id, company_id, sha256, media_type, byte_count, storage_key, data_label, source_kind, state, recorded_at) values (%s,%s,%s,'text/csv',1,'k2','internal','upload','pending_scan',now())",
    (new(), I["co"], "1" * 64)), True, "uq_attachment_company_id_sha256")
trial("H15 a generated file is clean and names its kind and audience (ADR-0049 rule 28)", lambda cx: cx.execute(
    "insert into attachment (id, company_id, sha256, media_type, byte_count, storage_key, data_label, source_kind, state, generated_kind, generated_audience, recorded_at) values (%s,%s,%s,'application/pdf',1,'k3','internal','generated','pending_scan','print','external',now())",
    (new(), I["co"], "2" * 64)), True, "ck_attachment_generated")
trial("H16 an attachment keeps the stricter label and never loses accounting evidence", lambda cx: (
    cx.execute("update attachment set is_accounting_evidence=true where id=%s", (ATT,)),
    cx.execute("update attachment set data_label='internal' where id=%s", (ATT,))), True, "attachment change not allowed")

# ======================================================================= J: taxes and the journal
INV = doc(X0, new(), "purchase_invoice", partner=I["p1"])
X("""insert into document_line_tax (id, company_id, document_id, line_number, tax_code_id, rate_percent, base_transaction_amount, tax_transaction_amount,
     computed_tax_transaction_amount, input_use, recorded_at) values (%s,%s,%s,1,%s,10,2000000,200000,200000,'taxable',now())""", (new(), I["co"], INV, I["tc"]))
trial("J01 one tax row per line and code (ADR-0041 rule 6)", lambda cx: cx.execute(
    """insert into document_line_tax (id, company_id, document_id, line_number, tax_code_id, base_transaction_amount, tax_transaction_amount, computed_tax_transaction_amount, recorded_at)
       values (%s,%s,%s,1,%s,1,1,1,now())""", (new(), I["co"], INV, I["tc"])), True, "document_line_tax_document_id_line_number_tax_code_id_key")
trial("J01b a purchase line's input_use is taxable, non_taxable or shared (ADR-0041 rule 6)", lambda cx: cx.execute(
    """insert into document_line_tax (id, company_id, document_id, line_number, tax_code_id, base_transaction_amount, tax_transaction_amount, computed_tax_transaction_amount, input_use, recorded_at)
       values (%s,%s,%s,2,%s,1,1,1,'private',now())""", (new(), I["co"], INV, I["tc"])), True, "ck_document_line_tax_input_use")
X("update document set state='posted', number='PI/1', posted_at=now() where id=%s", (INV,))
JE = new()
with conn() as cx:
    cx.execute("insert into journal_entry (id, company_id, document_id, posting_date, document_date, posting_period_id, fiscal_year_id, line_count) values (%s,%s,%s,%s,%s,%s,%s,2)",
               (JE, I["co"], INV, TODAY, TODAY, I["per"], I["fy"]))
    for n, side, amt, acc in ((1, "debit", 200000, "acRev"), (2, "credit", -200000, "acBank2")):
        cx.execute("""insert into journal_line (id, journal_entry_id, company_id, line_number, posting_period_id, posting_date, fiscal_year_id, account_id, system_account_id,
                      side, transaction_currency, transaction_amount, company_currency, company_amount, tax_code_id) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'VND',%s,'VND',%s,%s)""",
                   (new(), JE, I["co"], n, I["per"], TODAY, I["fy"], I[acc], I["sa"], side, amt, amt, I["tc"] if n == 1 else None))
TL = new()
X("""insert into tax_line (id, company_id, document_id, line_number, journal_entry_id, tax_code_id, direction, input_use, rate_percent, transaction_currency,
     base_transaction_amount, tax_transaction_amount, base_company_amount, tax_company_amount, tax_date, declaration_date, initial_deductibility, recorded_at)
     values (%s,%s,%s,1,%s,%s,'purchase','taxable',10,'VND',2000000,200000,2000000,200000,%s,%s,'conditional',now())""", (TL, I["co"], INV, JE, I["tc"], TODAY, TODAY))
check("J02 posting copies the frozen document taxes into the tax subledger beside a balanced journal entry (ADR-0041 rules 11-12)",
      X("select count(*) from tax_line where document_id=%s", (INV,)).fetchone()[0] == 1)
trial("J03 a posted document's tax rows are frozen", lambda cx: cx.execute("update document_line_tax set tax_transaction_amount=0 where document_id=%s", (INV,)), True, "immutable")
trial("J04 tax lines are immutable (ADR-0041 rule 11)", lambda cx: cx.execute("update tax_line set tax_company_amount=0 where id=%s", (TL,)), True, "never updated")
trial("J05 a sale row has no deductibility", lambda cx: cx.execute(
    """insert into tax_line (id, company_id, document_id, line_number, journal_entry_id, tax_code_id, direction, transaction_currency, base_transaction_amount,
       tax_transaction_amount, base_company_amount, tax_company_amount, tax_date, declaration_date, initial_deductibility, recorded_at)
       values (%s,%s,%s,2,%s,%s,'sale','VND',1,1,1,1,%s,%s,'deductible',now())""", (new(), I["co"], INV, JE, I["tc"], TODAY, TODAY)), True, "ck_tax_line_purchase")
trial("J06 condition_failed carries its reason (ADR-0053 rule 3)", lambda cx: cx.execute(
    """insert into tax_line_adjustment (id, company_id, adjusts_tax_line_id, kind, deductible_delta_transaction_amount, deductible_delta_company_amount, declaration_date, recorded_at)
       values (%s,%s,%s,'condition_failed',-200000,-200000,%s,now())""", (new(), I["co"], TL, TODAY)), True, "ck_tax_line_adjustment_reason")

# ======================================================================= K: posting intents and period unlock requests
SI = doc(X0, new(), "sales_invoice", partner=I["p1"])
SIV = version(X0, SI, 1, {"lines": [{"line_number": 1}]})
X("update document set state='issuing' where id=%s", (SI,))
PI = new()


def intent(cx, iid, state="pending"):
    cx.execute("""insert into posting_intent (id, company_id, document_id, document_version_id, state, posting_date, plan, plan_hash, rates, is_e_invoice_required,
                  issued_at, ended_at, recorded_at) values (%s,%s,%s,%s,%s,%s,'{}',%s,'{}',true,now(),%s,now())""",
               (iid, I["co"], SI, SIV, state, TODAY, "9" * 64, None if state == "pending" else NOW))


intent(X0, PI)
trial("K01 one pending intent per document (ADR-0028 rule 7)", lambda cx: intent(cx, new()), True, "ux_posting_intent_pending")
trial("K02 the frozen plan never changes", lambda cx: cx.execute("update posting_intent set plan_hash=%s where id=%s", ("8" * 64, PI)), True, "frozen")
X("update posting_intent set state='reopened', ended_at=now() where id=%s", (PI,))
trial("K03 an ended intent never changes again", lambda cx: cx.execute("update posting_intent set state='posted' where id=%s", (PI,)), True, "frozen")
trial("K04 after a rejection, a new Issue writes a new intent", lambda cx: intent(cx, new()), False)
trial("K05 a document in issuing freezes its tax rows (ADR-0028 rule 6)", lambda cx: cx.execute(
    """insert into document_line_tax (id, company_id, document_id, line_number, tax_code_id, base_transaction_amount, tax_transaction_amount, computed_tax_transaction_amount, recorded_at)
       values (%s,%s,%s,1,%s,1,1,1,now())""", (new(), I["co"], SI, I["tc"])), True, "immutable")
trial("K06 a period unlock request names an area of the period (ADR-0043 rule 16)", lambda cx: (
    doc(cx, (d := new()), "period_unlock_request"),
    cx.execute("insert into period_unlock_request (id, company_id, posting_period_id, area, reason, recorded_at) values (%s,%s,%s,'tax','late invoice',now())", (d, I["co"], I["per"]))),
      True, "ck_period_unlock_request_area")
# Period lock (ADR-0012 rule 7; ADR-0043 rule 16; S2 adversarial review N5): a locked period leaves locked only to soft_locked,
# with an approved period_unlock_request of the period and area, never for the migration period; a locked area is never deleted.
PER10, FYM, PERM = new(), new(), new()
ins_posting_period(X, PER10, I["co"], I["fy"], 10, "2026-10-01", "2026-10-31")
for area in ("general", "inventory"):
    ins_area_state(X, I["co"], PER10, area, "locked")
ins_fiscal_year(X, FYM, I["co"], "M2025", "2025-12-31", "2025-12-31", is_migration=True)
ins_posting_period(X, PERM, I["co"], FYM, 1, "2025-12-31", "2025-12-31")
ins_area_state(X, I["co"], PERM, "general", "locked")


def unlock_request(cx, period, area, state):
    d = doc(cx, new(), "period_unlock_request")
    cx.execute("insert into period_unlock_request (id, company_id, posting_period_id, area, reason, recorded_at) values (%s,%s,%s,%s,'late invoice',now())",
               (d, I["co"], period, area))
    if state != "draft":
        cx.execute("update document set state = %s where id = %s", (state, d))


def set_state(cx, period, area, state):
    cx.execute("update posting_period_area_state set state = %s where posting_period_id = %s and area = %s", (state, period, area))


trial("K07 N5: a locked period is not reopened by a plain UPDATE of its state to open", lambda cx: set_state(cx, PER10, "general", "open"), True,
      "goes back only to soft_locked")
trial("K08 N5: locked to soft_locked without an approved period_unlock_request is refused", lambda cx: set_state(cx, PER10, "general", "soft_locked"), True,
      "needs an approved period_unlock_request")
trial("K09 N5: ... a draft request does not count", lambda cx: (unlock_request(cx, PER10, "general", "draft"), set_state(cx, PER10, "general", "soft_locked")), True,
      "needs an approved period_unlock_request")
trial("K10 N5: ... nor an approved request of another area", lambda cx: (unlock_request(cx, PER10, "inventory", "approved"), set_state(cx, PER10, "general", "soft_locked")),
      True, "needs an approved period_unlock_request")
trial("K11 N5: with an approved request of the period and area the unlock to soft_locked is accepted (rolled back afterwards)", lambda cx: (
    unlock_request(cx, PER10, "general", "approved"), set_state(cx, PER10, "general", "soft_locked"), cx.execute("select 1/0")), True, "division by zero")
trial("K12 N5: the migration period never unlocks, even with an approved request (ADR-0044 rule 2)", lambda cx: (
    unlock_request(cx, PERM, "general", "approved"), set_state(cx, PERM, "general", "soft_locked")), True, "migration period")
trial("K13 N5: a locked area's row is never deleted (and so never recreated as open)", lambda cx: cx.execute(
    "delete from posting_period_area_state where posting_period_id = %s and area = 'general'", (PER10,)), True, "never deleted")

# T3-1 (S2 adversarial review, third pass): a locked period was reopened by moving its dates. A period with an area row that is not
# open, or with a journal entry, never changes its dates, fiscal year, kind or number and is never deleted; its fiscal year never
# changes its dates or code and is never deleted. PER10 (October) is locked; I["per"] (November) is open and has the entry JE.
PER12, FY27 = new(), new()
ins_posting_period(X, PER12, I["co"], I["fy"], 12, "2026-12-01", "2026-12-31")     # no area row and no entry yet
ins_fiscal_year(X, FY27, I["co"], "2027", "2027-01-01", "2027-12-31")              # no period yet
period_dates = lambda cx, pid, s, e: cx.execute("update posting_period set start_date = %s, end_date = %s where id = %s", (s, e, pid))


def reviewer_sequence(cx):
    """The reviewer's reproduction: shrink the locked period, extend the open one, post inside the locked dates, set the dates back."""
    period_dates(cx, PER10, "2026-10-01", "2026-10-10")
    period_dates(cx, I["per"], "2026-10-11", "2026-11-30")
    je = new()
    cx.execute("insert into journal_entry (id, company_id, document_id, posting_date, document_date, posting_period_id, fiscal_year_id, line_count) values (%s,%s,%s,%s,%s,%s,%s,2)",
               (je, I["co"], doc(cx, new(), "purchase_invoice", partner=I["p1"]), "2026-10-15", "2026-10-15", I["per"], I["fy"]))
    for n, side, amt, acc in ((1, "debit", 1000, "acRev"), (2, "credit", -1000, "acBank2")):
        cx.execute("""insert into journal_line (id, journal_entry_id, company_id, line_number, posting_period_id, posting_date, fiscal_year_id, account_id,
                      system_account_id, side, transaction_currency, transaction_amount, company_currency, company_amount) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'VND',%s,'VND',%s)""",
                   (new(), je, I["co"], n, I["per"], "2026-10-15", I["fy"], I[acc], I["sa"], side, amt, amt))
    period_dates(cx, I["per"], "2026-11-01", "2026-11-30")
    period_dates(cx, PER10, "2026-10-01", "2026-10-31")


trial("K14 T3-1: the reviewer's sequence (shrink the locked October, extend November, post on 2026-10-15 in November, set the dates back) is "
      "refused at its first step", reviewer_sequence, True, "posting_period_frozen")
trial("K15 T3-1: an open period with a journal entry (November) never moves its dates", lambda cx: period_dates(cx, I["per"], "2026-11-01", "2026-11-25"),
      True, "posting_period_frozen")
trial("K16 T3-1: ... nor changes its number", lambda cx: cx.execute("update posting_period set number = 13 where id = %s", (I["per"],)),
      True, "posting_period_frozen")
trial("K17 T3-1: a locked period (October) is never deleted", lambda cx: cx.execute("delete from posting_period where id = %s", (PER10,)), True,
      "posting_period_frozen")
trial("K18 T3-1: the fiscal year of a locked period never moves its dates", lambda cx: cx.execute(
    "update fiscal_year set end_date = '2026-12-30' where id = %s", (I["fy"],)), True, "posting_period_frozen")
trial("K19 T3-1: ... nor changes its code", lambda cx: cx.execute("update fiscal_year set code = '2026b' where id = %s", (I["fy"],)), True,
      "posting_period_frozen")
trial("K19a T3-1: ... nor is it deleted", lambda cx: cx.execute("delete from fiscal_year where id = %s", (I["fy"],)), True, "posting_period_frozen")
trial("K20 T3-1: the trigger lets a period with no area row that is not open and no entry (December) change its dates; the rest of ADR-0007 rule 20 is the command's (rolled back afterwards)",
      lambda cx: (period_dates(cx, PER12, "2026-12-01", "2026-12-30"), cx.execute("select 1/0")), True, "division by zero")
trial("K20a T3-1: ... and a fiscal year with no such period may change its dates and code (rolled back afterwards)", lambda cx: (cx.execute(
    "update fiscal_year set end_date = '2027-12-30', code = '2027b' where id = %s", (FY27,)), cx.execute("select 1/0")), True, "division by zero")
trial("K20b T3-1: a soft-locked area counts too: December, once soft-locked, never moves its dates", lambda cx: (
    ins_area_state(cx.execute, I["co"], PER12, "general", "soft_locked"), period_dates(cx, PER12, "2026-12-01", "2026-12-30")), True, "posting_period_frozen")

# ======================================================================= L: final simulation review, 2026-11-15
# The payment block on open_item_collection (ADR-0048 rule 17 note; ADR-0063 rule 27 note) and the settings auto-post evidence
# depends on (ADR-0063 rule 3 note; ADR-0043 rule 14 note).
JL2 = X("select id from journal_line where journal_entry_id=%s and line_number=2", (JE,)).fetchone()[0]
OI = new()
X("""insert into open_item (id, company_id, partner_id, account_id, open_item_kind, natural_side, transaction_currency, origin_document_id,
     origin_journal_line_id, document_date, posting_date, original_posting_date, due_date, original_transaction_amount, original_company_amount,
     open_transaction_amount, open_company_amount) values (%s,%s,%s,%s,'invoice','credit','VND',%s,%s,%s,%s,%s,%s,-200000,-200000,-200000,-200000)""",
  (OI, I["co"], I["p1"], I["acBank2"], INV, JL2, TODAY, TODAY, TODAY, TODAY))
def collection(cx, co="co", blocked=False, reason=None, disputed=False, why=None):
    cx.execute("""insert into open_item_collection (open_item_id, company_id, is_payment_blocked, payment_block_reason, is_disputed, dispute_reason, recorded_at)
                  values (%s,%s,%s,%s,%s,%s,now())""", (OI, I[co], blocked, reason, disputed, why))
trial("L01 a payment block names its reason (ADR-0048 rule 17 note)", lambda cx: collection(cx, blocked=True), True, "ck_open_item_collection_payment_block")
trial("L02 ... and a dispute its reason", lambda cx: collection(cx, disputed=True), True, "ck_open_item_collection_dispute")
trial("L03 the collection row belongs to its open item's company", lambda cx: collection(cx, co="co2"), True, "fk_open_item_collection_open_item_id")
collection(X0, blocked=True, reason="duplicate_review")
def settle(cx):
    pid = payment(cx, new())
    cx.execute("""insert into payment_line (id, company_id, payment_id, line_number, line_kind, transaction_amount, open_item_id, open_item_transaction_amount,
                  evidence_method, recorded_at) values (%s,%s,%s,2,'settle',200000,%s,200000,'bank_transfer',now())""", (new(), I["co"], pid, OI))
trial("L04 a bank payment cannot settle an open item blocked for payment under a near-duplicate review (open_item_payment_blocked; ADR-0063 rule 27 note)",
      settle, True, "open_item_payment_blocked")
trial("L05 ... once not a duplicate is recorded, which clears the block and its reason, it can", lambda cx: (
    cx.execute("update open_item_collection set is_payment_blocked=false, payment_block_reason=null where open_item_id=%s", (OI,)), settle(cx)), False)
PR2 = new()
X("insert into policy_rule (id, company_id, code, recorded_at) values (%s,%s,'bank_charge_auto_post',now())", (PR2, I["co"]))
def evidenced(cx, vid, n, keys, enabled=True, evidence=True):
    cx.execute("""insert into policy_rule_version (id, company_id, policy_rule_id, version, effective_from, action, actor_kind, amount_company_max, effect,
                  is_confirmation_required, owner_user_id, is_enabled, shadow_evidence, evidence_setting_keys, recorded_at)
                  values (%s,%s,%s,%s,'2026-12-01','post','system',500000,'allow',true,%s,%s,%s,%s,now())""",
               (vid, I["co"], PR2, n, I["uChief"], enabled, json.dumps({"function_code": "cash.match_bank_line"}) if evidence else None, keys))
trial("L06 auto-post evidence is stored with the setting keys it was judged under (ADR-0063 rule 3 note)", lambda cx: evidenced(cx, new(), 9, None), True,
      "ck_policy_rule_version_evidence_settings")
EVK = {"bank_charge": ["auto_post.max_error_rate", "cash.bank_charge.auto_post_ceiling", "cash.bank_charge.min_evidence_lines"],
       "cascade": ["auto_post.max_error_rate", "cash.auto_post.accept_llm_originated_rules"], "disabled": ["cash.bank_charge.auto_post_ceiling"]}
PRV = {k: new() for k in EVK}
for n_, (k, keys) in enumerate(EVK.items(), 1):
    evidenced(X0, PRV[k], n_, keys, enabled=(k != "disabled"))
MARK = ("update policy_rule_version set shadow_evidence_outdated_by=%s where company_id=%s and is_enabled and shadow_evidence_outdated_by is null"
        " and %s = any (evidence_setting_keys)")                   # the statement DS-05 states on the column
def marked(by):
    return {k for k, v in PRV.items() if X("select shadow_evidence_outdated_by from policy_rule_version where id=%s", (v,)).fetchone()[0] == by}
SV1, SV2 = new(), new()
X(MARK, (SV1, I["co"], "cash.bank_charge.auto_post_ceiling"))
m1 = marked(SV1)
X(MARK, (SV2, I["co"], "auto_post.max_error_rate"))
m2 = marked(SV2)
check("L07 a loosening of cash.bank_charge.auto_post_ceiling marks exactly the enabled rule versions whose evidence lists it (the bank charge rule, "
      "not the cascade rule, not a disabled one); a later loosening of auto_post.max_error_rate marks the cascade rule, the bank charge rule's "
      "marker staying the first (ADR-0063 rule 3 note)", m1 == {"bank_charge"} and m2 == {"cascade"}, (m1, m2))
trial("L08 the evidence's setting keys are set once with it", lambda cx: cx.execute(
    "update policy_rule_version set evidence_setting_keys='{auto_post.max_error_rate}' where id=%s", (PRV["cascade"],)), True, "append-only")

# ---------------------------------------------------------------- the end
X0.close()
c = conn(); c.autocommit = True
try:
    c.execute(f"DROP OWNED BY {RLS_ROLE}")
    c.execute(f"DROP ROLE {RLS_ROLE}")
except Exception as e:  # noqa: BLE001  (the role may still hold privileges in another lab database)
    print("note: role kept:", str(e).splitlines()[0])
c.close()
passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
