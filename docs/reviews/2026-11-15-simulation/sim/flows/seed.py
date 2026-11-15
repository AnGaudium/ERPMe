"""Seed: one fictional company of the DS-17 vn_manufacturing profile (rule 18 notes): cast, roles, pools, sample policy
rules, TT99 chart and determination from the DS-19 package files, tax codes, master data, the configurable product with
its released model and super bill of materials, price lists, planning data and opening balances.
All names are fictional and marked "(sample)"; e-mail domains are .example."""
import datetime as dt
import os
import re
from decimal import Decimal as D

from psycopg.types.json import Jsonb

from .core import EFF, W, ins, upd, new_id, now, sha, d, set_day
from . import platform as P
from . import ledger as L
from . import pure

PKG = os.path.join(P.DOCS, "design", "DS-19-vietnam-tt99")
B = {"kind": "company_decision", "note": "simulation seed (sample), DS-17 vn_manufacturing profile notes"}

CAST = [  # template, login, display name
    ("owner", "sample.owner", "Sample Owner"), ("chief_accountant", "binh.le", "Binh Le (sample)"),
    ("accountant", "chi.nguyen", "Chi Nguyen (sample)"), ("cashier", "dung.pham", "Dung Pham (sample)"),
    ("sales_clerk", "giang.vo", "Giang Vo (sample)"), ("sales_manager", "hoa.dang", "Hoa Dang (sample)"),
    ("buyer", "khoa.bui", "Khoa Bui (sample)"), ("purchasing_manager", "lan.ho", "Lan Ho (sample)"),
    ("warehouse_keeper", "minh.do", "Minh Do (sample)"), ("production_planner", "nam.trinh", "Nam Trinh (sample)"),
    ("shop_floor_lead", "phuc.ly", "Phuc Ly (sample)"),
]
WORKFLOW_OWNER = {"customer_onboarding": "sales_clerk", "quotation": "sales_clerk", "bank_matching": "accountant",
                  "purchase_invoice": "accountant", "planning": "production_planner"}   # sim review 4/5/9 (32e7b1c)

CH = {   # the neutral configurable unit of the design lab (t06)
    "width": ("variant", "number", (D(400), D(2000), D(50))),
    "height": ("variant", "number", (D(300), D(1200), D(50))),
    "material": ("variant", "list", ["aluminium", "steel", "stainless"]),
    "size_class": ("variant", "list", ["S", "M", "L"]),
    "mounting": ("variant", "list", ["none", "wall", "floor"]),
    "color": ("line_option", "list", ["grey", "blue"]),
    "label": ("line_option", "list", ["text"]),
}
RULES = [
    ("restrict", {"c": "width", "op": "gt", "v": 1400}, "material", {"values": ["steel", "stainless"]}, "large_needs_strong_material"),
    ("set", {"c": "size_class", "op": "eq", "v": "L"}, "mounting", {"value": "floor"}, "large_on_floor"),
    ("set", {"c": "material", "op": "eq", "v": "stainless"}, "mounting", {"value": "wall"}, "stainless_on_wall"),
    ("forbid", {"all": [{"c": "mounting", "op": "eq", "v": "wall"}, {"c": "height", "op": "gt", "v": 1000}]}, None, {}, "wall_too_tall"),
    ("require", {"c": "material", "op": "eq", "v": "steel"}, "color", {}, "steel_needs_color"),
    ("restrict", {"c": "mounting", "op": "eq", "v": "floor"}, "height", {"min": 600, "max": 1200}, "floor_min_height"),
    ("restrict", {"c": "material", "op": "eq", "v": "aluminium"}, "height", {"min": 300, "max": 550}, "aluminium_max_height"),
]
TABLES = [
    ("size_band", ["width", "size_class"], [[{"min": 400, "max": 800}, "S"], [{"min": 850, "max": 1400}, "M"], [{"min": 1450, "max": 2000}, "L"]]),
    ("material_size", ["material", "size_class"], [["aluminium", "S"], ["aluminium", "M"], ["steel", "*"], ["stainless", "M"], ["stainless", "L"]]),
]
DEFAULTS = [("mounting", "none", {}), ("height", 600, {})]
# components of the super bill of materials: code, name, uom, preliminary price, condition, sizing, qty, qty per value, characteristic, decimals
COMPONENTS = [
    ("FRAME-S", "Frame S (sample)", "EA", 2000000, {"c": "size_class", "op": "eq", "v": "S"}, "fixed", 1, None, None, 0),
    ("FRAME-M", "Frame M (sample)", "EA", 3200000, {"c": "size_class", "op": "eq", "v": "M"}, "fixed", 1, None, None, 0),
    ("FRAME-L", "Frame L (sample)", "EA", 6800000, {"c": "size_class", "op": "eq", "v": "L"}, "fixed", 1, None, None, 0),
    ("SIDE-RAIL", "Side rail profile (sample)", "M", 240000, {}, "linear", 0, D("0.002"), "height", 1),
    ("TOP-RAIL", "Top rail profile (sample)", "M", 240000, {}, "linear", 0, D("0.002"), "width", 1),
    ("EXT-RAIL", "Extension rail profile (sample)", "M", 240000, {}, "linear", D("-0.4"), D("0.001"), "width", 1),   # t06 parameters (DS-43 allows the negative intercept since 32e7b1c)
    ("WALL-KIT", "Wall mounting kit (sample)", "EA", 600000, {"c": "mounting", "op": "eq", "v": "wall"}, "fixed", 1, None, None, 0),
    ("FLOOR-KIT", "Floor stand kit (sample)", "EA", 900000, {"c": "mounting", "op": "eq", "v": "floor"}, "fixed", 1, None, None, 0),
    ("COATING-KIT", "Coating kit (sample)", "EA", 400000, {"c": "material", "op": "eq", "v": "steel"}, "fixed", 1, None, None, 0),
    ("PANEL-ALU", "Aluminium panel (sample)", "EA", 500000, {"c": "material", "op": "eq", "v": "aluminium"}, "fixed", 2, None, None, 0),
    ("PANEL-STEEL", "Steel panel (sample)", "EA", 600000, {"c": "material", "op": "eq", "v": "steel"}, "fixed", 2, None, None, 0),
    ("PANEL-SS", "Stainless panel (sample)", "EA", 1400000, {"c": "material", "op": "eq", "v": "stainless"}, "fixed", 2, None, None, 0),
]
OPENING_STOCK = {"FRAME-S": 2, "FRAME-M": 1, "FRAME-L": 0, "SIDE-RAIL": 20, "TOP-RAIL": 5, "EXT-RAIL": 10, "WALL-KIT": 3, "FLOOR-KIT": 5,
                 "COATING-KIT": 1, "PANEL-ALU": 6, "PANEL-STEEL": 2, "PANEL-SS": 2, "ABS": 60}
SAFETY = {"SIDE-RAIL": 10, "TOP-RAIL": 5, "PANEL-STEEL": 2, "COATING-KIT": 2, "FLOOR-KIT": 2, "ABS": 20}
ABS_HISTORY = [18, 22, 25, 20, 24, 27, 23, 26, 21, 25, 28, 24]       # 12 ISO weeks from 2026-08-10
POLICY_SAMPLE = [  # DS-17 rule 18 note: action submit, actor kind human, effect require_approval (VND)
    ("pr_standard", "purchase_request", {"amount_company_min": D(20000000)}, "standard"),
    ("pr_senior", "purchase_request", {"amount_company_min": D(200000000)}, "senior"),
    ("po_standard", "purchase_order", {"amount_company_min": D(50000000)}, "standard"),
    ("po_senior", "purchase_order", {"amount_company_min": D(500000000)}, "senior"),
    ("quotation_discount", "quotation", {"discount_percent_min": D(10)}, "standard"),
    ("quotation_margin", "quotation", {"margin_percent_max": D(15)}, "standard"),
    ("quotation_below_cost", "quotation", {"is_price_below_cost": True}, "senior"),
    ("production_order_release", "production_order", {}, "standard"),
]
POOLS = {  # ADR-0055 rule 2 with its notes (production_issue moved to consumption)
    "pr": ["purchase_request"], "po": ["purchase_order", "purchase_invoice", "purchase_return", "purchase_credit_note", "purchase_debit_note", "gr_ir_write_off"],
    "sales": ["quotation", "sales_order", "sales_invoice", "sales_return", "credit_note", "debit_note"], "mo": ["production_order"],
    "consumption": ["internal_consumption", "other_issue", "scrap", "stock_count", "production_issue"],
    "expense": ["advance_settlement", "general_journal"], "general": ["change_proposal", "bank_receipt", "bank_payment", "cash_receipt",
                                                                     "cash_payment", "outbound_message", "write_off", "period_unlock_request"],
}
EXTRA_MEMBERS = {  # DS-17 rule 18 note and ADR-0055 rule 5 notes
    ("sales", "standard"): ["sales_manager"], ("pr", "standard"): ["purchasing_manager"], ("po", "standard"): ["purchasing_manager"],
    ("general", "standard"): ["sales_manager", "purchasing_manager", "production_planner"], ("mo", "standard"): ["production_planner"],
}


def seed(db):
    set_day("2026-11-01")
    info = {}
    co = W.co = new_id("company")
    W.system_id = new_id("system")
    ins(db, "currency", code="VND", minor_unit=0)
    # cast (DS-17 rule 18 note: user_registered, role_assigned)
    W.users_list = []
    for tpl, login, name in CAST:
        uid = new_id("user_account")
        ins(db, "user_account", id=uid, login=f"{login}@sample-manufacturing.example", display_name=name, email=f"{login}@sample-manufacturing.example",
            language="vi", time_zone="Asia/Ho_Chi_Minh", password_hash="sim-no-login", created_at=now())
        u = {"id": uid, "login": login, "name": name, "template": tpl}
        W.user[tpl] = u
        W.users_list.append(u)
        W.code_of[uid] = name
    ins(db, "company", id=co, code="SMC", legal_name="Sample Manufacturing Co. (sample)", tax_id="0109990002", company_currency="VND",
        time_zone="Asia/Ho_Chi_Minh", localization_package="l10n_vn", accounting_regime="tt99", legal_form="joint_stock",
        valuation_area_level="warehouse", fiscal_calendar_owner_id=W.user["owner"]["id"], default_language="vi")
    db.set_company(co)
    ins(db, "company_currency_activation", currency="VND")
    # settings: regime settings from DS-19 settings.yaml, and the company settings the flows need (sample values)
    regime = read_settings(os.path.join(PKG, "settings.yaml"))
    W.settings = {"documents.issuance_without_delay": regime["documents.issuance_without_delay"],
                  "documents.e_invoice_required": regime["documents.e_invoice_required"],
                  "tax.stated_amount_tolerance": regime["tax.stated_amount_tolerance"]}
    company_settings = {"sales.default_credit_limit": "20000000", "sales.default_payment_term": "SPLIT-15-45",
                        "purchasing.match_quantity_tolerance_percent": "0", "purchasing.match_price_tolerance_percent": "1",
                        "purchasing.match_price_tolerance_amount": "0", "purchasing.receipt_required_for_invoice": True,
                        "partner.default_group.customer": "domestic", "quotation.validity_days": 14}
    for k, v in W.settings.items():
        ins(db, "company_setting", key=k, value=Jsonb(v), source="DS-19 settings.yaml (l10n_vn)")
    for k, v in company_settings.items():
        ins(db, "company_setting", key=k, value=Jsonb(v), source="company setting (sample value, simulation guess)")
    W.settings.update(company_settings)
    # fiscal year and monthly periods (lab stubs), all areas open
    fy = W.fiscal_year = new_id("fiscal_year")
    ins(db, "fiscal_year", id=fy)
    W.periods = {}
    for y, m in [(2026, k) for k in range(1, 13)] + [(2027, k) for k in range(1, 4)]:
        p = new_id("posting_period")
        start = d(f"{y}-{m:02d}-01")
        end = d(f"{y + (m == 12)}-{(m % 12) + 1:02d}-01") - dt.timedelta(days=1)
        ins(db, "posting_period", id=p, fiscal_year_id=fy, kind="regular", start_date=start, end_date=end)
        for area in ("general", "inventory", "receivable", "payable"):
            ins(db, "posting_period_area_state", posting_period_id=p, area=area, state="open")
        W.periods[(y, m)] = (p, fy)

    # ---------------------------------------------------------------- roles (ADR-0054 rule 11; catalogs)
    W.role = {}
    for t in P.TEMPLATES:
        rid = new_id("role")
        ins(db, "role", id=rid, code=t["template"], name=t["name"], template_code=t["template"], basis=B, is_totp_required=t["is_totp_required"] == "true",
            suggested_owner_scope_read=t["suggested_owner_scope_read"], suggested_owner_scope_edit=t["suggested_owner_scope_edit"],
            registry_version="0.1.0", expansion_hash=sha(P.ROLE_LEVELS.get(t["template"], {})))
        W.role[t["template"]] = rid
        for node, (level, appr) in sorted(P.ROLE_LEVELS.get(t["template"], {}).items()):
            ins(db, "role_level", role_id=rid, authorization_area=node, level=level, can_approve=appr)
    for u in W.users_list:
        t = next(x for x in P.TEMPLATES if x["template"] == u["template"])
        ins(db, "role_assignment", id=new_id("role_assignment"), role_id=W.role[u["template"]], principal_kind="user", user_account_id=u["id"],
            owner_scope_read=t["suggested_owner_scope_read"], owner_scope_edit=t["suggested_owner_scope_edit"], valid_from=d("2026-11-01"),
            granted_by_user_id=None if u["template"] == "owner" else W.user["owner"]["id"])
    # employee partners for the cast (salesperson_id, buyer_id and owner_employee_id refer to partners)
    W.pg, W.ptg = new_id("partner_group"), new_id("partner_tax_group")
    for code, name in (("domestic", "Domestic partners"), ("employee", "Employees")):
        gid = W.pg if code == "domestic" else new_id("partner_group")
        ins(db, "partner_group", id=gid, code=code, name=name, basis=B)
    ins(db, "partner_tax_group", id=W.ptg, code="domestic", name="Domestic", directions=["sale", "purchase"], basis=B)
    W.employee = {}
    for u in W.users_list:
        pid = new_id("partner")
        ins(db, "partner", id=pid, code="E-" + u["login"].upper().replace(".", "-"), name=u["name"], partner_kind="individual", country="VN")
        ins(db, "partner_role", partner_id=pid, role="employee")
        ins(db, "employee_profile", partner_id=pid, user_account_id=u["id"], job_title=u["template"].replace("_", " "))
        W.employee[u["template"]] = pid
        W.code_of[pid] = u["name"]
    # segregation rules (ADR-0054 rule 19; catalog) and the assignment-time scan for relation none
    for r in P.SEGREGATION:
        ins(db, "company_segregation_rule", rule_code=r["code"], is_enabled=True, basis=B)
    conflicts = []
    for u in W.users_list:
        for r in P.SEGREGATION:
            if r["document_relation"] != "none":
                continue
            a = [c for c in r["side_a"].split(";") if P.can(u, c)[0]]
            b = [c for c in r["side_b"].split(";") if P.can(u, c)[0]]
            if a and b:
                conflicts.append({"user": u["name"], "template": u["template"], "rule": r["code"], "side_a": a, "side_b": b})
    info["segregation_conflicts_at_assignment"] = conflicts

    # ---------------------------------------------------------------- policy and pools (ADR-0043 rule 15; ADR-0055; DS-17)
    W.proc = {}
    for code, name, rank, role in (("standard", "Standard approval", 10, "accountant"), ("senior", "Senior approval", 20, "chief_accountant")):
        pid = new_id("approval_procedure")
        ins(db, "approval_procedure", id=pid, code=code, name=name, rank=rank, basis={"approver_role": role, **B})
        W.proc[code] = pid
    W.pool, W.stage = {}, {}
    for code, types in POOLS.items():
        pid = new_id("approval_pool")
        ins(db, "approval_pool", id=pid, code=code, name=code.upper() if len(code) <= 3 else code.title(), basis=B)
        W.pool[code] = pid
        for t in types:
            ins(db, "approval_pool_document_type", document_type=t, position=0, approval_pool_id=pid)
        for seq, (sc, rank, k, roles) in enumerate((("standard", 10, 1, ["accountant", "chief_accountant", "owner"]),
                                                    ("senior", 20, 2 if code == "po" else 1, ["chief_accountant", "owner"] + (["purchasing_manager"] if code == "po" else []))), 1):
            sid = new_id("approval_stage")
            ins(db, "approval_stage", id=sid, approval_pool_id=pid, sequence=seq, code=sc, name=sc.title(), min_rank=rank, required_approvals=k)
            W.stage[(code, sc)] = sid
            W.code_of[sid] = f"{code}.{sc}"
            for tpl in roles + EXTRA_MEMBERS.get((code, sc), []):
                ins(db, "approval_stage_member", approval_stage_id=sid, member_kind="role", role_id=W.role[tpl])
    for t in ("cash_payment", "bank_payment", "purchase_invoice"):
        ins(db, "approval_pool_document_type", document_type=t, position=1, condition_input="is_direct_expense", approval_pool_id=W.pool["expense"])
    rules = [("seed_credit_exceeded", "submit", None, "human", {"is_credit_exceeded": True}, "standard", "core seed (ADR-0043 rule 15)"),
             ("seed_match_exceeded_submit", "submit", "purchase_invoice", None, {"is_match_exceeded": True}, "standard", "core seed (ADR-0047 rule 14)"),
             ("seed_match_exceeded_post", "post", "purchase_invoice", None, {"is_match_exceeded": True}, "standard", "core seed (ADR-0047 rule 14)"),
             ("seed_general_journal_submit", "submit", "general_journal", None, {}, "standard", "core seed (ADR-0048 rule 15)"),
             ("seed_cost_unknown", "submit", None, None, {"is_cost_unknown": True}, "standard", "core seed (ADR-0047 rule 22)")]
    rules += [(c, "submit", t, "human", cond, proc, "DS-17 vn_* sample company rule") for c, t, cond, proc in POLICY_SAMPLE]
    for code, action, dtype, akind, cond, proc, src in rules:
        rid = new_id("policy_rule")
        ins(db, "policy_rule", id=rid, code=code)
        ins(db, "policy_rule_version", id=new_id("policy_rule_version"), policy_rule_id=rid, version=1, effective_from=d("2026-01-01"), action=action,
            document_type=dtype, actor_kind=akind, effect="require_approval", approval_procedure_id=W.proc[proc], is_enabled=True,
            shadow_evidence=None, **cond)
    rid = new_id("policy_rule")
    ins(db, "policy_rule", id=rid, code="seed_bank_account_direct_change")
    ins(db, "policy_rule_version", id=new_id("policy_rule_version"), policy_rule_id=rid, version=1, effective_from=d("2026-01-01"),
        action="direct_master_data_change", command_type="CreatePartnerBankAccount", actor_kind="human", effect="deny", is_enabled=True)
    info["policy_rules"] = [r[0] for r in rules] + ["seed_bank_account_direct_change"]

    # ---------------------------------------------------------------- agents (ADR-0050, ADR-0051; decision 12 interim owners)
    W.agent_type_ids = {}
    for code, name in (("customer_onboarding", "Customer onboarding"), ("quotation", "Quotation"), ("bank_matching", "Bank matching"),
                       ("purchase_invoice", "Purchase invoice"), ("planning", "Planning"), ("data_migration", "Data migration")):
        aid = new_id("agent_type")
        ins(db, "agent_type", id=aid, code=code, name=name)
        W.agent_type_ids[code] = aid
        decl = {"version": "1.0.0", "may_read_untrusted": code != "planning", "fuzzy": {"accept": 92, "lead": 8}}
        ins(db, "agent_type_version", id=new_id("agent_type_version"), agent_type_code=code, version="1.0.0", content_hash=sha(decl),
            behavior_hash=sha({"b": decl}), declaration=decl, field_classes=["cost"] if code == "planning" else [])
        if code in WORKFLOW_OWNER:
            ins(db, "agent_type_setting", id=new_id("agent_type_setting"), agent_type_code=code, mode="assisted",
                workflow_owner_id=W.user[WORKFLOW_OWNER[code]]["id"], promoted_version="1.0.0", promoted_seat_models={"all": "gemma-4-31b-it"})
    info["workflow_owners"] = {k: W.user[v]["name"] + f" ({v})" for k, v in WORKFLOW_OWNER.items()}

    # ---------------------------------------------------------------- chart, determination, tax (DS-19 package; catalogs)
    W.acc, sa = {}, {}
    for r in P.read_csv(os.path.join(P.CAT, "system-accounts.csv")):
        sid = new_id("system_account")
        ins(db, "system_account", id=sid, code=r["code"], control_kind=r["control_kind"] or "none")
        sa[r["code"]] = (sid, r["control_kind"])
    n_acc = 0
    for r in P.read_csv(os.path.join(PKG, "regimes", "tt99", "chart_template.csv")):
        if r["is_postable"] != "true" or not r["system_account"]:
            continue
        aid = new_id("account")
        sid, ck = sa[r["system_account"]]
        ins(db, "account", id=aid, code=r["code"], system_account_id=sid, is_postable=True, currency=r["currency"] or None,
            name_en=r["name_en"], name_vi=r["name_vi"])
        W.acc[r["code"]] = {"id": aid, "sa": sid, "sa_code": r["system_account"], "name": r["name_en"], "name_vi": r["name_vi"], "control_kind": ck}
        n_acc += 1
    info["accounts"] = n_acc
    W.tk = {}
    for r in P.read_csv(os.path.join(P.CAT, "transaction-keys.csv")):
        tid = new_id("transaction_key")
        ins(db, "transaction_key", id=tid, code=r["code"])
        W.tk[r["code"]] = tid
    W.det_rows = []
    for r in P.read_csv(os.path.join(PKG, "regimes", "tt99", "account_determination.csv")):
        row = {k: (r[k] or None) for k in ("transaction_key", "valuation_class", "warehouse", "item_group", "partner_group", "tax_code", "currency", "account_code")}
        ins(db, "account_determination", basis=r["basis"], **row)
        W.det_rows.append(row)
    info["determination_rows"] = len(W.det_rows)
    W.tax = {}
    for r in P.read_csv(os.path.join(PKG, "tax", "tax_codes.csv")):
        tid = new_id("tax_code")
        ins(db, "tax_code", id=tid, code=r["code"], tax_kind=r["tax_kind"], direction=r["direction"], transaction_key=r["transaction_key"],
            deductibility=r["deductibility"] or None)
        W.tax[r["code"]] = tid
    for r in P.read_csv(os.path.join(PKG, "tax", "tax_rates.csv")):
        if r["tax_code"] in W.tax:
            ins(db, "tax_rate", id=new_id("tax_rate"), tax_code_id=W.tax[r["tax_code"]], effective_from=d(r["effective_from"]), rate_percent=D(r["rate_percent"]))
    for r in P.read_csv(os.path.join(PKG, "tax", "tax_matrix.csv")):
        ins(db, "tax_matrix", direction=r["direction"], partner_tax_group=r["partner_tax_group"], item_tax_group=r["item_tax_group"],
            effective_from=d(r["effective_from"]), tax_codes=r["tax_codes"].split(";"))
    W.movement = {}
    for r in P.read_csv(os.path.join(P.CAT, "movement-types.csv")):
        mid = new_id("movement_type")
        ins(db, "movement_type", id=mid, code=r["code"], name=r["name"], direction=r["direction"], value_source=r["value_source"],
            costing_role=r["costing_role"], offset_transaction_key=r["offset_transaction_key"] or None, needs_reference=r["needs_reference"] == "true",
            sap_analog=r["sap_analog"] or None, added_in=r["added_in"])
        W.movement[r["code"]] = {"id": mid, "direction": r["direction"]}

    # ---------------------------------------------------------------- organization and groups
    # core units and global conversions from catalogs/units.csv and unit-conversions.csv (ADR-0056 rules 2-3), uuid5 ids
    from . import uom as U
    W.uom, W.uom_dec, W.uom_code = {}, {}, {}
    for r in P.read_csv(os.path.join(P.CAT, "units.csv")):
        u = U.core_id(r["code"])
        ins(db, "uom", id=u, company_id=None, code=r["code"], name=r["name"], quantity_kind=r["quantity_kind"], decimal_places=int(r["decimal_places"]))
        W.uom[r["code"]], W.uom_dec[u], W.uom_code[u], W.code_of[u] = u, int(r["decimal_places"]), r["code"], r["code"]
    for r in P.read_csv(os.path.join(P.CAT, "unit-conversions.csv")):
        ins(db, "uom_conversion", id=U.uuid.uuid5(U.NS, f"uom_conversion:{r['from_code']}:{r['to_code']}"), from_uom_id=W.uom[r["from_code"]],
            to_uom_id=W.uom[r["to_code"]], numerator=int(r["numerator"]), denominator=int(r["denominator"]))
    # company units (code x-..., ADR-0018 rule 8): their size is product data
    for code, name, kind in (("x-box", "hộp (box)", "count"), ("x-carton", "thùng (carton)", "count"), ("x-bag", "bao (bag)", "count")):
        u = new_id("uom")
        ins(db, "uom", id=u, company_id=W.co, code=code, name=name, quantity_kind=kind, decimal_places=0)
        W.uom[code], W.uom_dec[u], W.uom_code[u], W.code_of[u] = u, 0, code, code
    W.uom.update(EA=W.uom["H87"], M=W.uom["MTR"], MM=W.uom["MMT"], BOX=W.uom["x-box"])     # short names used by the flow scripts
    # unit aliases for intake (ADR-0056 rule 19)
    for alias, code in (("Cái", "H87"), ("Chiếc", "H87"), ("m", "MTR"), ("Mét", "MTR"), ("Kg", "KGM"), ("Thùng", "x-carton"), ("Hộp", "x-box"), ("Bao", "x-bag")):
        ins(db, "uom_alias", id=new_id("uom_alias"), alias=alias, normalized_alias=U.normalize_unit_text(alias), uom_id=W.uom[code])
    W.ig, W.vc = {}, {}
    for r in P.read_csv(os.path.join(PKG, "regimes", "tt99", "item_groups.csv")):
        W.ig[r["code"]] = new_id("item_group")
        ins(db, "item_group", id=W.ig[r["code"]], code=r["code"], name=r["name_en"], basis=B)
    for r in P.read_csv(os.path.join(PKG, "regimes", "tt99", "valuation_classes.csv")):
        W.vc[r["code"]] = new_id("valuation_class")
        ins(db, "valuation_class", id=W.vc[r["code"]], code=r["code"], name=r["name_en"], basis=B)
    W.itg = new_id("item_tax_group")
    ins(db, "item_tax_group", id=W.itg, code="standard", name="Standard", basis=B)
    W.cal = new_id("working_calendar")
    ins(db, "working_calendar", id=W.cal, code="MON-FRI", name="Monday to Friday", working_weekdays=[1, 2, 3, 4, 5])
    W.wh = new_id("warehouse")
    zn, bn = new_id("zone"), new_id("bin")
    with db.tx():
        ins(db, "warehouse", id=W.wh, code="WH1", name="Main warehouse (sample)", kind="physical", default_bin_id=bn, working_calendar_id=W.cal)
        ins(db, "zone", id=zn, warehouse_id=W.wh, code="DEFAULT", name="Default")
        ins(db, "bin", id=bn, warehouse_id=W.wh, zone_id=zn, code="DEFAULT", barcode="WH1-DEFAULT", bin_type="storage")
    W.bins = {W.wh: bn}
    W.code_of[W.wh] = "WH1"
    W.terms = {}
    for code, name, lines in (("NET30", "30 days (sample)", [(100, 30)]), ("SPLIT-15-45", "50% in 15 days, 50% in 45 days (sample)", [(50, 15), (50, 45)])):
        t = new_id("payment_term")
        ins(db, "payment_term", id=t, code=code, name=name)
        for n, (p, days) in enumerate(lines, 1):
            ins(db, "payment_term_line", id=new_id("payment_term_line"), payment_term_id=t, line_number=n, amount_percent=D(p), due_days=days,
                due_date_base="document_date")
        W.terms[code] = {"id": t, "lines": [(D(p), days) for p, days in lines]}

    # ---------------------------------------------------------------- products, items, the configurable product
    W.items, W.products, W.prelim = {}, {}, {}
    period_nov = L.period_of(d("2026-11-01"))[0]

    def product(code, name, ig, vc, uom, purchase_uom=None, configurable=False):
        pid = new_id("product")
        ins(db, "product", id=pid, code=code, name=name, product_type="stock", item_group_id=W.ig[ig], valuation_class_id=W.vc[vc],
            inventory_uom_id=W.uom[uom], purchase_uom_id=W.uom[purchase_uom or uom], sales_uom_id=W.uom[uom], item_tax_group_id=W.itg,
            is_item_created_on_order=configurable, is_configurable=configurable)
        W.products[code] = {"id": pid, "name": name, "uom": uom, "vc": vc, "ig": ig}
        W.code_of[pid] = code
        return pid

    def item(code, pid, name, uom, vc, ig, price):
        iid = new_id("item")
        ins(db, "item", id=iid, product_id=pid, code=code)
        W.items[code] = {"id": iid, "product": pid, "name": name, "uom": uom, "vc": vc, "ig": ig, "code": code}
        W.code_of[iid] = code
        if price is not None:
            ins(db, "preliminary_price", id=new_id("preliminary_price"), item_id=iid, valuation_warehouse_id=W.wh, posting_period_id=period_nov,
                unit_price=D(price), price_source="opening")
            W.prelim[iid] = D(price)
        return iid

    for code, name, uom, price, *_ in COMPONENTS:
        pid = product(code, name, "other", "raw_material", uom)
        item(code, pid, name, uom, "raw_material", "other", price)
    pid = product("ABS", "Anchor bolt set (sample)", "merchandise", "merchandise", "EA", purchase_uom="BOX")
    ins(db, "product_uom", id=new_id("product_uom"), product_id=pid, uom_id=W.uom["x-box"], inventory_uom_id=W.uom["H87"], numerator=10, denominator=1,
        factor_source="stated", is_exact=U.is_exact(10, 1, 0, 0))
    item("ABS", pid, "Anchor bolt set (sample)", "EA", "merchandise", "merchandise", 92000)
    unit = W.unit = product("MFU", "Modular Frame Unit (sample)", "product", "finished_goods", "EA", configurable=True)
    W.A, W.V, W.A_code = {}, {}, {}
    for pos, (code, (mode, vt, spec)) in enumerate(CH.items(), 1):
        a = new_id("variant_attribute")
        W.A[code] = a
        W.A_code[a] = code
        if vt == "list":
            ins(db, "variant_attribute", id=a, code=code, name=code.replace("_", " ").title(), variant_mode=mode)
            for k, v in enumerate(spec):
                W.V[(code, v)] = new_id("variant_attribute_value")
                ins(db, "variant_attribute_value", id=W.V[(code, v)], variant_attribute_id=a, variant_mode=mode, code=v, name=v.title(),
                    position=k, is_custom=(code == "label"))
        else:
            lo, hi, st = spec
            ins(db, "variant_attribute", id=a, code=code, name=code.title() + " (mm)", variant_mode=mode, value_type="number",
                uom_id=W.uom["MM"], minimum_value=lo, maximum_value=hi, step_value=st, decimal_places=0)
        ins(db, "product_variant_attribute", product_id=unit, variant_attribute_id=a, position=pos, is_required=False)
    W.model, W.rev = new_id("configuration_model"), new_id("configuration_model_revision")
    ins(db, "configuration_model", id=W.model, product_id=unit, code="MFU", name="Modular Frame Unit model (sample)")
    with db.tx():
        ins(db, "configuration_model_revision", id=W.rev, configuration_model_id=W.model, product_id=unit, revision=1, start_date=d("2026-01-01"))
        for pos, (kind, cd, tg, ef, msg) in enumerate(RULES, 1):
            ins(db, "configuration_rule", id=new_id("configuration_rule"), configuration_model_revision_id=W.rev, product_id=unit, position=pos * 10,
                kind=kind, condition=Jsonb(cd), target_attribute_id=W.A[tg] if tg else None, effect=Jsonb(ef), message_code=msg)
        for code, cols, rows in TABLES:
            tid = new_id("configuration_table")
            ins(db, "configuration_table", id=tid, configuration_model_revision_id=W.rev, product_id=unit, code=code)
            for n, col in enumerate(cols, 1):
                ins(db, "configuration_table_column", configuration_table_id=tid, product_id=unit, column_number=n, variant_attribute_id=W.A[col])
            for n, cells in enumerate(rows, 1):
                ins(db, "configuration_table_row", configuration_table_id=tid, product_id=unit, row_number=n, cells=Jsonb(cells))
        for pos, (tg, v, cd) in enumerate(DEFAULTS, 1):
            ins(db, "configuration_default", configuration_model_revision_id=W.rev, product_id=unit, position=pos, target_attribute_id=W.A[tg],
                value=Jsonb(v), condition=Jsonb(cd))
        db.x("update configuration_model_revision set state='released', content_hash=%s, released_at=%s where id=%s",
             (sha({"rules": RULES, "tables": TABLES, "defaults": DEFAULTS}), now(), W.rev))
    W.MODEL = load_model(db, W.rev)
    # super bill of materials on the product (DS-43 bill_of_materials_component selection and linear sizing; ADR-0046 rule 12)
    W.bom, W.bom_rev = new_id("bill_of_materials"), new_id("bill_of_materials_revision")
    ins(db, "bill_of_materials", id=W.bom, product_id=unit, alternative="1", name="MFU super bill of materials (sample)")
    ins(db, "bill_of_materials_revision", id=W.bom_rev, bill_of_materials_id=W.bom, revision=1, start_date=d("2026-01-01"), base_quantity=1)
    W.COMP = []
    for pos, (code, name, uom, price, cd, sizing, q, qpv, ch, dec) in enumerate(COMPONENTS, 1):
        ins(db, "bill_of_materials_component", id=new_id("bill_of_materials_component"), bill_of_materials_revision_id=W.bom_rev, position=pos,
            component_item_id=W.items[code]["id"], quantity=D(str(q)), uom_id=W.uom[uom], selection_condition=Jsonb(cd), sizing=sizing,
            quantity_per_value=qpv, sizing_attribute_id=W.A[ch] if ch else None)
        W.COMP.append({"item": W.items[code]["id"], "code": code, "condition": cd, "sizing": sizing, "quantity": D(str(q)),
                       "quantity_per_value": qpv, "characteristic": ch, "decimals": dec})
    db.x("update bill_of_materials_revision set state='released', content_hash=%s, released_at=%s where id=%s",
         (sha([c["code"] for c in W.COMP]), now(), W.bom_rev))
    W.pv = new_id("production_version")
    ins(db, "production_version", id=W.pv, product_id=unit, production_warehouse_id=W.wh, code="V1", bill_of_materials_id=W.bom,
        start_date=d("2026-01-01"), production_lead_time_method="fixed", production_lead_time_days=2)
    ins(db, "item_low_level_code", product_id=unit, low_level_code=0)
    for c in W.COMP:
        ins(db, "item_low_level_code", item_id=c["item"], low_level_code=1)
    ins(db, "item_low_level_code", item_id=W.items["ABS"]["id"], low_level_code=0)

    # ---------------------------------------------------------------- partners
    W.partners = {}

    def partner(code, name, tax_id, roles, kind="organization"):
        p = new_id("partner")
        ins(db, "partner", id=p, code=code, name=name, legal_name=name, partner_kind=kind, tax_id=tax_id, country="VN",
            partner_group_id=W.pg, partner_tax_group_id=W.ptg)
        for r in roles:
            ins(db, "partner_role", partner_id=p, role=r)
        ins(db, "partner_search_key", partner_id=p, normalized_name=pure_fold(name), normalized_tax_id=tax_id)
        W.partners[code] = p
        W.code_of[p] = code
        return p
    W.retail = new_id("price_list")
    ins(db, "price_list", id=W.retail, code="RETAIL", name="Retail list (sample)", kind="sale", currency="VND", is_default=True)
    W.code_of[W.retail] = "RETAIL"
    ins(db, "price_list_entry", id=new_id("price_list_entry"), price_list_id=W.retail, item_id=W.items["ABS"]["id"], uom_id=W.uom["EA"],
        minimum_quantity=0, start_date=d("2026-01-01"), unit_price=D(175000))
    old = partner("C-GAMMA-TRD", "Gamma Showroom Trading (sample)", "0109990771", ["customer"])
    ins(db, "customer_profile", partner_id=old, receivable_account_id=W.acc["131"]["id"], payment_term_id=W.terms["NET30"]["id"],
        credit_limit=D(50000000), credit_limit_currency="VND", price_list_id=W.retail, currency="VND")
    W.bank_accounts, W.price_lists = {}, {"RETAIL": W.retail}
    for code, name, tax_id, plcode, bank_code, number in (("S-DELTA", "Delta Metal Supply (sample)", "0109990651", "BUY-DELTA", "SAMPLEBANK-A", "1000200030"),
                                                          ("S-OMEGA", "Omega Fasteners (sample)", "0109990884", "BUY-OMEGA", "SAMPLEBANK-B", "4000500060")):
        pl = new_id("price_list")
        ins(db, "price_list", id=pl, code=plcode, name=f"{name.split(' (')[0]} purchase prices (sample)", kind="purchase", currency="VND")
        W.price_lists[plcode] = pl
        W.code_of[pl] = plcode
        p = partner(code, name, tax_id, ["supplier"])
        ins(db, "supplier_profile", partner_id=p, payable_account_id=W.acc["331"]["id"], payment_term_id=W.terms["NET30"]["id"],
            buyer_id=W.employee["buyer"], price_list_id=pl, currency="VND", working_calendar_id=W.cal)
        ba = new_id("partner_bank_account")
        ins(db, "partner_bank_account", id=ba, partner_id=p, bank_name="Sample Bank (sample)", bank_code=bank_code, account_number=number,
            holder_name=name, currency="VND")
        W.bank_accounts[code] = {"id": ba, "key": (bank_code, number)}

    def pentry(pl, code, price, uom=None, minq=0):
        it = W.items[code]
        ins(db, "price_list_entry", id=new_id("price_list_entry"), price_list_id=W.price_lists[pl], item_id=it["id"], uom_id=W.uom[uom or it["uom"]],
            minimum_quantity=D(minq), start_date=d("2026-01-01"), unit_price=D(price))
    for code, name, uom, price, *_ in COMPONENTS:
        pentry("BUY-DELTA", code, price)
    pentry("BUY-DELTA", "TOP-RAIL", 230000, minq=12)        # a bar-length break
    pentry("BUY-OMEGA", "ABS", 900000, uom="BOX")
    for code in ("FRAME-L", "TOP-RAIL", "COATING-KIT", "SIDE-RAIL"):   # the supplier's own item codes (ADR-0019 rule 6); no PANEL-STEEL code yet
        ins(db, "partner_item", id=new_id("partner_item"), partner_id=W.partners["S-DELTA"], item_id=W.items[code]["id"], partner_item_code="DMS-" + code,
            partner_item_name=W.items[code]["name"].replace(" (sample)", ""), uom_id=W.uom[W.items[code]["uom"]],
            partner_uom_text="bộ" if code == "COATING-KIT" else None)
    # planning data (ADR-0024 rules 1-2; DS-43)
    ins(db, "planning_setting", planning_owner_id=W.user["production_planner"]["id"], planning_horizon_days=56, forecast_consumption_days=7,
        conversion_window_days=7, backtest_weeks=8)
    for code, it in W.items.items():
        ins(db, "item_warehouse_planning", id=new_id("item_warehouse_planning"), item_id=it["id"], warehouse_id=W.wh, planning_method="net_requirements",
            replenishment_source="purchase", safety_stock_quantity=D(SAFETY.get(code, 0)), lot_size_method="fixed" if code == "ABS" else "exact",
            fixed_lot_quantity=D(50) if code == "ABS" else None, receiving_days=1)
        if code == "ABS":
            ins(db, "supplier_item", id=new_id("supplier_item"), supplier_partner_id=W.partners["S-OMEGA"], item_id=it["id"], order_uom_id=W.uom["x-box"],
                supplier_processing_days=2, transit_days=1, minimum_order_quantity=D(1), order_multiple=D(1), is_preferred=True, start_date=d("2026-01-01"))
        else:
            frame = code.startswith("FRAME")
            ins(db, "supplier_item", id=new_id("supplier_item"), supplier_partner_id=W.partners["S-DELTA"], item_id=it["id"], order_uom_id=W.uom[it["uom"]],
                supplier_processing_days=8 if frame else 3, transit_days=2 if frame else 1, minimum_order_quantity=D(5) if code == "COATING-KIT" else D(0),
                order_multiple=D(6) if code == "TOP-RAIL" else None, is_preferred=True, start_date=d("2026-01-01"))
    ins(db, "supplier_item_lead_time", supplier_partner_id=W.partners["S-DELTA"], item_id=W.items["FRAME-L"]["id"], mean_days=D("21.0"),
        standard_deviation_days=D("2.4"), sample_count=10)
    for k, q in enumerate(ABS_HISTORY):
        ws = d("2026-08-10") + dt.timedelta(days=7 * k)
        ins(db, "sales_history", item_id=W.items["ABS"]["id"], warehouse_id=W.wh, iso_week=f"{ws.isocalendar()[0]}-W{ws.isocalendar()[1]:02d}", quantity=D(q))
    W.abs_history = [(d("2026-08-10") + dt.timedelta(days=7 * k), D(q)) for k, q in enumerate(ABS_HISTORY)]
    # CRM: public domains (core list, sample) and the sales mailbox
    for dom in ("mail.example", "freemail.example"):
        ins(db, "public_mail_domain", domain=dom, source="core")
    W.mailbox = new_id("mailbox")
    ins(db, "mailbox", id=W.mailbox, code="SALES", name="Sales inbox (sample)", email_address="sales@sample-manufacturing.example",
        connector_kind="imap", connector_settings={"host": "imap.sample-manufacturing.example"}, credential_ref="vault:sim/none",
        authserv_id="mx.sample-manufacturing.example", is_authentication_verified=True, authentication_probe_result="passed",
        authentication_checked_at=now(), owner_user_id=W.user["sales_clerk"]["id"])
    # money account (ADR-0048 rule 2)
    W.money = new_id("money_account")
    ins(db, "money_account", id=W.money, code="BANK-VND", name="Operating account (sample)", kind="bank", currency="VND", account_id=W.acc["112"]["id"],
        bank_name="Sample Bank (sample)", bank_code="SAMPLEBANK-A", bank_account_number="9990001112")
    seeded = EFF.take()

    # ---------------------------------------------------------------- opening balances (ADR-0044 shape): stock, then bank
    ch = P.person("chief_accountant")
    doc = P.create_doc(db, "opening_balance", ch, number="OB-2026-11-STOCK")
    md = L.material_document(db, doc["id"], d("2026-11-01"))
    lines, total = [], D(0)
    for code, qty in OPENING_STOCK.items():
        if not qty:
            continue
        it = W.items[code]
        value = D(qty) * W.prelim[it["id"]]
        mdl = L.stock_move(db, md, it["id"], W.wh, "opening_balance", D(qty), value)
        lines.append({"acct": L.determine("inventory_posting", valuation_class=it["vc"]), "side": "debit", "amount": value, "item": it["id"],
                      "warehouse": W.wh, "mdl": mdl, "key": "inventory_posting", "desc": f"opening stock {qty} {it['uom']} {code}"})
        total += value
    lines.append({"acct": L.determine("opening_balance"), "side": "credit", "amount": total, "key": "opening_balance", "desc": "opening balance clearing"})
    L.post_entry(db, doc["id"], d("2026-11-01"), lines, description="opening stock (sample)")
    P.set_state(db, doc, "posted")
    doc2 = P.create_doc(db, "opening_balance_entry", ch, number="OB-2026-11-BANK")
    L.post_entry(db, doc2["id"], d("2026-11-01"), [
        {"acct": "112", "side": "debit", "amount": D(500000000), "desc": "opening bank balance"},
        {"acct": L.determine("opening_balance"), "side": "credit", "amount": D(500000000), "key": "opening_balance", "desc": "opening balance clearing"}],
        description="opening bank balance (sample)")
    P.set_state(db, doc2, "posted")
    opening = EFF.take()
    info.update({"seed_rows": seeded.get("rows_written"), "opening_entries": opening.get("journal_entries")})
    return info


def pure_fold(s):
    from .core import fold
    import re
    return re.sub(r"[^a-z0-9 ]", "", fold(s).replace("(sample)", "")).strip()


def load_model(db, rev):
    code_of = W.A_code
    rules = [(k, cd, code_of.get(tg), ef, ms) for k, cd, tg, ef, ms in db.all(
        "select kind, condition, target_attribute_id, effect, message_code from configuration_rule where configuration_model_revision_id=%s order by position", (rev,))]
    tables = []
    for tid, code in db.all("select id, code from configuration_table where configuration_model_revision_id=%s order by code", (rev,)):
        cols = [code_of[r[0]] for r in db.all("select variant_attribute_id from configuration_table_column where configuration_table_id=%s order by column_number", (tid,))]
        rows = [r[0] for r in db.all("select cells from configuration_table_row where configuration_table_id=%s order by row_number", (tid,))]
        tables.append((code, cols, rows))
    defaults = [(code_of[tg], v, cd) for tg, v, cd in db.all(
        "select target_attribute_id, value, condition from configuration_default where configuration_model_revision_id=%s order by position", (rev,))]
    req = {k for k, (m, _, _) in CH.items() if m == "variant"}     # item-defining characteristics are required (ADR-0046 rule 2)
    return pure.Model(CH, rules, tables, defaults, req)


def read_settings(path):
    """The few keys of DS-19 settings.yaml the flows read (no YAML library in the lab venv): '- key:' then 'value:'."""
    out, key = {}, None
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^- key: (\S+)", line)
        if m:
            key = m.group(1)
            continue
        m = re.match(r"^  value: (.*)$", line)
        if m and key:
            v = m.group(1).strip()
            if v.startswith("{"):
                try:
                    v = {k.strip(): _scalar(x.strip()) for k, x in (p.split(":", 1) for p in v.strip("{}").split(","))}
                except ValueError:
                    pass
            else:
                v = _scalar(v)
            out[key] = v
            key = None
    return out


def _scalar(v):
    if v in ("true", "false"):
        return v == "true"
    return v.strip('"')
