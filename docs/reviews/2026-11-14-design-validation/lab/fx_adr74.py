"""Shared fixture of t27_partner_roles.py and t28_stock_count.py (ADR-0074, ADR-0075). Not product code.

build(c) inserts, in an autocommit connection on a database that load_all.py has loaded: one company with its user, unit, item
group, valuation class, item tax group, product and item, a site and two warehouses with their default bins, partners with
roles and addresses (a sold-to customer, a ship-to site, a head-office bill-to party, a paying group, a supplier, an invoicing
party and a payee, and a partner of a second company), and the reasons of every kind. It returns the dict of IDs.
"""
import os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lab import RESULTS, conn, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
B = '{"kind": "company_decision"}'


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def trial(name, fn, match):
    """fn must fail with an error whose first line contains match; everything is rolled back."""
    class Rollback(Exception):
        pass
    cx = conn()
    try:
        with cx.transaction():
            fn(cx)
            cx.execute("set constraints all immediate")
            raise Rollback()
    except Rollback:
        ok, detail = False, "succeeded (rolled back)"
    except Exception as e:  # noqa: BLE001
        msg = str(e).splitlines()[0]
        ok, detail = match in msg, "failed: " + msg
    finally:
        cx.close()
    check(name, ok, detail)


def reset_and_load(raw_dsn, docs):
    import psycopg
    from load_all import load_all
    with psycopg.connect(raw_dsn, autocommit=True) as cx:
        tables = [r[0] for r in cx.execute("select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
                                           " where n.nspname = 'nativeflows' and c.relkind in ('r', 'p') and not c.relispartition").fetchall()]
        for i in range(0, len(tables), 20):
            cx.execute("DROP TABLE IF EXISTS " + ", ".join(f'nativeflows."{t}"' for t in tables[i:i + 20]) + " CASCADE")
    return load_all(raw_dsn, docs)


def ins(cx, table, **v):
    cx.execute(f"insert into {table} ({', '.join(v)}) values ({', '.join(['%s'] * len(v))})", list(v.values()))
    return v.get("id")


def build(c):
    X = c.execute
    I = {}
    t = str(new())[-8:]
    I["t"] = t
    for k in ("user", "co", "co2", "ea", "ig", "vc", "itg", "prod", "item", "item2", "site", "w1", "z1", "b1", "w2", "z2", "b2", "wt", "zt", "bt",
              "bin_a", "sold", "ship", "bill", "payer", "sup", "inv", "payee", "other", "adr_ship", "adr_bill", "adr_other", "cc", "proj"):
        I[k] = new()
    X("insert into currency (code, minor_unit) values ('VND', 0) on conflict do nothing")
    X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I["user"], "u27" + t))
    for k, code in (("co", "C27-"), ("co2", "C27B-")):
        X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
          " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','warehouse',%s,'vi')", (I[k], code + t, I["user"]))
    X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,'Each','count',0)", (I["ea"], "EA27" + t))
    X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,'g','G',%s)", (I["ig"], I["co"], B))
    X("insert into valuation_class (id, company_id, code, name, basis) values (%s,%s,'v','V',%s)", (I["vc"], I["co"], B))
    X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,'s','S',%s)", (I["itg"], I["co"], B))
    X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
         item_tax_group_id) values (%s,%s,'STD','STD','stock',%s,%s,%s,%s,%s,%s)""", (I["prod"], I["co"], I["ig"], I["vc"], I["ea"], I["ea"], I["ea"], I["itg"]))
    X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'STD')", (I["item"], I["co"], I["prod"]))
    I["prod2"] = new()
    X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
         item_tax_group_id) values (%s,%s,'STD2','STD2','stock',%s,%s,%s,%s,%s,%s)""", (I["prod2"], I["co"], I["ig"], I["vc"], I["ea"], I["ea"], I["ea"], I["itg"]))
    X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'STD-2')", (I["item2"], I["co"], I["prod2"]))
    X("insert into site (id, company_id, code, name, kind) values (%s,%s,'MAIN','Main','factory')", (I["site"], I["co"]))
    with c.transaction():
        for w, z, b, code, kind in (("w1", "z1", "b1", "W1", "physical"), ("w2", "z2", "b2", "W2", "physical"), ("wt", "zt", "bt", "WT", "transit")):
            phys = kind == "physical"       # a transit warehouse has no site and is valued in a physical warehouse (ADR-0020 rule 2)
            X("insert into warehouse (id, company_id, site_id, valuation_warehouse_id, code, name, kind, default_bin_id) values (%s,%s,%s,%s,%s,%s,%s,%s)",
              (I[w], I["co"], I["site"] if phys else None, None if phys else I["w1"], code, code, kind, I[b]))
            X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'DEFAULT','Default')", (I[z], I["co"], I[w]))
            X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEFAULT',%s,'storage')",
              (I[b], I["co"], I[w], I[z], code + "-DEFAULT" + t.upper()))
    X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'A-01',%s,'storage')",
      (I["bin_a"], I["co"], I["w1"], I["z1"], "W1-A01" + t.upper()))
    for k, co, code in (("sold", "co", "SOLD"), ("ship", "co", "SHIP"), ("bill", "co", "BILL"), ("payer", "co", "PAYER"), ("sup", "co", "SUP"),
                        ("inv", "co", "INV"), ("payee", "co", "PAYEE"), ("other", "co2", "OTHER")):
        X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,%s,'organization','VN')", (I[k], I[co], code, code + " (sample)"))
    for k in ("sold", "bill", "payer"):
        X("insert into partner_role (company_id, partner_id, role) values (%s,%s,'customer')", (I["co"], I[k]))
    for k in ("sup", "inv", "payee"):
        X("insert into partner_role (company_id, partner_id, role) values (%s,%s,'supplier')", (I["co"], I[k]))
    for aid, pid, co, kind in (("adr_ship", "ship", "co", "delivery"), ("adr_bill", "bill", "co", "billing"), ("adr_other", "other", "co2", "billing")):
        X("insert into partner_address (id, company_id, partner_id, kind, address_lines, country) values (%s,%s,%s,%s,%s,'VN')",
          (I[aid], I[co], I[pid], kind, ["1 Example Street"]))
    X("insert into cost_center (id, company_id, code, name, kind) values (%s,%s,'CC1','CC','other')", (I["cc"], I["co"]))
    X("insert into project (id, company_id, code, name) values (%s,%s,'P1','P1')", (I["proj"], I["co"]))
    for kind in ("cancel", "reject", "return", "scrap", "count_difference", "block"):
        I["reason_" + kind] = new()
        X("insert into reason (id, company_id, kind, code, name) values (%s,%s,%s,%s,%s)", (I["reason_" + kind], I["co"], kind, kind + "_1", kind.title()))
    return I


def doc(cx, I, dtype, state="draft", partner=None, co="co", date="2026-11-10"):
    d = new()
    ins(cx, "document", id=d, company_id=I[co], document_type=dtype, state=state, version=1, partner_id=I[partner] if partner else None,
        document_date=date, created_by_user_id=I["user"], recorded_at=datetime.now(timezone.utc),
        posted_at=datetime.now(timezone.utc) if state in ("posted", "reversed") else None)
    return d
