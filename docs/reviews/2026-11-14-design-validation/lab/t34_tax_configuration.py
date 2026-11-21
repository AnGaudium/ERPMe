"""Scenario: tax configuration at three levels and the tax tables (ADR-0041 rules 2-4, 6-7 and their notes of 2026-11-21;
ADR-0018 rule 3 note). Not product code.

Run: python t34_tax_configuration.py --load
  NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and rebuilds schemas nativeflows and types there with
  every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs). Without --load only the catalog checks run.

C: the catalogs: settings.csv registers tax.default_item_tax_group (company scope, value type code, bounds item_tax_group,
   unset by default); DS-04 lists item_tax_group_missing and tax_rate_row_invalid; invariants.csv has INV-302.
T: the DDL (--load): what is configured at three levels is the item tax group, and tax_effective_item_tax_group resolves it:
   the product's own group, else the nearest category up a parent chain of depth 3, else the company default setting in force
   on the date; none raises item_tax_group_missing. tax_rate holds one rate per code and date, and tax_rate_in_force picks the
   row in force on the tax date across a temporary reduction; a rate's value never changes and a used rate cannot be deleted.
   A posted line keeps its tax rows (rate, group and its level) when the product's or the category's group changes afterwards.
   A company's own codes, rates and matrix rows (rule 4 note): an x- code with an approved proposal; a company rate of a
   package code, a company row without a proposal and a company matrix row that shadows a package key not marked adjustable
   are refused; an adjustable key and a key with the company's own group are accepted; company matrix rows never change.
D: the transaction axis (ADR-0080, --load): the author's example (one product at the standard rate: a domestic sale takes the
   standard code, an export the zero-rate code); a foreign customer with a domestic delivery is domestic; a domestic customer
   with delivery abroad is export; one customer with a site inside a zone and one outside gets two treatments; a document
   mixing goods and a cross-border service; most specific wins and the priority tie-break; an equal tie raises
   tax_treatment_ambiguous; no rule raises tax_treatment_missing; a manual override is flagged; a credit note copies the
   original's treatment after the rules changed; a rate change by date through the whole chain; company rules keep the package
   protection; a posted document's treatment rows never change.
Synthetic package l10n_xx and country codes XX and YY only (D16); no country's values. The example rows live in the lab, not
in DS-16-l10n_xx, which holds only settings.
"""
import csv, json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fx_adr74 import DOCS, RESULTS, check, conn, ins, new, reset_and_load, trial  # noqa: E402

CAT = os.path.join(DOCS, "catalogs")
B = '{"kind": "company_decision"}'
PKG = '{"status": "test_fixture"}'

# ======================================================================= C: catalogs
with open(os.path.join(CAT, "settings.csv"), encoding="utf-8", newline="") as f:
    S = {r["key"]: r for r in csv.DictReader(f)}
r = S.get("tax.default_item_tax_group", {})
check("C01 settings.csv registers tax.default_item_tax_group: company scope, setting_value, value type code naming item_tax_group, unset, neutral",
      (r.get("scope"), r.get("storage"), r.get("value_type"), r.get("core_default"), r.get("bounds"), r.get("direction"), r.get("leaf"))
      == ("company", "setting_value", "code", "unset", "item_tax_group", "neutral", "tax_setup"), r)
ds04 = open(os.path.join(DOCS, "design", "DS-04-command-envelope.md"), encoding="utf-8").read()
check("C02 DS-04 lists item_tax_group_missing and tax_rate_row_invalid", "| `item_tax_group_missing` |" in ds04 and "| `tax_rate_row_invalid` |" in ds04)
with open(os.path.join(CAT, "invariants.csv"), encoding="utf-8", newline="") as f:
    inv = {r["code"]: r for r in csv.DictReader(f)}
check("C03 invariants.csv has INV-302 (company tax rows approved, no shadowing), area tax", inv.get("INV-302", {}).get("area") == "tax")

# ======================================================================= T: the DDL (--load)
if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("T00 load_all.py loads every DDL file", n_tables > 400, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    nul = lambda t, col: X("select is_nullable from information_schema.columns where table_schema='nativeflows' and table_name=%s and column_name=%s",
                           (t, col)).fetchone()
    check("T01 product.item_tax_group_id is nullable (empty = inherit); tax_code and tax_rate have a nullable company_id; tax_matrix has none",
          nul("product", "item_tax_group_id") == ("YES",) and nul("tax_code", "company_id") == ("YES",) and nul("tax_rate", "company_id") == ("YES",)
          and nul("tax_matrix", "company_id") is None and nul("company_tax_matrix", "company_id") == ("NO",))
    fn = X("""select p.proname, p.provolatile, p.proconfig from pg_proc p where p.pronamespace = 'nativeflows'::regnamespace
              and p.proname in ('tax_effective_item_tax_group', 'tax_rate_in_force') order by 1""").fetchall()
    check("T02 the resolver and the rate lookup are STABLE functions with a pinned search_path",
          [(n, v) for n, v, _ in fn] == [("tax_effective_item_tax_group", "s"), ("tax_rate_in_force", "s")]
          and all("search_path=nativeflows, pg_temp" in (cfg or []) for _, _, cfg in fn), fn)

    # ---- fixtures: one company of the synthetic package l10n_xx, a second company, groups, categories, products
    I = {k: new() for k in """user user2 co co2 ea ig std red own ptg ptg_own tk cat1 cat2 cat3 cat_none p_own p_cat3 p_cat1 p_def p_none
                              cp cp2 vat vat_red x_own""".split()}
    t = str(new())[-8:]
    X("insert into currency (code, minor_unit) values ('USD', 2) on conflict do nothing")
    for u in ("user", "user2"):
        X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I[u], u + "34" + t))
    for k, code in (("co", "C34-"), ("co2", "C34B-")):
        X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
          " values (%s,%s,'Co','USD','UTC','l10n_xx','xx','company',%s,'en')", (I[k], code + t, I["user"]))
    X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,'Each','count',0)", (I["ea"], "EA34" + t))
    X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,'g','G',%s)", (I["ig"], I["co"], B))
    for k, code in (("std", "standard"), ("red", "reduced"), ("own", "own_special")):
        X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,%s,%s,%s)", (I[k], I["co"], code, code, PKG if k != "own" else B))
    # ADR-0080: the matrix's first axis is the tax treatment (ptg = the domestic treatment, ptg_own = a company-added treatment)
    for k, code in (("ptg", "domestic"), ("ptg_own", "own_partner")):
        X("insert into tax_treatment (id, company_id, code, name, directions, basis) values (%s,%s,%s,%s,'{sale,purchase}',%s)", (I[k], I["co"], code, code, B))
    # category chain of depth 3: cat3 -> cat2 -> cat1; only cat1 names a group
    X("insert into product_category (id, company_id, code, name, default_item_tax_group_id, basis) values (%s,%s,'C1','C1',%s,%s)", (I["cat1"], I["co"], I["red"], B))
    X("insert into product_category (id, company_id, code, name, parent_id, basis) values (%s,%s,'C2','C2',%s,%s)", (I["cat2"], I["co"], I["cat1"], B))
    X("insert into product_category (id, company_id, code, name, parent_id, basis) values (%s,%s,'C3','C3',%s,%s)", (I["cat3"], I["co"], I["cat2"], B))
    X("insert into product_category (id, company_id, code, name, basis) values (%s,%s,'C0','C0',%s)", (I["cat_none"], I["co"], B))

    def product(k, cat=None, group=None):
        X("""insert into product (id, company_id, code, name, product_type, item_group_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
             product_category_id, item_tax_group_id) values (%s,%s,%s,%s,'service',%s,%s,%s,%s,%s,%s)""",
          (I[k], I["co"], k, k, I["ig"], I["ea"], I["ea"], I["ea"], I[cat] if cat else None, I[group] if group else None))
    product("p_own", cat="cat3", group="std")
    product("p_cat3", cat="cat3")
    product("p_cat1", cat="cat1")
    product("p_def", cat="cat_none")
    product("p_none")

    def resolve(k, day="2026-11-21", co="co"):
        return X("select * from tax_effective_item_tax_group(%s, %s, %s)", (I[co], I[k], day)).fetchone()
    check("T03 level product: a product's own group wins over its category chain", resolve("p_own") == (I["std"], "product"), resolve("p_own"))
    check("T04 level category, chain of depth 3: an empty product under C3 -> C2 -> C1 takes C1's group", resolve("p_cat3") == (I["red"], "product_category"),
          resolve("p_cat3"))
    check("T05 level category: a product directly under the category that names the group takes it", resolve("p_cat1") == (I["red"], "product_category"))
    trial("T06 missing: no product, category or company group raises item_tax_group_missing", lambda cx: cx.execute(
        "select * from tax_effective_item_tax_group(%s, %s, '2026-11-21')", (I["co"], I["p_def"])), "item_tax_group_missing")
    trial("T06a a product of another company is not resolved (item_tax_group_missing)", lambda cx: cx.execute(
        "select * from tax_effective_item_tax_group(%s, %s, '2026-11-21')", (I["co2"], I["p_cat3"])), "item_tax_group_missing")
    # the company default: setting tax.default_item_tax_group, a code of item_tax_group, in force from 2026-12-01
    sd = S["tax.default_item_tax_group"]
    X("""insert into setting_definition (id, setting_key, area, scopes, storage, value_type, default_kind, direction, leaf_code, change_effect, outdates, source,
         registry_version) values (%s,%s,%s,%s,%s,%s,'unset',%s,%s,%s,%s,%s,'0.1.0')""",
      (new(), "tax.default_item_tax_group", sd["area"], sd["scope"].split(";"), sd["storage"], sd["value_type"], sd["direction"], sd["leaf"],
       sd["change_effect"], sd["outdates"], sd["source"]))
    X("""insert into setting_value (id, company_id, setting_key, scope_kind, value, reason, effective_from, changed_by_user_id, registry_version)
         values (%s,%s,'tax.default_item_tax_group','company',%s,'lab: company default',%s,%s,'0.1.0')""", (new(), I["co"], json.dumps("standard"), "2026-12-01", I["user"]))
    check("T07 level company: on 2026-12-01 a product with no group on itself or its categories takes the company default",
          resolve("p_def", "2026-12-01") == (I["std"], "company") and resolve("p_none", "2026-12-01") == (I["std"], "company"), resolve("p_def", "2026-12-01"))
    trial("T08 the company default is read by date: before 2026-12-01 the same product still raises item_tax_group_missing", lambda cx: cx.execute(
        "select * from tax_effective_item_tax_group(%s, %s, '2026-11-30')", (I["co"], I["p_def"])), "item_tax_group_missing")
    check("T09 the levels stay in order with a default set: product, then category, then company",
          (resolve("p_own", "2026-12-01")[1], resolve("p_cat3", "2026-12-01")[1], resolve("p_def", "2026-12-01")[1]) == ("product", "product_category", "company"))

    # ---- package codes, dated rates and matrix
    X("""insert into transaction_key (id, code, name, determinants, required_system_accounts, has_regime_alternatives, added_in, meaning)
         values (%s,%s,'Output tax','{tax_code}','{tax_payable_output}',false,'0.1.0','lab fixture')""", (I["tk"], "output_tax" + t))
    for k, code in (("vat", "VAT_OUT"), ("vat_red", "VAT_OUT_RED")):
        X("""insert into tax_code (id, localization_package, code, name, tax_kind, direction, calculation, sequence, transaction_key_id, basis)
             values (%s,'l10n_xx',%s,%s,'vat','sale','percent',1,%s,%s)""", (I[k], code + t, code, I["tk"], PKG))

    def rate(code, day, pct, co=None, cp=None, source="package"):
        rid = new()
        X("insert into tax_rate (id, company_id, source, tax_code_id, effective_from, rate_percent, basis, change_proposal_id) values (%s,%s,%s,%s,%s,%s,%s,%s)",
          (rid, I[co] if co else None, source, I[code], day, pct, PKG if co is None else B, I[cp] if cp else None))
        return rid
    r10 = rate("vat", "2020-01-01", 10)
    r8 = rate("vat", "2025-07-01", 8)       # a temporary reduction ...
    r10b = rate("vat", "2027-01-01", 10)    # ... followed by a row restoring the rate (ADR-0041 rule 2)
    inforce = lambda day: X("select * from tax_rate_in_force(%s, %s)", (I["vat"], day)).fetchone()
    check("T10 a dated rate change picks the row in force on the tax date: 10% in 2024, 8% on 2026-12-31, 10% from 2027-01-01",
          (inforce("2024-05-01")[0], inforce("2026-12-31")[0], inforce("2027-01-01")[0]) == (r10, r8, r10b)
          and inforce("2026-12-31")[1] == 8, [inforce(d) for d in ("2024-05-01", "2026-12-31", "2027-01-01")])
    trial("T11 no rate before the first date raises tax_rate_missing", lambda cx: cx.execute("select * from tax_rate_in_force(%s, '2019-12-31')", (I["vat"],)),
          "tax_rate_missing")
    trial("T12 one rate per code and effective date", lambda cx: cx.execute(
        "insert into tax_rate (id, tax_code_id, effective_from, rate_percent, basis) values (%s,%s,'2025-07-01',9,%s)", (new(), I["vat"], PKG)),
        "uq_tax_rate_tax_code_id_effective_from")
    trial("T13 a rate's value never changes after insert (history never changes; a change is a new dated row)",
          lambda cx: cx.execute("update tax_rate set rate_percent = 9 where id = %s", (r8,)), "tax_rate.rate_percent is append-only")
    X("update tax_rate set basis = %s where id = %s", ('{"status": "test_fixture", "verified_on": "2026-11-21"}', r8))
    check("T14 a rate's basis may change (ADR-0016 rule 13)", X("select basis ? 'verified_on' from tax_rate where id=%s", (r8,)).fetchone()[0])
    X("""insert into tax_matrix (id, localization_package, direction, tax_treatment_code, item_tax_group_code, effective_from, tax_code_ids, basis)
         values (%s,'l10n_xx','sale','domestic','standard','2020-01-01',%s,%s)""", (new(), [I["vat"]], PKG))
    X("""insert into tax_matrix (id, localization_package, direction, tax_treatment_code, item_tax_group_code, effective_from, tax_code_ids, is_adjustable, basis)
         values (%s,'l10n_xx','sale','domestic','reduced','2020-01-01',%s,true,%s)""", (new(), [I["vat_red"]], PKG))
    trial("T15 a package matrix row names only codes of its package and direction", lambda cx: cx.execute(
        """insert into tax_matrix (id, localization_package, direction, tax_treatment_code, item_tax_group_code, effective_from, tax_code_ids, basis)
           values (%s,'l10n_yy','sale','domestic','standard','2020-01-01',%s,%s)""", (new(), [I["vat"]], PKG)), "tax_matrix_row_invalid")
    trial("T15a a package matrix row is never for direction import (import codes are not determined)", lambda cx: cx.execute(
        """insert into tax_matrix (id, localization_package, direction, tax_treatment_code, item_tax_group_code, effective_from, tax_code_ids, basis)
           values (%s,'l10n_xx','import','domestic','standard','2020-01-01',%s,%s)""", (new(), [I["vat"]], PKG)), "import")

    # ---- a posted line keeps its tax rows when the configuration changes afterwards
    def document(state, did=None):
        did = did or new()
        ins(c, "document", id=did, company_id=I["co"], document_type="sales_invoice", state=state, version=1, document_date="2026-11-10",
            created_by_user_id=I["user"], recorded_at=datetime.now(timezone.utc), posted_at=datetime.now(timezone.utc) if state == "posted" else None)
        return did
    inv = document("draft")
    g, src = resolve("p_cat3")
    rid, pct = inforce("2026-11-10")
    ins(c, "document_line_tax", id=new(), company_id=I["co"], document_id=inv, line_number=1, tax_code_id=I["vat"], tax_rate_id=rid, rate_percent=pct,
        item_tax_group_id=g, item_tax_group_source=src, base_transaction_amount=100, tax_transaction_amount=8, computed_tax_transaction_amount=8)
    X("update document set state = 'posted', posted_at = now() where id = %s", (inv,))
    X("update product_category set default_item_tax_group_id = %s where id = %s", (I["std"], I["cat1"]))
    X("update product set item_tax_group_id = %s where id = %s", (I["std"], I["p_cat3"]))
    kept = X("select tax_rate_id, rate_percent, item_tax_group_id, item_tax_group_source from document_line_tax where document_id=%s", (inv,)).fetchone()
    check("T16 after the product's and the category's group change, the posted line keeps its rate row, rate, group and level (rule 6 snapshot)",
          kept == (r8, 8, I["red"], "product_category") and resolve("p_cat3") == (I["std"], "product"), (kept, resolve("p_cat3")))
    trial("T17 the posted line's tax rows cannot be rewritten to follow the new configuration", lambda cx: cx.execute(
        "update document_line_tax set item_tax_group_id = %s, item_tax_group_source = 'product' where document_id = %s", (I["std"], inv)), "immutable")
    trial("T18 a used rate cannot be deleted (document_line_tax refers to it by key)", lambda cx: cx.execute("delete from tax_rate where id = %s", (r8,)),
          "document_line_tax_tax_rate_id_fkey")
    trial("T18a a group and its level come together on a tax row", lambda cx: cx.execute(
        """insert into document_line_tax (id, company_id, document_id, line_number, tax_code_id, item_tax_group_id, base_transaction_amount, tax_transaction_amount,
           computed_tax_transaction_amount) values (%s,%s,%s,2,%s,%s,1,0,0)""", (new(), I["co"], document("draft"), I["vat"], I["std"])), "ck_document_line_tax_item_tax_group")

    # ---- a company's own codes, rates and matrix rows (ADR-0041 rule 4 note, 2026-11-21)
    for k in ("cp", "cp2"):
        document("draft", I[k])
        ins(c, "change_proposal", id=I[k], company_id=I["co"], plan="{}", plan_hash="0" * 64, reason="lab: own tax rows", document_date="2026-11-21")

    def own_code(cx, code="x-own", cp="cp", co="co", direction="sale"):
        cx.execute("""insert into tax_code (id, company_id, source, code, name, tax_kind, direction, calculation, sequence, transaction_key_id, deductibility, basis,
                      change_proposal_id) values (%s,%s,'company',%s,'Own','vat',%s,'percent',1,%s,%s,%s,%s)""",
                   (new() if code != "x-own" else I["x_own"], I[co], code, direction, I["tk"], "deductible" if direction == "purchase" else None, B,
                    I[cp] if cp else None))
    own_code(c)
    rate("x_own", "2026-01-01", 7, co="co", cp="cp", source="company")
    check("T19 a company's own code (x- prefix, source company) and its dated rate are accepted with an approved proposal",
          X("select count(*) from tax_rate r join tax_code k on k.id = r.tax_code_id where k.company_id = %s and r.source = 'company'", (I["co"],)).fetchone()[0] == 1)
    trial("T20 a company code without its proposal is refused", lambda cx: own_code(cx, code="x-no-proposal", cp=None), "ck_tax_code_scope")
    trial("T21 a company code must begin with x-, so it never equals a package code", lambda cx: own_code(cx, code="VAT_OUT" + t), "ck_tax_code_company_code")
    trial("T22 a company rate without a proposal is refused", lambda cx: cx.execute(
        "insert into tax_rate (id, company_id, source, tax_code_id, effective_from, rate_percent, basis) values (%s,%s,'company',%s,'2026-06-01',6,%s)",
        (new(), I["co"], I["x_own"], B)), "ck_tax_rate_scope")
    trial("T23 a company rate of a package code is refused (it would shadow the package's rate)", lambda cx: cx.execute(
        "insert into tax_rate (id, company_id, source, tax_code_id, effective_from, rate_percent, basis, change_proposal_id) values (%s,%s,'company',%s,'2026-06-01',6,%s,%s)",
        (new(), I["co"], I["vat"], B, I["cp"])), "tax_rate_row_invalid")
    trial("T23a a package rate of a company code is refused", lambda cx: cx.execute(
        "insert into tax_rate (id, tax_code_id, effective_from, rate_percent, basis) values (%s,%s,'2026-06-01',6,%s)", (new(), I["x_own"], PKG)), "tax_rate_row_invalid")

    def own_row(cx, ptg="ptg", itg="std", codes=("x_own",), cp="cp", day="2026-01-01"):
        cx.execute("""insert into company_tax_matrix (id, company_id, direction, tax_treatment_id, item_tax_group_id, effective_from, tax_code_ids, basis, change_proposal_id)
                      values (%s,%s,'sale',%s,%s,%s,%s,%s,%s)""", (new(), I["co"], I[ptg], I[itg], day, [I[x] for x in codes], B, I[cp] if cp else None))
    trial("T24 a company matrix row shadowing a package key that is not adjustable is refused (domestic x standard)", lambda cx: own_row(cx), "tax_matrix_row_invalid")
    own_row(c, itg="red")
    own_row(c, itg="own", codes=("vat", "x_own"))
    own_row(c, ptg="ptg_own", itg="std")
    check("T25 accepted: an adjustable package key (domestic x reduced), a key with the company's own item group and one with its own treatment",
          X("select count(*) from company_tax_matrix where company_id = %s", (I["co"],)).fetchone()[0] == 3)
    trial("T26 a company matrix row without a proposal is refused", lambda cx: own_row(cx, itg="own", cp=None, day="2026-06-01"), "change_proposal_id")
    trial("T27 a company matrix row names only codes of its package or of the company, of its direction", lambda cx: (
        own_code(cx, code="x-purchase", direction="purchase"),
        own_row(cx, itg="own", codes=("vat",), day="2026-06-01"),
        cx.execute("""insert into company_tax_matrix (id, company_id, direction, tax_treatment_id, item_tax_group_id, effective_from, tax_code_ids, basis, change_proposal_id)
                      select %s,%s,'sale',%s,%s,'2026-07-01',array[k.id],%s,%s from tax_code k where k.company_id = %s and k.code = 'x-purchase'""",
                   (new(), I["co"], I["ptg"], I["own"], B, I["cp"], I["co"]))), "tax_matrix_row_invalid")
    trial("T28 company matrix rows are never updated (a change is a new dated row)", lambda cx: cx.execute(
        "update company_tax_matrix set effective_from = '2026-02-01' where company_id = %s", (I["co"],)), "never updated")

    # ======================================================================= D: the transaction axis (ADR-0080)
    cols = lambda tbl: {r[0] for r in X("select column_name from information_schema.columns where table_schema='nativeflows' and table_name=%s", (tbl,)).fetchall()}
    check("D00 schema: partner.partner_tax_status_id, is_tax_zone on partner_address and site, tax_treatment and tax_treatment_rule exist, no partner_tax_group",
          "partner_tax_status_id" in cols("partner") and "is_tax_zone" in cols("partner_address") and "is_tax_zone" in cols("site")
          and cols("tax_treatment") and cols("tax_treatment_rule") and not cols("partner_tax_group") and "tax_treatment_code" in cols("tax_matrix"))
    for k, code, dirs in (("tt_exp", "export", "{sale}"), ("tt_zone", "export_zone", "{sale}"), ("tt_srv", "foreign_service", "{sale}")):
        I[k] = new()
        X("insert into tax_treatment (id, company_id, code, name, directions, basis) values (%s,%s,%s,%s,%s,%s)", (I[k], I["co"], code, code, dirs, B))
    for k, code in (("st_reg", "registered"), ("st_for", "foreign")):
        I[k] = new()
        X("insert into partner_tax_status (id, company_id, code, name, basis) values (%s,%s,%s,%s,%s)", (I[k], I["co"], code, code, B))
    I["vat0"] = new()
    X("""insert into tax_code (id, localization_package, code, name, tax_kind, direction, calculation, sequence, transaction_key_id, basis)
         values (%s,'l10n_xx',%s,'Zero rate','vat','sale','percent',1,%s,%s)""", (I["vat0"], "VAT_ZERO" + t, I["tk"], PKG))
    rate("vat0", "2020-01-01", 0)
    for tr in ("export", "export_zone", "foreign_service"):
        X("""insert into tax_matrix (id, localization_package, direction, tax_treatment_code, item_tax_group_code, effective_from, tax_code_ids, basis)
             values (%s,'l10n_xx','sale',%s,'standard','2020-01-01',%s,%s)""", (new(), tr, [I["vat0"]], PKG))

    def rule(direction="sale", treatment=None, priority=0, day="2020-01-01", **det):
        rid = new()
        cols_ = ["document_type", "ship_from_country", "ship_to_country", "is_tax_zone", "partner_tax_status_code", "item_kind"]
        X(f"""insert into tax_treatment_rule (id, localization_package, direction, {', '.join(cols_)}, priority, effective_from, tax_treatment_code, basis)
              values (%s,'l10n_xx',%s,{', '.join(['%s'] * len(cols_))},%s,%s,%s,%s)""",
          [rid, direction] + [det.get(k) for k in cols_] + [priority, day, treatment, PKG])
        return rid
    R_EXP = rule(treatment="export")                                                  # any sale: export (0 determinants)
    R_DOM = rule(treatment="domestic", priority=10, ship_to_country="XX")             # destination XX: domestic (1)
    R_ZONE = rule(treatment="export_zone", ship_to_country="XX", is_tax_zone=True)    # destination XX in a zone (2)
    R_SRV = rule(treatment="foreign_service", priority=5, item_kind="service")        # a service (1, lower priority than R_DOM)
    R_TIE = rule(treatment="export", priority=10, document_type="lab_tie")            # same weight and priority as R_DOM

    def derive(ship_to, zone=False, status="registered", kind="goods", day="2026-11-21", dtype="sales_invoice", direction="sale"):
        return X("select * from tax_treatment_derive(%s,%s,%s,'XX',%s,%s,%s,%s,%s)", (I["co"], direction, dtype, ship_to, zone, status, kind, day)).fetchone()

    def codes(treatment_id, group="std", day="2026-11-21"):
        return X("select tax_code_ids from tax_matrix_codes(%s,'sale',%s,%s,%s)", (I["co"], treatment_id, I[group], day)).fetchone()[0]
    dom, exp_ = derive("XX"), derive("YY")
    check("D01 the author's example: one product at the standard rate is taxed by the standard code sold domestically and by the zero-rate code exported",
          (dom[1], exp_[1]) == ("domestic", "export") and codes(dom[0]) == [I["vat"]] and codes(exp_[0]) == [I["vat0"]], (dom, exp_))
    check("D02 a foreign customer with a domestic delivery is domestic (the destination decides, not the partner)",
          derive("XX", status="foreign")[1:] == ("domestic", R_DOM), derive("XX", status="foreign"))
    check("D03 a domestic customer with delivery abroad is export", derive("YY", status="registered")[1:] == ("export", R_EXP))
    a_in, a_out = new(), new()
    X("insert into partner (id, company_id, code, name, partner_kind, country, partner_tax_status_id) values (%s,%s,%s,'Zone customer (sample)','organization','XX',%s)",
      (I.setdefault("cust", new()), I["co"], "ZC" + t, I["st_reg"]))
    for aid, zone in ((a_in, True), (a_out, False)):
        X("insert into partner_address (id, company_id, partner_id, kind, address_lines, country, is_tax_zone) values (%s,%s,%s,'delivery','{1 Sample Road}','XX',%s)",
          (aid, I["co"], I["cust"], zone))
    two = [derive(*X("select country, is_tax_zone from partner_address where id=%s", (a,)).fetchone())[1] for a in (a_in, a_out)]
    check("D04 one customer with a delivery site inside a zone and one outside gets two treatments (zone flag on partner_address)",
          two == ["export_zone", "domestic"], two)
    check("D05 most specific wins: the zone rule (2 determinants) beats the domestic rule (1) and the general export rule (0)",
          derive("XX", zone=True)[2] == R_ZONE)
    check("D06 the priority breaks a tie of filled determinants: a domestic service matches R_DOM and R_SRV with one each, R_DOM's priority 10 wins",
          derive("XX", kind="service")[1:] == ("domestic", R_DOM) and derive("YY", kind="service")[1:] == ("foreign_service", R_SRV))
    trial("D07 two rules with as many determinants and the same priority raise tax_treatment_ambiguous", lambda cx: cx.execute(
        "select * from tax_treatment_derive(%s,'sale','lab_tie','XX','XX',false,'registered','goods','2026-11-21')", (I["co"],)), "tax_treatment_ambiguous")
    trial("D08 no rule raises tax_treatment_missing (no purchase rule exists)", lambda cx: cx.execute(
        "select * from tax_treatment_derive(%s,'purchase','purchase_invoice','YY','XX',false,'foreign','goods','2026-11-21')", (I["co"],)), "tax_treatment_missing")
    # D09-D10: the document's header and lines
    def doc_tt(cx, did, line, treatment, source, rule_id=None, derived=None):
        cx.execute("""insert into document_tax_treatment (id, company_id, document_id, line_number, tax_treatment_id, source, tax_treatment_rule_id, derived_tax_treatment_id)
                      values (%s,%s,%s,%s,%s,%s,%s,%s)""", (new(), I["co"], did, line, treatment, source, rule_id, derived))
    mixed = document("draft")
    doc_tt(c, mixed, None, dom[0], "rule", R_DOM, dom[0])
    doc_tt(c, mixed, 1, dom[0], "rule", R_DOM, dom[0])                    # goods delivered at home
    srv = derive("YY", kind="service")                                    # a service to a customer abroad (tax.services_place_of_supply)
    doc_tt(c, mixed, 2, srv[0], "rule", srv[2], srv[0])
    got = X("""select d.line_number, t.code from document_tax_treatment d join tax_treatment t on t.id = d.tax_treatment_id
               where d.document_id = %s order by d.line_number nulls first""", (mixed,)).fetchall()
    check("D09 a document mixing goods and a cross-border service: header and goods line domestic, the service line foreign_service, each with its rule",
          got == [(None, "domestic"), (1, "domestic"), (2, "foreign_service")], got)
    doc_tt(c, mixed, 3, exp_[0], "manual", R_DOM, dom[0])
    flag = X("select line_number, differs_from_rule from document_tax_treatment where document_id = %s order by line_number nulls first", (mixed,)).fetchall()
    check("D10 a manual treatment that differs from the rule is flagged (differs_from_rule, check result tax_treatment_differs_from_rule); rule rows are not",
          flag == [(None, False), (1, False), (2, False), (3, True)], flag)
    trial("D10a a row of source rule names its rule and gives the rule's treatment", lambda cx: doc_tt(cx, document("draft"), None, exp_[0], "rule", R_DOM, dom[0]),
          "ck_document_tax_treatment_rule")
    trial("D10b one treatment row per document and line", lambda cx: doc_tt(cx, mixed, 1, dom[0], "rule", R_DOM, dom[0]), "uq_document_tax_treatment_document_id_line_number")
    # D11: a credit note copies the original's treatment after the rules changed
    orig = document("draft")
    doc_tt(c, orig, None, dom[0], "rule", R_DOM, dom[0])
    X("update document set state = 'posted', posted_at = now() where id = %s", (orig,))
    rule(treatment="export", priority=10, day="2026-12-01", ship_to_country="XX")    # the package changes the rule from 2026-12-01
    later = derive("XX", day="2026-12-15")
    cn = new()
    ins(c, "document", id=cn, company_id=I["co"], document_type="credit_note", state="draft", version=1, document_date="2026-12-15",
        created_by_user_id=I["user"], correction_of_id=orig, recorded_at=datetime.now(timezone.utc))
    trial("D11 after the rule changed (domestic -> export on 2026-12-01), a credit note may not take the newly derived treatment",
          lambda cx: doc_tt(cx, cn, None, later[0], "rule", later[2], later[0]), "copies the original")
    doc_tt(c, cn, None, dom[0], "original")
    check("D11a ... it copies the original's treatment (source original), though the rules now derive export",
          later[1] == "export" and X("select tax_treatment_id, source from document_tax_treatment where document_id=%s and line_number is null", (cn,)).fetchone() == (dom[0], "original"))
    trial("D11b source original needs a corrected or reversed document", lambda cx: doc_tt(cx, document("draft"), None, dom[0], "original"), "source original needs")
    trial("D12 a posted document's treatment rows never change", lambda cx: cx.execute(
        "update document_tax_treatment set tax_treatment_id = %s where document_id = %s", (exp_[0], orig)), "immutable")
    # D13: a rate change by date through the whole chain (treatment -> matrix -> code -> rate)
    chain = lambda day: X("select r.rate_percent from tax_matrix_codes(%s,'sale',%s,%s,%s) m, tax_rate_in_force(m.tax_code_ids[1], %s) r",
                          (I["co"], dom[0], I["std"], day, day)).fetchone()[0]
    check("D13 a rate change by date through the chain: a domestic standard sale is taxed at 8% on 2026-12-31 and 10% on 2027-01-01",
          (chain("2026-12-31"), chain("2027-01-01")) == (8, 10), (chain("2026-12-31"), chain("2027-01-01")))
    # D14: company rules keep the package protection (ADR-0041 rule 4 note)
    def own_rule(cx, cp="cp", **det):
        cx.execute("""insert into tax_treatment_rule (id, company_id, source, direction, ship_to_country, is_tax_zone, effective_from, tax_treatment_code, basis, change_proposal_id)
                      values (%s,%s,'company','sale',%s,%s,'2026-01-01',%s,%s,%s)""",
                   (new(), I["co"], det.get("ship_to"), det.get("zone"), det.get("treatment", "export"), B, I[cp] if cp else None))
    trial("D14 a company rule with the determinants of a package rule not marked adjustable is refused", lambda cx: own_rule(cx, ship_to="XX"), "tax_treatment_rule_invalid")
    trial("D14a a company rule without a proposal is refused", lambda cx: own_rule(cx, cp=None, ship_to="YY"), "ck_tax_treatment_rule_scope")
    trial("D14b a company rule names a treatment of its company", lambda cx: own_rule(cx, ship_to="YY", treatment="no_such"), "tax_treatment_rule_invalid")
    own_rule(c, ship_to="YY", zone=True, treatment="export_zone")
    check("D14c a company rule with new determinants is accepted and used", derive("YY", zone=True)[1] == "export_zone")
    trial("D15 a rule's determinants never change after insert", lambda cx: cx.execute("update tax_treatment_rule set ship_to_country = 'YY' where id = %s", (R_DOM,)),
          "append-only")
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
