"""Scenario: DS-15 access (ADR-0054) and approval pools and stages (ADR-0055), on DS-15-access.sql loaded with DS-20 and DS-06.

Part 0 checks the field counts of every catalog file it reads and the glossary verbs against the verb catalog.
Part A loads the DDL into a clean schema and checks company_id coverage. Part B checks constraints the database holds.
Part C checks the level expansion of ADR-0054 rules 8-11 on the core catalogs. Part D checks owner scope (rules 13-15)
with SQL on real rows. Part E checks segregation of duties (rules 17-21) on every rights path and part F the delegation
window (rule 21). Part H checks invitations, linked and shared users and the credential guards of rules 3-4, the permission holds
of rule 9 and the organization guard of rule 6, on real rows. Part G checks the approval engine of ADR-0055 rules 3-20 as pure functions.
Not covered: the dispatcher, RLS policies, the live-update stream, the upgrade job itself, work item visibility queries.

Environment: NATIVEFLOWS_LAB_DSN (a throwaway database), PGPASSWORD, NATIVEFLOWS_DOCS (a docs directory with DS-15-access.sql
and the catalogs in place). Loading needs the lab loader and stubs of that docs directory.
"""
import csv, hashlib, io, os, random, re, subprocess, sys, tempfile
from datetime import date, datetime, timedelta, timezone
from lab import RESULTS, conn, expect, new

DOCS = os.environ.get("NATIVEFLOWS_DOCS", os.path.expanduser("~/Projects/NativeFlows/docs"))
LAB = os.path.join(DOCS, "reviews/2026-11-14-design-validation/lab")
CAT = os.path.join(DOCS, "catalogs")


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail else ""))


def read_csv(name):
    with open(os.path.join(CAT, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 0: catalog files and verbs
FILES = ("authorization-areas.csv", "authorization-verb-levels.csv", "role-templates.csv", "role-template-levels.csv",
         "segregation-rules.csv", "invariants.csv", "edge-cases.csv", "work-item-kinds.csv")
bad = []
for name in FILES:
    with open(os.path.join(CAT, name), encoding="utf-8", newline="") as f:
        rows_ = list(csv.reader(f))
    bad += [f"{name}:{i + 1}" for i, row in enumerate(rows_) if row and len(row) != len(rows_[0])]
check(f"01 every row of the {len(FILES)} catalog files the lab reads has its header's field count", bad == [], bad[:5] or "")
inv_codes = {r["code"] for r in read_csv("invariants.csv")}
ec_codes = {r["code"] for r in read_csv("edge-cases.csv")}
ec_gap = [r for r in read_csv("edge-cases.csv") if r["code"] in {f"EC-{n}" for n in range(97, 110)}]
check("02 the access invariants INV-220 to INV-231 and edge cases EC-110 to EC-118 are in the catalogs; INV-217 to INV-219 stay unused (INV-216 is ADR-0050's), and no edge case EC-97 to EC-109 is ADR-0054's or ADR-0055's",
      {f"INV-{n}" for n in range(220, 232)} <= inv_codes and {f"EC-{n}" for n in range(110, 119)} <= ec_codes
      and "INV-216" in inv_codes and not ({f"INV-{n}" for n in range(217, 220)} & inv_codes) and not any("ADR-0054" in r["source"] or "ADR-0055" in r["source"] for r in ec_gap),
      [r["code"] for r in ec_gap])
kinds = {r["code"]: r for r in read_csv("work-item-kinds.csv")}
check("03 no owner rule role:sales is left; approval_pending uses approval_stage and stage_due_days",
      not any(r["owner_rule"] == "role:sales" for r in kinds.values())
      and (kinds["approval_pending"]["owner_rule"], kinds["approval_pending"]["due_rule"]) == ("approval_stage", "stage_due_days"))
guide = open(os.path.join(DOCS, "spec/00-reading-guide.md"), encoding="utf-8").read()
vt = guide.split("| Verb | Intent | Event form |", 1)[1].split("\n\n", 1)[0]
GLOSSARY_VERBS = {v.strip() for line in vt.splitlines()[2:] if line.startswith("| ") for v in line.split("|")[1].split(",")}
CATALOG_VERBS = {r["verb"] for r in read_csv("authorization-verb-levels.csv")}
check("04 every glossary verb has a level in the verb catalog, and every catalog command verb is in the glossary (Send, File, Render, Set included)",
      GLOSSARY_VERBS <= CATALOG_VERBS and CATALOG_VERBS - {"Get", "List"} <= GLOSSARY_VERBS and {"Send", "File", "Render", "Set"} <= GLOSSARY_VERBS,
      sorted(GLOSSARY_VERBS ^ (CATALOG_VERBS - {"Get", "List"})))

# ---------------------------------------------------------------- A: load
stubs = open(os.path.join(LAB, "00_stubs.sql"), encoding="utf-8").read()
stub_line = "CREATE TABLE user_account (id uuid PRIMARY KEY);\n"
assert stubs.count(stub_line) == 1
stubs = stubs.replace(stub_line, "")                       # DS-15 defines user_account in full
ddl15 = open(os.path.join(DOCS, "design/DS-15-access.sql"), encoding="utf-8").read()
src = "".join(open(os.path.join(DOCS, "design", f), encoding="utf-8").read() + "\n"
              for f in ("DS-20-master-data.sql", "DS-06-universal-journal.sql")) + ddl15
with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as tf:
    tf.write(src)
p = subprocess.run([sys.executable, os.path.join(LAB, "load_ds06.py"), tf.name], capture_output=True, text=True)
os.unlink(tf.name)
check("A1 loader orders DS-20, DS-06 and DS-15 together", p.returncode == 0, p.stderr.splitlines()[0] if p.stderr else "")
c = conn(); c.autocommit = True
c.execute(stubs)
c.execute(p.stdout)
X = c.execute
tables15 = re.findall(r"CREATE TABLE (\w+)", ddl15)
installation = {"user_account", "user_session", "credential_reset", "integration_client", "integration_token", "installation_role_assignment"}
missing = [t for t in tables15 if t not in installation and not X(
    "select 1 from information_schema.columns where table_schema='nativeflows' and table_name=%s and column_name='company_id'", (t,)).fetchone()]
check(f"A2 all {len(tables15) - len(installation)} company tables of DS-15 carry company_id", missing == [], missing or "")
inst_with = [t for t in installation if X(
    "select 1 from information_schema.columns where table_schema='nativeflows' and table_name=%s and column_name='company_id'", (t,)).fetchone()]
check("A3 the six installation tables carry no company_id", inst_with == [], inst_with or "")

# ---------------------------------------------------------------- fixtures
I = {k: new() for k in ["co", "co2", "op", "uA", "uB", "uC", "uM", "uE", "uS", "b1", "b2", "b1x", "wh", "role", "role2",
                        "dSales", "dNorth", "dOther", "dX", "eA", "eB", "eC", "eM", "eE", "eX", "team", "pool", "pool2",
                        "stage", "per"]}
t = str(I["co"])[-8:]
X("insert into currency (code, minor_unit) values ('VND',0) on conflict do nothing")
for k in ("op", "uA", "uB", "uC", "uM", "uE", "uS"):
    X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,%s,'en','x',now())",
      (I[k], (k + t).lower(), k))
for k, code in (("co", "C12-"), ("co2", "C12B-")):
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','warehouse',%s,'vi')", (I[k], code + t, I["op"]))
X("insert into branch (id, company_id, code, name) values (%s,%s,'B1','B1'),(%s,%s,'B2','B2'),(%s,%s,'BX','BX')",
  (I["b1"], I["co"], I["b2"], I["co"], I["b1x"], I["co2"]))
for k in ("eA", "eB", "eC", "eM", "eE"):
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,%s,'individual','VN')", (I[k], I["co"], k + t, k))
X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,'X','individual','VN')", (I["eX"], I["co2"], "eX" + t))
X("insert into department (id, company_id, code, name, manager_partner_id) values (%s,%s,'SALES','Sales',%s)", (I["dSales"], I["co"], I["eM"]))
X("insert into department (id, company_id, code, name, parent_id) values (%s,%s,'NORTH','North',%s)", (I["dNorth"], I["co"], I["dSales"]))
X("insert into department (id, company_id, code, name) values (%s,%s,'OTHER','Other')", (I["dOther"], I["co"]))
X("insert into department (id, company_id, code, name) values (%s,%s,'X','X')", (I["dX"], I["co2"]))
# employees: M manages Sales; A in Sales reports to M; B in North; C in Other; E in Other reports to A
for e, u, d, mgr in (("eM", "uM", "dSales", None), ("eA", "uA", "dSales", "eM"), ("eB", "uB", "dNorth", None),
                     ("eC", "uC", "dOther", None), ("eE", "uE", "dOther", "eA")):
    X("insert into employee_profile (company_id, partner_id, user_account_id, department_id, manager_partner_id) values (%s,%s,%s,%s,%s)",
      (I["co"], I[e], I[u], I[d], I[mgr] if mgr else None))
X("insert into team (id, company_id, code, name) values (%s,%s,'T','T')", (I["team"], I["co"]))
X("insert into team_member values (%s,%s,%s),(%s,%s,%s)", (I["co"], I["team"], I["eA"], I["co"], I["team"], I["eC"]))
X("""insert into role (id, company_id, code, name, basis, registry_version, expansion_hash) values (%s,%s,'r','R','{"kind":"company_decision"}','lab','x'),
     (%s,%s,'r2','R2','{"kind":"company_decision"}','lab','x')""", (I["role"], I["co"], I["role2"], I["co2"]))

# ---------------------------------------------------------------- B: constraints the database holds
def ra(cx, scope_r="own", scope_e="own", kind="user", user="uA", granted="op", vfrom="2026-01-01", vto=None, co="co", role="role", inv=None):
    rid = new()
    cx.execute("""insert into role_assignment (id, company_id, role_id, principal_kind, user_account_id, owner_scope_read, owner_scope_edit,
                  valid_from, valid_to, granted_by_user_id, user_invitation_id) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
               (rid, I[co], I[role], kind, I[user] if user else None, scope_r, scope_e, vfrom, vto, I[granted] if granted else None, inv))
    return rid
expect("B1 assignment own read with company edit (edit wider than read)", lambda cx: ra(cx, "own", "company"), True, "ck_role_assignment_owner_scope_pair")
expect("B2 assignment team read with department edit", lambda cx: ra(cx, "team", "department"), True, "ck_role_assignment_owner_scope_pair")
expect("B3 assignment department read with own edit", lambda cx: ra(cx, "department", "own"), False)
expect("B4 an assignment to an agent type (agent types get no assignments, ADR-0054 rule 16)", lambda cx: ra(cx, None, None, kind="agent_type", user=None), True, "ck_role_assignment_principal_kind")
check("B4b role_assignment has no agent_type column", not X("select 1 from information_schema.columns where table_schema='nativeflows' and table_name='role_assignment' and column_name='agent_type'").fetchone())
expect("B5 user assignment without owner scope", lambda cx: ra(cx, None, None), True, "ck_role_assignment_owner_scope")
expect("B6 assignment granted to oneself", lambda cx: ra(cx, granted="uA"), True, "ck_role_assignment_not_self")
expect("B7 assignment ending before it starts", lambda cx: ra(cx, vfrom="2026-02-01", vto="2026-01-31"), True, "ck_role_assignment_dates")
expect("B8 assignment of another company's role", lambda cx: ra(cx, role="role2"), True, "foreign key")
expect("B9 role level that approves at level none",
       lambda cx: cx.execute("insert into role_level values (%s,%s,'sales','none',true)", (I["co"], I["role"])), True, "ck_role_level_approve")
expect("B10 record scope row naming both a branch and a warehouse",
       lambda cx: (ra(cx), cx.execute("""insert into role_assignment_scope select company_id, id, %s, %s from role_assignment where user_account_id=%s limit 1""",
                                      (I["b1"], new(), I["uA"]))), True, "ck_role_assignment_scope_one")
expect("B11 record scope on another company's branch",
       lambda cx: (ra(cx), cx.execute("""insert into role_assignment_scope (company_id, role_assignment_id, branch_id) select company_id, id, %s from role_assignment where user_account_id=%s limit 1""",
                                      (I["b1x"], I["uA"]))), True, "foreign key")
def deleg(cx, a="uA", b="uB", s="2026-03-01", e="2026-03-10"):
    cx.execute("""insert into delegation (id, company_id, delegator_user_id, substitute_user_id, kind, start_date, end_date, reason, created_by_user_id)
                  values (%s,%s,%s,%s,'approval',%s,%s,'leave',%s)""", (new(), I["co"], I[a], I[b] if b in I else b, s, e, I[a]))
expect("B12 delegation to oneself", lambda cx: deleg(cx, b="uA"), True, "ck_delegation_not_self")
expect("B13 delegation ending before it starts", lambda cx: deleg(cx, s="2026-03-10", e="2026-03-01"), True, "ck_delegation_dates")
expect("B14 delegation longer than 366 days", lambda cx: deleg(cx, s="2026-01-01", e="2027-01-02"), True, "ck_delegation_dates")
expect("B15 delegation to something that is not a user account (an agent)", lambda cx: deleg(cx, b=new()), True, "foreign key")
expect("B16 department with another company's parent",
       lambda cx: cx.execute("insert into department (id, company_id, code, name, parent_id) values (%s,%s,'Z','Z',%s)", (new(), I["co"], I["dX"])), True, "foreign key")
expect("B17 employee in another company's department",
       lambda cx: cx.execute("update employee_profile set department_id=%s where partner_id=%s", (I["dX"], I["eB"])), True, "fk_employee_profile_department")
expect("B18 employee who manages themselves",
       lambda cx: cx.execute("update employee_profile set manager_partner_id=partner_id where partner_id=%s", (I["eB"],)), True, "ck_employee_profile_manager")
expect("B19 login with capitals",
       lambda cx: cx.execute("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,'Abc'||%s,'x','en','x',now())", (new(), t)), True, "ck_user_account_login")
expect("B20 integration token valid for more than a year",
       lambda cx: (cx.execute("insert into integration_client (id, code, name, accountable_user_id) values (%s,%s,'I',%s)", (I["pool2"], "ic" + t, I["op"])),
                   cx.execute("insert into integration_token (id, integration_client_id, token_hash, created_at, expires_at) values (%s,%s,'\\x01',now(),now()+interval '13 months')", (new(), I["pool2"]))),
       True, "ck_integration_token_expiry")
X("insert into approval_pool (id, company_id, code, name, basis) values (%s,%s,'po','PO','{}')", (I["pool"], I["co"]))
expect("B21 a second default selector row for one document type",
       lambda cx: cx.execute("insert into approval_pool_document_type values (%s,'purchase_order',0,null,%s),(%s,'purchase_order',0,null,%s)", (I["co"], I["pool"], I["co"], I["pool"])), True, "duplicate key")
expect("B22 a default selector row with a condition",
       lambda cx: cx.execute("insert into approval_pool_document_type values (%s,'purchase_order',0,'is_direct_expense',%s)", (I["co"], I["pool"])), True, "ck_approval_pool_document_type_default")
expect("B23 a stage needing zero approvals",
       lambda cx: cx.execute("insert into approval_stage (id, company_id, approval_pool_id, sequence, code, name, min_rank, required_approvals) values (%s,%s,%s,1,'s','S',10,0)", (new(), I["co"], I["pool"])), True, "ck_approval_stage_required_approvals")
expect("B24 two stages with one sequence",
       lambda cx: cx.execute("insert into approval_stage (id, company_id, approval_pool_id, sequence, code, name, min_rank, required_approvals) values (%s,%s,%s,1,'a','A',10,1),(%s,%s,%s,1,'b','B',20,1)",
                             (new(), I["co"], I["pool"], new(), I["co"], I["pool"])), True, "duplicate key")
expect("B25 a stage member that names both a user and a role",
       lambda cx: (cx.execute("insert into approval_stage (id, company_id, approval_pool_id, sequence, code, name, min_rank, required_approvals) values (%s,%s,%s,1,'a','A',10,1)", (I["stage"], I["co"], I["pool"])),
                   cx.execute("insert into approval_stage_member values (%s,%s,'user',%s,%s)", (I["co"], I["stage"], I["uA"], I["role"]))), True, "ck_approval_stage_member_target")

# ---------------------------------------------------------------- C: levels and their expansion
AREAS = read_csv("authorization-areas.csv")
PARENT = {r["code"]: r["parent_code"] or None for r in AREAS}
KIND = {r["code"]: r["kind"] for r in AREAS}
VERB = {r["verb"]: r["level"] for r in read_csv("authorization-verb-levels.csv")}
ORDER = {"none": 0, "read": 1, "edit": 2, "post": 3, "full": 4}
EFFECT = {"posting": "post", "outbound_send": "post", "master_data_change": "edit", "other": "none"}
check("C1 the area tree has twelve roots (crm included; quality from ADR-0070) and every parent exists",
      sorted(k for k, v in PARENT.items() if v is None) == sorted(["sales", "purchasing", "inventory", "production", "planning", "finance", "banking", "master_data", "crm", "administration", "reports", "quality"])
      and all(v is None or v in PARENT for v in PARENT.values()))

def camel(s): return "".join(w.capitalize() for w in s.split("_"))
# A sample registry: each document type's generated commands (ADR-0009 rule 2) plus functions and capabilities.
POSTING = {"sales_invoice", "sales_return", "credit_note", "debit_note", "purchase_invoice", "purchase_return", "goods_receipt",
           "delivery", "scrap", "general_journal", "cash_payment", "bank_payment", "cash_receipt", "production_issue", "stock_count"}
REVERSIBLE = {"purchase_invoice", "goods_receipt", "general_journal", "cash_payment", "bank_payment", "production_issue", "scrap"}
REG = []                                                   # (permission, leaf, kind, verb, effect)
for code, kind in KIND.items():
    if kind != "document_type":
        continue
    n = camel(code)
    REG += [(f"Get{n}", code, "query", "Get", None), (f"List{n}", code, "query", "List", None)]
    for v in ("Create", "Update", "Delete", "Submit", "Cancel"):
        REG.append((f"{v}{n}", code, "command", v, "other"))
    REG += [(f"Approve{n}", code, "command", "Approve", "other"), (f"Reject{n}", code, "command", "Reject", "other")]
    if code in POSTING:
        REG.append((f"Post{n}", code, "command", "Post", "posting"))
        if code in REVERSIBLE:
            REG.append((f"Reverse{n}", code, "command", "Reverse", "posting"))
    else:
        REG.append((f"Close{n}", code, "command", "Close", "other"))
REG += [("CreatePartner", "partner", "command", "Create", "master_data_change"), ("UpdatePartner", "partner", "command", "Update", "master_data_change"),
        ("CreatePartnerBankAccount", "partner_bank_account", "command", "Create", "master_data_change"),
        ("UpdatePartnerBankAccount", "partner_bank_account", "command", "Update", "master_data_change"),
        ("CreatePriceList", "price_list", "command", "Create", "master_data_change"), ("UpdatePriceList", "price_list", "command", "Update", "master_data_change"),
        ("SetPriceListEntries", "price_list", "command", "Set", "master_data_change"), ("SetPriceListOptionExtras", "price_list", "command", "Set", "master_data_change"),
        ("RestrictPostingPeriod", "posting_period", "command", "Restrict", "other"), ("LockPostingPeriod", "posting_period", "command", "Lock", "other"),
        ("ListPostingPeriod", "posting_period", "query", "List", None), ("CreateExchangeRate", "exchange_rate", "command", "Create", "master_data_change"),
        ("CreateRole", "role", "command", "Create", "master_data_change"), ("UpdateRole", "role", "command", "Update", "master_data_change"),
        ("CreateRoleAssignment", "role", "command", "Create", "master_data_change"), ("UpdateRoleAssignment", "role", "command", "Update", "master_data_change"),
        ("RunDunning", "dunning", "command", "Run", "other"), ("CreateDunningMessage", "dunning", "command", "Create", "outbound_send"),
        ("ListAllowedCommand", "general_access", "query", "List", None), ("ListWorkItem", "work_queue", "query", "List", None),
        ("ClaimWorkItem", "work_queue", "command", "Claim", "other"), ("AssignWorkItem", "work_queue_administration", "command", "Assign", "other"),
        ("post_in_soft_locked_period", "posting_period", "capability", None, "full"), ("list_all_work_items", "work_queue_administration", "capability", None, "full"),
        # ADR-0054 rules 6, 8, 11, 21, 24 and the verbs Send, File, Render
        ("UpdateEmployeeOrganization", "organization", "command", "Update", "master_data_change", "full"),
        ("UpdateDepartment", "organization", "command", "Update", "master_data_change", "full"),
        ("CreateBranch", "organization", "command", "Create", "master_data_change"),
        ("AcceptMigrationDifference", "opening_balance_entry", "command", "Accept", "other", "full"),
        ("read_agent_run_bodies", "agent_run_bodies", "capability", None, "full"),
        ("CreateDelegation", "delegation", "command", "Create", "master_data_change"), ("CancelDelegation", "delegation", "command", "Cancel", "master_data_change"),
        ("delegate_for_others", "delegation", "capability", None, "full"),
        ("ValidateImportBatch", "data_import", "command", "Validate", "other"),
        ("SendDunningReminder", "dunning", "command", "Send", "outbound_send"),
        ("RenderReport", "report_finance", "command", "Render", "other"), ("FileStatutoryReport", "report_finance", "command", "File", "other"),
        ("FileTaxReturn", "report_tax", "command", "File", "other")]
# CRM (ADR-0052 rule 32) beyond the generated commands of outbound_message and data_subject_request: leaf, verb, effect,
# declared minimum. Commands only a system job or worker runs declare full (ADR-0054 rule 8).
CRM = {"CreateMailbox": ("mailbox", "master_data_change"), "UpdateMailbox": ("mailbox", "master_data_change"),
       "VerifyMailboxAuthentication": ("mailbox", "other"), "RecordMailboxAuthenticationCheck": ("mailbox", "other", "full"),
       "RunMailboxIntake": ("mailbox", "other", "full"), "RecordInboundMessage": ("mailbox", "other", "full"),
       "RecordMailboxIntakeOutcome": ("mailbox", "other", "full"),
       "CreateInteraction": ("interaction", "other"), "MatchInteraction": ("interaction", "other"), "UnmatchInteraction": ("interaction", "other"),
       "CreateInteractionLink": ("interaction", "other"), "DeleteInteractionLink": ("interaction", "other"),
       "CreatePartnerEmailDomain": ("interaction", "master_data_change"), "UpdatePartnerEmailDomain": ("interaction", "master_data_change"),
       "CreateProcessingPurpose": ("data_protection", "master_data_change"), "UpdateProcessingPurpose": ("data_protection", "master_data_change"),
       "CreateComplaint": ("complaint", "other"), "UpdateComplaint": ("complaint", "other"), "CloseComplaint": ("complaint", "other"),
       "ReopenComplaint": ("complaint", "other"), "CreateProcessingBasis": ("data_protection", "other"), "CloseProcessingBasis": ("data_protection", "other"),
       "ReopenOutboundMessage": ("outbound_message", "other"), "SendOutboundMessage": ("outbound_message", "outbound_send"),
       "RecordOutboundMessageOutcome": ("outbound_message", "other", "full"), "EraseDataSubject": ("data_protection", "other"),
       "CreateInteractionSummary": ("interaction", "other"), "UpdateInteractionSummary": ("interaction", "other"), "DeleteInteractionSummary": ("interaction", "other"),
       "UpdatePartnerInsight": ("partner_insight", "other"), "DeletePartnerInsight": ("partner_insight", "other"),
       "RunPartnerDuplicateScan": ("partner_insight", "other", "full"), "RunPartnerInsightComputation": ("partner_insight", "other", "full"),
       "RecordPartnerTaxLookup": ("partner_insight", "other", "full")}
CRM_QUERIES = {"ListPartnerTimeline": "interaction", "ListInteraction": "interaction", "GetInteraction": "interaction", "ListInboundMessage": "interaction",
               "ListComplaint": "complaint", "GetComplaint": "complaint", "ListProcessingBasis": "data_protection",
               "ListPartnerDuplicateCandidate": "partner_insight", "ListMailbox": "mailbox", "GetOutboundContentCheck": "outbound_message"}
VERBS_BY_LENGTH = sorted(VERB, key=len, reverse=True)
def verb_of(name):
    return next((v for v in VERBS_BY_LENGTH if name.startswith(v) and name[len(v):len(v) + 1].isupper()), re.match(r"[A-Z][a-z]+", name).group(0))
for n, spec in CRM.items():
    REG.append((n, spec[0], "command", verb_of(n), spec[1]) + tuple(spec[2:]))
for n, leaf in CRM_QUERIES.items():
    REG.append((n, leaf, "query", verb_of(n), None))
# Reporting and printing (ADR-0049; ADR-0054 rule 24). RenderReport, FileStatutoryReport and FileTaxReturn are above.
REPORTING = {"RenderPrint": ("general_access", "other"), "RenderTaxReturn": ("report_tax", "other"), "RunTaxReturnOffset": ("report_tax", "posting"),
             "CreateReportDefinition": ("report_finance", "master_data_change"), "UpdateReportDefinition": ("report_finance", "master_data_change"),
             "CreateReportComparativeValue": ("report_finance", "other"), "UpdateReportComparativeValue": ("report_finance", "other"),
             "DeleteReportComparativeValue": ("report_finance", "other"),
             "CreatePrintTemplate": ("print_template", "master_data_change"), "UpdatePrintTemplate": ("print_template", "master_data_change"),
             "RecordRenderOutcome": ("print_template", "other", "full"),
             "CreatePrintProfile": ("print_profile", "master_data_change"), "UpdatePrintProfile": ("print_profile", "master_data_change")}
REPORTING_QUERIES = {"GetStatutoryReport": "report_finance", "ListBookRow": "report_finance", "ListReportLineContribution": "report_finance",
                     "ListReportDefinition": "report_finance", "GetReportDefinition": "report_finance", "ListStatutoryReportFiling": "report_finance",
                     "GetStatutoryReportFiling": "report_finance", "ListReportComparativeValue": "report_finance",
                     "GetRenderJob": "general_access", "ListRenderJob": "general_access",
                     "GetPrintDataContract": "print_template", "GetPrintData": "general_access"}
for n, spec in REPORTING.items():
    REG.append((n, spec[0], "command", verb_of(n), spec[1]) + tuple(spec[2:]))
for n, leaf in REPORTING_QUERIES.items():
    REG.append((n, leaf, "query", verb_of(n), None))
# Barcodes (ADR-0061 rule 10): leaf, effect and declared minimum; the human_only commands among them.
BARCODES = {"CreateItemBarcode": ("product", "master_data_change"), "UpdateItemBarcode": ("product", "master_data_change"),
            "DeleteItemBarcode": ("product", "master_data_change"), "CreateBarcodeReservation": ("product", "master_data_change"),
            "DeleteBarcodeReservation": ("product", "master_data_change", "full"), "CreateGs1CompanyPrefix": ("product", "master_data_change"),
            "UpdateGs1CompanyPrefix": ("product", "master_data_change"), "DeleteGs1CompanyPrefix": ("product", "master_data_change"),
            "SetLotBarcode": ("warehouse", "master_data_change"), "SetSerialNumberBarcode": ("warehouse", "master_data_change"),
            "RunRetiredSsccCleanup": ("product", "other")}
BARCODE_HUMAN_ONLY = {"DeleteBarcodeReservation"}
BARCODE_QUERIES = {"EvaluateBarcode": "general_access", "ListItemLabel": "product", "ListLotLabel": "warehouse", "ListSerialLabel": "warehouse"}
for n, spec in BARCODES.items():
    REG.append((n, spec[0], "command", verb_of(n), spec[1]) + tuple(spec[2:]))
for n, leaf in BARCODE_QUERIES.items():
    REG.append((n, leaf, "query", verb_of(n), None))
# Agent and platform commands of ADR-0054 rule 24's table note (holistic platform review).
AGENT_TYPES = ("customer_onboarding", "quotation", "bank_matching", "purchase_invoice", "planning", "data_migration", "analysis")   # analysis: ADR-0060
REG += [(f"start_agent:{a}", f"agent_{a}", "capability", None, "edit") for a in AGENT_TYPES]
# Agent-assisted analysis (ADR-0060 rules 14, 21, 26, 28, 36).
ANALYSIS = {"CreateAnalysisQuestion": ("analysis_question", "other"), "UpdateAnalysisFeedback": ("analysis_question", "other"),
            "UpdateAnalysisAnswer": ("analysis_question", "other"), "CreateSavedAnalysis": ("general_access", "master_data_change"),
            "UpdateSavedAnalysis": ("general_access", "master_data_change"), "CreateAnalysisExample": ("saved_analysis", "master_data_change"),
            "UpdateAnalysisExample": ("saved_analysis", "master_data_change"), "ReleaseSavedAnalysis": ("saved_analysis", "master_data_change"),
            "ReleaseAnalysisExample": ("saved_analysis", "master_data_change")}
ANALYSIS_QUERIES = {"EvaluateAnalysisPlan": "general_access", "GetAnalysisPlanExplanation": "general_access", "ListAnalysisCatalog": "general_access",
                    "ListAnalysisDimensionMember": "general_access", "ListAnalysisCellRow": "general_access", "ListAnalysisResultRow": "general_access",
                    "ListSavedAnalysis": "general_access", "GetSavedAnalysis": "general_access", "ListAnalysisExample": "saved_analysis",
                    "ListAnalysisQuestion": "analysis_question", "GetAnalysisQuestion": "analysis_question"}
for n, spec in ANALYSIS.items():
    REG.append((n, spec[0], "command", verb_of(n), spec[1]))
for n, leaf in ANALYSIS_QUERIES.items():
    REG.append((n, leaf, "query", verb_of(n), None))
REG += [("read_analysis_debug", "analysis_debug", "capability", None, "full"), ("share_saved_analysis", "saved_analysis", "capability", None, "edit")]
# The lead-time update of ADR-0024 rule 23 (simulation review 2026-11-15).
REG += [("CreateSupplierItem", "supplier_item", "command", "Create", "master_data_change"),
        ("UpdateSupplierItem", "supplier_item", "command", "Update", "master_data_change")]
# Unit maintenance off the owner (ADR-0056 rule 20 note; UoM simulation review 2026-11-15).
UNIT_CMDS, ALIAS_CMDS = ("CreateProductUom", "UpdateProductUom", "CreateUom", "UpdateUom"), ("CreateUomAlias", "UpdateUomAlias")
REG += [(n, "product_unit", "command", verb_of(n), "master_data_change") for n in UNIT_CMDS]
REG += [(n, "uom_alias", "command", verb_of(n), "master_data_change") for n in ALIAS_CMDS]
REG += [("cancel_agent_runs", "agent", "capability", None, "full"),
        ("UpdateAgentTypeSetting", "agent", "command", "Update", "master_data_change", "full"),
        ("CreateAgentPromotionEvidence", "agent", "command", "Create", "other"), ("ListAgentRun", "agent", "query", "List", None),
        ("CompleteAgentRun", "agent", "command", "Complete", "other"), ("RunAgentQualityCheck", "agent", "command", "Run", "other"),
        ("ClearTaint", "policy", "command", "Clear", "other"), ("ConfirmAutoPost", "policy", "command", "Confirm", "other"),
        ("ListPolicyDecision", "policy", "query", "List", None), ("RunApprovalEscalation", "policy", "command", "Run", "other"),
        ("GetApprovalProgress", "general_access", "query", "Get", None), ("CreateAttachment", "general_access", "command", "Create", "other"),
        ("CreateListExport", "general_access", "command", "Create", "other"),
        ("RetryEventDelivery", "event_delivery", "command", "Retry", "other"), ("SkipEventDelivery", "event_delivery", "command", "Skip", "other"),
        ("ReplayEvents", "event_delivery", "command", "Replay", "other"),
        ("RecordSalesInvoiceEInvoiceOutcome", "sales_invoice", "command", "Record", "other"),
        ("RunAutomationOwnerScopeCheck", "automation", "command", "Run", "other")]   # ADR-0058 rule 9: a daily system job
# Configurable policy settings (ADR-0063 rule 28).
REG += [("UpdateCompanySetting", "company_setting", "command", "Update", "master_data_change"),
        ("RunSettingUpgradeCheck", "company_setting", "command", "Run", "other"),
        ("RunDataProcessingProviderCheck", "data_processing", "command", "Run", "other"),
        ("SetDataProcessingPermission", "data_processing", "command", "Set", "master_data_change", "full"),
        ("EndDataProcessingPermission", "data_processing", "command", "End", "master_data_change", "full"),
        ("ListSettingDefinition", "company_setting", "query", "List", None), ("ListSettingValue", "company_setting", "query", "List", None),
        ("EvaluateSetting", "company_setting", "query", "Evaluate", None), ("ListItemCandidate", "product", "query", "List", None),
        ("GetArtifactVersionContent", "configuration", "query", "Get", None)]
# Commands registered is_internal_only (ADR-0008 rule 1 note; ADR-0054 rule 8 note): outside the level expansion.
INTERNAL = {"RunRetiredSsccCleanup", "CompleteAgentRun", "RunAgentQualityCheck", "RunApprovalEscalation", "RecordSalesInvoiceEInvoiceOutcome",
            "RecordInboundMessage", "RecordMailboxIntakeOutcome", "RecordMailboxAuthenticationCheck", "RecordOutboundMessageOutcome",
            "RecordPartnerTaxLookup", "RecordRenderOutcome", "RunPartnerDuplicateScan", "RunPartnerInsightComputation", "RunAutomationOwnerScopeCheck",
            "RunSettingUpgradeCheck", "RunDataProcessingProviderCheck"}

def need(entry):
    perm, leaf, kind, verb, effect = entry[:5]
    declared = entry[5] if len(entry) > 5 else "none"      # a command's declared minimum level (ADR-0054 rule 8)
    if kind == "query":
        return "read"
    if kind == "capability":
        return effect
    if verb not in VERB:
        raise KeyError(f"verb {verb} has no level")
    if VERB[verb] == "approve":
        return "approve"
    return max(VERB[verb], EFFECT[effect], declared, key=ORDER.get)

def effective(rows, leaf):
    node = leaf
    while node is not None:
        if node in rows:
            return rows[node]
        node = PARENT[node]
    return ("none", False)

def expand(rows, registry=REG):
    out = set()
    for e in registry:
        if e[0] in INTERNAL:                               # is_internal_only: no level grants it
            continue
        lvl, appr = effective(rows, e[1])
        n = need(e)
        if (n == "approve" and appr and ORDER[lvl] >= 1) or (n != "approve" and ORDER[lvl] >= ORDER[n]):
            out.add(e[0])
    return sorted(out)

def ehash(perms): return hashlib.sha256("\n".join(perms).encode()).hexdigest()

TPL = {}
for r in read_csv("role-template-levels.csv"):
    TPL.setdefault(r["template"], {})[r["node"]] = (r["level"], r["can_approve"] == "true")
TEMPLATES = {r["template"] for r in read_csv("role-templates.csv")}
check("C2 template catalogs agree: 14 templates (quality_inspector from ADR-0070), every level row names a template and a node of the tree",
      len(TEMPLATES) == 14 and set(TPL) == TEMPLATES and all(n in PARENT for rows in TPL.values() for n in rows))
rnd = random.Random(12)
ok = True
for _ in range(200):
    nodes = rnd.sample(list(PARENT), rnd.randint(1, 25))
    rows = {n: (rnd.choice(list(ORDER)), False) for n in nodes}
    rows = {n: (l, rnd.random() < 0.3 and l != "none") for n, (l, _) in rows.items()}
    items = list(rows.items()); rnd.shuffle(items); reg = REG[:]; rnd.shuffle(reg)
    if ehash(expand(rows)) != ehash(expand(dict(items), reg)):
        ok = False
check("C3 expansion is deterministic: 200 random roles give the same set and hash for shuffled rows and registry", ok)
rows = {"sales": ("post", False), "credit_note": ("read", False)}
e = expand(rows)
check("C4 an area level applies to its leaves and a leaf row overrides it",
      "PostSalesInvoice" in e and "CloseSalesOrder" in e and "PostCreditNote" not in e and "ListCreditNote" in e and "CreateCreditNote" not in e)
e_edit, e_post, e_full = (expand({"purchasing": (l, False)}) for l in ("edit", "post", "full"))
check("C5 edit excludes Post, post excludes Reverse, full includes Reverse",
      "CreatePurchaseInvoice" in e_edit and "PostPurchaseInvoice" not in e_edit and "PostPurchaseInvoice" in e_post
      and "ReversePurchaseInvoice" not in e_post and "ReversePurchaseInvoice" in e_full)
e_d = expand({"dunning": ("edit", False)})
check("C6 effect class raises the level: an outbound Create needs post, a master data Set needs edit",
      "CreateDunningMessage" not in e_d and "CreateDunningMessage" in expand({"dunning": ("post", False)})
      and "SetPriceListEntries" in expand({"price_list": ("edit", False)}))
check("C7 Approve comes only from the approval flag, never from full",
      "ApprovePurchaseOrder" not in e_full and "ApprovePurchaseOrder" in expand({"purchasing": ("read", True)})
      and "ApproveSalesOrder" not in expand({"purchasing": ("read", True)}))
ca, acc = expand(TPL["chief_accountant"]), expand(TPL["accountant"])
check("C8 post_in_soft_locked_period: chief accountant yes, accountant no (posting periods read); accountant may enter manual rates",
      "post_in_soft_locked_period" in ca and "post_in_soft_locked_period" not in acc and "LockPostingPeriod" not in acc and "CreateExchangeRate" in acc)
it = expand(TPL["it_administrator"])
check("C9 IT administrator: roles and assignments, no finance or banking posting",
      "CreateRoleAssignment" in it and not any(p.startswith(("Post", "Reverse")) for p in it))
aud = expand(TPL["auditor"])
check("C10 auditor: only queries and Render (a file of what they may read), no File or Send",
      aud and all(p.startswith(("Get", "List", "Evaluate", "Render")) for p in aud) and "RenderReport" in aud and "FileStatutoryReport" not in aud)
try:
    need(("FrobnicateSomething", "dunning", "command", "Frobnicate", "other")); unknown = False
except KeyError:
    unknown = True
check("C11 a verb without a catalog level is refused (the CI rule)", unknown)
EXP = {t: set(expand(TPL[t])) for t in TEMPLATES}
check("C13 read_agent_run_bodies: only the owner template, every other template sets agent_run_bodies to none",
      [t for t in TEMPLATES if "read_agent_run_bodies" in EXP[t]] == ["owner"]
      and all(TPL[t].get("agent_run_bodies") == ("none", False) for t in TEMPLATES - {"owner"}))
check("C14 a declared minimum level: UpdateEmployeeOrganization needs full on organization, while CreateBranch on the same leaf needs edit",
      "UpdateEmployeeOrganization" not in expand({"organization": ("post", False)}) and "CreateBranch" in expand({"organization": ("edit", False)})
      and "UpdateEmployeeOrganization" in EXP["it_administrator"] and "UpdateEmployeeOrganization" in EXP["owner"])
approvers = {t for t in TEMPLATES if any(a for _, a in TPL[t].values())}
check("C15 every approving template can delegate its own approvals; delegate_for_others only owner and it_administrator",
      approvers == {"owner", "chief_accountant", "accountant", "sales_manager", "purchasing_manager", "production_planner", "quality_inspector"}
      and all({"CreateDelegation", "CancelDelegation"} <= EXP[t] for t in approvers)
      and {t for t in TEMPLATES if "delegate_for_others" in EXP[t]} == {"owner", "it_administrator"})
check("C16 IT administrator: no data import, no agent run bodies", not ({"ValidateImportBatch", "read_agent_run_bodies"} & EXP["it_administrator"]))
check("C17 AcceptMigrationDifference by permission: owner and chief accountant, not accountant",
      "AcceptMigrationDifference" in EXP["owner"] and "AcceptMigrationDifference" in EXP["chief_accountant"] and "AcceptMigrationDifference" not in EXP["accountant"])
check("C18 Send needs post, Render read, File post",
      need(REG[[e[0] for e in REG].index("SendDunningReminder")]) == "post" and need(REG[[e[0] for e in REG].index("RenderReport")]) == "read"
      and need(REG[[e[0] for e in REG].index("FileStatutoryReport")]) == "post")
check("C19 File commands on report leaves at post: chief accountant and owner file statements and tax returns, the accountant and auditor do not",
      {"FileStatutoryReport", "FileTaxReturn"} <= EXP["chief_accountant"] and {"FileStatutoryReport", "FileTaxReturn"} <= EXP["owner"]
      and not ({"FileStatutoryReport", "FileTaxReturn"} & (EXP["accountant"] | EXP["auditor"])))
# Every CRM command and query of ADR-0052 has a leaf in the tree under crm, and its verb a level.
a52 = open(os.path.join(DOCS, "adr/0052-minimal-crm.md"), encoding="utf-8").read()
table = a52.split("| Commands | Effect class |", 1)[1].split("\n\n", 1)[0]
names = {n for line in table.splitlines() if line.strip().startswith("| `") for n in re.findall(r"`([A-Z][A-Za-z]+)`", line.split("|")[1])}
qline = a52.split("Queries: `ListPartnerTimeline`", 1)[1].split("\n", 1)[0]
names |= {"ListPartnerTimeline"} | set(re.findall(r"`([A-Z][A-Za-z]+)`", qline))
by_name = {e[0]: e for e in REG}
def under_crm(leaf):
    while leaf is not None and leaf != "crm":
        leaf = PARENT.get(leaf)
    return leaf == "crm"
missing = []
for n in sorted(names):
    e = by_name.get(n)
    try:
        ok_ = e is not None and e[1] in PARENT and under_crm(e[1]) and need(e) is not None
    except KeyError:
        ok_ = False
    if not ok_:
        missing.append(n)
check(f"C20 every one of the {len(names)} CRM commands and queries of ADR-0052 has a leaf under crm and a verb level", len(names) > 40 and missing == [], missing)
# Every command and query ADR-0049 names as its own has a leaf. Names it cites from other ADRs and event names are listed.
a49 = open(os.path.join(DOCS, "adr/0049-statutory-reporting-and-printing.md"), encoding="utf-8").read()
a49_rules = a49.split("### Rules", 1)[1].split("\n## ", 1)[0]
FOREIGN_49 = {"AmountInWords": "package interface", "CompleteMigration": "ADR-0044", "CreateListExport": "ADR-0050", "CreateOpeningTurnover": "ADR-0044",
              "FileTaxReturn": "ADR-0041", "GetBankReconciliation": "ADR-0048", "GetDocumentTaxes": "ADR-0041", "GetTaxReturn": "ADR-0041",
              "ListBin": "ADR-0023", "ListItemLabel": "ADR-0061", "ListLotLabel": "ADR-0061", "ListSerialLabel": "ADR-0061", "RecordEInvoiceOutcome": "ADR-0028", "RunBalanceCarryForward": "ADR-0012"}
names49 = {n for n in re.findall(r"`([A-Z][a-z]+[A-Z][A-Za-z]+)`", a49_rules)
           if not re.search(r"(Requested|Recorded|Completed|Created|Updated|Posted)$", n) and n not in FOREIGN_49}
missing49 = []
for n in sorted(names49):
    e = by_name.get(n)
    try:
        ok_ = e is not None and e[1] in PARENT and need(e) is not None
    except KeyError:
        ok_ = False
    if not ok_:
        missing49.append(n)
check(f"C23 every one of the {len(names49)} reporting and printing commands and queries of ADR-0049 has a leaf and a verb level",
      len(names49) >= 25 and missing49 == [], missing49)
# Every barcode command and query of ADR-0061 rule 10 is named there and has a leaf and a verb level; human_only ones declare full.
a61 = open(os.path.join(DOCS, "adr/0061-barcodes.md"), encoding="utf-8").read()
missing61 = []
for n in list(BARCODES) + list(BARCODE_QUERIES):
    try:
        ok_ = f"`{n}`" in a61 and by_name[n][1] in PARENT and need(by_name[n]) is not None
        ok_ = ok_ and (n not in BARCODE_HUMAN_ONLY or (len(by_name[n]) > 5 and by_name[n][5] == "full" and "human_only" in a61))
    except KeyError:
        ok_ = False
    if not ok_:
        missing61.append(n)
check(f"C23b every one of the {len(BARCODES) + len(BARCODE_QUERIES)} barcode commands and queries of ADR-0061 has a leaf and a verb level; DeleteBarcodeReservation declares full",
      missing61 == [], missing61)
check("C24 UpdatePrintProfile only for the owner; every other template sets print_profile to none",
      [t for t in TEMPLATES if "UpdatePrintProfile" in EXP[t]] == ["owner"]
      and all(TPL[t].get("print_profile") == ("none", False) for t in TEMPLATES - {"owner"}))
check("C25 reporting queries for owner, chief accountant, accountant and auditor; the cashier has no report leaf; everyone may print what they read",
      all({"GetStatutoryReport", "ListBookRow", "RenderReport"} <= EXP[t] for t in ("owner", "chief_accountant", "accountant", "auditor"))
      and not any(p in EXP["cashier"] for p in ("GetStatutoryReport", "ListBookRow", "RenderReport", "ListReportLineContribution"))
      and all("RenderPrint" in EXP[t] for t in TEMPLATES))
def get_print_data(perms, subject_type, in_read_scope=True):
    """GetPrintData (general_access, read) also needs the subject's own Get<Type> and read scope (ADR-0054 rule 24)."""
    if "GetPrintData" not in perms or f"Get{camel(subject_type)}" not in perms:
        return "permission_denied"
    return None if in_read_scope else "record_not_found"
check("C26 GetPrintData follows its subject: an IT administrator's and an auditor's request on a sales invoice is refused unless they may read it; a sales clerk's is allowed, outside their scope refused",
      get_print_data(EXP["it_administrator"], "sales_invoice") == "permission_denied"
      and get_print_data(EXP["sales_clerk"], "sales_invoice") is None and get_print_data(EXP["sales_clerk"], "sales_invoice", in_read_scope=False) == "record_not_found"
      and "GetPrintData" in EXP["it_administrator"] and REG[[e[0] for e in REG].index("GetPrintData")][1] == "general_access"
      and not any(e[1] == "print_template" and e[2] == "query" and e[0] != "GetPrintDataContract" for e in REG))
sc, sm, it_, ow = EXP["sales_clerk"], EXP["sales_manager"], EXP["it_administrator"], EXP["owner"]
check("C21 CRM levels: the sales clerk edits interactions, complaints and outbound drafts but neither sends, approves nor closes; the sales manager approves and sends",
      {"CreateInteraction", "CreateComplaint", "CreateOutboundMessage", "SubmitOutboundMessage", "ListPartnerTimeline"} <= sc
      and not ({"SendOutboundMessage", "ApproveOutboundMessage", "CloseComplaint", "EraseDataSubject"} & sc)
      and {"ApproveOutboundMessage", "SendOutboundMessage", "CloseComplaint"} <= sm)
full_on = lambda t, leaf: effective(TPL[t], leaf)[0] == "full"
check("C22 CRM levels: the IT administrator has mailbox full; EraseDataSubject only the owner; system commands a person may start only where a template has full on their leaf (internal-only ones: C27)",
      {"CreateMailbox", "VerifyMailboxAuthentication", "RunMailboxIntake", "ListMailbox"} <= it_
      and [t for t in TEMPLATES if "EraseDataSubject" in EXP[t]] == ["owner"] and "RunPartnerDuplicateScan" not in sm
      and all({t for t in TEMPLATES if n in EXP[t]} == {t for t in TEMPLATES if full_on(t, spec[0])} for n, spec in CRM.items() if spec[2:] == ("full",) and n not in INTERNAL))
# holistic platform review: internal-only commands, the interim agent start seed, the platform command leaves
ALL_ROOTS_FULL = {r: ("full", True) for r, p in PARENT.items() if p is None}
check("C27 is_internal_only commands are in no template's expansion, owner included, nor in one with full and approve on every root",
      INTERNAL <= set(by_name) and not any(INTERNAL & EXP[t] for t in TEMPLATES) and not (INTERNAL & set(expand(ALL_ROOTS_FULL))))
starts = lambda t: {p.split(":", 1)[1] for p in EXP[t] if p.startswith("start_agent:")}
# simulation review 2026-11-15: workflow owners are not the planned approvers (ADR-0054 rule 11 note)
SEED = {"sales_clerk": {"quotation", "customer_onboarding"}, "accountant": {"bank_matching", "purchase_invoice", "analysis"},
        "production_planner": {"planning", "analysis"}, "owner": set(AGENT_TYPES), "it_administrator": set(AGENT_TYPES),
        "chief_accountant": {"analysis"}, "sales_manager": {"analysis"}, "purchasing_manager": {"analysis"}}   # analysis seed: ADR-0060 rule 36
check("C28 start_agent follows the interim seed per agent type leaf; UpdateAgentTypeSetting and cancel_agent_runs need full on agent",
      all(starts(t) == SEED.get(t, set()) for t in TEMPLATES) and all(f"agent_{a}" in PARENT and PARENT[f"agent_{a}"] == "agent" for a in AGENT_TYPES)
      and {t for t in TEMPLATES if "UpdateAgentTypeSetting" in EXP[t]} == {"owner", "it_administrator"}
      and not ({"UpdateAgentTypeSetting", "cancel_agent_runs"} & set(expand({"agent": ("post", False)})))
      and "start_agent:quotation" in expand({"agent": ("edit", False)}))
check("C28b the supplier item commands (lead-time update, ADR-0024 rule 23 note) need edit on the leaf supplier_item under Planning: buyer, purchasing manager, production planner and owner hold them; the sales clerk, accountant and auditor do not",
      PARENT.get("supplier_item") == "planning" and KIND.get("supplier_item") == "function"
      and {t for t in TEMPLATES if "UpdateSupplierItem" in EXP[t]} == {"buyer", "purchasing_manager", "production_planner", "owner"}
      and {t for t in TEMPLATES if "CreateSupplierItem" in EXP[t]} == {"buyer", "purchasing_manager", "production_planner", "owner"})
OLD_REG = [(e[0], "product") + tuple(e[2:]) if e[0] in UNIT_CMDS + ALIAS_CMDS else e for e in REG]   # as before: on the leaf product
check("C28c unit maintenance (ADR-0056 rule 20 note): the unit commands need edit on the leaf product_unit and the alias commands on uom_alias below it, under product; the purchasing manager, chief accountant, warehouse keeper and owner hold all six, the accountant only the alias commands, the sales roles, buyer, production planner, IT administrator and auditor none; on the leaf product only the owner held them",
      PARENT.get("product_unit") == "product" and PARENT.get("uom_alias") == "product_unit"
      and all({t for t in TEMPLATES if n in EXP[t]} == {"owner", "purchasing_manager", "chief_accountant", "warehouse_keeper"} for n in UNIT_CMDS)
      and all({t for t in TEMPLATES if n in EXP[t]} == {"owner", "purchasing_manager", "chief_accountant", "warehouse_keeper", "accountant"} for n in ALIAS_CMDS)
      and all({t for t in TEMPLATES if n in expand(TPL[t], OLD_REG)} == {"owner"} for n in UNIT_CMDS + ALIAS_CMDS))
check("C29 general_access at edit for every template but the auditor (uploads, list exports, approval progress); event deliveries only owner and IT administrator; ClearTaint owner and chief accountant",
      all({"CreateAttachment", "CreateListExport", "GetApprovalProgress"} <= EXP[t] for t in TEMPLATES - {"auditor"})
      and "CreateAttachment" not in EXP["auditor"] and "GetApprovalProgress" in EXP["auditor"]
      and {t for t in TEMPLATES if "RetryEventDelivery" in EXP[t]} == {"owner", "it_administrator"}
      and {t for t in TEMPLATES if "ClearTaint" in EXP[t]} == {"owner", "chief_accountant"})
FIVE_AN = {"chief_accountant", "accountant", "sales_manager", "purchasing_manager", "production_planner"}
check("C29b agent-assisted analysis (ADR-0060 rule 36): every template runs plans; every template but the auditor saves private analyses; sharing and examples for the owner and the five; release for the owner and the chief accountant; questions for the owner and the five; read_analysis_debug for the owner alone",
      all("EvaluateAnalysisPlan" in EXP[t] for t in TEMPLATES) and {t for t in TEMPLATES if "CreateSavedAnalysis" in EXP[t]} == TEMPLATES - {"auditor"}
      and {t for t in TEMPLATES if "share_saved_analysis" in EXP[t]} == FIVE_AN | {"owner"} and {t for t in TEMPLATES if "ReleaseSavedAnalysis" in EXP[t]} == {"owner", "chief_accountant"}
      and {t for t in TEMPLATES if "CreateAnalysisQuestion" in EXP[t]} == FIVE_AN | {"owner"}
      and [t for t in TEMPLATES if "read_analysis_debug" in EXP[t]] == ["owner"] and "ListAnalysisQuestion" in EXP["auditor"])
# stored expansion and INV-220
perms = expand(TPL["sales_manager"])
X("update role set expansion_hash=%s, registry_version='lab' where id=%s", (ehash(perms), I["role"]))
for node, (lvl, appr) in TPL["sales_manager"].items():
    X("insert into role_level values (%s,%s,%s,%s,%s)", (I["co"], I["role"], node, lvl, appr))
with c.cursor() as cur:
    cur.executemany("insert into role_permission values (%s,%s,%s)", [(I["co"], I["role"], p) for p in perms])
stored_rows = {r[0]: (r[1], r[2]) for r in X("select authorization_area, level, can_approve from role_level where role_id=%s", (I["role"],))}
stored = [r[0] for r in X("select permission from role_permission where role_id=%s order by permission collate \"C\"", (I["role"],))]
h = X("select expansion_hash from role where id=%s", (I["role"],)).fetchone()[0]
check("C12 INV-220: the stored permissions equal the expansion of the stored levels, and the hash matches",
      stored == expand(stored_rows) and h == ehash(stored))

# ---------------------------------------------------------------- D: owner scope on real rows
X("alter table document add column owner_employee_id uuid, add column created_by_user_id uuid, add column branch_id uuid")  # lab: DS-05 has no DDL yet
D = {}
for name, owner, creator, br in (("d1", "eA", "uA", "b1"), ("d2", "eB", "uB", "b1"), ("d3", "eC", "uC", "b2"), ("d4", "eE", "uE", "b2"),
                                 ("d5", None, "uA", "b1"), ("d6", "eM", "uM", "b2")):
    D[name] = new()
    X("insert into document (id, company_id, document_type, owner_employee_id, created_by_user_id, branch_id) values (%s,%s,'sales_order',%s,%s,%s)",
      (D[name], I["co"], I[owner] if owner else None, I[creator], I[br]))
NAME = {v: k for k, v in D.items()}

UNDER = """
with recursive me as (select partner_id, department_id from employee_profile where company_id=%(co)s and user_account_id=%(u)s),
managed(id) as (select d.id from department d join me on d.manager_partner_id = me.partner_id where d.company_id=%(co)s
                union select d.id from department d join managed m on d.parent_id = m.id where d.company_id=%(co)s),
chain(id, path) as (select e.partner_id, array[e.partner_id] from employee_profile e join me on e.manager_partner_id = me.partner_id where e.company_id=%(co)s
                    union all select e.partner_id, c.path || e.partner_id from employee_profile e join chain c on e.manager_partner_id = c.id
                    where e.company_id=%(co)s and not e.partner_id = any(c.path))
select partner_id from employee_profile where company_id=%(co)s and department_id in (select department_id from me union select id from managed)
union select id from chain union select partner_id from me"""
TEAM = """select tm2.partner_id from team_member tm1 join team_member tm2 on tm1.team_id = tm2.team_id
          join employee_profile e on e.partner_id = tm1.partner_id where e.company_id=%(co)s and e.user_account_id=%(u)s
          union select partner_id from employee_profile where company_id=%(co)s and user_account_id=%(u)s"""

def owner_set(user, scope):
    """The resolver of ADR-0054 rule 2: employees whose documents the scope reaches (None means no owner restriction)."""
    if scope in ("branch", "company"):
        return None
    if scope == "own":
        return [r[0] for r in X("select partner_id from employee_profile where company_id=%(co)s and user_account_id=%(u)s", {"co": I["co"], "u": I[user]})]
    return [r[0] for r in X(TEAM if scope == "team" else UNDER, {"co": I["co"], "u": I[user]})]

def visible(user, assignments):
    """assignments: list of (owner scope, record scope branch keys or None). Union over assignments (ADR-0054 rule 15)."""
    seen, total = set(), X("select count(*) from document where company_id=%s", (I["co"],)).fetchone()[0]
    for scope, branches in assignments:
        emps = owner_set(user, scope)
        q = "select id from document where company_id=%(co)s"
        args = {"co": I["co"], "u": I[user]}
        if branches is not None:
            q += " and branch_id = any(%(br)s)"; args["br"] = [I[b] for b in branches]
        if emps is not None:
            q += " and (owner_employee_id = any(%(emps)s) or created_by_user_id = %(u)s)"; args["emps"] = emps
        seen |= {NAME[r[0]] for r in X(q, args)}
    return sorted(seen), len(seen) < total               # rows, is_scope_filtered

check("D1 own: the user's documents and those they created without an owner", visible("uA", [("own", None)])[0] == ["d1", "d5"])
check("D2 team: plus documents of team members", visible("uA", [("team", None)])[0] == ["d1", "d3", "d5"])
check("D3 department for a member: own department and their reporting chain, not a sibling sub-department",
      visible("uA", [("department", None)])[0] == ["d1", "d4", "d5", "d6"])
check("D4 department for the manager: the department subtree and the whole reporting chain",
      visible("uM", [("department", None)])[0] == ["d1", "d2", "d4", "d6"])
check("D5 branch: every document in the record scope", visible("uC", [("branch", ["b1"])])[0] == ["d1", "d2", "d5"])
rows_, filt = visible("uC", [("company", None)])
check("D6 company: every document, not scope filtered", rows_ == ["d1", "d2", "d3", "d4", "d5", "d6"] and not filt)
check("D7 two assignments are a union", visible("uA", [("own", None), ("branch", ["b2"])])[0] == ["d1", "d3", "d4", "d5", "d6"])
check("D8 own inside a record scope is the intersection", visible("uA", [("own", ["b2"])]) == ([], True))
check("D9 is_scope_filtered is true when rows were left out", visible("uA", [("own", None)])[1] is True)
X("update employee_profile set department_id=%s where partner_id=%s", (I["dOther"], I["eB"]))
check("D10 a transfer takes effect at once: the manager no longer sees the moved employee's documents",
      visible("uM", [("department", None)])[0] == ["d1", "d4", "d6"])
X("update employee_profile set manager_partner_id=%s where partner_id=%s", (I["eE"], I["eM"]))   # M -> E -> A -> M: a cycle
cyc = X("""with recursive walk(id, path, cyc) as (select partner_id, array[partner_id], false from employee_profile where company_id=%s
           union all select e.manager_partner_id, w.path || e.manager_partner_id, e.manager_partner_id = any(w.path)
           from employee_profile e join walk w on e.partner_id = w.id where not w.cyc and e.manager_partner_id is not null)
           select bool_or(cyc) from walk""", (I["co"],)).fetchone()[0]
rows_ = visible("uM", [("department", None)])[0]
check("D11 a manager cycle is found (employee_manager_cycle) and the resolver still terminates", cyc is True and "d6" in rows_)
X("update employee_profile set manager_partner_id=null where partner_id=%s", (I["eM"],))
read_rows = visible("uA", [("department", None)])[0]; edit_rows = visible("uA", [("own", None)])[0]
check("D12 the edit scope (own) is a subset of the read scope (department)", set(edit_rows) <= set(read_rows) and edit_rows != read_rows)
# Followers of owner scope (ADR-0054 rule 15): every row that shows a document's data is filtered by the document's scope.
X("create temporary table follower (kind text, document_id uuid)")
FOLLOWERS = ("work_item", "timeline_entry", "audit_record", "open_item", "attachment_link", "render_job", "live_header")
with c.cursor() as cur:
    cur.executemany("insert into follower values (%s,%s)", [(k, D[d]) for k in FOLLOWERS for d in D])
def followers_seen(user, assignments):
    docs = [D[d] for d in visible(user, assignments)[0]]
    return {(k, NAME[d]) for k, d in X("select kind, document_id from follower where document_id = any(%s)", (docs,))}
fs = followers_seen("uA", [("own", None)])
check(f"D13 the {len(FOLLOWERS)} followers of a document (work items, timeline, audit, open items, attachments, prints, live headers) are seen exactly with it",
      fs == {(k, d) for k in FOLLOWERS for d in ("d1", "d5")})
def aggregate_allowed(assignments):
    """is_owner_scoped false: a total over documents needs owner scope branch or company (ADR-0054 rule 15)."""
    return any(scope in ("branch", "company") for scope, _ in assignments)
check("D14 aggregates such as GetPartnerExposure are refused to own, team and department scopes and allowed to branch and company",
      not aggregate_allowed([("own", None), ("department", None)]) and aggregate_allowed([("own", None), ("branch", ["b1"])]))

# ---------------------------------------------------------------- E: segregation of duties
SOD = read_csv("segregation-rules.csv")
for r in SOD:
    r["a"], r["b"] = set(r["side_a"].split(";")), set(r["side_b"].split(";"))
check("E1 segregation catalog: six rules, sides non-empty and disjoint, relations known",
      len(SOD) == 6 and all(r["a"] and r["b"] and not (r["a"] & r["b"]) and r["document_relation"] in ("none", "referenced_order", "settled_item", "bank_account_used") for r in SOD))

class SodError(Exception):
    pass

def assignment_check(perms, enabled, mode):
    hits = [r["code"] for r in SOD if r["code"] in enabled and perms & r["a"] and perms & r["b"]]
    if hits and mode == "block":
        raise SodError("segregation_conflict " + ",".join(hits))
    return [("segregation_conflict_found", h) for h in hits]

enabled = {r["code"] for r in SOD}
buyer_wh = set(expand(TPL["buyer"])) | set(expand(TPL["warehouse_keeper"]))
res = assignment_check(buyer_wh, enabled, "warn")
check("E2 assignment check, warn: buyer plus warehouse keeper gives the check result for purchase_order_vs_goods_receipt",
      ("segregation_conflict_found", "purchase_order_vs_goods_receipt") in res)
try:
    assignment_check(buyer_wh, enabled, "block"); blocked = False
except SodError:
    blocked = True
check("E3 assignment check, block: the same assignment is refused with segregation_conflict", blocked)
check("E4 assignment check: buyer alone has no conflict", assignment_check(set(expand(TPL["buyer"])), enabled, "block") == [])
owner_conflicts = assignment_check(set(expand(TPL["owner"])), enabled, "warn")
check("E5 the owner template holds both sides of at least four seeded rules (rule 19's per-document check is its control)", len(owner_conflicts) >= 4)
conflicts_by_template = {t: [h for _, h in assignment_check(EXP[t], enabled, "warn")] for t in sorted(TEMPLATES - {"owner"})}
check("E5a every seeded template except owner is free of conflicts with the seeded segregation rules (ADR-0054 rule 11 note)",
      not any(conflicts_by_template.values()), {t: v for t, v in conflicts_by_template.items() if v})

def block_switch_conflicts(assignments, enabled_rules):
    """The switch to mode block (ADR-0054 rule 18) with the rule 17 note: assignments of the owner template are exempt;
    the owner still meets rule 19's per-document check. assignments: (user, template) pairs."""
    perms = {}
    for user, template in assignments:
        if template != "owner":
            perms.setdefault(user, set()).update(EXP[template])
    return sorted((u, h) for u, p in perms.items() for _, h in assignment_check(p, enabled_rules, "warn"))

sw = block_switch_conflicts([("uO", "owner"), ("uB", "buyer"), ("uW", "warehouse_keeper")], enabled)
check("E5b block mode can be enabled while only the owner template conflicts (ADR-0054 rule 17 note)", sw == [], sw)
sw = block_switch_conflicts([("uO", "owner"), ("uO", "buyer"), ("uO", "warehouse_keeper")], enabled)
check("E5c but not while a user, the owner included, holds both sides through other templates", sw == [("uO", "purchase_order_vs_goods_receipt")], sw)

# Per-document check (ADR-0054 rule 19). actions: list of (human, permission, document).
LINKS = {("g1", "referenced_order"): ["p1"], ("pay1", "settled_item"): ["inv1"], ("p1", "referenced_order"): [], ("inv1", "settled_item"): []}
REVERSE_LINKS = {("p1", "referenced_order"): ["g1"], ("inv1", "settled_item"): ["pay1"]}

def related(doc, relation):
    return LINKS.get((doc, relation), []) + REVERSE_LINKS.get((doc, relation), [])

def doc_check(actor, perm, doc, history, enabled, small_mode=False, exceptions=None):
    humans = {actor["human"]} | ({actor["delegator"]} if actor.get("delegator") else set())
    for r in SOD:
        if r["code"] not in enabled or r["document_relation"] == "none":
            continue
        for side, other in ((r["b"], r["a"]), (r["a"], r["b"])):
            if perm not in side:
                continue
            for rel in related(doc, r["document_relation"]):
                if any(h in humans and p in other and d == rel for h, p, d in history):
                    if small_mode:
                        exceptions.append((r["code"], actor["human"], perm, doc, rel)); continue
                    raise SodError(f"segregation_of_duties {r['code']} {rel}")

def allowed(*a, **k):
    try:
        doc_check(*a, **k); return True
    except SodError:
        return False

hist = [("X", "CreatePurchaseOrder", "p1")]
check("E6 the buyer who wrote the order cannot post its goods receipt", not allowed({"human": "X"}, "PostGoodsReceipt", "g1", hist, enabled))
check("E7 another person can", allowed({"human": "Y"}, "PostGoodsReceipt", "g1", hist, enabled))
check("E8 the other way round: who posted the receipt cannot then change the order",
      not allowed({"human": "Y"}, "UpdatePurchaseOrder", "p1", [("Y", "PostGoodsReceipt", "g1")], enabled))
check("E9 a system job acting for the buyer is refused too (on_behalf_of is the acting human)",
      not allowed({"human": "X", "kind": "system"}, "PostGoodsReceipt", "g1", hist, enabled))
check("E10 a substitute acting for the buyer is refused (the delegator counts)",
      not allowed({"human": "S", "delegator": "X"}, "PostGoodsReceipt", "g1", hist, enabled))
check("E11 who posted the supplier invoice cannot post the payment settling it",
      not allowed({"human": "Z"}, "PostBankPayment", "pay1", [("Z", "PostPurchaseInvoice", "inv1")], enabled))
check("E12 a disabled rule does not refuse", allowed({"human": "X"}, "PostGoodsReceipt", "g1", hist, enabled - {"purchase_order_vs_goods_receipt"}))
exc = []
check("E13 small-company mode: the command runs and an exception is recorded",
      allowed({"human": "X"}, "PostGoodsReceipt", "g1", hist, enabled, small_mode=True, exceptions=exc) and exc == [("purchase_order_vs_goods_receipt", "X", "PostGoodsReceipt", "g1", "p1")])

def small_mode_allowed(users_perms):
    return sum(1 for p in users_perms.values() if any(x.startswith(("Post", "Approve", "Reverse")) for x in p)) <= 2
check("E14 small-company mode is allowed with two posting users and refused with three",
      small_mode_allowed({"o": {"PostX"}, "a": {"ApproveY"}, "s": {"ListZ"}}) and not small_mode_allowed({"o": {"PostX"}, "a": {"ApproveY"}, "s": {"PostZ"}}))


# Every path that changes effective rights runs the same checks (ADR-0054 rules 9, 18, 20, 21).
PATHS = ("CreateRoleAssignment", "UpdateRoleAssignment", "UpdateRole", "EnableUserAccount", "CreateDelegation", "upgrade")
def posting_user(perms):
    return any(x.startswith(("Post", "Approve")) for x in perms)

def change_rights(state, path, user, gained, mode, enabled, small=False):
    """state: user -> permissions in force. Returns check results; raises SodError; an upgrade holds back instead."""
    new_perms = state.get(user, set()) | set(gained)
    if small:
        others = sum(1 for u, p in state.items() if u != user and posting_user(p))
        if posting_user(new_perms) and not posting_user(state.get(user, set())) and others >= 2:
            if path == "upgrade":
                return [("held_back", "small_company_mode_active")]
            raise SodError("small_company_mode_active")
        state[user] = new_perms
        return []
    try:
        res = assignment_check(new_perms, enabled, mode)
    except SodError:
        if path == "upgrade":
            return [("held_back", "segregation_conflict")]
        raise
    state[user] = new_perms
    return res

def enable_rule(state, code, enabled, mode):
    hits = [u for u, p in state.items() if assignment_check(p, enabled | {code}, "warn") != assignment_check(p, enabled, "warn")]
    if hits and mode == "block":
        raise SodError("segregation_conflict")
    enabled.add(code)
    return [("segregation_conflict_found", u) for u in hits]

def outcome(fn, *a, **k):
    try:
        return fn(*a, **k)
    except SodError as e:
        return str(e).split()[0]

BUYER, WH = set(expand(TPL["buyer"])), set(expand(TPL["warehouse_keeper"]))
res = {p: outcome(change_rights, {"u": set(BUYER)}, p, "u", WH, "block", set(enabled)) for p in PATHS}
check("E15 block mode on every rights path: assignment, role change, enabling a user and delegation are refused; the upgrade holds the gain back",
      all(res[p] == "segregation_conflict" for p in PATHS if p != "upgrade") and res["upgrade"] == [("held_back", "segregation_conflict")], res)
part = enabled - {"purchase_order_vs_goods_receipt"}
st = {"u": BUYER | WH}
check("E16 EnableSegregationRule: refused in block while a holder conflicts, a check result in warn",
      outcome(enable_rule, dict(st), "purchase_order_vs_goods_receipt", set(part), "block") == "segregation_conflict"
      and outcome(enable_rule, dict(st), "purchase_order_vs_goods_receipt", set(part), "warn") == [("segregation_conflict_found", "u")])
inv229 = True
pool_perms = sorted({p for r in SOD for p in r["a"] | r["b"]} | {"ListPartner", "CreateQuotation"})
for trial in range(50):
    state, en = {}, set(enabled)
    for _ in range(40):
        u = rnd.choice("abcd"); g = set(rnd.sample(pool_perms, rnd.randint(1, 3)))
        if rnd.random() < 0.1:
            outcome(enable_rule, state, rnd.choice([r["code"] for r in SOD]), en, "block")
        else:
            outcome(change_rights, state, rnd.choice(PATHS), u, g, "block", en)
        inv229 &= all(assignment_check(p, en, "warn") == [] for p in state.values())
check("E17 INV-229: over 2,000 random rights changes in block mode no conflict ever exists", inv229)
st = {"o": {"PostX"}, "a": {"ApproveY"}, "s": {"ListZ"}}
check("E18 small-company bound on every path: enabling or delegating to a third posting user is refused, the upgrade holds back, the two may gain more",
      outcome(change_rights, dict(st), "EnableUserAccount", "s", {"PostZ"}, "warn", enabled, small=True) == "small_company_mode_active"
      and outcome(change_rights, dict(st), "CreateDelegation", "s", {"ApproveY"}, "warn", enabled, small=True) == "small_company_mode_active"
      and outcome(change_rights, dict(st), "upgrade", "s", {"PostZ"}, "warn", enabled, small=True) == [("held_back", "small_company_mode_active")]
      and outcome(change_rights, dict(st), "UpdateRole", "a", {"PostQ"}, "warn", enabled, small=True) == [])

def create_delegation(state, delegator, substitute, kind, lent, roles_totp, substitute_totp, mode, en):
    """ADR-0054 rule 21: segregation for both kinds; a TOTP role is lent only to a substitute with TOTP."""
    if delegator == substitute:
        return "delegation_invalid"
    if roles_totp and not substitute_totp:
        return "delegation_invalid"
    return outcome(change_rights, state, "CreateDelegation", substitute, lent, mode, en)
st = {"k": set(WH), "m": {"ApprovePurchaseOrder", "ListPurchaseOrder"}}
check("E19 a delegation of kind approval is checked for segregation: a warehouse keeper given purchase order approvals is refused in block, warned in warn",
      create_delegation(dict(st), "m", "k", "approval", {"ApprovePurchaseOrder"}, False, True, "block", enabled) == "segregation_conflict"
      and ("segregation_conflict_found", "purchase_order_vs_goods_receipt") in create_delegation(dict(st), "m", "k", "approval", {"ApprovePurchaseOrder"}, False, True, "warn", enabled))
check("E20 a delegated role that requires TOTP needs a substitute with TOTP",
      create_delegation({}, "m", "k", "approval", {"ApproveBankPayment"}, True, False, "warn", set()) == "delegation_invalid"
      and create_delegation({}, "m", "k", "approval", {"ApproveBankPayment"}, True, True, "warn", set()) == [])

# ---------------------------------------------------------------- F: delegation window
X("""insert into delegation (id, company_id, delegator_user_id, substitute_user_id, kind, start_date, end_date, reason, created_by_user_id)
     values (%s,%s,%s,%s,'approval','2026-03-01','2026-03-10','leave',%s)""", (I["per"], I["co"], I["uM"], I["uS"], I["uM"]))
IN_FORCE = """select count(*) from delegation dl join user_account u on u.id = dl.delegator_user_id
              where dl.company_id=%s and dl.substitute_user_id=%s and dl.state='active' and u.is_active and %s between dl.start_date and dl.end_date"""
f = lambda d: X(IN_FORCE, (I["co"], I["uS"], d)).fetchone()[0] == 1
check("F1 delegation in force on its first and last day, not the day before or after",
      f(date(2026, 3, 1)) and f(date(2026, 3, 10)) and not f(date(2026, 2, 28)) and not f(date(2026, 3, 11)))
X("update user_account set is_active=false, disabled_at=now() where id=%s", (I["uM"],))
inactive = f(date(2026, 3, 5))
X("update user_account set is_active=true, disabled_at=null where id=%s", (I["uM"],))
X("update delegation set state='canceled' where id=%s", (I["per"],))
check("F2 a disabled delegator or a canceled delegation lends nothing", not inactive and not f(date(2026, 3, 5)))
X("update delegation set state='active' where id=%s", (I["per"],))

# ---------------------------------------------------------------- H: users, invitations, holds, organization (ADR-0054 rules 3-4, 6, 9)
TODAY = date(2026, 4, 1)
for u, scope in (("uA", "own"), ("uB", "company"), ("uC", "company"), ("uE", "company"), ("uM", "department")):
    ra(c, scope, scope, user=u)
ra(c, "own", "own", user="uB", co="co2", role="role2")                                   # linked to co2 now: shared
ra(c, "own", "own", user="uC", co="co2", role="role2", vfrom="2027-01-01")               # linked from a future date: shared
ra(c, "own", "own", user="uE", co="co2", role="role2", vfrom="2025-01-01", vto="2026-01-31")  # ended: not linked to co2
LINKED = """select count(distinct ra.company_id) from role_assignment ra
            left join user_invitation ui on ui.company_id = ra.company_id and ui.id = ra.user_invitation_id
            where ra.user_account_id=%(u)s and (ra.valid_to is null or ra.valid_to >= %(d)s)
              and (ra.user_invitation_id is null or ui.state = 'confirmed') and (%(co)s::uuid is null or ra.company_id = %(co)s::uuid)"""
def linked(u, co, today=TODAY):
    return X(LINKED, {"u": I[u], "d": today, "co": I[co]}).fetchone()[0] > 0
def shared(u, today=TODAY):
    return X(LINKED, {"u": I[u], "d": today, "co": None}).fetchone()[0] > 1
GUARDED = ("UpdateUserAccount.name", "UpdateUserAccount.email", "CreateCredentialReset", "ClearUserAccountLockout", "DisableUserAccount")
NO_ESCALATION = ("UpdateUserAccount.name", "UpdateUserAccount.email", "CreateCredentialReset")
def credential_command(command, target, caller_perms, target_perms, operator=False, co="co"):
    """ADR-0054 rule 3: the operator always; a company only for its linked users, never a shared one's guarded fields."""
    if operator:
        return None
    if not linked(target, co):
        return "record_not_found"
    if command in GUARDED and shared(target):
        return "user_shared_across_companies"
    if command in NO_ESCALATION and not set(target_perms) <= set(caller_perms):
        return "grant_exceeds_own_rights"
    return None
check("H1 shared users: a company caller is refused name and e-mail changes, reset, lockout clearance and disabling; an operator is not",
      [credential_command(cmd, "uB", EXP["owner"], set()) for cmd in GUARDED] == ["user_shared_across_companies"] * 5
      and all(credential_command(cmd, "uB", set(), EXP["owner"], operator=True) is None for cmd in GUARDED[:4]))
check("H2 a future assignment in another company links and so shares a user, an ended one does not; language is not guarded",
      shared("uC") and not shared("uE") and not shared("uA") and credential_command("UpdateUserAccount.language", "uB", set(), set()) is None)
check("H3 no escalation: an IT administrator cannot reset an owner's password or change their e-mail; an owner can reset an IT administrator's",
      credential_command("CreateCredentialReset", "uA", EXP["it_administrator"], EXP["owner"]) == "grant_exceeds_own_rights"
      and credential_command("UpdateUserAccount.email", "uA", EXP["it_administrator"], EXP["owner"]) == "grant_exceeds_own_rights"
      and credential_command("CreateCredentialReset", "uA", EXP["owner"], EXP["it_administrator"]) is None)
check("H4 lockout clearance grants no access, so it is exempt from no-escalation; a sole owner is recovered by the operator",
      credential_command("ClearUserAccountLockout", "uA", EXP["sales_clerk"], EXP["owner"]) is None
      and credential_command("CreateCredentialReset", "uA", set(), EXP["owner"], operator=True) is None)

def create_user_account(co, login, display_name, email, creator="op"):
    """ADR-0054 rule 3: match on the exact login only; always an invitation; the same answer either way."""
    row = X("select id from user_account where login=%s", (login,)).fetchone()
    iid = new()
    if row:
        uid, is_new, state = row[0], False, "pending"
    else:
        uid, is_new, state = new(), True, "confirmed"
        X("insert into user_account (id, login, display_name, email, language, password_hash, created_at) values (%s,%s,%s,%s,'en','x',now())",
          (uid, login, display_name, email))
    X("""insert into user_invitation (id, company_id, user_account_id, login, display_name, email, is_new_account, state, created_by_user_id,
         created_at, expires_at, decided_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s,%s)""",
      (iid, I[co], uid, login, display_name, email, is_new, state, I[creator],
       datetime.now(timezone.utc) + timedelta(days=30) if state == "pending" else None,   # invitation_expiry_days
       None if state == "pending" else datetime.now(timezone.utc)))
    return {"user_invitation_id": str(iid)}, iid
def create_role_assignment(co, user, inv=None, role="role2"):
    """ADR-0054 rule 12: record_not_found for a user not linked to the company, unless the assignment names that user's
    pending or confirmed invitation there."""
    if not linked(user, co):
        row = X("select user_account_id, state from user_invitation where company_id=%s and id=%s", (I[co], inv)).fetchone() if inv else None
        if not row or row[0] != I[user] or row[1] not in ("pending", "confirmed"):
            return "record_not_found"
    return ra(c, "own", "own", user=user, co=co, role=role, inv=inv)
def company_view(co, iid):
    """What the company's queries show of an invitation: its own typed fields and the state, never the account's data."""
    return X("select login, display_name, email, state from user_invitation where company_id=%s and id=%s", (I[co], iid)).fetchone()
IN_FORCE_SQL = """select count(*) from role_assignment ra left join user_invitation ui on ui.company_id = ra.company_id and ui.id = ra.user_invitation_id
                  where ra.id=%s and ra.valid_from <= %s and (ra.valid_to is null or ra.valid_to >= %s)
                    and (ra.user_invitation_id is null or ui.state = 'confirmed')"""
in_force = lambda rid: X(IN_FORCE_SQL, (rid, TODAY, TODAY)).fetchone()[0] == 1
X("update user_account set email=%s where id=%s", ("a" + t + "@example.test", I["uA"]))
# Two people, one login: company co2 means someone else but types uA's login.
resp_existing, inv_x = create_user_account("co2", ("uA" + t).lower(), "Someone Else", "other@example.test")
ra_x = create_role_assignment("co2", "uA", inv_x)
resp_new, inv_n = create_user_account("co2", ("brandnew" + t).lower(), "Brand New", "new@example.test")
check("H5 CreateUserAccount answers the same shape for an existing and a new login: an invitation ID and nothing else",
      resp_existing.keys() == resp_new.keys() == {"user_invitation_id"})
check("H6 EC-118 two people, one login: the assignment stays pending and grants nothing, the user is not linked or shared, the account is untouched",
      not in_force(ra_x) and not linked("uA", "co2") and not shared("uA")
      and X("select display_name, email from user_account where id=%s", (I["uA"],)).fetchone() == ("uA", "a" + t + "@example.test"))
check("H7 the inviting company sees only what it typed, and its credential commands answer record_not_found for that user",
      company_view("co2", inv_x)[1:] == ("Someone Else", "other@example.test", "pending")
      and credential_command("CreateCredentialReset", "uA", EXP["owner"], set(), co="co2") == "record_not_found")
expect("H8 only the invited user can confirm an existing account's invitation (INV-231)",
       lambda cx: cx.execute("update user_invitation set state='confirmed', decided_at=now(), decided_by_user_id=%s where id=%s", (I["op"], inv_x)), True,
       "ck_user_invitation_confirmed_by_user")
X("update user_invitation set state='canceled', decided_at=now(), decided_by_user_id=%s where id=%s", (I["op"], inv_x))
check("H9 the company cancels the invitation; the assignment never came into force (INV-231)",
      not in_force(ra_x) and not shared("uA") and company_view("co2", inv_x)[3] == "canceled")
# A real second company: uE, no longer linked to co2, is invited again, and confirms.
reset_e = new()
X("insert into credential_reset (id, user_account_id, token_hash, created_by_user_id, issued_in_company_id, created_at, expires_at) values (%s,%s,%s,%s,%s,now(),now()+interval '1 hour')",
  (reset_e, I["uE"], b"e" + t.encode(), I["uB"], I["co"]))
former = [create_role_assignment("co2", "uE"), create_role_assignment("co2", "uE", inv_x)]
_, inv_e = create_user_account("co2", ("uE" + t).lower(), "E", None)
ra_e = create_role_assignment("co2", "uE", inv_e)
check("H9b a former user whose ID co2 still knows cannot be given rights without their own invitation: record_not_found, also with someone else's invitation",
      former == ["record_not_found", "record_not_found"] and not isinstance(ra_e, str))
pending_ok = not in_force(ra_e) and not shared("uE") and credential_command("CreateCredentialReset", "uE", EXP["owner"], set()) is None
def confirm_invitation(iid, user):
    """ConfirmUserInvitation, company-scoped: the permission check is that the caller is the invitation's user; an
    expired invitation is refused; a user who becomes shared loses every company-issued reset token."""
    row = X("select user_account_id, state, expires_at <= now() from user_invitation where id=%s", (iid,)).fetchone()
    if row[0] != I[user]:
        return "permission_denied"
    if row[1] != "pending" or row[2]:
        if row[1] == "pending":
            X("update user_invitation set state='expired', decided_at=now() where id=%s", (iid,))
        return "invalid_state_transition"
    X("update user_invitation set state='confirmed', decided_at=now(), decided_by_user_id=%s where id=%s and state='pending'", (I[user], iid))
    if shared(user):
        X("""update credential_reset set voided_at=now() where user_account_id=%s and issued_in_company_id is not null
             and used_at is null and voided_at is null""", (I[user],))
by_other = confirm_invitation(inv_e, "uB")
confirm_invitation(inv_e, "uE")
FIRST_LINK = """select ui.state from role_assignment ra join user_invitation ui on ui.company_id = ra.company_id and ui.id = ra.user_invitation_id where ra.id=%s"""
check("H9c the confirmation's check is that the caller is the invitation's user; the first link names a confirmed invitation (INV-231)",
      by_other == "permission_denied" and X(FIRST_LINK, (ra_e,)).fetchone()[0] == "confirmed")
check("H10 pending, the invitation did not share uE; confirmed by uE, the assignment is in force, uE is shared, and co's reset token is voided",
      pending_ok and in_force(ra_e) and shared("uE")
      and X("select voided_at is not null from credential_reset where id=%s", (reset_e,)).fetchone()[0]
      and credential_command("CreateCredentialReset", "uE", EXP["owner"], set()) == "user_shared_across_companies")

_, inv_m = create_user_account("co2", ("uM" + t).lower(), "M", None)
ra_m = create_role_assignment("co2", "uM", inv_m)
X("update user_invitation set created_at=now()-interval '40 days', expires_at=now()-interval '10 days' where id=%s", (inv_m,))
late = confirm_invitation(inv_m, "uM")
_, inv_m2 = create_user_account("co2", ("uM" + t).lower(), "M", None)
check("H10b a pending invitation expires after 30 days: confirming it is refused, it becomes expired, its assignment never comes into force, and it can be re-sent",
      late == "invalid_state_transition" and company_view("co2", inv_m)[3] == "expired" and not in_force(ra_m)
      and company_view("co2", inv_m2)[3] == "pending")
X("update user_account set totp_secret='\\x01', is_totp_enabled=true where id=%s", (I["uA"],))
for k in range(2):
    X("insert into user_session (id, user_account_id, token_hash, csrf_token_hash, created_at, last_seen_at, absolute_expires_at) values (%s,%s,%s,'\\x00',now(),now(),now()+interval '1 hour')",
      (new(), I["uA"], bytes([k + 1]) + t.encode()))
resets = [new(), new()]
for k, rid in enumerate(resets):
    X("insert into credential_reset (id, user_account_id, token_hash, created_by_user_id, issued_in_company_id, created_at, expires_at) values (%s,%s,%s,%s,%s,now(),now()+interval '1 hour')",
      (rid, I["uA"], bytes([k + 9]) + t.encode(), I["uB"], I["co"]))
def consume_reset(rid, password_hash):
    u = X("update credential_reset set used_at=clock_timestamp() where id=%s and used_at is null and voided_at is null and expires_at > now() returning user_account_id", (rid,)).fetchone()[0]
    X("update user_account set password_hash=%s, password_changed_at=clock_timestamp() where id=%s", (password_hash, u))
    X("update user_session set revoked_at=clock_timestamp() where user_account_id=%s and revoked_at is null", (u,))
    X("update credential_reset set voided_at=clock_timestamp() where user_account_id=%s and used_at is null and voided_at is null", (u,))
consume_reset(resets[0], "y")
st_ = X("""select u.is_totp_enabled, (select count(*) from user_session s where s.user_account_id=u.id and s.revoked_at is null),
           (select count(*) from credential_reset r where r.user_account_id=u.id and r.used_at is null and r.voided_at is null) from user_account u where u.id=%s""", (I["uA"],)).fetchone()
check("H11 consuming a reset keeps TOTP enrolled, revokes every session and voids the other reset token (INV-227)", st_ == (True, 0, 0), st_)

# Permission holds on upgrade (ADR-0054 rule 9), on real rows.
REG_OLD = [e for e in REG if e[0] != "PostGoodsReceipt"]
holder = {"uC": set(BUYER)}                              # uC also holds a buyer role
roles_w = {}
for code in ("w1", "w2"):
    rid = new(); roles_w[code] = rid
    X("""insert into role (id, company_id, code, name, template_code, basis, registry_version, expansion_hash) values (%s,%s,%s,%s,'warehouse_keeper','{}','old','x')""",
      (rid, I["co"], code, code))
    for node, (lvl, appr) in TPL["warehouse_keeper"].items():
        X("insert into role_level values (%s,%s,%s,%s,%s)", (I["co"], rid, node, lvl, appr))
    with c.cursor() as cur:
        cur.executemany("insert into role_permission values (%s,%s,%s)", [(I["co"], rid, p) for p in expand(TPL["warehouse_keeper"], REG_OLD)])
    holder["uC"] |= set(expand(TPL["warehouse_keeper"], REG_OLD))
items = []
def upgrade(rid, mode="block"):
    rows_ = {r_[0]: (r_[1], r_[2]) for r_ in X("select authorization_area, level, can_approve from role_level where role_id=%s", (rid,))}
    old = {r_[0] for r_ in X("select permission from role_permission where role_id=%s", (rid,))}
    for p in sorted(set(expand(rows_)) - old):
        res_ = outcome(change_rights, holder, "upgrade", "uC", {p}, mode, enabled)
        if res_ and res_[0][0] == "held_back":
            X("insert into role_permission_hold (id, company_id, role_id, permission, reason, registry_version, created_at) values (%s,%s,%s,%s,%s,'new',now())",
              (new(), I["co"], rid, p, res_[0][1]))
        else:
            X("insert into role_permission values (%s,%s,%s)", (I["co"], rid, p))
    if X("select count(*) from role_permission_hold where company_id=%s and state='held'", (I["co"],)).fetchone()[0] and not items:
        items.append(("role_permission_held", I["co"]))
def inv220(rid):
    rows_ = {r_[0]: (r_[1], r_[2]) for r_ in X("select authorization_area, level, can_approve from role_level where role_id=%s", (rid,))}
    holds = {r_[0] for r_ in X("select permission from role_permission_hold where role_id=%s and state in ('held','ignored')", (rid,))}
    stored = {r_[0] for r_ in X("select permission from role_permission where role_id=%s", (rid,))}
    return stored == set(expand(rows_)) - holds
upgrade(roles_w["w1"]); upgrade(roles_w["w2"])
held = X("select role_id, permission from role_permission_hold where company_id=%s and state='held' order by role_id", (I["co"],)).fetchall()
check("H12 an upgrade gain that would break block mode becomes a hold, the stored set is the expansion minus the holds (INV-220), one work item per company",
      sorted(p for _, p in held) == ["PostGoodsReceipt", "PostGoodsReceipt"] and inv220(roles_w["w1"]) and inv220(roles_w["w2"])
      and "PostGoodsReceipt" not in {r_[0] for r_ in X("select permission from role_permission where role_id=%s", (roles_w["w1"],))} and items == [("role_permission_held", I["co"])])
expect("H13 a granted hold needs the person who decided, and one permission has one hold in force",
       lambda cx: cx.execute("update role_permission_hold set state='granted', decided_at=now() where role_id=%s", (roles_w["w1"],)), True, "ck_role_permission_hold_person")
def confirm_hold(rid, p, user="uB"):
    """ConfirmRolePermissionHold: a change of rights, so the checks run again; refused while the conflict lasts."""
    r_ = outcome(change_rights, holder, "ConfirmRolePermissionHold", "uC", {p}, "block", enabled)
    if r_ == "segregation_conflict":
        return r_
    X("update role_permission_hold set state='granted', decided_at=now(), decided_by_user_id=%s where role_id=%s and permission=%s and state='held'", (I[user], rid, p))
    X("insert into role_permission values (%s,%s,%s)", (I["co"], rid, p))
    return None
first = confirm_hold(roles_w["w1"], "PostGoodsReceipt")
holder["uC"] -= BUYER                                    # the buyer role ends
second = confirm_hold(roles_w["w1"], "PostGoodsReceipt")
check("H14 confirming a hold re-runs the checks: refused while uC is also a buyer, granted once that ends; INV-220 holds",
      first == "segregation_conflict" and second is None and inv220(roles_w["w1"]))
X("update role_permission_hold set state='ignored', decided_at=now(), decided_by_user_id=%s where role_id=%s and state='held'", (I["uB"], roles_w["w2"]))
ignored_withheld = inv220(roles_w["w2"]) and "PostGoodsReceipt" not in {r_[0] for r_ in X("select permission from role_permission where role_id=%s", (roles_w["w2"],))}
X("update role_level set level='post' where role_id=%s and authorization_area='sales_order'", (roles_w["w2"],))   # UpdateRole changes levels
X("update role_permission_hold set state='ended', decided_at=now() where role_id=%s and state in ('held','ignored')", (roles_w["w2"],))
rows_w2 = {r_[0]: (r_[1], r_[2]) for r_ in X("select authorization_area, level, can_approve from role_level where role_id=%s", (roles_w["w2"],))}
gain = set(expand(rows_w2)) - {r_[0] for r_ in X("select permission from role_permission where role_id=%s", (roles_w["w2"],))}
if outcome(change_rights, holder, "UpdateRole", "uC", gain, "block", enabled) != "segregation_conflict":
    with c.cursor() as cur:
        cur.executemany("insert into role_permission values (%s,%s,%s)", [(I["co"], roles_w["w2"], p) for p in gain])
check("H15 an ignored hold stays withheld; an UpdateRole that changes levels ends it and stores the full expansion under the checks",
      ignored_withheld and "PostGoodsReceipt" in gain and inv220(roles_w["w2"]))

ORG_FIELDS = {"department_id", "manager_partner_id", "user_account_id"}
def update_partner(payload, via="UpdatePartner"):
    """UpdatePartner, CreatePartner and change proposals refuse the organization columns (ADR-0054 rule 6)."""
    return "employee_organization_command_required" if ORG_FIELDS & set(payload.get("employee_profile", {})) else None
check("H16 UpdatePartner, CreatePartner and a change proposal that name a department, manager or user link are refused",
      update_partner({"employee_profile": {"manager_partner_id": "x"}}) == "employee_organization_command_required"
      and update_partner({"employee_profile": {"user_account_id": "x"}}, "CreatePartner") == "employee_organization_command_required"
      and update_partner({"employee_profile": {"department_id": "x"}}, "change_proposal") == "employee_organization_command_required"
      and update_partner({"employee_profile": {"job_title": "x"}}) is None)
def resolver(cx, user):
    args = {"co": I["co"], "u": I[user]}
    return tuple(frozenset(r_[0] for r_ in cx.execute(q, args)) for q in (TEAM, UNDER))
def organization_command(caller, perms, sql, args):
    """ADR-0054 rule 6: full on organization; refused when the caller's resolver result changes, unless all their
    assignments in force have owner scope company. Run in a transaction that the lab always rolls back."""
    if "UpdateEmployeeOrganization" not in perms:
        return "permission_denied"
    exempt = X("""select coalesce(bool_and(owner_scope_read = 'company'), false) from role_assignment
                  where company_id=%s and user_account_id=%s and valid_from <= %s and (valid_to is null or valid_to >= %s)""",
               (I["co"], I[caller], TODAY, TODAY)).fetchone()[0]
    cx = conn()
    try:
        before = resolver(cx, caller)
        cx.execute(sql, args)
        after = resolver(cx, caller)
        cx.rollback()
    finally:
        cx.close()
    return None if before == after or exempt else "organization_self_change"
SET_MANAGER = "update employee_profile set manager_partner_id=%s where partner_id=%s"
SET_DEPT = "update employee_profile set department_id=%s where partner_id=%s"
check("H17 UpdateEmployeeOrganization needs full on organization; a change that leaves the caller's reach alone is allowed",
      organization_command("uA", EXP["sales_manager"], SET_DEPT, (I["dNorth"], I["eC"])) == "permission_denied"
      and organization_command("uA", EXP["it_administrator"], SET_DEPT, (I["dNorth"], I["eC"])) is None)
check("H18 no self-change by effect: setting an employee's manager to the caller is refused",
      organization_command("uA", EXP["it_administrator"], SET_MANAGER, (I["eA"], I["eC"])) == "organization_self_change")
check("H19 no self-change by effect: moving an employee into the caller's department is refused",
      organization_command("uA", EXP["it_administrator"], SET_DEPT, (I["dSales"], I["eB"])) == "organization_self_change")
check("H20 no self-change by effect: reparenting a department under one the caller manages is refused",
      organization_command("uM", EXP["it_administrator"], "update department set parent_id=%s where id=%s", (I["dNorth"], I["dOther"])) == "organization_self_change")
check("H21 a caller whose assignments all have owner scope company is exempt, e.g. a sole owner linking or moving their own profile",
      organization_command("uC", EXP["owner"], SET_DEPT, (I["dSales"], I["eC"])) is None)

# ---------------------------------------------------------------- G: approval engine (ADR-0055)
class Refused(Exception):
    pass

def fill(places, cand, exclude=frozenset()):
    """Can the places (stage id, count) be filled by distinct people, each a candidate of the stage they fill?
    A bipartite matching (augmenting paths), as ADR-0055 rules 4 and 7 count."""
    slots = [sid for sid, k in places for _ in range(k)]
    match = {}                                             # person -> slot index
    def augment(i, seen):
        for p in sorted(cand.get(slots[i], set()) - set(exclude)):
            if p in seen:
                continue
            seen.add(p)
            if p not in match or augment(match[p], seen):
                match[p] = i
                return True
        return False
    return all(augment(i, set()) for i in range(len(slots)))

class Engine:
    """Pure model of ADR-0055 rules 3-13. People: dict person -> {roles: {role: branches or None}, approve: set of types,
    read: branches or None, human: bool, active: bool}. Delegations: list of (id, delegator, substitute, start, end)."""
    def __init__(self, pools, selectors, procedures, people, delegations=(), small_mode=False, inactive_pools=()):
        self.pools, self.selectors, self.procedures = pools, selectors, list(procedures)
        self.people, self.delegations, self.small_mode = people, list(delegations), small_mode
        self.inactive_pools = set(inactive_pools)
        self.exceptions, self.work_items = [], []

    # rule 3
    def select_pool(self, dtype, inputs):
        rows = sorted(self.selectors.get(dtype, []), key=lambda r: r[0])
        for pos, cond, pool in rows:
            if pos > 0 and inputs.get(cond):
                return pool
        return next((pool for pos, cond, pool in rows if pos == 0), "general")

    # rule 5
    def plan(self, pool, rank):
        if rank is None or pool in self.inactive_pools:
            return []
        return [s for s in sorted(self.pools.get(pool, []), key=lambda s: s["sequence"]) if s.get("active", True) and s["min_rank"] <= rank]

    def approvals_needed(self, pool, rank):
        return sum(s["k"] for s in self.plan(pool, rank))

    # rule 4 and rule 3 save checks; also run by the procedure commands of ADR-0043
    def save_check(self):
        if "general" in self.inactive_pools:
            raise Refused("approval_pool_invalid: general deactivated")
        low = min(self.procedures)
        for code, stages in self.pools.items():
            if code in self.inactive_pools:
                continue
            act = sorted((s for s in stages if s.get("active", True)), key=lambda s: s["sequence"])
            if not act:
                raise Refused("approval_pool_invalid: an active pool without an active stage")
            if any(a["min_rank"] > b["min_rank"] for a, b in zip(act, act[1:])):
                raise Refused("approval_pool_invalid: min_rank decreases")
            if act[0]["min_rank"] > low:
                raise Refused("approval_pool_invalid: a rank requires no stage")
        for dtype, rows in self.selectors.items():
            if any(pool in self.inactive_pools for _, _, pool in rows):
                raise Refused("approval_pool_invalid: a selector names an inactive pool")
            default = next(p for pos, c, p in rows if pos == 0)
            for pos, cond, pool in rows:
                if pos > 0 and any(self.approvals_needed(pool, r) < self.approvals_needed(default, r) for r in self.procedures):
                    raise Refused("approval_pool_invalid: selector loosens")

    def set_procedures(self, ranks):
        old, self.procedures = self.procedures, list(ranks)
        try:
            self.save_check()
        except Refused:
            self.procedures = old
            raise

    def member(self, person, stage, scope):
        """scope None: any scope (the save-time count)."""
        info = self.people[person]
        if not info.get("active", True):
            return False
        if person in stage.get("users", ()):
            return True
        for role in stage.get("roles", ()):
            if role in info["roles"]:
                br = info["roles"][role]
                if scope is None or stage.get("binding", "document_scope") == "company" or br is None or scope in br:
                    return True
        return False

    def direct(self, p, stage, doc_type, scope):
        pi = self.people[p]
        return (pi.get("human", True) and self.member(p, stage, scope) and (doc_type in pi["approve"] if doc_type else bool(pi["approve"]))
                and (scope is None or pi["read"] is None or scope in pi["read"]))

    # rule 4: satisfiable by distinct people, leaving the preparer out unless small-company mode
    def unsatisfiable(self, pool):
        out = []
        for r in self.procedures:
            stages = self.plan(pool, r)
            cand = {s["id"]: {p for p in self.people if self.direct(p, s, None, None)} for s in stages}
            places = [(s["id"], s["k"]) for s in stages]
            everyone = set().union(*cand.values()) if cand else set()
            ok = fill(places, cand) and (self.small_mode or all(fill(places, cand, {p}) for p in everyone))
            if not ok:
                out.append(("approval_stage_unsatisfiable", r))
        return out

    def submit(self, doc, rank, today):
        pool = self.select_pool(doc["type"], doc["inputs"])
        plan = self.plan(pool, rank)
        if rank is not None and not plan:
            raise Refused("approval_plan_empty")
        cont = doc.get("continue_round") and doc.get("decision", {}).get("pool") == pool and doc.get("round_open")
        if not cont:
            doc["round"] = doc.get("round", 0) + 1
            doc["since"] = {}
        doc["decision"] = {"pool": pool, "rank": rank, "plan": plan, "day": today, "round": doc["round"]}
        doc["continue_round"] = False
        doc["round_open"] = bool(plan)
        doc["state"] = "pending_approval" if plan else "approved"
        self.refresh_item(doc, today)
        checks = []
        if plan:
            places = [(s["id"], s["k"] - len(self.counted(doc, s["id"]))) for s in plan]
            if not fill(places, {s["id"]: self.candidates(doc, s, today) for s in plan}):
                checks.append(("approval_stage_unsatisfiable", rank))
        return checks

    def counted(self, doc, stage_id=None):
        """Rule 8: approved rows of the current round at stages of the current plan."""
        in_plan = {s["id"] for s in doc["decision"]["plan"]}
        return [a for a in doc["approvals"] if a["round"] == doc.get("round") and a["decision"] == "approved"
                and a["stage"] in in_plan and (stage_id is None or a["stage"] == stage_id)]

    def current_stage(self, doc):
        for s in doc["decision"]["plan"]:
            if len(self.counted(doc, s["id"])) < s["k"]:
                return s
        return None

    def due(self, doc, stage):
        """Rule 12: the day the stage became current plus its due days."""
        return doc["since"][stage["id"]] + timedelta(days=stage["due_days"])

    def stage_live(self, doc, stage):
        return stage.get("active", True) and doc["decision"]["pool"] not in self.inactive_pools

    def writers(self, doc):
        out = set()
        for v in doc["versions"]:
            if v["actor_kind"] == "human":
                out.add(v["actor"])
            out |= {v.get("on_behalf_of"), v.get("origin_on_behalf_of")} - {None}
        return out

    def agent_writers(self, doc):
        return {v.get("origin_on_behalf_of") for v in doc["versions"]} | {v["on_behalf_of"] for v in doc["versions"] if v["actor_kind"] == "agent"} - {None}

    def counted_humans(self, doc):
        return {a["approver"] for a in self.counted(doc)} | {a["delegated_from"] for a in self.counted(doc)} - {None}

    def candidates(self, doc, stage, today, overdue_ok=True):
        """People who meet conditions 1-7 for the stage now (rule 7), for rule 4's Submit check, condition 8 and rule 12."""
        if not self.stage_live(doc, stage):
            return set()
        out = set()
        for p in self.people:
            try:
                self.eligible(p, doc, today, stage=stage, check_strand=False)
                out.add(p)
            except Refused:
                pass
        return out

    def eligible(self, person, doc, today, delegated_from=None, stage=None, check_strand=True):
        info, stage = self.people[person], stage or self.current_stage(doc)
        if not info.get("human", True):
            raise Refused("human_only")
        if not self.stage_live(doc, stage):
            raise Refused("approver_not_eligible")
        sc, dt = doc["scope"], doc["type"]
        dfrom, escalated = None, False
        if not self.direct(person, stage, dt, sc):        # direct membership wins (rule 7)
            subs = sorted((i, d) for i, d, s, a, b in self.delegations
                          if s == person and a <= today <= b and self.people[d].get("active", True) and self.direct(d, stage, dt, sc))
            if delegated_from is not None:
                subs = [x for x in subs if x[1] == delegated_from]
            if subs:
                dfrom = subs[0][1]                          # the lowest delegation ID when none is named
            elif delegated_from is None and stage.get("escalation_role") and stage["id"] in doc["since"] and today > self.due(doc, stage) \
                    and stage["escalation_role"] in info["roles"] and dt in info["approve"] and info.get("active", True):
                escalated = True
            else:
                raise Refused("approver_not_eligible")
        humans = {person} | ({dfrom} if dfrom else set())
        if humans & self.agent_writers(doc):
            raise Refused("segregation_of_duties")      # hard floor, never lifted
        own = humans & self.writers(doc)
        if own and not self.small_mode:
            raise Refused("segregation_of_duties")
        if humans & self.counted_humans(doc):
            raise Refused("approval_already_given")
        if check_strand:                                  # condition 8
            plan = doc["decision"]["plan"]
            i = plan.index(stage)
            open_places = [(s["id"], s["k"] - len(self.counted(doc, s["id"]))) for s in plan[i:]]
            cand = {s["id"]: self.candidates(doc, s, today) for s in plan[i:]}
            after = [(sid, k - 1 if sid == stage["id"] else k) for sid, k in open_places]
            if fill(open_places, cand) and not fill(after, cand, humans):
                raise Refused("approval_would_strand_stage")
        return stage, dfrom, escalated, bool(own)

    def approve(self, person, doc, today, decision="approved", delegated_from=None):
        if doc["state"] != "pending_approval":
            raise Refused("invalid_state_transition")
        stage, dfrom, esc, own = self.eligible(person, doc, today, delegated_from, check_strand=(decision == "approved"))
        doc["approvals"].append({"version": doc["version"], "round": doc["round"], "stage": stage["id"], "approver": person,
                                 "delegated_from": dfrom, "escalated": esc, "decision": decision})
        if own:
            self.exceptions.append(("own_document_approval", person, doc["id"]))
        if decision == "rejected":
            doc["state"] = "draft"; doc["round_open"] = False
        elif self.current_stage(doc) is None:
            doc["state"] = "approved"                     # the round stays open until Post (rule 8)
        self.refresh_item(doc, today)

    def reject(self, person, doc, today):
        self.approve(person, doc, today, "rejected")

    def fallback_reason(self, doc, stage, today):
        if not stage.get("active", True):
            return "stage_inactive"
        if doc["decision"]["pool"] in self.inactive_pools:
            return "pool_inactive"
        members = [p for p in self.people if self.direct(p, stage, doc["type"], doc["scope"]) or
                   (any(p in stage.get("users", ()) or r in self.people[p]["roles"] for r in stage.get("roles", ())) and not self.people[p].get("active", True))]
        if not members:
            return "members_left"
        if all(not self.people[p].get("active", True) for p in members):
            return "members_disabled"
        live = [p for p in members if self.people[p].get("active", True)]
        if all(p in self.writers(doc) and (not self.small_mode or p in self.agent_writers(doc)) for p in live):
            return "members_all_writers"
        return "members_all_counted"

    def refresh_item(self, doc, today):
        """Rules 12-13: one item for the current stage; owner company_owner with a reason when nobody could approve."""
        self.work_items = [w for w in self.work_items if w["doc"] != doc["id"]]
        if doc["state"] == "pending_approval":
            s = self.current_stage(doc)
            doc["since"].setdefault(s["id"], today)
            item = {"doc": doc["id"], "kind": "approval_pending", "owner_stage": s["id"], "owner": "approval_stage", "due": self.due(doc, s), "reason": None}
            if not self.candidates(doc, s, today):
                item["owner"], item["reason"] = "company_owner", self.fallback_reason(doc, s, today)
            self.work_items.append(item)

    def item(self, doc):
        return next((w for w in self.work_items if w["doc"] == doc["id"]), None)

    def update(self, doc, actor, kind="human", on_behalf_of=None, origin=None):
        doc["version"] += 1
        doc["versions"].append({"actor_kind": kind, "actor": actor, "on_behalf_of": on_behalf_of, "origin_on_behalf_of": origin})
        doc["state"] = "draft"; doc["round_open"] = False   # an edit ends the round
        self.work_items = [w for w in self.work_items if w["doc"] != doc["id"]]

    def post(self, doc):
        assert doc["state"] == "approved"
        doc["state"] = "posted"; doc["round_open"] = False  # Post ends the round

    def post_check(self, doc, new_rank, today, new_inputs=None):
        """ADR-0028 rule 14 with stages: approvals stand when the new plan is satisfied in the round."""
        if new_inputs is not None:
            doc["inputs"] = new_inputs
        plan = self.plan(self.select_pool(doc["type"], doc["inputs"]), new_rank)
        if all(len(self.counted(doc, s["id"])) >= s["k"] for s in plan):
            return "stands"
        doc["continue_round"] = True
        doc["state"] = "draft"
        return "approval_context_changed"

def ok_call(fn, *a, **k):
    try:
        fn(*a, **k); return None
    except Refused as e:
        return str(e).split(":")[0]

def stage(i, seq, rank, k, roles=(), users=(), esc=None, binding="document_scope", due=2):
    return {"id": i, "sequence": seq, "min_rank": rank, "k": k, "roles": roles, "users": users, "escalation_role": esc, "binding": binding, "due_days": due}

def people():
    P = {}
    for p, roles in (("A", {"R1": None}), ("B", {"R1": {"b1"}}), ("C", {"R2": None}), ("D", {"R2": None}), ("E", {"R2": None}),
                     ("F", {"R1": None, "R2": None}), ("ESC", {"BOSS": None}), ("W", {"R1": None}), ("OUT", {"R1": {"b2"}}), ("NOAP", {"R1": None})):
        P[p] = {"roles": roles, "approve": {"purchase_order", "bank_payment", "purchase_invoice"}, "read": None, "human": True}
    P["NOAP"]["approve"] = set()
    P["AGENT"] = {"roles": {"R1": None}, "approve": {"purchase_order"}, "read": None, "human": False}
    P["U9"] = {"roles": {}, "approve": {"purchase_order"}, "read": None, "human": True}
    return P

def fresh_pools():
    return {"po": [stage("s1", 1, 10, 1, roles=("R1",)), stage("s2", 2, 20, 2, roles=("R2",), esc="BOSS"), stage("s3", 3, 30, 1, users=("U9",))],
            "general": [stage("g1", 1, 10, 1, roles=("R1",)), stage("g2", 2, 20, 1, roles=("R2",))],
            "expense": [stage("x1", 1, 10, 1, roles=("R1",)), stage("x2", 2, 20, 1, roles=("R2",)), stage("x3", 3, 20, 1, roles=("R2",)),
                        stage("x4", 4, 30, 1, users=("U9",))]}
POOLS = fresh_pools()
SEL = {"purchase_order": [(0, None, "po")], "bank_payment": [(0, None, "general"), (1, "is_direct_expense", "expense")],
       "purchase_invoice": [(0, None, "po"), (1, "is_direct_expense", "expense")]}
PROC = [10, 20, 30]
T0 = date(2026, 4, 1)

def new_doc(author="W", dtype="purchase_order", scope="b1", inputs=None):
    return {"id": new(), "type": dtype, "scope": scope, "inputs": inputs or {}, "version": 1, "state": "draft", "approvals": [],
            "versions": [{"actor_kind": "human", "actor": author, "on_behalf_of": None, "origin_on_behalf_of": None}]}

eng = Engine(POOLS, SEL, PROC, people())
check("G1 rank selects a prefix of stages: none, 10, 15, 20, 30",
      [[s["id"] for s in eng.plan("po", r)] for r in (None, 10, 15, 20, 30)] == [[], ["s1"], ["s1"], ["s1", "s2"], ["s1", "s2", "s3"]])
mono = True
for _ in range(500):
    n = rnd.randint(1, 5); ranks = sorted(rnd.choice([10, 20, 30, 40]) for _ in range(n))
    pool = [stage(f"r{i}", i + 1, ranks[i], rnd.randint(1, 3)) for i in range(n)]
    e2 = Engine({"p": pool}, {}, [10, 20, 30, 40], {})
    counts = [e2.approvals_needed("p", r) for r in (None, 10, 20, 30, 40)]
    mono &= all(a <= b for a, b in zip(counts, counts[1:]))
check("G2 monotonic: over 500 random pools a higher rank never needs fewer approvals", mono)
bad1 = Engine({"p": [stage("a", 1, 20, 1, roles=("R1",)), stage("b", 2, 10, 1, roles=("R1",))]}, {}, PROC, people())
bad2 = Engine({"p": [stage("a", 1, 20, 1, roles=("R1",))]}, {}, PROC, people())
check("G3 save checks: decreasing min_rank, and a rank that requires no stage, give approval_pool_invalid",
      ok_call(bad1.save_check) == "approval_pool_invalid" and ok_call(bad2.save_check) == "approval_pool_invalid" and ok_call(eng.save_check) is None)
loose = Engine({**POOLS, "expense": [stage("x1", 1, 10, 1, roles=("R1",))]}, SEL, PROC, people())
check("G4 a selector that sends a riskier document to a pool with fewer approvals is refused", ok_call(loose.save_check) == "approval_pool_invalid")
check("G5 the selector: direct-expense payments and purchase invoices go to expense, others to their default",
      eng.select_pool("bank_payment", {"is_direct_expense": True}) == "expense" and eng.select_pool("bank_payment", {}) == "general"
      and eng.select_pool("purchase_invoice", {}) == "po" and eng.select_pool("stock_count", {}) == "general")

d = new_doc(); eng.submit(d, 30, T0)
check("G6 submit at rank 30: pending, current stage s1, one work item owned by the stage",
      d["state"] == "pending_approval" and eng.current_stage(d)["id"] == "s1"
      and [(w["owner_stage"], w["owner"]) for w in eng.work_items if w["doc"] == d["id"]] == [("s1", "approval_stage")])
check("G7 the author is not eligible (writer exclusion)", ok_call(eng.approve, "W", d, T0) == "segregation_of_duties")
check("G8 a non-member, a member without the Approve permission, a member outside the document's scope, an agent",
      [ok_call(eng.approve, p, d, T0) for p in ("C", "NOAP", "OUT", "AGENT")] == ["approver_not_eligible", "approver_not_eligible", "approver_not_eligible", "human_only"])
check("G8b F is needed at s2 only if nobody else can fill it: here C, D and E can, so F may approve s1", ok_call(eng.approve, "F", d, T0) is None)
check("G9 stage s1 complete after one approval; s2 is current and its work item replaced s1's",
      eng.current_stage(d)["id"] == "s2" and [w["owner_stage"] for w in eng.work_items if w["doc"] == d["id"]] == ["s2"])
check("G10 the s1 approver cannot approve s2 too (one stage per person)", ok_call(eng.approve, "F", d, T0) == "approval_already_given")
eng.approve("C", d, T0)
check("G11 k of n: one of two approvals leaves s2 current, and the same person twice is refused",
      eng.current_stage(d)["id"] == "s2" and ok_call(eng.approve, "C", d, T0) == "approval_already_given")
eng.approve("D", d, T0)
check("G12 s2 complete with two distinct approvers; s3 (a user member) is current", eng.current_stage(d)["id"] == "s3")
eng.approve("U9", d, T0)
check("G13 the last stage completes the document: approved, no open work item",
      d["state"] == "approved" and not [w for w in eng.work_items if w["doc"] == d["id"]])
check("G14 INV-224: no person counted twice in the round", len({a["approver"] for a in eng.counted(d)}) == len(eng.counted(d)) == 4)

d2 = new_doc(); eng.submit(d2, 20, T0); eng.approve("A", d2, T0)
eng.update(d2, "W"); eng.submit(d2, 20, T0)
check("G15 an edit after s1 voids the approval and ends the round; resubmission needs s1 again", eng.current_stage(d2)["id"] == "s1" and eng.counted(d2) == [])
eng.update(d2, "B")
eng.submit(d2, 20, T0)
check("G16 an editor of a later version is excluded as well as the author",
      ok_call(eng.approve, "B", d2, T0) == "segregation_of_duties" and ok_call(eng.approve, "W", d2, T0) == "segregation_of_duties")
eng.approve("A", d2, T0); eng.approve("C", d2, T0); eng.reject("D", d2, T0)
check("G17 a rejection at s2 returns the document to draft and closes the work item",
      d2["state"] == "draft" and not [w for w in eng.work_items if w["doc"] == d2["id"]])
eng.submit(d2, 20, T0)
check("G18 resubmission after a rejection starts a new round at s1; earlier approvals do not count, so A may approve again (condition 6 reads this round only)",
      eng.current_stage(d2)["id"] == "s1" and eng.counted(d2) == [] and ok_call(eng.approve, "A", d2, T0) is None)

d3 = new_doc(); eng.submit(d3, 10, T0); eng.approve("A", d3, T0)
check("G19 rank 10 approved after s1", d3["state"] == "approved")
check("G20 rank falls at Post: the approvals stand", eng.post_check(d3, 10, T0) == "stands")
r = eng.post_check(d3, 20, T0)
eng.submit(d3, 20, T0)
check("G21 rank rises at Post: approval_context_changed; resubmission continues the round, s1 kept and s2 pending",
      r == "approval_context_changed" and eng.current_stage(d3)["id"] == "s2" and len(eng.counted(d3, "s1")) == 1)
eng.approve("C", d3, T0); eng.approve("D", d3, T0); eng.post(d3)
rd = d3["round"]
d3["state"] = "draft"; eng.submit(d3, 10, T0)
check("G21b Post ends the round: a later submission is a new round and counts nothing from before", d3["round"] == rd + 1 and eng.counted(d3) == [])
pay = new_doc(dtype="bank_payment"); eng.submit(pay, 20, T0); eng.approve("A", pay, T0); eng.approve("C", pay, T0)
r = eng.post_check(pay, 20, T0, new_inputs={"is_direct_expense": True}); rd = pay["round"]
eng.submit(pay, 20, T0)
check("G21c a pool switch on resubmission (general to expense) starts a new round: no earlier approval counts",
      r == "approval_context_changed" and pay["decision"]["pool"] == "expense" and pay["round"] == rd + 1 and eng.counted(pay) == []
      and eng.current_stage(pay)["id"] == "x1")

d4 = new_doc(); d4["versions"].append({"actor_kind": "agent", "actor": "run1", "on_behalf_of": "A", "origin_on_behalf_of": "A"}); d4["version"] = 2
eng.submit(d4, 10, T0)
check("G22 the human an agent run acted for is excluded (ADR-0017 rule 16)", ok_call(eng.approve, "A", d4, T0) == "segregation_of_duties")
d5 = new_doc(); d5["versions"].append({"actor_kind": "system", "actor": "consumer", "on_behalf_of": "E", "origin_on_behalf_of": "E"}); d5["version"] = 2
eng.submit(d5, 20, T0); eng.approve("A", d5, T0)
check("G23 a consumer version carrying an origin run excludes that run's human at a later stage", ok_call(eng.approve, "E", d5, T0) == "segregation_of_duties")

eng.delegations = [(7, "C", "S1", date(2026, 4, 1), date(2026, 4, 5))]
eng.people["S1"] = {"roles": {}, "approve": set(), "read": {"b9"}, "human": True}
d6 = new_doc(); eng.submit(d6, 20, T0); eng.approve("A", d6, T0)
eng.approve("S1", d6, date(2026, 4, 5))
a = eng.counted(d6, "s2")[0]
check("G24 a substitute approves inside the window, recorded with delegated_from", a["approver"] == "S1" and a["delegated_from"] == "C")
check("G25 the delegator cannot then approve the same round (counted through the substitute)", ok_call(eng.approve, "C", d6, T0) == "approval_already_given")
d7 = new_doc(); eng.submit(d7, 20, T0); eng.approve("A", d7, T0)
check("G26 after the window the substitute is not eligible", ok_call(eng.approve, "S1", d7, date(2026, 4, 6)) == "approver_not_eligible")
d8 = new_doc(author="C"); eng.submit(d8, 20, T0); eng.approve("A", d8, T0)
check("G27 a substitute cannot approve a document the delegator wrote", ok_call(eng.approve, "S1", d8, T0) == "segregation_of_duties")
eng.delegations = [(3, "D", "S1", T0, T0), (2, "E", "S1", T0, T0), (9, "C", "D", T0, T0)]
d8b = new_doc(); eng.submit(d8b, 20, T0); eng.approve("A", d8b, T0)
eng.approve("D", d8b, T0)
check("G27b direct membership wins: D, a member who also holds a delegation from C, approves as themselves",
      eng.counted(d8b, "s2")[0]["delegated_from"] is None)
eng.approve("S1", d8b, T0)
check("G27c with no delegator named, the delegation with the lowest ID is used (E's, ID 2, not D's, ID 3, and D is counted anyway)",
      eng.counted(d8b, "s2")[1]["delegated_from"] == "E")
d8c = new_doc(); eng.submit(d8c, 20, T0); eng.approve("A", d8c, T0)
eng.approve("S1", d8c, T0, delegated_from="D")
check("G27d a named delegator is used; naming someone who did not delegate is refused",
      eng.counted(d8c, "s2")[0]["delegated_from"] == "D" and ok_call(eng.approve, "S1", d8c, T0, delegated_from="F") == "approver_not_eligible")
eng.delegations = []

d9 = new_doc(); eng.submit(d9, 20, T0); eng.approve("A", d9, T0)
check("G28 escalation: before the due date the escalation role is not eligible", ok_call(eng.approve, "ESC", d9, T0 + timedelta(days=2)) == "approver_not_eligible")
eng.approve("ESC", d9, T0 + timedelta(days=3))
check("G29 escalation: after the due date its holder is eligible and the row says so", eng.counted(d9, "s2")[0]["escalated"] is True)
d10 = new_doc(author="ESC"); eng.submit(d10, 20, T0); eng.approve("A", d10, T0)
check("G30 escalation does not lift the writer exclusion", ok_call(eng.approve, "ESC", d10, T0 + timedelta(days=5)) == "segregation_of_duties")
d9b = new_doc(); eng.submit(d9b, 20, T0); eng.approve("A", d9b, T0 + timedelta(days=3))
check("G30b a stage is due on the day it became current plus due_days: s2 became current on day 3, so it is due on day 5, not day 2",
      eng.item(d9b)["due"] == T0 + timedelta(days=5) and ok_call(eng.approve, "ESC", d9b, T0 + timedelta(days=5)) == "approver_not_eligible"
      and ok_call(eng.approve, "ESC", d9b, T0 + timedelta(days=6)) is None)

small = Engine(POOLS, SEL, PROC, people(), small_mode=True)
d11 = new_doc(author="A"); small.submit(d11, 10, T0); small.approve("A", d11, T0)
check("G31 small-company mode: the author approves their own document and an exception is recorded",
      d11["state"] == "approved" and small.exceptions == [("own_document_approval", "A", d11["id"])])
d12 = new_doc(); d12["versions"].append({"actor_kind": "agent", "actor": "run1", "on_behalf_of": "A", "origin_on_behalf_of": "A"}); d12["version"] = 2
small.submit(d12, 10, T0)
check("G32 small-company mode never lifts the agent-run floor", ok_call(small.approve, "A", d12, T0) == "segregation_of_duties")

tiny = {p: v for p, v in people().items() if p in ("A", "C", "W")}
e3 = Engine(POOLS, SEL, PROC, tiny)
check("G33 approval_stage_unsatisfiable names the ranks that too few people can satisfy",
      [r for _, r in e3.unsatisfiable("po")] == [20, 30] and Engine(POOLS, SEL, PROC, people()).unsatisfiable("general") == [])
pp = {"P": {"roles": {"R1": None, "R2": None}, "approve": {"purchase_order"}, "read": None}, "Q": {"roles": {"R1": None}, "approve": {"purchase_order"}, "read": None},
      "Z": {"roles": {}, "approve": set(), "read": None}}
three = {"p": [stage("a", 1, 10, 1, roles=("R1",)), stage("b", 2, 20, 1, roles=("R2",)), stage("c", 3, 20, 1, roles=("R2",))]}
check("G33b distinct people per stage, not a head count: two R2 places with one R2 holder fail although three people exist",
      [r for _, r in Engine(three, {}, [10, 20], pp, small_mode=True).unsatisfiable("p")] == [20])
binding = Engine({"po": [stage("c1", 1, 10, 1, roles=("R1",), binding="company")]}, SEL, PROC, people())
d13 = new_doc(scope="b9"); binding.submit(d13, 10, T0)
check("G34 scope binding: outside the role's record scope a member is not eligible, unless the stage binds to the company",
      ok_call(eng.approve, "OUT", new_doc(), T0) in ("invalid_state_transition", "approver_not_eligible") and ok_call(binding.approve, "OUT", d13, T0) is None)
d14 = new_doc(); eng.submit(d14, None, T0)
check("G35 no rank: approved at Submit with no stage and no work item", d14["state"] == "approved" and not [w for w in eng.work_items if w["doc"] == d14["id"]])
open_items = {}
for w in eng.work_items:
    open_items[w["doc"]] = open_items.get(w["doc"], 0) + 1
check("G36 INV-204: at most one open approval item per document throughout", all(v == 1 for v in open_items.values()))

# S7: empty plans, general, procedure changes, fallback
odd = Engine({"general": [stage("g1", 1, 20, 1, roles=("R1",))]}, {}, [10, 20], people())
check("G37 a ranked decision with an empty plan is refused (approval_plan_empty); INV-230", ok_call(odd.submit, new_doc(), 10, T0) == "approval_plan_empty")
check("G38 general cannot be deactivated, and a selector may not name an inactive pool",
      ok_call(Engine(POOLS, SEL, PROC, people(), inactive_pools={"general"}).save_check) == "approval_pool_invalid"
      and ok_call(Engine(POOLS, SEL, PROC, people(), inactive_pools={"expense"}).save_check) == "approval_pool_invalid")
pe = Engine(fresh_pools(), SEL, PROC, people())
check("G39 the procedure commands re-run the pool checks: adding rank 5 below every first stage is refused, rank 40 is accepted",
      ok_call(pe.set_procedures, [5, 10, 20, 30]) == "approval_pool_invalid" and pe.procedures == PROC and ok_call(pe.set_procedures, [10, 20, 30, 40]) is None)
fb = Engine(fresh_pools(), SEL, PROC, people())
d15 = new_doc(); fb.submit(d15, 20, T0); fb.approve("A", d15, T0)
for p_ in ("C", "D", "E", "F"):
    fb.people[p_]["active"] = False
fb.refresh_item(d15, T0)
check("G40 members disabled after the plan was recorded: the item falls back to company_owner with the reason",
      (fb.item(d15)["owner"], fb.item(d15)["reason"]) == ("company_owner", "members_disabled"))
for p_ in ("C", "D", "E", "F"):
    fb.people[p_]["active"] = True
fb.refresh_item(d15, T0)
check("G41 the item returns to the stage once someone is eligible again", fb.item(d15)["owner"] == "approval_stage")
fb.pools["po"][1]["active"] = False; fb.refresh_item(d15, T0)
check("G42 a stage deactivated after the plan was recorded: nobody is eligible, reason stage_inactive",
      (fb.item(d15)["owner"], fb.item(d15)["reason"]) == ("company_owner", "stage_inactive") and ok_call(fb.approve, "C", d15, T0) == "approver_not_eligible")
fb.pools["po"][1]["active"] = True
d16 = new_doc(author="C"); d16["versions"] += [{"actor_kind": "human", "actor": a_, "on_behalf_of": None, "origin_on_behalf_of": None} for a_ in ("D", "E", "F")]
d16["version"] = 4
chk = fb.submit(d16, 20, T0)
fb.approve("A", d16, T0)
check("G43 Submit returns approval_stage_unsatisfiable when the writers leave too few people; the item then falls back with members_all_writers",
      chk == [("approval_stage_unsatisfiable", 20)] and (fb.item(d16)["owner"], fb.item(d16)["reason"]) == ("company_owner", "members_all_writers"))

# Condition 6 reads only approvals at stages of the current plan
QP = {"q": [stage("q1", 1, 10, 1, roles=("R1",)), stage("q2", 2, 20, 1, roles=("R2",)), stage("q3", 3, 30, 1, roles=("R2",))]}
qe = Engine(QP, {"purchase_order": [(0, None, "q")]}, PROC, people())
d17 = new_doc(); qe.submit(d17, 20, T0); qe.approve("A", d17, T0); qe.approve("C", d17, T0)
QP["q"][1]["active"] = False                              # q2 is deactivated after it was approved
r17 = qe.post_check(d17, 30, T0); qe.submit(d17, 30, T0)
check("G52 condition 6 reads only approvals at stages of the current plan: after q2 leaves the continued round's plan, its approver C may approve q3",
      r17 == "approval_context_changed" and [s["id"] for s in d17["decision"]["plan"]] == ["q1", "q3"] and ok_call(qe.approve, "C", d17, T0) is None
      and d17["state"] == "approved")

# S5, S6: seeded stages and the walk-throughs of ADR-0055 rule 20
SEED = {"po": [stage("std", 1, 10, 1, roles=("ACC", "CHIEF", "OWNER")), stage("sen", 2, 20, 1, roles=("CHIEF", "OWNER"))],
        "general": [stage("gstd", 1, 10, 1, roles=("ACC", "CHIEF", "OWNER")), stage("gsen", 2, 20, 1, roles=("CHIEF", "OWNER"))]}
check("G44 every seeded stage names the owner", all("OWNER" in s["roles"] for st_ in SEED.values() for s in st_))
def person(role):
    return {"roles": {role: None}, "approve": {"purchase_order"}, "read": None}
one_off = Engine(SEED, SEL, [10, 20], {"O": person("OWNER")})
one_on = Engine(SEED, SEL, [10, 20], {"O": person("OWNER")}, small_mode=True)
check("G45 one person: unsatisfiable at ranks 10 and 20 without the mode, at rank 20 only with it",
      [r for _, r in one_off.unsatisfiable("po")] == [10, 20] and [r for _, r in one_on.unsatisfiable("po")] == [20])
w1 = new_doc(author="O"); one_on.submit(w1, 10, T0); one_on.approve("O", w1, T0)
w2 = new_doc(author="O"); chk = one_on.submit(w2, 20, T0)
ok_std = ok_call(one_on.approve, "O", w2, T0)
check("G46 one person with the mode: rank 10 approved by O with an exception; rank 20 is unsatisfiable at Submit, O may approve std, then the item falls back with members_all_counted",
      w1["state"] == "approved" and ("own_document_approval", "O", w1["id"]) in one_on.exceptions and chk == [("approval_stage_unsatisfiable", 20)]
      and ok_std is None and (one_on.item(w2)["owner"], one_on.item(w2)["reason"]) == ("company_owner", "members_all_counted"))
two = {"O": person("OWNER"), "A": person("ACC")}
two_off = Engine(SEED, SEL, [10, 20], two)
check("G47 two people without the mode: rank 10 satisfiable, rank 20 not", [r for _, r in two_off.unsatisfiable("po")] == [20])
w3 = new_doc(author="A"); two_off.submit(w3, 10, T0); two_off.approve("O", w3, T0)
w4 = new_doc(author="O"); two_off.submit(w4, 10, T0); two_off.approve("A", w4, T0)
check("G48 two people without the mode: each approves the other's rank-10 document", w3["state"] == w4["state"] == "approved")
two_on = Engine(SEED, SEL, [10, 20], two, small_mode=True)
w5 = new_doc(author="A"); chk = two_on.submit(w5, 20, T0)
check("G49 EC-117: two people with the mode, rank 20 written by A: the owner's approval of std would strand sen and is refused",
      chk == [] and ok_call(two_on.approve, "O", w5, T0) == "approval_would_strand_stage")
two_on.approve("A", w5, T0); two_on.approve("O", w5, T0)
check("G50 A approves std (own document, an exception) and O approves sen: approved by two different people",
      w5["state"] == "approved" and {a_["approver"] for a_ in two_on.counted(w5)} == {"A", "O"} and ("own_document_approval", "A", w5["id"]) in two_on.exceptions)
w6 = new_doc(author="O"); two_on.submit(w6, 20, T0); two_on.approve("A", w6, T0); two_on.approve("O", w6, T0)
check("G51 rank 20 written by O: A approves std and O approves sen with an exception", w6["state"] == "approved")

# UoM simulation review 2026-11-15: a unit alias proposal is approved by a non-owner (ADR-0056 rule 20 note). The approver needs
# ApproveChangeProposal and the target command (ADR-0055 rule 7; ADR-0043 rule 12), and membership of the general pool's
# seeded standard stage with the flow review's members (ADR-0055 rule 5 notes); the templates' expansions decide the rest.
GEN_STD = ("accountant", "chief_accountant", "owner", "sales_manager", "purchasing_manager", "production_planner")
def cp_holder(t, targets):
    ok_ = "ApproveChangeProposal" in EXP[t] and set(targets) <= EXP[t]
    return {"roles": {t: None}, "approve": {"change_proposal"} if ok_ else set(), "read": None, "human": True}
GEN = {"general": [stage("gstd", 1, 10, 1, roles=GEN_STD), stage("gsen", 2, 20, 1, roles=("chief_accountant", "owner"))]}
ua = Engine(GEN, {}, [10, 20], {t: cp_holder(t, ("CreateUomAlias",)) for t in TEMPLATES})
d53 = new_doc(author="accountant", dtype="change_proposal")
chk53 = ua.submit(d53, 10, T0)
cand53 = ua.candidates(d53, d53["decision"]["plan"][0], T0)
r53a, r53b = ok_call(ua.approve, "accountant", d53, T0), ok_call(ua.approve, "chief_accountant", d53, T0)
check("G53 the accountant submits the purchase invoice agent's CreateUomAlias proposal; the eligible approvers are the chief accountant, the purchasing manager and the owner (ApproveChangeProposal, general.standard and the target command; the sales manager and the planner lack the target); the accountant is refused; the chief accountant approves it",
      chk53 == [] and cand53 == {"chief_accountant", "purchasing_manager", "owner"} and r53a == "approver_not_eligible"
      and r53b is None and d53["state"] == "approved", (sorted(cand53), r53a, r53b))

# Final simulation review 2026-11-15: an automation activation (ADR-0058 rule 24) and a loosening of a policy setting (ADR-0063 rule 3)
# each have a submitter and a different approver in the role templates (ADR-0054 rule 11 note). The registry gains the commands involved.
REG += [("SetArtifactVersionState", "configuration", "command", "Set", "master_data_change", "full"),
        ("SetArtifactCurrentVersion", "configuration", "command", "Set", "other", "full"),
        ("CreateAutomationRuleVersion", "configuration", "command", "Create", "other"),
        ("CreateDecisionTableVersion", "configuration", "command", "Create", "other"),
        ("CreateArtifactEvidence", "automation", "command", "Create", "other", "full")]
NEW_ROWS = {("chief_accountant", "change_proposal"), ("chief_accountant", "company_setting"), ("chief_accountant", "configuration"),
            ("chief_accountant", "automation")} | {(m, n) for m in ("sales_manager", "purchasing_manager", "production_planner") for n in ("configuration", "automation")}
EXP2 = {t: set(expand(TPL[t])) for t in TEMPLATES}
OLD_TPL = {t: {n: v for n, v in rows.items() if (t, n) not in NEW_ROWS} for t, rows in TPL.items()}
EXP_OLD = {t: set(expand(OLD_TPL[t])) for t in TEMPLATES}
AUTHOR = {"CreateAutomationRuleVersion", "CreateDecisionTableVersion", "CreateArtifactEvidence", "SubmitChangeProposal"}
ACT_APPROVE = {"ApproveChangeProposal", "SetArtifactVersionState"}
def holders(exp, need_):
    return {t for t in TEMPLATES if need_ <= exp[t]}
check("G54 automation activation in the templates: the owner, the chief accountant and the sales, purchasing and production managers draft, create "
      "evidence and submit; the owner and the chief accountant approve (ApproveChangeProposal and SetArtifactVersionState at full); the IT "
      "administrator drafts and rolls back but neither submits nor approves; before the review only the owner did both, so nobody could approve the "
      "owner's draft",
      holders(EXP2, AUTHOR) == {"owner", "chief_accountant", "sales_manager", "purchasing_manager", "production_planner"}
      and holders(EXP2, ACT_APPROVE) == {"owner", "chief_accountant"} and holders(EXP_OLD, AUTHOR) == holders(EXP_OLD, ACT_APPROVE) == {"owner"}
      and {"CreateAutomationRuleVersion", "SetArtifactCurrentVersion"} <= EXP2["it_administrator"] and "SubmitChangeProposal" not in EXP2["it_administrator"],
      (sorted(holders(EXP2, AUTHOR)), sorted(holders(EXP2, ACT_APPROVE))))
def cp2(t, targets):
    ok_ = "ApproveChangeProposal" in EXP2[t] and set(targets) <= EXP2[t]
    return {"roles": {t: None}, "approve": {"change_proposal"} if ok_ else set(), "read": None, "human": True}
act = Engine(GEN, {}, [10, 20], {t: cp2(t, ("SetArtifactVersionState",)) for t in TEMPLATES})
d54o, d54p = new_doc(author="owner", dtype="change_proposal"), new_doc(author="purchasing_manager", dtype="change_proposal")
act.submit(d54o, 10, T0); act.submit(d54p, 10, T0)
c54o, c54p = act.candidates(d54o, d54o["decision"]["plan"][0], T0), act.candidates(d54p, d54p["decision"]["plan"][0], T0)
r54a, r54b = ok_call(act.approve, "owner", d54o, T0), ok_call(act.approve, "chief_accountant", d54o, T0)
check("G55 an activation the owner drafted and submitted goes to the chief accountant, who approves it, and the owner is refused "
      "(segregation_of_duties); one the purchasing manager submitted may go to the owner or the chief accountant (ADR-0058 rule 24 note)",
      c54o == {"chief_accountant"} and c54p == {"owner", "chief_accountant"} and r54a == "segregation_of_duties" and r54b is None
      and d54o["state"] == "approved", (sorted(c54o), sorted(c54p), r54a, r54b))
LVL = lambda tpl, t, leaf: ORDER[effective(tpl[t], leaf)[0]]
SUBMIT_P = lambda exp, tpl: {t for t in TEMPLATES if {"SubmitChangeProposal", "UpdateCompanySetting"} <= exp[t] and LVL(tpl, t, "policy") >= ORDER["edit"]}
APPROVE_P = lambda exp, tpl: {t for t in TEMPLATES if {"ApproveChangeProposal", "UpdateCompanySetting"} <= exp[t] and LVL(tpl, t, "policy") == ORDER["full"]}
def lp(t):
    ok_ = t in APPROVE_P(EXP2, TPL)
    return {"roles": {t: None}, "approve": {"change_proposal"} if ok_ else set(), "read": None, "human": True}
loose = Engine(GEN, {}, [10, 20], {t: lp(t) for t in TEMPLATES})
d56 = new_doc(author="chief_accountant", dtype="change_proposal")
loose.submit(d56, 10, T0)
c56 = loose.candidates(d56, d56["decision"]["plan"][0], T0)
r56a, r56b = ok_call(loose.approve, "chief_accountant", d56, T0), ok_call(loose.approve, "owner", d56, T0)
check("G56 a loosening of auto_post.max_error_rate (leaf policy): the chief accountant now submits it (change_proposal edit, company_setting "
      "edit, policy full) as the owner does; the approvers hold policy at full; she is refused on her own proposal and the owner approves it; "
      "before the review only the owner could submit (ADR-0063 rule 3; ADR-0054 rule 11 note)",
      SUBMIT_P(EXP2, TPL) == APPROVE_P(EXP2, TPL) == {"owner", "chief_accountant"} and SUBMIT_P(EXP_OLD, OLD_TPL) == {"owner"}
      and c56 == {"owner"} and r56a == "segregation_of_duties" and r56b is None and d56["state"] == "approved",
      (sorted(SUBMIT_P(EXP2, TPL)), sorted(APPROVE_P(EXP2, TPL)), sorted(c56), r56a, r56b))

c.close()
passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
