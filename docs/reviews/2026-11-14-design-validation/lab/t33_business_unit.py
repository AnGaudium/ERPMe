"""Scenario: business unit derivation (ADR-0069 rules 4-5, 9, 11-14). Not product code.

Run: python t33_business_unit.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs).

The derivation is posting logic, not DDL: this lab writes it as a small reference function (ledger.contract.derive_business_unit)
and tests it, then runs it on candidates read from the DDL's master data and checks the stored result.
D: the derivation (rule 9): first match wins in the order line, item, cost center, project, document, site, company default;
   a production order line takes the order's output product as its item; the trace keeps the seven candidates per line, so
   the losing values are visible (EC-270); reversal and closing lines copy their unit (rule 11); a company without units
   skips it (rule 12); a balance-sheet line never carries a unit, and an explicit unit on one is refused (rule 5).
Q: the requirement (rule 14): business_unit_missing for a profit-and-loss line without a unit while the setting is on;
   reversal and closing lines exempt; no check in a company without active units; business_unit_default_unset when the
   setting is on and no default is set (EC-271).
C: the catalogs: the two settings as rule 13 states them; the three errors in DS-04; the DDL's business_unit_source CHECK
   lists exactly the reference function's sources.
With --load: business_unit keys (unique code, parent of the same company, not its own parent); the master data defaults on
product, cost center, project and site; candidates read through the DDL (the item's product, a transit warehouse's site
through its valuation warehouse); a journal entry whose lines carry the derived unit and source, with its trace
(rule_code business_unit_derivation) named by business_unit_trace_id; INV-821 in SQL (each line equals the trace's result,
the first non-null candidate); the pair CHECK, the source CHECK, and the company-composite keys to business_unit and
derivation_trace (S2: derivation_trace gained UNIQUE (company_id, id)).
Not covered: the posting command, account determination, the hook wiring, the analysis dimension.
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from fx_adr74 import DOCS, RESULTS, build, check, conn, doc, ins, new, reset_and_load, trial  # noqa: E402
from lab import ins_account, ins_area_state, ins_fiscal_year, ins_posting_period, ins_system_account  # noqa: E402

ORDER = ("line", "item", "cost_center", "project", "document", "site", "company_default")
SOURCES = ORDER + ("reversal", "closing")
PNL = {"income", "expense"}


# ======================================================================= reference functions
def derive_business_unit(lines, header_unit, defaults, company_has_units):
    """lines: [{n, account_type, unit (explicit), item, cost_center, project, warehouse, production_order, copied (reversal/closing: (unit, source))}].
    defaults: {"product_of_item", "output_product_of_order", "product", "cost_center", "project", "site_of_warehouse", "site", "company_default"}.
    Returns (results {n: (unit, source)}, trace or None, errors)."""
    if not company_has_units:
        return {l["n"]: (None, None) for l in lines}, None, []
    results, steps, errors = {}, {}, []
    for l in lines:
        if l.get("copied"):
            results[l["n"]] = l["copied"]
            continue
        if l["account_type"] not in PNL:
            if l.get("unit"):
                errors.append(("business_unit_invalid", l["n"]))
            results[l["n"]] = (None, None)
            continue
        item = l.get("item")
        if l.get("production_order"):
            item = defaults["output_product_of_order"][l["production_order"]]   # rule 9 step 2: the order's output product
            product = item
        else:
            product = defaults["product_of_item"].get(item)
        wh = l.get("warehouse")
        cand = [l.get("unit"), defaults["product"].get(product), defaults["cost_center"].get(l.get("cost_center")),
                defaults["project"].get(l.get("project")), header_unit, defaults["site"].get(defaults["site_of_warehouse"].get(wh)),
                defaults["company_default"]]
        steps[l["n"]] = cand
        hit = next((i for i, u in enumerate(cand) if u is not None), None)
        results[l["n"]] = (cand[hit], ORDER[hit]) if hit is not None else (None, None)
    trace = {"rule_code": "business_unit_derivation", "rule_version": "1", "steps": steps,
             "result": {n: list(r) for n, r in results.items()}}
    return results, trace, errors


def requirement(lines, results, required, company_has_active_units, default_set):
    """Rule 14: errors per line, and the check result of UpdateCompanySetting."""
    errs = []
    if required and company_has_active_units:
        for l in lines:
            if l["account_type"] in PNL and not l.get("copied") and results[l["n"]][0] is None:
                errs.append(("business_unit_missing", l["n"]))
    check_result = "business_unit_default_unset" if required and not default_set else None
    return errs, check_result


# ======================================================================= D: the derivation
DEF = {"product_of_item": {"i1": "p1", "i2": "p2"}, "output_product_of_order": {"po1": "p3"}, "product": {"p1": "A", "p3": "F"},
       "cost_center": {"cc1": "CC"}, "project": {"pj1": "PJ"}, "site_of_warehouse": {"w1": "s1", "wt": "s1"}, "site": {"s1": "B"}, "company_default": None}
case = lambda **l: dict({"n": 1, "account_type": "expense"}, **l)


def one(line, header=None, d=DEF):
    return derive_business_unit([line], header, d, True)[0][1]


check("D01 first match wins in rule 9's order: line, item, cost center, project, header, site, company default",
      [one(case(unit="L", item="i1", cost_center="cc1")), one(case(item="i1", cost_center="cc1")), one(case(item="i2", cost_center="cc1", project="pj1")),
       one(case(item="i2", project="pj1"), header="H"), one(case(item="i2", warehouse="w1"), header="H"), one(case(item="i2", warehouse="w1")),
       one(case(item="i2"), d=dict(DEF, company_default="D")), one(case(item="i2"))]
      == [("L", "line"), ("A", "item"), ("CC", "cost_center"), ("PJ", "project"), ("H", "document"), ("B", "site"), ("D", "company_default"), (None, None)])
res, tr, _ = derive_business_unit([case(account_type="expense", item="i1", warehouse="w1")], "C", DEF, True)
check("D02 EC-270: product unit A, site unit B, header C: the line gets A with source item, and the trace keeps B and C as losing candidates",
      res[1] == ("A", "item") and tr["steps"][1] == [None, "A", None, None, "C", "B", None], tr["steps"][1])
check("D03 a production order line takes the order's output product as its item, whatever item the line moves (rule 9 step 2)",
      one(case(item="i1", production_order="po1")) == ("F", "item"))
check("D04 a transit warehouse finds its site through its valuation warehouse (rule 9 step 6; ADR-0068 rule 2)", one(case(item="i2", warehouse="wt")) == ("B", "site"))
res, tr, _ = derive_business_unit([case(item="i1")], None, DEF, False)
check("D05 a company without business units skips the derivation: no trace, every unit null (rule 12)", tr is None and res[1] == (None, None))
res, _, _ = derive_business_unit([case(item="i2", copied=("OLD", "reversal")), case(n=2, account_type="income", copied=("A", "closing"))], None, DEF, True)
check("D06 reversal and closing lines copy their unit with source reversal or closing, even an inactive one (rule 11; rule 2)",
      res == {1: ("OLD", "reversal"), 2: ("A", "closing")})
res, _, errs = derive_business_unit([case(account_type="asset", item="i1"), case(n=2, account_type="liability", unit="L")], None, DEF, True)
check("D07 a balance-sheet line never carries a unit, even with a product unit; an explicit unit on one is refused with business_unit_invalid (rule 5)",
      res[1] == (None, None) and errs == [("business_unit_invalid", 2)])

# ======================================================================= Q: the requirement
ls = [case(item="i2"), case(n=2, item="i2", copied=("A", "reversal")), case(n=3, account_type="asset")]
r, _, _ = derive_business_unit(ls, None, DEF, True)
check("Q01 with the requirement on, a profit-and-loss line without a unit is refused with business_unit_missing; reversal and balance-sheet lines are not (rule 14)",
      requirement(ls, r, True, True, False)[0] == [("business_unit_missing", 1)])
check("Q02 the requirement does not apply in a company without active units, or while it is off",
      requirement(ls, r, True, False, False)[0] == [] and requirement(ls, r, False, True, False)[0] == [])
r2, _, _ = derive_business_unit(ls, None, dict(DEF, company_default="D"), True)
check("Q03 EC-271: after the company default is set, the line posts with source company_default; with the requirement on and no default the setting command returns business_unit_default_unset",
      requirement(ls, r2, True, True, True)[0] == [] and r2[1] == ("D", "company_default")
      and requirement(ls, r, True, True, False)[1] == "business_unit_default_unset" and requirement(ls, r, True, True, True)[1] is None)

# ======================================================================= C: catalogs
S = {r_["key"]: r_ for r_ in csv.DictReader(open(os.path.join(DOCS, "catalogs", "settings.csv"), encoding="utf-8"))}
d1, d2 = S.get("ledger.business_unit.default", {}), S.get("ledger.business_unit.required_on_profit_and_loss", {})
check("C01 the two settings of rule 13: the default a code of business_unit, core default unset, neutral; the requirement a boolean, false, true_tighter",
      (d1.get("value_type"), d1.get("core_default"), d1.get("bounds"), d1.get("direction"), d1.get("scope")) == ("code", "unset", "business_unit", "neutral", "company")
      and (d2.get("value_type"), d2.get("core_default"), d2.get("direction"), d2.get("scope")) == ("boolean", "false", "true_tighter", "company"))
ds04 = open(os.path.join(DOCS, "design", "DS-04-command-envelope.md"), encoding="utf-8").read()
errs04 = dict(re.findall(r"^\| `(business_unit_\w+)` \| (\w+) \|", ds04, re.M))
check("C02 DS-04 lists business_unit_missing and business_unit_in_use (precondition) and business_unit_invalid (validation)",
      errs04 == {"business_unit_missing": "precondition", "business_unit_in_use": "precondition", "business_unit_invalid": "validation"}, errs04)
ds06 = re.sub(r"\s+", " ", open(os.path.join(DOCS, "design", "DS-06-universal-journal.sql"), encoding="utf-8").read())
m = re.search(r"ck_journal_line_business_unit_source CHECK \(business_unit_source IN \(([^)]*)\)\)", ds06)
check("C03 the DDL's business_unit_source CHECK lists exactly the reference function's nine sources", m and set(re.findall(r"'(\w+)'", m.group(1))) == set(SOURCES),
      m and m.group(1))

# ======================================================================= X: the DDL (--load)
if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("X00 load_all.py loads every DDL file", n_tables > 0, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    I = build(c)

    def unit(cx, code, co="co", parent=None):
        u = new()
        ins(cx, "business_unit", id=u, company_id=I[co], code=code, name=code, parent_id=parent)
        return u
    BU = {k: unit(c, k) for k in ("A", "B", "C", "CC", "PJ")}
    BU2 = unit(c, "OTHER", co="co2")
    trial("X01 a business unit code is unique in its company", lambda cx: unit(cx, "A"), "business_unit_company_id_code_key")
    trial("X02 a parent is a unit of the same company", lambda cx: unit(cx, "X", parent=BU2), "business_unit_company_id_parent_id_fkey")
    trial("X03 a unit is not its own parent", lambda cx: (lambda u: cx.execute("update business_unit set parent_id=id where id=%s", (u,)))(unit(cx, "SELF")), "ck_business_unit_not_own_parent")
    X("update product set business_unit_id=%s where id=%s", (BU["A"], I["prod"]))
    X("update cost_center set business_unit_id=%s where id=%s", (BU["CC"], I["cc"]))
    X("update project set business_unit_id=%s where id=%s", (BU["PJ"], I["proj"]))
    X("update site set business_unit_id=%s where id=%s", (BU["B"], I["site"]))
    trial("X04 a master data default names a unit of its own company (product)", lambda cx: cx.execute("update product set business_unit_id=%s where id=%s", (BU2, I["prod2"])),
          "product_company_id_business_unit_id_fkey")

    # candidates read through the DDL, as the hook business_unit_defaults would
    def defaults_from_db():
        d = {"product_of_item": dict(X("select id, product_id from item where company_id=%s", (I["co"],)).fetchall()),
             "output_product_of_order": {},
             "product": dict(X("select id, business_unit_id from product where company_id=%s and business_unit_id is not null", (I["co"],)).fetchall()),
             "cost_center": dict(X("select id, business_unit_id from cost_center where company_id=%s and business_unit_id is not null", (I["co"],)).fetchall()),
             "project": dict(X("select id, business_unit_id from project where company_id=%s and business_unit_id is not null", (I["co"],)).fetchall()),
             "site_of_warehouse": dict(X("""select w.id, coalesce(w.site_id, v.site_id) from warehouse w left join warehouse v on v.company_id = w.company_id
                                            and v.id = w.valuation_warehouse_id where w.company_id=%s""", (I["co"],)).fetchall()),
             "site": dict(X("select id, business_unit_id from site where company_id=%s and business_unit_id is not null", (I["co"],)).fetchall()),
             "company_default": None}
        return d
    D = defaults_from_db()
    check("X05 the site of the transit warehouse is the site of its valuation warehouse, read through the DDL (ADR-0068 rule 2)", D["site_of_warehouse"][I["wt"]] == I["site"])
    LINES = [dict(n=1, account_type="income", item=I["item"], warehouse=I["w1"]),                     # product A wins over site B and header C
             dict(n=2, account_type="expense", item=I["item2"], cost_center=I["cc"], warehouse=I["w1"]),  # cost center CC wins over site B
             dict(n=3, account_type="expense", item=I["item2"], warehouse=I["wt"]),                  # header C wins over the site through transit
             dict(n=4, account_type="asset", item=I["item"], warehouse=I["w1"])]                     # balance sheet: none
    RES, TR, ERRS = derive_business_unit(LINES, BU["C"], D, True)
    check("X06 on the DDL's master data: line 1 gets the product's unit, line 2 the cost center's, line 3 the header's, the balance-sheet line none",
          [RES[n] for n in (1, 2, 3, 4)] == [(BU["A"], "item"), (BU["CC"], "cost_center"), (BU["C"], "document"), (None, None)] and not ERRS)

    # post the entry: fiscal year, period, accounts (the lab writes what posting would)
    fy, pp = new(), new()
    ins_fiscal_year(X, fy, I["co"], "2026", "2026-01-01", "2026-12-31")
    ins_posting_period(X, pp, I["co"], fy, 11, "2026-11-01", "2026-11-30")
    for area in ("general", "inventory", "receivable", "payable"):
        ins_area_state(X, I["co"], pp, area, "open")
    ACC = {}
    for code, account_type in (("rev", "income"), ("exp", "expense"), ("bs", "asset")):
        sa, a = new(), new()
        ins_system_account(X, sa, code + I["t"], account_type=account_type)
        ins_account(X, a, I["co"], code, sa)
        ACC[code] = (a, sa)
    JL_COLS = {r_[0] for r_ in X("select column_name from information_schema.columns where table_schema='nativeflows' and table_name='journal_line'").fetchall()}
    POST_DATE = "2026-11-10"

    def post(cx, lines, trace_id, company="co", unit_of=lambda n: RES[n]):
        d = doc(cx, I, "sales_invoice", state="posted")
        je = new()
        ins(cx, "journal_entry", id=je, company_id=I[company], document_id=d, posting_date=POST_DATE, document_date=POST_DATE, posting_period_id=pp,
            fiscal_year_id=fy, line_count=len(lines), business_unit_trace_id=trace_id)
        for n, acc, side, amount in lines:
            extra = {k: v for k, v in (("posting_date", POST_DATE), ("fiscal_year_id", fy)) if k in JL_COLS}   # the S2 ledger columns, when present
            u, src = unit_of(n)
            ins(cx, "journal_line", id=new(), journal_entry_id=je, company_id=I["co"], line_number=n, posting_period_id=pp, account_id=ACC[acc][0],
                system_account_id=ACC[acc][1], side=side, transaction_currency="VND", transaction_amount=amount if side == "debit" else -amount,
                company_currency="VND", company_amount=amount if side == "debit" else -amount, business_unit_id=u, business_unit_source=src, **extra)
        return je

    def trace(cx, co="co"):
        t = new()
        ins(cx, "derivation_trace", id=t, company_id=I[co], rule_code=TR["rule_code"], rule_version=TR["rule_version"], recorded_at="2026-11-10T10:00:00+00",
            command_id=new(), inputs=json.dumps({"header_unit": str(BU["C"]), "setting": None}),
            steps=json.dumps({str(n): [str(u) if u else None for u in s] for n, s in TR["steps"].items()}),
            result=json.dumps({str(n): [str(r_[0]) if r_[0] else None, r_[1]] for n, r_ in TR["result"].items()}))
        return t
    ENTRY = [(1, "rev", "credit", 300), (2, "exp", "debit", 100), (3, "exp", "debit", 100), (4, "bs", "debit", 100)]
    with c.transaction():
        TID = trace(c)
        JE = post(c, ENTRY, TID)
    check("X07 a journal entry with the derived unit and source on each line, and its trace named by business_unit_trace_id, is stored", True)
    bad = X("""select l.line_number from journal_line l join journal_entry e on e.id = l.journal_entry_id join derivation_trace t on t.company_id = e.company_id
               and t.id = e.business_unit_trace_id
               where e.id = %s and (t.result -> l.line_number::text ->> 0 is distinct from l.business_unit_id::text
                     or t.result -> l.line_number::text ->> 1 is distinct from l.business_unit_source
                     or (l.business_unit_source in ('line', 'item', 'cost_center', 'project', 'document', 'site', 'company_default')
                         and (select min(o) from jsonb_array_elements(t.steps -> l.line_number::text) with ordinality a(v, o) where a.v <> 'null'::jsonb)
                             <> array_position(array['line', 'item', 'cost_center', 'project', 'document', 'site', 'company_default'], l.business_unit_source)))""",
            (JE,)).fetchall()
    joined = X("""select count(*) from journal_line l join journal_entry e on e.id = l.journal_entry_id join derivation_trace t on t.company_id = e.company_id
                  and t.id = e.business_unit_trace_id where e.id = %s and t.result ? l.line_number::text""", (JE,)).fetchone()[0]
    check("X08 INV-821 in SQL: each line's unit and source equal the trace's result, and the source is the first non-null candidate of its steps",
          bad == [] and joined == 4, bad or f"{joined} lines joined to the trace")
    trial("X09 a unit without a source is refused (ck_journal_line_business_unit_pair)",
          lambda cx: post(cx, ENTRY[:2], trace(cx), unit_of=lambda n: (BU["A"], None) if n == 1 else RES[n]), "ck_journal_line_business_unit_pair")
    trial("X10 a source outside rule 4's list is refused", lambda cx: post(cx, ENTRY[:2], trace(cx), unit_of=lambda n: (BU["A"], "header") if n == 1 else RES[n]),
          "ck_journal_line_business_unit_source")
    trial("X11 a line's unit is of its company (company-composite key)", lambda cx: post(cx, ENTRY[:2], trace(cx), unit_of=lambda n: (BU2, "line") if n == 1 else RES[n]),
          "journal_line_company_id_business_unit_id_fkey")
    trial("X12 the entry's trace is of its company: derivation_trace (company_id, id) is the composite target (S2)",
          lambda cx: post(cx, ENTRY[:2], trace(cx, co="co2")), "journal_entry_company_id_business_unit_trace_id_fkey")
    uq = X("""select count(*) from pg_constraint k join pg_class r on r.oid = k.conrelid where r.relname = 'derivation_trace' and k.contype = 'u'
              and (select array_agg(a.attname::text order by a.attname) from pg_attribute a where a.attrelid = r.oid and a.attnum = any (k.conkey)) = array['company_id', 'id']""").fetchone()[0]
    check("X13 derivation_trace has UNIQUE (company_id, id)", uq == 1, uq)
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
