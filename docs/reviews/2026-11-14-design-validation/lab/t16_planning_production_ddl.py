"""Scenario: DS-43 and DS-51 to DS-55 planning and production DDL (ADR-0024, ADR-0033 to ADR-0037), loaded with DS-20, DS-56, DS-15 and DS-06.

Run: python t16_planning_production_ddl.py [--load]
  NATIVEFLOWS_LAB_DSN must name a throwaway database; --load drops and rebuilds schemas nativeflows and types there.
  NATIVEFLOWS_DOCS points at the docs/ tree to load (default ~/Projects/NativeFlows/docs); NATIVEFLOWS_LAB_DIR at lab.py and
  load_ds06.py (default: this file's directory).

S: static checks on the loaded schema: load order without cycles, external references only to stub tables, company_id
   and recorded_at on every new table, CHECK names, composite company keys, the holistic review's table decisions.
P: one small real dataset, written as the commands would: a bill of materials, a routing and a production version are
   released; planning parameters, a forecast and a run; a make-to-order planned production order pegged to a sales
   line, with its components, operations and a purchase planned order pegged to a component line; conversion into a
   production order with demand and supply lines; release with its cost object; an issue, a confirmation with
   backflush into operation_progress_component, a receipt; a released cost estimate and a period cost row.
N: the main checks and keys reject bad rows, each by the constraint or trigger named in the DDL.
R: with the generated company policy (ADR-0017 rule 19) a non-superuser role sees and writes only its company's rows.
Not covered: rules that need other rows (cycles, low-level codes, validity gaps, version selection, pegging sums,
tolerance, backflush quantities), which are command checks; the planning run and costing job themselves (mrp_lab.py,
costing_lab2.py).
"""
import os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import conn, expect, new, RESULTS  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
DESIGN = os.path.join(DOCS, "design")
STUBS = os.path.join(DOCS, "reviews/2026-11-14-design-validation/lab/00_stubs.sql")
NEW = "DS-43-54-planning-production.sql"
FILES = ["DS-20-master-data.sql", "DS-56-product-configuration.sql", "DS-06-universal-journal.sql", "DS-15-access.sql", NEW]
STUB_TABLES = {"document", "material_document", "material_document_line", "posting_period", "posting_period_area_state", "fiscal_year",
               "account", "system_account", "applied_rate", "close_task", "tax_code", "transaction_key"}
# Lab-only stub additions: the shared document row's columns and composite key of ADR-0052 rule 18.
EXTRA_STUBS = """SET search_path = nativeflows;
ALTER TABLE document ADD COLUMN IF NOT EXISTS partner_id uuid, ADD COLUMN IF NOT EXISTS document_date date;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'nativeflows.document'::regclass AND contype = 'u') THEN
    ALTER TABLE document ADD CONSTRAINT uq_document_company_id_id UNIQUE (company_id, id);
  END IF;
END $$;
"""
NEW_TEXT = open(os.path.join(DESIGN, NEW), encoding="utf-8").read()
NEW_TABLES = re.findall(r"^CREATE TABLE (\w+)", NEW_TEXT, re.M)


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail else ""))


def ordered_source():
    stubs = open(STUBS, encoding="utf-8").read()
    stub_line = "CREATE TABLE user_account (id uuid PRIMARY KEY);\n"
    assert stubs.count(stub_line) == 1, "00_stubs.sql: user_account stub not found once"
    stubs = stubs.replace(stub_line, "")                       # DS-15 defines user_account in full (as t12_access.py)
    src = "".join(open(os.path.join(DESIGN, f), encoding="utf-8").read() + "\n" for f in FILES)
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as tf:
        tf.write(src)
    p = subprocess.run([sys.executable, os.path.join(LAB, "load_ds06.py"), tf.name], capture_output=True, text=True)
    os.unlink(tf.name)
    return stubs, p


stubs, p = ordered_source()
external = next((l.split(":", 1)[1].strip() for l in p.stderr.splitlines() if l.startswith("-- external:")), "")
check("S01 load_ds06.py orders DS-20, DS-56, DS-06, DS-15 and DS-43-54 together without a cycle", p.returncode == 0, p.stderr.strip()[:200] if p.returncode else "")
ext = {e.strip() for e in external.split(",") if e.strip()}
check("S02 the combined files reference no table outside themselves except the lab stubs", ext <= STUB_TABLES, sorted(ext - STUB_TABLES))
if "--load" in sys.argv:
    cx = conn(); cx.autocommit = True
    cx.execute(stubs)
    cx.execute(EXTRA_STUBS)
    cx.execute("SET search_path = nativeflows;\n" + p.stdout)
    cx.close()

c = conn(); c.autocommit = True
X = c.execute
cols = {}
for t_, col, nullable in X("select table_name, column_name, is_nullable from information_schema.columns where table_schema='nativeflows'").fetchall():
    cols.setdefault(t_, {})[col] = nullable
check(f"S03 all {len(NEW_TABLES)} tables of {NEW} exist and carry company_id", all("company_id" in cols.get(t_, {}) for t_ in NEW_TABLES),
      [t_ for t_ in NEW_TABLES if "company_id" not in cols.get(t_, {})])
check("S04 every new table carries recorded_at NOT NULL (ADR-0007 rule 9)",
      all(cols.get(t_, {}).get("recorded_at") == "NO" for t_ in NEW_TABLES), [t_ for t_ in NEW_TABLES if cols.get(t_, {}).get("recorded_at") != "NO"])
bad_ck = X("""select r.relname, k.conname from pg_constraint k join pg_class r on r.oid = k.conrelid join pg_namespace n on n.oid = r.relnamespace
              where n.nspname='nativeflows' and k.contype='c' and r.relname = any(%s) and k.conname not like 'ck\\_' || r.relname || '\\_%%'""", (NEW_TABLES,)).fetchall()
check("S05 every CHECK constraint of the new tables is named ck_<table>_<name> (ADR-0004 rule 15)", bad_ck == [], bad_ck[:5])
# Every key to a table that has UNIQUE (company_id, id) uses it, so a reference cannot leave the company.
company_keyed = {r[0] for r in X("""select r.relname from pg_constraint k join pg_class r on r.oid = k.conrelid join pg_namespace n on n.oid = r.relnamespace
    where n.nspname='nativeflows' and k.contype in ('u','p') and (select array_agg(a.attname::text order by a.attname) from unnest(k.conkey) u(x)
    join pg_attribute a on a.attrelid = k.conrelid and a.attnum = u.x) = array['company_id','id']""").fetchall()}
fks = X("""select r.relname, f.relname, k.conname, (select array_agg(a.attname::text) from unnest(k.conkey) u(x) join pg_attribute a on a.attrelid = k.conrelid and a.attnum = u.x)
           from pg_constraint k join pg_class r on r.oid = k.conrelid join pg_class f on f.oid = k.confrelid join pg_namespace n on n.oid = r.relnamespace
           where n.nspname='nativeflows' and k.contype='f' and r.relname = any(%s)""", (NEW_TABLES,)).fetchall()
loose = [(a, b, n) for a, b, n, cl in fks if b in company_keyed and "company_id" not in cl and a != "planning_setting"]
check(f"S06 all {len(fks)} foreign keys of the new tables that reach a company-keyed table carry company_id", loose == [], loose[:5])
check("S07 the B3 columns exist as the interim: demand_supply_line production line keys, for_demand_supply_line_id and owner_partner_id; owner_partner_id on order components and outputs",
      {"production_order_component_id", "production_order_output_id", "for_demand_supply_line_id", "owner_partner_id"} <= set(cols["demand_supply_line"])
      and "for_demand_supply_line_id" in cols["production_order"] and "owner_partner_id" in cols["production_order_component"]
      and "owner_partner_id" in cols["production_order_output"] and "production_order_operation_id" in NEW_TEXT)
check("S08 one operation_progress_component table; no operation_confirmation_component or production_receipt_component (holistic decision 11)",
      "operation_progress_component" in cols and "operation_confirmation_component" not in cols and "production_receipt_component" not in cols)
check("S09 cost_estimate has costing_lot_quantity NOT NULL (holistic decision 18)", cols["cost_estimate"].get("costing_lot_quantity") == "NO")
check("S10 the forecast, message and exception tables exist: forecast_run, forecast_line, forecast_adjustment, planning_action_message, planning_exception, planned_order_pegging, planning_state, planning_run",
      all(t_ in cols for t_ in ("forecast_run", "forecast_line", "forecast_adjustment", "planning_action_message", "planning_exception", "planned_order_pegging", "planning_state", "planning_run")))
interims = [l for l in NEW_TEXT.splitlines() if "interim: not stated in" in l and "ADR-00xx" not in l]
uncited = [l.strip()[:80] for l in interims if not re.search(r"interim: not stated in ADR-00\d\d\b", l)]
check(f"S11 each of the {len(interims)} interim markers cites the silent ADR", interims and uncited == [], uncited[:3])

# ======================================================================= P: a small real dataset
I = {k: new() for k in """user co co2 ea kg hr ig vc itg pFG pC1 pC2 pSV pK iFG iC1 iC2 iSV iK iX2 pX2 S1 P1 E1 cal cc cc2
    WP WD WX zP zD zX bP bD bX SB OB bP2 setup machine WC1 B BK R1 RK RT RR1 RR2 op10 op20 PV ds_so ds_po FR PR
    PO_P PO_C1 PO_RP poc1 poc2 doc PO L1 L2 OUT OP10 OP20 CO CO_POOL doc_i ISS md_i mdl_i doc_c CONF md_c mdl_c doc_r REC
    LOT1 SER1 SER2 CE per settle doc_s RQ""".split()}
t = str(I["co"])[-8:]
H = lambda s: (s * 64)[:64]
B_ = '{"kind": "company_decision"}'
X("insert into currency (code, minor_unit) values ('VND',0) on conflict do nothing")
X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Planner','vi','x',now())", (I["user"], "planner" + t))
for k, code in (("co", "C13-"), ("co2", "C13B-")):
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,legal_form,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','joint_stock','warehouse',%s,'vi')", (I[k], code + t, I["user"]))
for k, code, kind in (("ea", "EA13", "count"), ("kg", "KG13", "mass"), ("hr", "HR13", "time")):
    X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,%s,2)", (I[k], code + t, code, kind))
for tbl, k in (("item_group", "ig"), ("valuation_class", "vc"), ("item_tax_group", "itg")):
    X(f"insert into {tbl} (id, company_id, code, name, basis) values (%s,%s,'std','Std',%s)", (I[k], I["co"], B_))
def product(pk, ik, code, ptype="stock", tracking="none", co="co"):
    X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
         item_tax_group_id, tracking) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (I[pk], I[co], code, code, ptype, I["ig"] if co == "co" else ig2, I["vc"] if ptype == "stock" and co == "co" else (vc2 if ptype == "stock" else None),
       I["ea"], I["ea"], I["ea"], I["itg"] if co == "co" else itg2, tracking))
    X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,%s)", (I[ik], I[co], I[pk], code))
product("pFG", "iFG", "FG-UNIT"); product("pC1", "iC1", "C1-FRAME"); product("pC2", "iC2", "C2-PANEL", tracking="lot"); product("pSV", "iSV", "SV-PAINT", "service")
product("pK", "iK", "K-KIT")
ig2, vc2, itg2 = new(), new(), new()
for tbl, k in (("item_group", ig2), ("valuation_class", vc2), ("item_tax_group", itg2)):
    X(f"insert into {tbl} (id, company_id, code, name, basis) values (%s,%s,'std','Std',%s)", (k, I["co2"], B_))
product("pX2", "iX2", "X2-OTHER", co="co2")
for k, code in (("S1", "SUP1"), ("P1", "PROC1"), ("E1", "EMP1")):
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,%s,'organization','VN')", (I[k], I["co"], code, code))
X("insert into working_calendar (id, company_id, code, name, working_weekdays) values (%s,%s,'STD','Std','{1,2,3,4,5}')", (I["cal"], I["co"]))
X("insert into cost_center (id, company_id, code, name, kind) values (%s,%s,'ASM','Assembly','production')", (I["cc"], I["co"]))
X("insert into cost_center (id, company_id, code, name, kind) values (%s,%s,'ASM','Assembly','production')", (I["cc2"], I["co2"]))
def warehouse(wk, zk, bk, code, processor=None, co="co"):
    with c.transaction():
        X("insert into warehouse (id, company_id, code, name, kind, processor_partner_id, working_calendar_id, default_bin_id) values (%s,%s,%s,%s,'physical',%s,%s,%s)",
          (I[wk], I[co], code, code, I[processor] if processor else None, I["cal"] if co == "co" else None, I[bk]))
        X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'Z','Zone')", (I[zk], I[co], I[wk]))
        X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEF',%s,'storage')", (I[bk], I[co], I[wk], I[zk], code + "-DEF"))
warehouse("WP", "zP", "bP", "WP"); warehouse("WD", "zD", "bD", "WD"); warehouse("WX", "zX", "bX", "WX", processor="P1")
for k, code in (("SB", "WP-SUP"), ("OB", "WP-OUT")):
    X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,%s,%s,'production')", (I[k], I["co"], I["WP"], I["zP"], code, code))
X("insert into production_structure (company_id, recorded_at) values (%s, now())", (I["co"],))

def step(name, sqls):
    """A positive step: every statement must succeed; it stays committed for later steps."""
    try:
        with c.transaction():
            for s, a in sqls:
                X(s, a)
        check(name, True)
    except Exception as e:
        check(name, False, str(e).splitlines()[0])

step("P01 activity types, a work center with production bins in its warehouse, and its activities", [
    ("insert into activity_type (id, company_id, code, name, time_uom_id, recorded_at) values (%s,%s,'setup','Setup',%s,now())", (I["setup"], I["co"], I["hr"])),
    ("insert into activity_type (id, company_id, code, name, time_uom_id, recorded_at) values (%s,%s,'machine','Machine',%s,now())", (I["machine"], I["co"], I["hr"])),
    ("""insert into work_center (id, company_id, code, name, production_warehouse_id, working_calendar_id, hours_per_day, cost_center_id, supply_bin_id, output_bin_id, recorded_at)
        values (%s,%s,'WC1','Assembly line',%s,%s,8,%s,%s,%s,now())""", (I["WC1"], I["co"], I["WP"], I["cal"], I["cc"], I["SB"], I["OB"])),
    ("insert into work_center_activity (company_id, work_center_id, activity_type_id, quantity, basis, recorded_at) values (%s,%s,%s,1,'per_order',now())", (I["co"], I["WC1"], I["setup"])),
])
step("P02 a bill of materials with two components (backflush at operation 10, manual) is written in draft and released", [
    ("insert into bill_of_materials (id, company_id, item_id, alternative, name, recorded_at) values (%s,%s,%s,'1','Unit',now())", (I["B"], I["co"], I["iFG"])),
    ("insert into bill_of_materials_revision (id, company_id, bill_of_materials_id, revision, start_date, base_quantity, recorded_at) values (%s,%s,%s,1,'2026-01-01',1,now())",
     (I["R1"], I["co"], I["B"])),
    ("""insert into bill_of_materials_component (id, company_id, bill_of_materials_revision_id, position, component_item_id, quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, operation_number, consumption_method, recorded_at)
        values (%s,%s,%s,10,%s,2,%s,1,1,'identity',10,'backflush_at_operation',now())""", (new(), I["co"], I["R1"], I["iC1"], I["ea"])),
    ("""insert into bill_of_materials_component (id, company_id, bill_of_materials_revision_id, position, component_item_id, quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, operation_number, consumption_method, recorded_at)
        values (%s,%s,%s,20,%s,1,%s,1,1,'identity',10,'manual',now())""", (new(), I["co"], I["R1"], I["iC2"], I["ea"])),
    ("update bill_of_materials_revision set state='released', content_hash=%s, released_at=now() where id=%s", (H("a"), I["R1"])),
    ("insert into bill_of_materials (id, company_id, item_id, usage, alternative, name, recorded_at) values (%s,%s,%s,'kit','1','Kit',now())", (I["BK"], I["co"], I["iK"])),
])
step("P03 a routing with an internal operation 10 (activities) and an external operation 20 (service item, default supplier) is released", [
    ("insert into routing (id, company_id, code, name, recorded_at) values (%s,%s,'RT-UNIT','Unit',now())", (I["RT"], I["co"])),
    ("insert into routing_revision (id, company_id, routing_id, revision, start_date, base_quantity, recorded_at) values (%s,%s,%s,1,'2026-01-01',1,now())", (I["RR1"], I["co"], I["RT"])),
    ("""insert into routing_operation (id, company_id, routing_revision_id, operation_number, work_center_id, control, setup_duration, run_duration, recorded_at)
        values (%s,%s,%s,10,%s,'internal',1,0.5,now())""", (I["op10"], I["co"], I["RR1"], I["WC1"])),
    ("""insert into routing_operation (id, company_id, routing_revision_id, operation_number, control, service_item_id, default_supplier_id, recorded_at)
        values (%s,%s,%s,20,'external',%s,%s,now())""", (I["op20"], I["co"], I["RR1"], I["iSV"], I["P1"])),
    ("insert into routing_operation_activity (company_id, routing_operation_id, routing_revision_id, activity_type_id, quantity, basis, recorded_at) values (%s,%s,%s,%s,0.5,'per_base_quantity',now())",
     (I["co"], I["op10"], I["RR1"], I["machine"])),
    ("update routing_revision set state='released', content_hash=%s, released_at=now() where id=%s", (H("b"), I["RR1"])),
    ("insert into routing_revision (id, company_id, routing_id, revision, start_date, base_quantity, recorded_at) values (%s,%s,%s,2,'2027-01-01',1,now())", (I["RR2"], I["co"], I["RT"])),
])
step("P04 a production version, the production setting, low-level codes, routes, planning parameters (make to order), a supplier item and the planning setting", [
    ("""insert into production_version (id, company_id, item_id, production_warehouse_id, code, bill_of_materials_id, routing_id, minimum_lot_quantity, maximum_lot_quantity, start_date, recorded_at)
        values (%s,%s,%s,%s,'V1',%s,%s,1,100,'2026-01-01',now())""", (I["PV"], I["co"], I["iFG"], I["WP"], I["B"], I["RT"])),
    ("insert into item_production_setting (company_id, item_id, production_warehouse_id, recorded_at) values (%s,%s,%s,now())", (I["co"], I["iFG"], I["WP"])),
    ("insert into item_low_level_code (company_id, item_id, low_level_code, recorded_at) values (%s,%s,0,now()), (%s,%s,1,now()), (%s,%s,1,now())",
     (I["co"], I["iFG"], I["co"], I["iC1"], I["co"], I["iC2"])),
    ("insert into transfer_route (id, company_id, source_warehouse_id, destination_warehouse_id, lead_time_days, recorded_at) values (%s,%s,%s,%s,2,now())", (I["RQ"], I["co"], I["WP"], I["WD"])),
    ("insert into transfer_route (id, company_id, source_warehouse_id, destination_warehouse_id, lead_time_days, recorded_at) values (%s,%s,%s,%s,1,now())", (new(), I["co"], I["WP"], I["WX"])),
    ("insert into transfer_route (id, company_id, source_warehouse_id, destination_warehouse_id, lead_time_days, recorded_at) values (%s,%s,%s,%s,1,now())", (new(), I["co"], I["WX"], I["WP"])),
    ("""insert into item_warehouse_planning (id, company_id, item_id, warehouse_id, planning_method, replenishment_source, planning_strategy, recorded_at)
        values (%s,%s,%s,%s,'net_requirements','production','make_to_order',now())""", (new(), I["co"], I["iFG"], I["WP"])),
    ("""insert into item_warehouse_planning (id, company_id, item_id, warehouse_id, planning_method, replenishment_source, safety_stock_quantity, receiving_days, recorded_at)
        values (%s,%s,%s,%s,'net_requirements','purchase',5,1,now())""", (new(), I["co"], I["iC1"], I["WP"])),
    ("""insert into item_warehouse_planning (id, company_id, item_id, warehouse_id, planning_method, replenishment_source, transfer_route_id, reorder_point, recorded_at)
        values (%s,%s,%s,%s,'reorder_point','transfer',%s,4,now())""", (new(), I["co"], I["iFG"], I["WD"], I["RQ"])),
    ("""insert into supplier_item (id, company_id, supplier_partner_id, item_id, order_uom_id, supplier_processing_days, transit_days, minimum_order_quantity, order_multiple, is_preferred, start_date, recorded_at)
        values (%s,%s,%s,%s,%s,5,3,10,5,true,'2026-01-01',now())""", (new(), I["co"], I["S1"], I["iC1"], I["ea"])),
    ("insert into supplier_purchasing_term (company_id, supplier_partner_id, minimum_order_amount, currency, recorded_at) values (%s,%s,1000000,'VND',now())", (I["co"], I["S1"])),
    ("insert into planning_setting (company_id, planning_owner_id, planning_horizon_days, conversion_window_days, backtest_weeks, recorded_at) values (%s,%s,180,3,26,now())", (I["co"], I["user"])),
])
step("P05 sales history, a forecast run with lines, a sales demand line and a purchase supply line, and a completed planning run that names the forecast", [
    ("insert into sales_history (company_id, item_id, warehouse_id, iso_week, quantity, recorded_at) values (%s,%s,%s,'2026-W40',4,now())", (I["co"], I["iFG"], I["WP"])),
    ("insert into forecast_run (id, company_id, planning_date, requested_by_user_id, recorded_at) values (%s,%s,'2026-11-16',%s,now())", (I["FR"], I["co"], I["user"])),
    ("insert into forecast_line (company_id, forecast_run_id, item_id, warehouse_id, forecast_date, quantity, forecast_tier, recorded_at) values (%s,%s,%s,%s,'2026-12-01',1,'short_mean',now())",
     (I["co"], I["FR"], I["iFG"], I["WP"])),
    ("""insert into demand_supply_line (id, company_id, item_id, warehouse_id, direction, open_quantity, requested_date, source_kind, sales_order_line_id, recorded_at)
        values (%s,%s,%s,%s,'demand',10,'2026-12-15','sales_order_line',%s,now())""", (I["ds_so"], I["co"], I["iFG"], I["WP"], new())),
    ("""insert into demand_supply_line (id, company_id, item_id, warehouse_id, direction, open_quantity, requested_date, ordered_date, source_kind, purchase_order_line_id, recorded_at)
        values (%s,%s,%s,%s,'supply',10,'2026-12-05','2026-11-01','purchase_order_line',%s,now())""", (I["ds_po"], I["co"], I["iC1"], I["WP"], new())),
    ("""insert into planning_run (id, company_id, planning_date, forecast_run_id, requested_by_user_id, state, output_counts, input_hash, output_hash, started_at, completed_at, recorded_at)
        values (%s,%s,'2026-11-16',%s,%s,'completed','{"planned_order": 2}',%s,%s,now(),now(),now())""", (I["PR"], I["co"], I["FR"], I["user"], H("c"), H("d"))),
    ("insert into planning_state (company_id, last_planning_run_id, recorded_at) values (%s,%s,now())", (I["co"], I["PR"])),
])
step("P06 a make-to-order planned production order pegged to the sales line, with components and operations, and a purchase planned order pegged to its component line", [
    ("""insert into planned_order (id, company_id, item_id, warehouse_id, order_type, need_date, for_demand_supply_line_id, quantity, order_quantity, order_uom_id, uom_numerator, uom_denominator,
        uom_factor_source, release_date, production_version_id, planned_start_date, planned_end_date, availability_date, planning_run_id, recorded_at)
        values (%s,%s,%s,%s,'production','2026-12-15',%s,10,10,%s,1,1,'identity','2026-12-01',%s,'2026-12-01','2026-12-10','2026-12-11',%s,now())""",
     (I["PO_P"], I["co"], I["iFG"], I["WP"], I["ds_so"], I["ea"], I["PV"], I["PR"])),
    ("insert into planned_order_component (id, company_id, planned_order_id, line_number, component_item_id, warehouse_id, quantity, requested_date, operation_number, recorded_at) values (%s,%s,%s,1,%s,%s,20,'2026-12-01',10,now())",
     (I["poc1"], I["co"], I["PO_P"], I["iC1"], I["WP"])),
    ("insert into planned_order_component (id, company_id, planned_order_id, line_number, component_item_id, warehouse_id, quantity, requested_date, operation_number, recorded_at) values (%s,%s,%s,2,%s,%s,10,'2026-12-01',10,now())",
     (I["poc2"], I["co"], I["PO_P"], I["iC2"], I["WP"])),
    ("insert into planned_order_operation (company_id, planned_order_id, operation_number, work_center_id, control, scheduled_start_date, scheduled_end_date, load_hours, recorded_at) values (%s,%s,10,%s,'internal','2026-12-01','2026-12-02',6,now())",
     (I["co"], I["PO_P"], I["WC1"])),
    ("insert into planned_order_operation (company_id, planned_order_id, operation_number, control, scheduled_start_date, scheduled_end_date, recorded_at) values (%s,%s,20,'external','2026-12-03','2026-12-10',now())",
     (I["co"], I["PO_P"])),
    ("insert into planned_order_pegging (id, company_id, planned_order_id, pegging_target_kind, demand_supply_line_id, quantity, recorded_at) values (%s,%s,%s,'demand_line',%s,10,now())",
     (new(), I["co"], I["PO_P"], I["ds_so"])),
    ("""insert into planned_order (id, company_id, item_id, warehouse_id, order_type, supplier_partner_id, need_date, quantity, order_quantity, order_uom_id, uom_numerator, uom_denominator,
        uom_factor_source, rounding_excess_quantity, release_date, planning_run_id, recorded_at)
        values (%s,%s,%s,%s,'purchase',%s,'2026-11-30',25,25,%s,1,1,'identity',0,'2026-11-18',%s,now())""", (I["PO_C1"], I["co"], I["iC1"], I["WP"], I["S1"], I["ea"], I["PR"])),
    ("insert into planned_order_pegging (id, company_id, planned_order_id, pegging_target_kind, target_planned_order_id, planned_order_component_id, quantity, recorded_at) values (%s,%s,%s,'planned_order',%s,%s,20,now())",
     (new(), I["co"], I["PO_C1"], I["PO_P"], I["poc1"])),
    ("insert into planned_order_pegging (id, company_id, planned_order_id, pegging_target_kind, quantity, recorded_at) values (%s,%s,%s,'lot_size_excess',5,now())", (new(), I["co"], I["PO_C1"])),
    ("insert into planning_action_message (id, company_id, planning_run_id, kind, demand_supply_line_id, requested_date, proposed_date, projected_effect, recorded_at) values (%s,%s,%s,'expedite',%s,'2026-12-05','2026-11-30','{}',now())",
     (new(), I["co"], I["PR"], I["ds_po"])),
    ("""insert into planning_exception (id, company_id, planning_run_id, kind, exception_key, item_id, warehouse_id, planned_order_id, lateness_days, recorded_at)
        values (%s,%s,%s,'shortage_inside_lead_time','sil:C1:WP',%s,%s,%s,2,now())""", (new(), I["co"], I["PR"], I["iC1"], I["WP"], I["PO_C1"])),
])
step("P07 the purchase planned order converts: replenishment request line with origin_planned_order_id", [
    ("insert into replenishment_request (id, company_id, requested_by_user_id, recorded_at) values (%s,%s,%s,now())", (I["RQ"], I["co"], I["user"])),
    ("""insert into replenishment_request_line (company_id, replenishment_request_id, line_number, origin_planned_order_id, item_id, warehouse_id, order_type, supplier_partner_id, quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity, need_date, release_date, recorded_at)
        values (%s,%s,1,%s,%s,%s,'purchase',%s,25,%s,1,1,'identity',25,'2026-11-30','2026-11-18',now())""", (I["co"], I["RQ"], I["PO_C1"], I["iC1"], I["WP"], I["S1"], I["ea"])),
    ("update planned_order set state='converted' where id=%s", (I["PO_C1"],)),
])
step("P08 the production planned order converts into a draft production order with components, outputs, operations and demand and supply lines", [
    ("insert into document (id, company_id, document_type, state, document_date) values (%s,%s,'production_order','draft','2026-11-16')", (I["doc"], I["co"])),
    ("""insert into production_order (id, company_id, order_type, item_id, production_warehouse_id, production_version_id, bill_of_materials_revision_id, routing_revision_id,
        good_quantity, planned_output_quantity, planned_start_date, planned_end_date, origin_planned_order_id, for_demand_supply_line_id, recorded_at)
        values (%s,%s,'standard',%s,%s,%s,%s,%s,10,10,'2026-12-01','2026-12-10',%s,%s,now())""",
     (I["doc"], I["co"], I["iFG"], I["WP"], I["PV"], I["R1"], I["RR1"], I["PO_P"], I["ds_so"])),
    ("""insert into production_order_component (id, company_id, production_order_id, line_number, component_item_id, required_quantity, issue_warehouse_id, operation_number, consumption_method, requested_date, recorded_at)
        values (%s,%s,%s,1,%s,20,%s,10,'backflush_at_operation','2026-12-01',now())""", (I["L1"], I["co"], I["doc"], I["iC1"], I["WP"])),
    ("""insert into production_order_component (id, company_id, production_order_id, line_number, component_item_id, required_quantity, issue_warehouse_id, operation_number, consumption_method, requested_date, recorded_at)
        values (%s,%s,%s,2,%s,10,%s,10,'manual','2026-12-01',now())""", (I["L2"], I["co"], I["doc"], I["iC2"], I["WP"])),
    ("insert into production_order_output (id, company_id, production_order_id, line_number, output_item_id, output_type, planned_quantity, requested_date, recorded_at) values (%s,%s,%s,1,%s,'main',10,'2026-12-10',now())",
     (I["OUT"], I["co"], I["doc"], I["iFG"])),
    ("""insert into production_order_operation (id, company_id, production_order_id, line_number, operation_number, work_center_id, control, setup_duration, run_duration, expected_quantity, scheduled_start_date, scheduled_end_date, recorded_at)
        values (%s,%s,%s,1,10,%s,'internal',1,0.5,10,'2026-12-01','2026-12-02',now())""", (I["OP10"], I["co"], I["doc"], I["WC1"])),
    ("""insert into production_order_operation (id, company_id, production_order_id, line_number, operation_number, control, supplier_partner_id, service_item_id, expected_quantity, scheduled_start_date, scheduled_end_date, recorded_at)
        values (%s,%s,%s,2,20,'external',%s,%s,10,'2026-12-03','2026-12-10',now())""", (I["OP20"], I["co"], I["doc"], I["P1"], I["iSV"])),
    ("insert into production_order_operation_activity (company_id, production_order_operation_id, activity_type_id, quantity, basis, recorded_at) values (%s,%s,%s,0.5,'per_base_quantity',now())",
     (I["co"], I["OP10"], I["machine"])),
    ("""insert into demand_supply_line (id, company_id, item_id, warehouse_id, direction, open_quantity, requested_date, source_kind, production_order_component_id, recorded_at)
        values (%s,%s,%s,%s,'demand',20,'2026-12-01','production_order_component',%s,now()), (%s,%s,%s,%s,'demand',10,'2026-12-01','production_order_component',%s,now())""",
     (new(), I["co"], I["iC1"], I["WP"], I["L1"], new(), I["co"], I["iC2"], I["WP"], I["L2"])),
    ("""insert into demand_supply_line (id, company_id, item_id, warehouse_id, direction, open_quantity, requested_date, source_kind, production_order_output_id, for_demand_supply_line_id, origin_planned_order_id, recorded_at)
        values (%s,%s,%s,%s,'supply',10,'2026-12-10','production_order_output',%s,%s,%s,now())""", (new(), I["co"], I["iFG"], I["WP"], I["OUT"], I["ds_so"], I["PO_P"])),
    ("update planned_order set state='converted' where id=%s", (I["PO_P"],)),
])
step("P09 release: the order is approved and gets its cost object of kind production_order; an output serial is assigned", [
    ("update document set state='approved' where id=%s", (I["doc"],)),
    ("insert into cost_object (id, company_id, code, name, kind, production_order_id) values (%s,%s,%s,'PO','production_order',%s)", (I["CO"], I["co"], "PO-" + t, I["doc"])),
    ("insert into cost_object (id, company_id, code, name, kind, cost_center_id) values (%s,%s,%s,'Pool','cost_pool',%s)", (I["CO_POOL"], I["co"], "POOL-" + t, I["cc"])),
    ("update production_order set cost_object_id=%s where id=%s", (I["CO"], I["doc"])),
    ("insert into serial_number (id, company_id, item_id, code) values (%s,%s,%s,'S-1'), (%s,%s,%s,'S-2')", (I["SER1"], I["co"], I["iFG"], I["SER2"], I["co"], I["iFG"])),
    ("insert into production_order_output_serial (company_id, production_order_id, production_order_output_id, serial_number_id, assigned_at, recorded_at) values (%s,%s,%s,%s,now(),now())",
     (I["co"], I["doc"], I["OUT"], I["SER1"])),
])
def posting_doc(dk, mk, lk, dtype):
    return [("insert into document (id, company_id, document_type, state) values (%s,%s,%s,'posted')", (I[dk], I["co"], dtype)),
            ("insert into material_document (id, document_id) values (%s,%s)", (I[mk], I[dk])),
            ("insert into material_document_line (id, material_document_id) values (%s,%s)", (I[lk], I[mk]))]
step("P10 a production issue of the manual lot-tracked component, carrying the order's cost object", posting_doc("doc_i", "md_i", "mdl_i", "production_issue") + [
    ("insert into lot (id, company_id, item_id, code) values (%s,%s,%s,'LOT-1')", (I["LOT1"], I["co"], I["iC2"])),
    ("insert into production_issue (id, company_id, production_order_id, posting_date, recorded_at) values (%s,%s,%s,'2026-12-01',now())", (I["doc_i"], I["co"], I["doc"])),
    ("""insert into production_issue_line (id, company_id, production_issue_id, production_order_id, line_number, production_order_component_id, item_id, warehouse_id, quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity, lot_id, bin_id,
        output_serial_number_id, cost_object_id, material_document_line_id, recorded_at) values (%s,%s,%s,%s,1,%s,%s,%s,10,%s,1,1,'identity',10,%s,%s,%s,%s,%s,now())""",
     (new(), I["co"], I["doc_i"], I["doc"], I["L2"], I["iC2"], I["WP"], I["ea"], I["LOT1"], I["SB"], I["SER1"], I["CO"], I["mdl_i"])),
    ("update production_order set execution_state='in_progress' where id=%s", (I["doc"],)),
])
step("P11 a confirmation of internal operation 10 with actual activities, and its backflush line in operation_progress_component", posting_doc("doc_c", "md_c", "mdl_c", "operation_confirmation") + [
    ("""insert into operation_confirmation (id, company_id, production_order_id, production_order_operation_id, yield_quantity, scrap_quantity, is_final, employee_partner_id, posting_date, recorded_at)
        values (%s,%s,%s,%s,10,0,true,%s,'2026-12-02',now())""", (I["doc_c"], I["co"], I["doc"], I["OP10"], I["E1"])),
    ("insert into operation_confirmation_activity (company_id, operation_confirmation_id, activity_type_id, quantity, recorded_at) values (%s,%s,%s,5,now())", (I["co"], I["doc_c"], I["machine"])),
    ("""insert into operation_progress_component (id, company_id, production_order_id, operation_confirmation_id, production_order_component_id, item_id, warehouse_id, quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity, bin_id, cost_object_id,
        material_document_line_id, recorded_at) values (%s,%s,%s,%s,%s,%s,%s,20,%s,1,1,'identity',20,%s,%s,%s,now())""",
     (new(), I["co"], I["doc"], I["doc_c"], I["L1"], I["iC1"], I["WP"], I["ea"], I["SB"], I["CO"], I["mdl_c"])),
])
step("P12 a production receipt of the main output (serial S-1) into the output bin", posting_doc("doc_r", "md_r", "mdl_r", "production_receipt") if False else [
    ("insert into document (id, company_id, document_type, state) values (%s,%s,'production_receipt','posted')", (I["doc_r"], I["co"])),
    ("insert into production_receipt (id, company_id, production_order_id, posting_date, operation_confirmation_id, recorded_at) values (%s,%s,%s,'2026-12-10',%s,now())",
     (I["doc_r"], I["co"], I["doc"], I["doc_c"])),
    ("""insert into production_receipt_line (id, company_id, production_receipt_id, production_order_id, line_number, production_order_output_id, item_id, warehouse_id, quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity, serial_number_id, bin_id,
        movement_type, cost_object_id, recorded_at) values (%s,%s,%s,%s,1,%s,%s,%s,1,%s,1,1,'identity',1,%s,%s,'production_receipt',%s,now())""",
     (new(), I["co"], I["doc_r"], I["doc"], I["OUT"], I["iFG"], I["WP"], I["ea"], I["SER1"], I["OB"], I["CO"])),
])
step("P13 a cost estimate with a costing lot quantity and lines is released; rates, a pool allocation rule and normal capacity are set", [
    ("insert into posting_period (id, company_id, start_date, end_date) values (%s,%s,'2026-12-01','2026-12-31')", (I["per"], I["co"])),
    ("""insert into cost_estimate (id, company_id, production_version_id, costing_date, costing_lot_quantity, bill_of_materials_revision_id, routing_revision_id, recorded_at)
        values (%s,%s,%s,'2026-11-16',10,%s,%s,now())""", (I["CE"], I["co"], I["PV"], I["R1"], I["RR1"])),
    ("insert into cost_estimate_line (company_id, cost_estimate_id, line_number, cost_component, component_item_id, quantity, price, company_amount, recorded_at) values (%s,%s,1,'material',%s,20,1000,20000,now())",
     (I["co"], I["CE"], I["iC1"])),
    ("insert into cost_estimate_line (company_id, cost_estimate_id, line_number, cost_component, activity_type_id, quantity, price, company_amount, recorded_at) values (%s,%s,2,'labor',%s,5,2000,10000,now())",
     (I["co"], I["CE"], I["machine"])),
    ("update cost_estimate set state='released', released_at=now(), company_amount=30000, unit_cost=3000 where id=%s", (I["CE"],)),
    ("insert into activity_rate (company_id, work_center_id, activity_type_id, posting_period_id, rate, recorded_at) values (%s,%s,%s,%s,2000,now())", (I["co"], I["WC1"], I["machine"], I["per"])),
    ("insert into pool_allocation_rule (company_id, cost_center_id, pool_group, driver, activity_type_id, recorded_at) values (%s,%s,'overhead','activity_type',%s,now())", (I["co"], I["cc"], I["machine"])),
    ("insert into normal_capacity (company_id, cost_center_id, driver, activity_type_id, posting_period_id, quantity, recorded_at) values (%s,%s,'activity_type',%s,%s,160,now())", (I["co"], I["cc"], I["machine"], I["per"])),
])
step("P14 the period-end job writes a settlement document with lines and a balanced period cost row", [
    ("insert into document (id, company_id, document_type, state) values (%s,%s,'production_cost_settlement','posted')", (I["settle"], I["co"])),
    ("insert into production_cost_settlement (id, company_id, posting_period_id, recorded_at) values (%s,%s,%s,now())", (I["settle"], I["co"], I["per"])),
    ("insert into production_cost_settlement_line (company_id, production_cost_settlement_id, cost_object_id, cost_component, step, company_amount, recorded_at) values (%s,%s,%s,'material','wip_transfer',30000,now())",
     (I["co"], I["settle"], I["CO"])),
    ("""insert into production_order_period_cost (company_id, production_order_id, posting_period_id, cost_component, opening_amount, incurred_amount, abnormal_amount, to_output_amount, closing_amount,
        production_cost_settlement_id, recorded_at) values (%s,%s,%s,'material',0,30000,1000,3000,26000,%s,now())""", (I["co"], I["doc"], I["per"], I["settle"])),
])
n_po = X("select count(*) from planned_order where company_id=%s and state='converted'", (I["co"],)).fetchone()[0]
n_ds = X("select count(*) from demand_supply_line where company_id=%s and origin_planned_order_id=%s", (I["co"], I["PO_P"])).fetchone()[0]
check("P15 both planned orders are converted, and the order's output supply line keeps origin_planned_order_id (INV-62)", n_po == 2 and n_ds == 1, (n_po, n_ds))

# ======================================================================= N: the main checks reject bad rows
def uom_fixture(table, v):
    """Lab fixture: the identity snapshot in the inventory unit EA unless the scenario gives one (ADR-0056 rules 9, 14)."""
    ident = dict(uom_numerator=1, uom_denominator=1, uom_factor_source="identity")
    if table == "supplier_item":
        v.setdefault("order_uom_id", I["ea"])
    elif table == "planned_order":
        v.setdefault("order_quantity", v.get("quantity")); v.setdefault("order_uom_id", I["ea"])
        for k_, x_ in ident.items(): v.setdefault(k_, x_)
    elif table in ("bill_of_materials_component", "bill_of_materials_output"):
        for k_, x_ in ident.items(): v.setdefault(k_, x_)
    elif table in ("production_issue_line", "production_receipt_line", "operation_progress_component"):
        v.setdefault("uom_id", I["ea"]); v.setdefault("inventory_quantity", v.get("quantity"))
        for k_, x_ in ident.items(): v.setdefault(k_, x_)
def ins(table, **v):
    v.setdefault("company_id", I["co"]); v.setdefault("recorded_at", "2026-11-16T00:00:00Z")
    uom_fixture(table, v)
    return (f"insert into {table} ({', '.join(v)}) values ({', '.join(['%s'] * len(v))})", list(v.values()))
def bad(name, match, *stmts):
    def fn(cx):
        for s, a in stmts:
            cx.execute(s, a)
    expect(name, fn, True, match)
def good(name, *stmts):
    def fn(cx):
        for s, a in stmts:
            cx.execute(s, a)
    expect(name, fn, False)

bom_comp = lambda rev, **o: ins("bill_of_materials_component", id=new(), bill_of_materials_revision_id=rev, position=o.pop("position", 30), component_item_id=I["iC1"],
                                quantity=o.pop("quantity", 1), uom_id=I["ea"], **o)
bad("N01 a released bill of materials revision cannot be updated (revision_released)", "revision_released",
    ("update bill_of_materials_revision set base_quantity=2 where id=%s", (I["R1"],)))
bad("N02 no component is added to a released revision (revision_released)", "revision_released", bom_comp(I["R1"]))
bad("N03 an operation of a released routing revision cannot be deleted (revision_released)", "revision_released",
    ("delete from routing_operation where id=%s", (I["op20"],)))
bad("N04 a second draft revision of one bill of materials is rejected (draft_revision_exists)", "ux_bill_of_materials_revision_draft",
    ins("bill_of_materials_revision", id=new(), bill_of_materials_id=I["B"], revision=2, start_date="2027-01-01", base_quantity=1),
    ins("bill_of_materials_revision", id=new(), bill_of_materials_id=I["B"], revision=3, start_date="2027-02-01", base_quantity=1))
R2 = new()
X(*ins("bill_of_materials_revision", id=R2, bill_of_materials_id=I["B"], revision=2, start_date="2027-01-01", base_quantity=1, copy_from_revision_id=I["R1"]))
bad("N05 component scrap of 100 percent is rejected (scrap in [0, 100))", "ck_bill_of_materials_component_scrap", bom_comp(R2, component_scrap_percent=100))
bad("N06 linear sizing needs quantity_per_value and a numeric characteristic", "ck_bill_of_materials_component_linear", bom_comp(R2, sizing="linear", quantity=0))
bad("N07 a zero quantity is allowed only as the base of linear sizing", "ck_bill_of_materials_component_quantity", bom_comp(R2, quantity=0))
VA_W = new()
good("N07b a linear base may be negative (-0.4 + 0.001 x width); the result over the width range is a release check (ADR-0046 rule 12 note)",
     ("insert into variant_attribute (id, company_id, code, name, value_type, minimum_value, maximum_value, step_value, decimal_places) "
      "values (%s,%s,'W_N07B','Width','number',600,2000,1,0)", (VA_W, I["co"])),
     bom_comp(R2, position=31, sizing="linear", quantity=-0.4, quantity_per_value=0.001, sizing_attribute_id=VA_W))
bad("N07c ... a negative quantity with fixed sizing is refused", "ck_bill_of_materials_component_quantity", bom_comp(R2, quantity=-1))
bad("N08 a co-product output needs a cost coefficient", "ck_bill_of_materials_output_coefficient",
    ins("bill_of_materials_output", id=new(), bill_of_materials_revision_id=R2, position=1, output_item_id=I["iK"], quantity=1, uom_id=I["ea"], output_type="co_product"))
bad("N09 an internal routing operation needs a work center and no service fields", "ck_routing_operation_control_fields",
    ins("routing_operation", id=new(), routing_revision_id=I["RR2"], operation_number=10, control="internal"))
bad("N10 an external routing operation needs a service item and a default supplier", "ck_routing_operation_control_fields",
    ins("routing_operation", id=new(), routing_revision_id=I["RR2"], operation_number=20, control="external", service_item_id=I["iSV"]))
pv = lambda **o: ins("production_version", id=new(), item_id=I["iFG"], production_warehouse_id=I["WP"], code=o.pop("code", "V9"), bill_of_materials_id=o.pop("bom", I["B"]),
                     start_date="2026-01-01", **o)
bad("N11 a production version's maximum lot below its minimum is rejected", "ck_production_version_lot_range", pv(minimum_lot_quantity=10, maximum_lot_quantity=5))
bad("N12 lead time method fixed needs production_lead_time_days", "ck_production_version_lead_time", pv(production_lead_time_method="fixed"))
bad("N13 a production version cannot use a kit bill of materials (usage production)", "fk_production_version_bill", pv(bom=I["BK"]))
bad("N14 a work center's supply bin must lie in its production warehouse", "fk_work_center_supply_bin",
    ins("work_center", id=new(), code="WC9", name="x", production_warehouse_id=I["WD"], working_calendar_id=I["cal"], hours_per_day=8, cost_center_id=I["cc"], supply_bin_id=I["SB"]))
iwp = lambda **o: ins("item_warehouse_planning", id=new(), item_id=o.pop("item", I["iC2"]), warehouse_id=o.pop("wh", I["WP"]), planning_method=o.pop("m", "net_requirements"), **o)
bad("N15 make_to_order needs source production, net_requirements and lot size exact (make_to_order_not_allowed)", "ck_item_warehouse_planning_make_to_order",
    iwp(replenishment_source="purchase", planning_strategy="make_to_order"))
bad("N16 a transfer source names a route", "ck_item_warehouse_planning_route", iwp(replenishment_source="transfer"))
bad("N17 the route of a planning row ends in that row's warehouse", "fk_item_warehouse_planning_route", iwp(item=I["iC2"], wh=I["WP"], replenishment_source="transfer", transfer_route_id=I["RQ"]))
bad("N18 min_max needs maximum >= minimum", "ck_item_warehouse_planning_min_max", iwp(m="min_max", replenishment_source="purchase", minimum_quantity=10, maximum_quantity=5))
bad("N19 a fixed lot size needs a positive fixed_lot_quantity", "ck_item_warehouse_planning_fixed_lot", iwp(replenishment_source="purchase", lot_size_method="fixed"))
bad("N20 supplier items of one supplier and item never overlap in dates", "ex_supplier_item_overlap",
    ins("supplier_item", id=new(), supplier_partner_id=I["S1"], item_id=I["iC1"], supplier_processing_days=1, transit_days=0, start_date="2026-06-01"))
bad("N21 a route from a warehouse to itself is rejected", "ck_transfer_route_distinct",
    ins("transfer_route", id=new(), source_warehouse_id=I["WD"], destination_warehouse_id=I["WD"], lead_time_days=0))
po = lambda **o: ins("planned_order", id=o.pop("id", new()), item_id=o.pop("item", I["iC1"]), warehouse_id=I["WP"], order_type=o.pop("ot", "purchase"), quantity=5,
                     release_date="2026-11-20", planning_run_id=I["PR"], **o)
bad("N22 a production planned order needs its version and planned dates", "ck_planned_order_production", po(ot="production", need_date="2026-12-20"))
bad("N23 a purchase planned order names its supplier", "ck_planned_order_source", po(need_date="2026-12-20"))
bad("N24 a make-to-order key names a demand line only on production planned orders", "ck_planned_order_make_to_order",
    po(supplier_partner_id=I["S1"], need_date="2026-12-20", for_demand_supply_line_id=I["ds_so"]))
bad("N25 the business key is unique: same item, warehouse, type, source, need date and sequence", "planned_order_company_id_item_id",
    po(supplier_partner_id=I["S1"], need_date="2026-11-30"))
good("N26 a canceled planned order never blocks a new proposal, which takes the next sequence",
     ("update planned_order set state='canceled' where id=%s", (I["PO_C1"],)), po(supplier_partner_id=I["S1"], need_date="2026-11-30", sequence=2))
bad("N27 one open reorder-point proposal per key without need_date", "ux_planned_order_open_without_need_date",
    po(supplier_partner_id=I["S1"]), po(supplier_partner_id=I["S1"], sequence=2))
bad("N28 a production planned order's version must make in its warehouse", "fk_planned_order_version",
    ins("planned_order", id=new(), item_id=I["iFG"], warehouse_id=I["WD"], order_type="production", need_date="2026-12-20", quantity=1, release_date="2026-12-01",
        production_version_id=I["PV"], planned_start_date="2026-12-01", planned_end_date="2026-12-05", availability_date="2026-12-06", planning_run_id=I["PR"]))
bad("N29 a demand_line peg names its demand line", "ck_planned_order_pegging_target",
    ins("planned_order_pegging", id=new(), planned_order_id=I["PO_P"], pegging_target_kind="demand_line", quantity=1))
PX = new()
bad("N30 a peg's component line belongs to its target planned order", "fk_planned_order_pegging_component",
    po(id=PX, supplier_partner_id=I["S1"], need_date="2026-12-27"),
    ins("planned_order_pegging", id=new(), planned_order_id=I["PO_C1"], pegging_target_kind="planned_order", target_planned_order_id=PX, planned_order_component_id=I["poc1"], quantity=1))
bad("N31 expedite proposes an earlier date", "ck_planning_action_message_fields",
    ins("planning_action_message", id=new(), planning_run_id=I["PR"], kind="expedite", demand_supply_line_id=I["ds_po"], requested_date="2026-12-05", proposed_date="2026-12-09", projected_effect="{}"))
bad("N32 capacity_overload names a work center and its range", "ck_planning_exception_subject",
    ins("planning_exception", id=new(), planning_run_id=I["PR"], kind="capacity_overload", exception_key="co:x"))
bad("N33 planning_parameter_missing carries its reason, and only it does", "ck_planning_exception_reason_kind",
    ins("planning_exception", id=new(), planning_run_id=I["PR"], kind="planning_parameter_missing", exception_key="ppm:x", item_id=I["iC2"], warehouse_id=I["WP"]))
bad("N34 one open exception per key", "ux_planning_exception_open",
    ins("planning_exception", id=new(), planning_run_id=I["PR"], kind="shortage_inside_lead_time", exception_key="sil:C1:WP", item_id=I["iC1"], warehouse_id=I["WP"]))
bad("N35 a forecast adjustment is a quantity or a factor, not both", "ck_forecast_adjustment_one",
    ins("forecast_adjustment", id=new(), item_id=I["iFG"], warehouse_id=I["WP"], start_date="2026-12-01", end_date="2026-12-07", quantity=1, factor=1.2,
        created_by_user_id=I["user"], reason="promotion"))
bad("N36 an unindexed forecast line keeps index 1", "ck_forecast_line_index",
    ins("forecast_line", forecast_run_id=I["FR"], item_id=I["iFG"], warehouse_id=I["WP"], forecast_date="2026-12-02", quantity=1, forecast_tier="unindexed", index_factor=1.3))
dsl = lambda **o: ins("demand_supply_line", id=new(), item_id=I["iC1"], warehouse_id=I["WP"], requested_date="2026-12-01", **o)
bad("N37 a production component line counts as demand only", "ck_demand_supply_line_kind_direction",
    dsl(direction="supply", open_quantity=1, source_kind="production_order_component", production_order_component_id=I["L1"]))
bad("N38 a demand and supply row names exactly the source its kind names", "ck_demand_supply_line_source",
    dsl(direction="demand", open_quantity=1, source_kind="sales_order_line", sales_order_line_id=new(), purchase_order_line_id=new()))
bad("N39 open quantity never goes below 0", "ck_demand_supply_line_open_quantity", dsl(direction="demand", open_quantity=-1, source_kind="sales_order_line", sales_order_line_id=new()))
bad("N40 one row per source line and direction", "ux_demand_supply_line_component",
    dsl(direction="demand", open_quantity=1, source_kind="production_order_component", production_order_component_id=I["L1"]))
bad("N41a hold reasons are a set of not_approved and credit_hold", "ck_demand_supply_line_hold_reasons",
    dsl(direction="demand", open_quantity=1, source_kind="sales_order_line", sales_order_line_id=new(), hold_reasons=["blocked"]))
good("N41b a held sales demand row (credit_hold) is written, released later by emptying the set",
     dsl(direction="demand", open_quantity=1, source_kind="sales_order_line", sales_order_line_id=(sl := new()), hold_reasons=["not_approved", "credit_hold"]),
     ("update demand_supply_line set hold_reasons='{}' where sales_order_line_id=%s", (sl,)))
bad("N41 for_demand_supply_line_id only on production output supply rows", "ck_demand_supply_line_for_demand",
    dsl(direction="supply", open_quantity=1, source_kind="purchase_order_line", purchase_order_line_id=new(), for_demand_supply_line_id=I["ds_so"]))
doc2 = new()
bad("N42 a production order's cost object is the production_order cost object that names it, never a pool or another order's", "fk_production_order_cost_object",
    ("insert into document (id, company_id, document_type) values (%s,%s,'production_order')", (doc2, I["co"])),
    ins("production_order", id=doc2, order_type="rework", item_id=I["iFG"], production_warehouse_id=I["WP"], good_quantity=1, planned_output_quantity=1,
        planned_start_date="2026-12-01", planned_end_date="2026-12-02", cost_object_id=I["CO"]))
bad("N42b a released order's cost object cannot be swapped for a pool while lines carry it", "fk_production_issue_line_cost_object",
    ("update production_order set cost_object_id=%s where id=%s", (I["CO_POOL"], I["doc"])))
bad("N43 a planned order converts into at most one production order", "ux_production_order_origin_planned_order",
    ("insert into document (id, company_id, document_type) values (%s,%s,'production_order')", (doc2, I["co"])),
    ins("production_order", id=doc2, order_type="standard", item_id=I["iFG"], production_warehouse_id=I["WP"], production_version_id=I["PV"], bill_of_materials_revision_id=I["R1"],
        good_quantity=1, planned_output_quantity=1, planned_start_date="2026-12-01", planned_end_date="2026-12-02", origin_planned_order_id=I["PO_P"]))
bad("N44 a standard production order needs its version and bill of materials snapshot", "ck_production_order_version",
    ("insert into document (id, company_id, document_type) values (%s,%s,'production_order')", (doc2, I["co"])),
    ins("production_order", id=doc2, order_type="standard", item_id=I["iFG"], production_warehouse_id=I["WP"], good_quantity=1, planned_output_quantity=1,
        planned_start_date="2026-12-01", planned_end_date="2026-12-02"))
bad("N45 planned output quantity Q is never below the good quantity G", "ck_production_order_planned_output",
    ("insert into document (id, company_id, document_type) values (%s,%s,'production_order')", (doc2, I["co"])),
    ins("production_order", id=doc2, order_type="rework", item_id=I["iFG"], production_warehouse_id=I["WP"], good_quantity=2, planned_output_quantity=1,
        planned_start_date="2026-12-01", planned_end_date="2026-12-02"))
iline = lambda **o: ins("production_issue_line", id=new(), production_issue_id=I["doc_i"], production_order_id=I["doc"], line_number=o.pop("ln", 9),
                        production_order_component_id=o.pop("comp", I["L2"]), item_id=o.pop("item", I["iC2"]), warehouse_id=I["WP"], quantity=o.pop("quantity", 1), bin_id=o.pop("bin_id", I["SB"]),
                        cost_object_id=o.pop("co_", I["CO"]), **o)
bad("N46 every material line of an issue carries its order's cost object (INV-103)", "fk_production_issue_line_cost_object", iline(co_=I["CO_POOL"]))
bad("N47 an issue line names a component line of the same order, item and issue warehouse", "fk_production_issue_line_component", iline(item=I["iC1"]))
bad("N48 an issue line's output serial is assigned to the same order (INV-105)", "fk_production_issue_line_output_serial", iline(output_serial_number_id=I["SER2"]))
bad("N49 an issue line takes stock from a bin of its warehouse", "fk_production_issue_line_bin", iline(bin_id=I["bD"]))
bad("N50 a serial issue line moves exactly one unit", "ck_production_issue_line_tracking", iline(serial_number_id=I["SER2"], quantity=2))
bad("N51 only an internal operation is confirmed (operation_not_confirmable)", "fk_operation_confirmation_operation",
    ("insert into document (id, company_id, document_type) values (%s,%s,'operation_confirmation')", (doc2, I["co"])),
    ins("operation_confirmation", id=doc2, production_order_id=I["doc"], production_order_operation_id=I["OP20"], yield_quantity=1, posting_date="2026-12-02"))
bad("N52 a scrap reason needs scrap", "ck_operation_confirmation_scrap_reason",
    ("insert into document (id, company_id, document_type) values (%s,%s,'operation_confirmation')", (doc2, I["co"])),
    ins("operation_confirmation", id=doc2, production_order_id=I["doc"], production_order_operation_id=I["OP10"], yield_quantity=1, scrap_reason_code="damaged", posting_date="2026-12-02"))
bad("N53 a generated progress line has exactly one calling document", "ck_operation_progress_component_caller",
    ins("operation_progress_component", id=new(), production_order_id=I["doc"], operation_confirmation_id=I["doc_c"], production_receipt_id=I["doc_r"], production_order_component_id=I["L1"],
        item_id=I["iC1"], warehouse_id=I["WP"], quantity=1, bin_id=I["SB"], cost_object_id=I["CO"], material_document_line_id=I["mdl_c"]))
bad("N53b a generated progress line is in the inventory unit (identity; ADR-0056 rule 9)", "ck_operation_progress_component_uom_identity",
    ins("operation_progress_component", id=new(), production_order_id=I["doc"], operation_confirmation_id=I["doc_c"], production_order_component_id=I["L1"],
        item_id=I["iC1"], warehouse_id=I["WP"], quantity=1, uom_id=I["ea"], uom_numerator=2, uom_denominator=1, uom_factor_source="product",
        inventory_quantity=2, bin_id=I["SB"], cost_object_id=I["CO"], material_document_line_id=I["mdl_c"]))
rline = lambda **o: ins("production_receipt_line", id=new(), production_receipt_id=I["doc_r"], production_order_id=I["doc"], line_number=o.pop("ln", 9),
                        production_order_output_id=I["OUT"], item_id=o.pop("item", I["iFG"]), warehouse_id=I["WP"], quantity=1, bin_id=o.pop("bin", I["OB"]),
                        movement_type=o.pop("mt", "production_receipt"), cost_object_id=I["CO"], **o)
bad("N54 a receipt line receives the item of its output line", "fk_production_receipt_line_output", rline(item=I["iC1"]))
bad("N55 a received serial is assigned to the same order", "fk_production_receipt_line_serial", rline(serial_number_id=I["SER2"]))
bad("N56 receipt movement types are the four production receipts", "ck_production_receipt_line_movement", rline(mt="goods_receipt"))
bad("N57 an order has at most one main output", "ux_production_order_output_main",
    ins("production_order_output", id=new(), production_order_id=I["doc"], line_number=2, output_item_id=I["iK"], output_type="main", planned_quantity=1, requested_date="2026-12-10"))
o2 = new()
bad("N58 a serial has at most one open assignment, across orders", "ux_production_order_output_serial_open",
    ("insert into document (id, company_id, document_type) values (%s,%s,'production_order')", (doc2, I["co"])),
    ins("production_order", id=doc2, order_type="rework", item_id=I["iFG"], production_warehouse_id=I["WP"], good_quantity=1, planned_output_quantity=1,
        planned_start_date="2026-12-01", planned_end_date="2026-12-02"),
    ins("production_order_output", id=o2, production_order_id=doc2, line_number=1, output_item_id=I["iFG"], output_type="main", planned_quantity=1, requested_date="2026-12-02"),
    ("insert into production_order_output_serial (company_id, production_order_id, production_order_output_id, serial_number_id, assigned_at, recorded_at) values (%s,%s,%s,%s,now(),now())",
     (I["co"], doc2, o2, I["SER1"])))
bad("N59 a cost estimate's costing lot quantity is positive", "ck_cost_estimate_lot",
    ins("cost_estimate", id=new(), production_version_id=I["PV"], costing_date="2026-11-16", costing_lot_quantity=0, bill_of_materials_revision_id=I["R1"]))
bad("N60 a released cost estimate is frozen", "revision_released", ("update cost_estimate set costing_lot_quantity=20 where id=%s", (I["CE"],)))
bad("N61 a period cost row balances: closing = opening + incurred - abnormal - residual - to output", "ck_production_order_period_cost_balance",
    ins("production_order_period_cost", production_order_id=I["doc"], posting_period_id=I["per"], cost_component="labor", opening_amount=0, incurred_amount=100,
        abnormal_amount=0, to_output_amount=50, closing_amount=10, production_cost_settlement_id=I["settle"]))
bad("N62 a pool allocation rule by activity names the activity type", "ck_pool_allocation_rule_activity",
    ins("pool_allocation_rule", cost_center_id=I["cc"], pool_group="labor", driver="activity_type"))
bad("N63 references stay inside one company: a planned order cannot name another company's item", "planned_order_company_id_item_id_fkey",
    po(item=I["iX2"], supplier_partner_id=I["S1"], need_date="2026-12-24"))
bad("N64 a low-level code is never negative", "ck_item_low_level_code_value", ins("item_low_level_code", item_id=I["iK"], low_level_code=-1))
bad("N65 a settlement line's step is one of the job's posting steps", "ck_production_cost_settlement_line_step",
    ins("production_cost_settlement_line", production_cost_settlement_id=I["settle"], cost_object_id=I["CO"], cost_component="material", step="adjustment", company_amount=1))

# ======================================================================= R: generated company policy
ROLE = "nativeflows_lab_t13"
try:
    X(f"DROP OWNED BY {ROLE}") if X("select 1 from pg_roles where rolname=%s", (ROLE,)).fetchone() else X(f"CREATE ROLE {ROLE} NOLOGIN")
    if X("select 1 from pg_roles where rolname=%s", (ROLE,)).fetchone() is None:
        X(f"CREATE ROLE {ROLE} NOLOGIN")
    X(f"GRANT USAGE ON SCHEMA nativeflows, types TO {ROLE}")
    for t_ in NEW_TABLES:
        X(f"ALTER TABLE {t_} ENABLE ROW LEVEL SECURITY")
        X(f"ALTER TABLE {t_} FORCE ROW LEVEL SECURITY")
        X(f"DROP POLICY IF EXISTS company ON {t_}")
        X(f"CREATE POLICY company ON {t_} USING (company_id = current_setting('nativeflows.company_id', true)::uuid) WITH CHECK (company_id = current_setting('nativeflows.company_id', true)::uuid)")
        X(f"GRANT SELECT, INSERT ON {t_} TO {ROLE}")
    X(f"GRANT SELECT ON ALL TABLES IN SCHEMA nativeflows TO {ROLE}")
    def seen(co):
        with c.transaction():
            X(f"SET LOCAL ROLE {ROLE}")
            X("SELECT set_config('nativeflows.company_id', %s, true)", (str(I[co]),))
            r = X("select (select count(*) from production_order), (select count(*) from planned_order), (select count(*) from demand_supply_line)").fetchone()
        return r
    own, other = seen("co"), seen("co2")
    check("R01 under the generated company policy a role sees its company's orders, planned orders and demand lines, and none of another company's",
          min(own) > 0 and other == (0, 0, 0), (own, other))
    def cross(cx):
        cx.execute(f"SET LOCAL ROLE {ROLE}")
        cx.execute("SELECT set_config('nativeflows.company_id', %s, true)", (str(I["co2"]),))
        cx.execute(*ins("transfer_route", id=new(), source_warehouse_id=I["WP"], destination_warehouse_id=I["WX"], lead_time_days=1))
    expect("R02 a row for another company is refused by the policy's WITH CHECK", cross, True, "row-level security")
finally:
    X(f"DROP OWNED BY {ROLE}") if X("select 1 from pg_roles where rolname=%s", (ROLE,)).fetchone() else None
    X(f"DROP ROLE IF EXISTS {ROLE}")

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
