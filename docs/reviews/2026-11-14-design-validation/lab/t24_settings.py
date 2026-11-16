"""Scenario: configurable policy settings (ADR-0063), on the settings catalog, as pure functions and on the DDL drafts.

Run: python t24_settings.py [--load]
  The catalog checks (part C) and the pure checks (part A) always run. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway
  database: load_all.py drops and rebuilds schemas nativeflows and types there and loads every DDL file of design/, and the
  database checks (part D) run. NATIVEFLOWS_DOCS points at the docs/ tree (default ~/Projects/NativeFlows/docs); NATIVEFLOWS_LAB_DIR at
  lab.py and load_all.py (default: this file's directory). PGPASSWORD holds the database password.

C: the catalog settings.csv: constant field count, unique keys, scope, storage, type, a core default or fail-closed,
   bounds, direction and a known leaf on every row, defaults within bounds, order directions listing every allowed value,
   every setting key ADR-0063 names catalogued, every catalog key named by an ADR its row's source cites, no country content; the ADR's invariant, edge case,
   work item kind and leaf rows, their codes unique and the tables they name defined; the DS-04 codes they use.
A: rule 3's change path (tighten at once by one person, loosen only through another person's approved proposal, neutral
   directly, outdating dependent auto-post evidence, period starts, scope overrides); rule 4's bounds as a property test
   over random values and orders between settings; rule 10's acting ceiling (the rule of three against the exact
   binomial bound); the gates of rules 8 (LLM-originated rules) and 9 (bank charges); rule 11's wake-up modes, whose
   default reproduces today's starts; rule 12's drift action; rule 15's per-request personal-data gate; rule 16's declared
   projections; rule 21's breaker and flood guard; rule 22's product codes; rule 25's narrative bound; rule 26's day 00
   and best-before readings; rule 27's near-duplicate check.
D: with --load, on all DDL: every catalog row loads into setting_definition under its checks, and broken definitions are
   refused; setting values outside their bounds are refused by the database, agreeing with the pure check on random
   values; a loosening without a proposal or approved by its submitter is refused; values are append-only; installation
   rows have no company; row-level security is forced with the installation exception; extension point ceilings and
   decision kinds; the suspension pair of data_processing_permission; the new columns and values of DS-05, DS-20, DS-28-34.
Not covered: commands, the gateway, the upgrade job, the UI.
"""
import csv, glob, hashlib, json, math, os, random, re, sys
from datetime import date, timedelta
from decimal import Decimal as Dec

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import RESULTS, conn, expect, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
CAT = os.path.join(DOCS, "catalogs")
ADR = os.path.join(DOCS, "adr", "0063-configurable-policy-settings.md")
random.seed(63)


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def read_rows(name):
    with open(os.path.join(CAT, name), encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def read_dicts(name):
    with open(os.path.join(CAT, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def refused(fn):
    try:
        fn()
    except ValueError as e:
        return str(e)
    return None


# ======================================================================= C: the catalog
RAW = read_rows("settings.csv")
HEADER = RAW[0]
SET = read_dicts("settings.csv")
S = {r["key"]: r for r in SET}
SCOPES = {"installation", "regime", "company", "product_category", "money_account", "scanner_profile", "agent_type", "rule_version"}
STORAGE = {"setting_value", "regime_setting", "agent_type_setting", "data_processing_permission", "rule_version", "deployment"}
TYPES = {"boolean", "integer", "decimal", "percent", "amount", "enum", "code_list", "field_list", "object"}
NUMERIC = {"integer", "decimal", "percent", "amount"}
DIRS = {"higher_tighter", "lower_tighter", "true_tighter", "false_tighter", "subset_tighter", "superset_tighter", "neutral"}
LEAVES = {r["code"] for r in read_dicts("authorization-areas.csv")}


def bounds_of(r):
    b, t = r["bounds"], r["value_type"]
    if t in NUMERIC:
        m = re.fullmatch(r"(-?[0-9.]+)\.\.(-?[0-9.]*)", b)
        if not m:
            raise ValueError(f"numeric bounds {b!r}")
        return {"min": Dec(m.group(1)), "max": Dec(m.group(2)) if m.group(2) else None}
    if t in ("boolean", "enum"):
        vals = b.split("|")
        if t == "boolean" and not set(vals) <= {"true", "false"}:
            raise ValueError(f"boolean bounds {b!r}")
        return {"values": vals}
    if t == "code_list" and b == "codes" or t == "field_list" and b == "fields" or t == "object" and b == "schema":
        return {}
    raise ValueError(f"bounds {b!r} for {t}")


def direction_of(r):
    d = r["direction"]
    if d.startswith("order:"):
        return "order", d[len("order:"):].split("<")
    if d not in DIRS:
        raise ValueError(f"direction {d!r}")
    return d, None


def default_of(r):
    d = r["core_default"]
    if d in ("fail_closed", "unset"):
        return d
    t = r["value_type"]
    if t in NUMERIC:
        return Dec(d)
    if t == "boolean":
        return {"true": True, "false": False}[d]
    if t in ("code_list", "field_list"):
        return json.loads(d)
    return d


def in_bounds(r, v):
    """The registry's bound check (rule 4), as setting_out_of_bounds applies it."""
    t, b = r["value_type"], bounds_of(r)
    if t in NUMERIC:
        if isinstance(v, bool) or not isinstance(v, (int, Dec, float)):
            return False
        v = Dec(str(v))
        if t == "integer" and v != v.to_integral_value():
            return False
        return v >= b["min"] and (b["max"] is None or v <= b["max"])
    if t == "boolean":
        return isinstance(v, bool) and ("true" if v else "false") in b["values"]
    if t == "enum":
        return isinstance(v, str) and v in b["values"]
    if t in ("code_list", "field_list"):
        return isinstance(v, list) and all(isinstance(x, str) and x for x in v) and (t != "field_list" or all(re.fullmatch(r"[a-z_]+\.[a-z_]+", x) for x in v))
    return isinstance(v, dict)


check(f"C01 settings.csv: every one of its {len(RAW) - 1} rows has the header's {len(HEADER)} fields",
      all(len(x) == len(HEADER) for x in RAW) and len(HEADER) == 14, [i for i, x in enumerate(RAW) if len(x) != len(HEADER)][:5])
check("C02 setting keys are unique and well formed (lowercase dotted segments, placeholders in angle brackets)",
      len(S) == len(SET) and all(re.fullmatch(r"[a-z0-9_<>]+(\.[a-z0-9_<>]+)+", k) and "<>" not in k for k in S),
      [k for k in S if not re.fullmatch(r"[a-z0-9_<>]+(\.[a-z0-9_<>]+)+", k)])
bad = [r["key"] for r in SET if not r["scope"] or not set(r["scope"].split(";")) <= SCOPES or r["storage"] not in STORAGE or r["value_type"] not in TYPES]
check("C03 every setting has a scope, a storage and a value type from the registry's lists (rule 1)", not bad, bad)
bad = [r["key"] for r in SET if not r["core_default"] or (r["core_default"] == "fail_closed" and "regime" not in r["scope"].split(";"))]
check("C04 every setting has a core default or fail_closed, and only regime keys fail closed (ADR-0053; rule 1)", not bad, bad)
bad = []
for r in SET:
    try:
        bounds_of(r)
    except ValueError as e:
        bad.append((r["key"], str(e)))
check("C05 every setting has hard bounds that parse for its type (rule 4)", not bad, bad)
bad = [r["key"] for r in SET if r["core_default"] not in ("fail_closed", "unset") and not in_bounds(r, default_of(r))]
check("C06 every core default lies within its bounds", not bad, bad)
bad = []
for r in SET:
    d, order = direction_of(r)
    t = r["value_type"]
    if d == "order":
        if t != "enum" or not set(bounds_of(r)["values"]) <= set(order) or len(set(order)) != len(order):
            bad.append(r["key"])
    elif d in ("higher_tighter", "lower_tighter") and t not in NUMERIC or d in ("true_tighter", "false_tighter") and t != "boolean" \
            or d in ("subset_tighter", "superset_tighter") and t not in ("code_list", "field_list"):
        bad.append(r["key"])
check("C07 every direction suits its type, and an order lists every allowed value once (rule 3)", not bad, bad)
bad = [r["key"] for r in SET if r["leaf"] not in LEAVES | {"package", "operator"}
       or (r["leaf"] == "package") != (r["storage"] == "regime_setting" and r["scope"] == "regime")
       or (r["leaf"] == "operator") != (r["storage"] == "deployment")]
check("C08 every setting names a leaf of authorization-areas.csv, package for package-only rows or operator for deployment values", not bad, bad)
bad = [r["key"] for r in SET if r["change_effect"] not in ("immediate", "period_start", "package_release", "deployment")
       or r["outdates"] not in ("auto_post", "promotion", "none")
       or (r["change_effect"] == "package_release") != (r["storage"] == "regime_setting" and "company" not in r["scope"].split(";"))]
check("C09 change effects and outdating are from the registry's lists, and package_release exactly for package-only keys", not bad, bad)
acting = sorted(k for k, r in S.items() if r["outdates"] == "auto_post")
ADR_DIR = os.path.dirname(ADR)
_ADR_TEXT = {}


def adr_text_of(num):
    """The text of ADR-<num> beside ADR-0063, or empty when there is none (ADR-0064 note on rule 29)."""
    if num not in _ADR_TEXT:
        hits = [f for f in os.listdir(ADR_DIR) if f.startswith(num + "-") and f.endswith(".md")]
        _ADR_TEXT[num] = open(os.path.join(ADR_DIR, hits[0]), encoding="utf-8").read() if len(hits) == 1 else ""
    return _ADR_TEXT[num]


def cited_adrs(r):
    return re.findall(r"ADR-(\d{4})", r["source"])


def rule_blocks(text):
    """Numbered rules (a top-level `N. ` line up to the next), where a declaration and its key stand together."""
    return re.split(r"\n(?=\d+\. )", text)


def declares_auto_post(r):
    return any(f"`{r['key']}`" in b and re.search(r"auto-post|auto_post|evidence", b)
               for n in cited_adrs(r) for b in rule_blocks(adr_text_of(n)))


bad = [k for k in acting if not declares_auto_post(S[k])]
check("C10 every key whose loosening outdates auto-post evidence stands in a rule of an ADR its row cites that declares an auto-post or evidence path (ADR-0063 rules 8-10 and later ADRs)",
      not bad and "auto_post.max_error_rate" in acting, bad or acting)
adr_text = open(ADR, encoding="utf-8").read()
PREFIXES = ("intake.", "cash.", "auto_post.", "artifacts.", "agents.", "data_processing.", "analysis.", "extensions.", "automation.",
            "master_data.", "documents.", "movement_type.", "barcode.")
NOT_SETTINGS = {"cash.match_bank_line"}            # a tunable function's code, not a setting
named = {t for t in re.findall(r"`([a-z0-9_<>.]+)`", adr_text) if t.startswith(PREFIXES) and t.count(".") >= 1} - NOT_SETTINGS
unnamed = sorted(k for k, r in S.items() if not any(f"`{k}`" in adr_text_of(n) for n in cited_adrs(r)))
check("C11 every setting key ADR-0063 names is in the catalog, and every catalog key is named by an ADR its row's source cites",
      not (named - set(S)) and not unnamed and all(cited_adrs(r) for r in SET), {"missing": sorted(named - set(S)), "unnamed": unnamed})
m = re.search(r"\[settings\.csv\]\(\.\./catalogs/settings\.csv\), version 0\.1\.0, (\d+) definitions", adr_text)
added = sum(int(x) for x in re.findall(r"\) adds (\d+) definitions", adr_text))
check("C12 the catalog's row count is rule 29's stated count plus the definitions that later ADRs' notes on rule 29 add",
      m and int(m.group(1)) + added == len(SET), (m and m.group(1), added, len(SET)))
COUNTRY = re.compile(r"Vietnam|vietnam|l10n_vn|\bTT ?99\b|\btt99\b|\bVND\b|\bVAS\b|Decree|Circular|DS-19")
texts = {"adr": adr_text, "settings.csv": open(os.path.join(CAT, "settings.csv"), encoding="utf-8").read(),
         "DS-28-settings.sql": open(os.path.join(DOCS, "design", "DS-28-settings.sql"), encoding="utf-8").read()}
check("C13 no country content in the ADR, the catalog or the DDL file (the author's rule for this work)",
      not any(COUNTRY.search(t) for t in texts.values()), [n for n, t in texts.items() if COUNTRY.search(t)])
check("C14 the core default of the purchase return keys stays fail-closed, as accounting rules of the regime (ADR-0020 rule 5; rule 24)",
      S["movement_type.purchase_return.value_source"]["core_default"] == "fail_closed" and S["movement_type.purchase_return.costing_role"]["core_default"] == "fail_closed"
      and S["data_processing.policy"]["core_default"] == "fail_closed" and S["movement_type.purchase_return.include_landed_cost"]["core_default"] == "true")

INV = read_dicts("invariants.csv")
EC = read_dicts("edge-cases.csv")
WIK = read_dicts("work-item-kinds.csv")
inv63 = [r for r in INV if "ADR-0063" in r["source"]]
ec63 = [r for r in EC if "ADR-0063" in r["source"]]
fc = {}
for name in ("invariants.csv", "edge-cases.csv", "work-item-kinds.csv", "authorization-areas.csv"):
    rows_ = read_rows(name)
    fc[name] = [i for i, x in enumerate(rows_) if len(x) != len(rows_[0])]
check("C15 invariants, edge cases, work item kinds and authorization areas keep a constant field count", not any(fc.values()), fc)
dups = {n: [c for c in {r[k] for r in rows} if [r[k] for r in rows].count(c) > 1]
        for n, rows, k in (("invariants", INV, "code"), ("edge cases", EC, "code"), ("work item kinds", WIK, "code"))}
check("C16 no duplicate codes in invariants, edge cases or work item kinds", not any(dups.values()), dups)
inv_n = sorted(int(r["code"][4:]) for r in inv63)
ec_n = sorted(int(r["code"][3:]) for r in ec63)
check("C17 ADR-0063's invariants are INV-700 to INV-718 and its edge cases EC-180 to EC-193, inside their blocks, and nothing else uses the blocks",
      inv_n == list(range(700, 719)) and ec_n == list(range(180, 194))
      and not [r["code"] for r in INV if 700 <= int(r["code"][4:]) <= 729 and "ADR-0063" not in r["source"]]
      and not [r["code"] for r in EC if 180 <= int(r["code"][3:]) <= 199 and "ADR-0063" not in r["source"]], (inv_n, ec_n))
check("C18 every ADR-0063 invariant and edge case is listed in the ADR with its name", all(f"**{r['code']}** `{r['name']}`" in adr_text for r in inv63 + ec63))
TABLES = set()
for p in glob.glob(os.path.join(DOCS, "design", "*.sql")):
    TABLES |= set(re.findall(r"^CREATE TABLE (\w+) \(", open(p, encoding="utf-8").read(), re.M))
bad = [(r["code"], k) for r in inv63 for k in r["keys"].split(";") if k not in TABLES]
check("C19 every table an ADR-0063 invariant names as its key is defined in a design DDL file", not bad, bad)
kinds63 = {r["code"]: r for r in WIK if "ADR-0063" in r["meaning"]}
owner_rules = {r["owner_rule"] for r in WIK if "ADR-0063" not in r["meaning"]}
check("C20 the five work item kinds are catalogued with subject tables the DDL defines and owner rules already in use",
      set(kinds63) == {"setting_review_required", "data_processing_permission_suspended", "automation_rule_rate_limited", "auto_post_suspended", "duplicate_document_review"}
      and all(r["subject_table"] in TABLES and r["owner_rule"] in owner_rules for r in kinds63.values()), sorted(kinds63))
areas = {r["code"]: r for r in read_dicts("authorization-areas.csv")}
check("C21 the leaf data_processing sits under agent in module agents (ADR-0054 rule 7 note)",
      areas.get("data_processing", {}).get("parent_code") == "agent" and areas["data_processing"]["module"] == "agents")
ds04 = open(os.path.join(DOCS, "design", "DS-04-command-envelope.md"), encoding="utf-8").read()
codes = {"setting_out_of_bounds", "setting_scope_invalid", "setting_effective_date_invalid", "tainted_projection_cap_reached", "product_code_taken", "product_code_immutable"}
used = {c for r in ec63 for part in r["expected_outcome"].split("|") if part.startswith("must_reject:") for c in [part.split(":", 1)[1]]}
check("C22 the new DS-04 codes have rows, and every code an ADR-0063 edge case expects is in DS-04",
      all(f"| `{c}` |" in ds04 for c in codes | used | {"proposal_required", "approver_is_submitter"}), sorted(c for c in codes | used if f"| `{c}` |" not in ds04))
QUERIES = re.findall(r"`((?:Get|List|Evaluate|Render|Resolve|Find|Search|Compute)[A-Z]\w+)`", adr_text.split("28. Commands and queries:")[1].split("29. Catalog rows:")[0])
check("C23 every query of rule 28 starts with Get, List, Evaluate or Render (ADR-0004 rule 21; ResolveItemCandidates is renamed)",
      QUERIES and all(q.startswith(("Get", "List", "Evaluate", "Render")) for q in QUERIES) and "ListItemCandidate" in QUERIES, QUERIES)

# ======================================================================= A: the change path (rules 3-4)
TODAY = date(2026, 11, 16)
PERIOD_STARTS = {date(2026, m, 1) for m in range(1, 13)} | {date(2027, m, 1) for m in range(1, 13)}


def compare(r, old, new_):
    """tighten, loosen, neutral or same, by the definition's direction (rule 3)."""
    if old == new_:
        return "same"
    d, order = direction_of(r)
    if d == "neutral":
        return "neutral"
    if d == "order":
        return "tighten" if order.index(new_) > order.index(old) else "loosen"
    if d == "higher_tighter":
        return "tighten" if Dec(str(new_)) > Dec(str(old)) else "loosen"
    if d == "lower_tighter":
        return "tighten" if Dec(str(new_)) < Dec(str(old)) else "loosen"
    if d == "true_tighter":
        return "tighten" if new_ else "loosen"
    if d == "false_tighter":
        return "tighten" if not new_ else "loosen"
    if d == "subset_tighter":
        return "tighten" if set(new_) <= set(old) else "loosen"
    return "tighten" if set(new_) >= set(old) else "loosen"     # superset_tighter


def outdated_by(r, kind, company_rules):
    """Rule versions whose stored auto-post evidence a change marks outdated (rule 3; ADR-0059 rule 6)."""
    if kind != "loosen" or r["outdates"] != "auto_post":
        return []
    return [v for v in company_rules if r["key"] in v["depends_on"] and v["enabled"]]


def update_setting(r, old, new_, actor, leaves, scope="company", eff=None, proposal=None, rules=(), others=None):
    """UpdateCompanySetting (or a regime option) as a pure function; returns the setting_value row or raises the error."""
    others = others or {}
    if scope not in r["scope"].split(";") or scope in ("regime", "installation", "rule_version"):
        raise ValueError("setting_scope_invalid")
    if not in_bounds(r, new_):
        raise ValueError("setting_out_of_bounds")
    if r["key"] == "automation.breaker_consecutive" and Dec(str(new_)) < Dec(str(others.get("automation.breaker_failures", 5))):
        raise ValueError("setting_out_of_bounds")
    if r["key"] == "automation.breaker_failures" and Dec(str(new_)) > Dec(str(others.get("automation.breaker_consecutive", 20))):
        raise ValueError("setting_out_of_bounds")
    if leaves.get(r["leaf"]) not in ("edit", "full"):
        raise ValueError("permission_denied")
    kind = compare(r, old, new_)
    if kind == "same":
        raise ValueError("no_change")
    eff = eff or TODAY
    if eff < TODAY:
        raise ValueError("setting_effective_date_invalid")
    if r["change_effect"] == "period_start" and eff not in PERIOD_STARTS:
        raise ValueError("setting_effective_date_invalid")
    row = {"key": r["key"], "value": new_, "previous_value": old, "change_kind": kind, "effective_from": eff, "changed_by": actor}
    if kind == "loosen":
        if proposal is None or not proposal.get("approved"):
            raise ValueError("proposal_required")
        if proposal["approver"] == proposal["submitter"] or proposal["approver"] in proposal.get("writers", ()):
            raise ValueError("approver_is_submitter")
        if proposal.get("approver_level") != "full":
            raise ValueError("approver_not_eligible")
        row.update(change_proposal=proposal["id"], approved_by=proposal["approver"], changed_by=proposal["submitter"])
    row["outdated"] = outdated_by(r, kind, rules)
    return row


def tighter_and_looser(r):
    """((start, tighter value), (start, looser value)) inside the bounds, or None where the direction gives none."""
    d, order = direction_of(r)
    t, b = r["value_type"], bounds_of(r)
    base = default_of(r)
    if t in NUMERIC and d in ("higher_tighter", "lower_tighter"):
        lo, hi = b["min"], b["max"] if b["max"] is not None else b["min"] + 1000
        if base not in ("unset", "fail_closed") and lo < base < hi:
            mid = base
        else:
            mid = Dec(int((lo + hi) / 2)) if t == "integer" else (lo + hi) / 2
        step = Dec(1) if t == "integer" else min(hi - mid, mid - lo) / 2
        up, down = mid + step, mid - step
        if not (lo <= down < mid < up <= hi):
            return None
        return ((mid, up), (mid, down)) if d == "higher_tighter" else ((mid, down), (mid, up))
    if t == "boolean" and d in ("true_tighter", "false_tighter") and len(b["values"]) == 2:
        tight = d == "true_tighter"
        return ((not tight, tight), (tight, not tight))
    if d == "order":
        vals = [v for v in order if v in b["values"]]
        return ((vals[0], vals[1]), (vals[1], vals[0])) if len(vals) >= 2 else None
    if t in ("code_list", "field_list") and d in ("subset_tighter", "superset_tighter"):
        small, big = (["a.b"], ["a.b", "c.d"]) if t == "field_list" else (["C1"], ["C1", "C2"])
        return ((big, small), (small, big)) if d == "subset_tighter" else ((small, big), (big, small))
    return None


def other_value(r):
    """A valid value different from the core default (for neutral changes)."""
    t, b, dv = r["value_type"], bounds_of(r), default_of(r)
    if t == "boolean":
        return not dv
    if t == "enum":
        return next(v for v in b["values"] if v != dv)
    if t in NUMERIC:
        return dv + 1 if b["max"] is None or dv + 1 <= b["max"] else dv - 1
    return ["C9"]


EDITOR = {lf: "edit" for lf in LEAVES}


def cscope(r):
    return [x for x in r["scope"].split(";") if x not in ("regime", "installation", "rule_version")][0]


P_OK = {"id": "cp1", "approved": True, "submitter": "u1", "approver": "u2", "approver_level": "full"}
fails, tested = [], 0
for r in SET:
    tl = tighter_and_looser(r)
    if tl is None or r["leaf"] in ("package", "operator") or r["scope"] == "regime":
        continue
    scope = [s for s in r["scope"].split(";") if s not in ("regime", "installation", "rule_version")][0]
    (st_t, tight), (st_l, loose) = tl
    eff = date(2026, 12, 1) if r["change_effect"] == "period_start" else None
    tested += 1
    if refused(lambda: update_setting(r, st_t, tight, "u1", EDITOR, scope, eff)) is not None:
        fails.append((r["key"], "tighten refused"))
    if refused(lambda: update_setting(r, st_l, loose, "u1", EDITOR, scope, eff)) != "proposal_required":
        fails.append((r["key"], "direct loosening accepted"))
    if refused(lambda: update_setting(r, st_l, loose, "u1", EDITOR, scope, eff, proposal=P_OK)) is not None:
        fails.append((r["key"], "approved loosening refused"))
    if refused(lambda: update_setting(r, st_l, loose, "u1", EDITOR, scope, eff, proposal=dict(P_OK, approver="u1"))) != "approver_is_submitter":
        fails.append((r["key"], "self-approval accepted"))
check(f"A01 for each of the {tested} company-held settings with a direction: one person tightens at once, a direct loosening returns proposal_required, "
      "another person's approved proposal loosens, and a self-approval returns approver_is_submitter (rule 3)", tested >= 35 and not fails, fails[:6])
neutral = [r for r in SET if r["direction"] == "neutral" and r["storage"] == "setting_value"]
check("A02 a neutral setting changes directly with one person's edit, a writer's approval of a loosening is refused, and an approver below full is not eligible",
      neutral and all(update_setting(r, default_of(r), other_value(r), "u1", EDITOR, cscope(r))["change_kind"] == "neutral" for r in neutral)
      and refused(lambda: update_setting(S["automation.max_active_rules"], Dec(200), Dec(300), "u1", EDITOR, proposal=dict(P_OK, writers=("u2",)))) == "approver_is_submitter"
      and refused(lambda: update_setting(S["automation.max_active_rules"], Dec(200), Dec(300), "u1", EDITOR, proposal=dict(P_OK, approver_level="edit"))) == "approver_not_eligible",
      [r["key"] for r in neutral])
RULES = [{"id": "prv1", "enabled": True, "depends_on": {"cash.bank_charge.auto_post_ceiling", "auto_post.max_error_rate"}},
         {"id": "prv2", "enabled": True, "depends_on": {"auto_post.max_error_rate"}}, {"id": "prv3", "enabled": False, "depends_on": {"cash.bank_charge.auto_post_ceiling"}}]
ceil_def = S["cash.bank_charge.auto_post_ceiling"]
row_down = update_setting(ceil_def, Dec(500000), Dec(200000), "u1", EDITOR, rules=RULES)
row_up = update_setting(ceil_def, Dec(200000), Dec(800000), "u1", EDITOR, proposal=P_OK, rules=RULES)
row_rate = update_setting(S["auto_post.max_error_rate"], Dec(1), Dec(2), "u1", EDITOR, proposal=P_OK, rules=RULES)
row_promo = update_setting(S["artifacts.analysis.min_verified_examples"], Dec(30), Dec(10), "u1", EDITOR, proposal=P_OK, rules=RULES)
check("A03 a loosening of an acting setting outdates the evidence of every enabled dependent auto-post rule version, a tightening none, a promotion threshold no auto-post evidence (EC-180)",
      row_down["outdated"] == [] and [v["id"] for v in row_up["outdated"]] == ["prv1"] and [v["id"] for v in row_rate["outdated"]] == ["prv1", "prv2"]
      and row_promo["outdated"] == [] and row_up["approved_by"] == "u2" and row_up["changed_by"] == "u1")
# property test over random values (rule 4): accepted values lie within the bounds, values strictly inside are accepted
prop_bad, prop_n = [], 0
WIDE = {"automation.breaker_failures": 1, "automation.breaker_consecutive": 200}   # orders between settings are A06's
for r in SET:
    if r["value_type"] not in NUMERIC or r["storage"] != "setting_value":
        continue
    b = bounds_of(r)
    hi = b["max"] if b["max"] is not None else b["min"] + 10 ** 7
    span = hi - b["min"]
    for _ in range(200):
        v = Dec(str(round(random.uniform(float(b["min"] - span), float(hi + span)), random.choice([0, 0, 2]))))
        prop_n += 1
        ok = in_bounds(r, v)
        inside = b["min"] <= v and (b["max"] is None or v <= b["max"]) and (r["value_type"] != "integer" or v == v.to_integral_value())
        if ok != inside or (ok and refused(lambda: update_setting(r, v, v, "u1", EDITOR, cscope(r), others=WIDE)) not in (None, "no_change")):
            prop_bad.append((r["key"], str(v)))
        if not ok and refused(lambda: update_setting(r, default_of(r), v, "u1", EDITOR, cscope(r), proposal=P_OK, others=WIDE)) != "setting_out_of_bounds":
            prop_bad.append((r["key"], str(v), "accepted"))
check(f"A04 property: of {prop_n} random values over every numeric company setting, exactly those within the bounds (whole for integers) are accepted; every other returns setting_out_of_bounds",
      not prop_bad, prop_bad[:5])
enum_bad = [r["key"] for r in SET if r["value_type"] == "enum" and r["storage"] == "setting_value"
            and refused(lambda: update_setting(r, default_of(r), "not_a_value", "u1", EDITOR, cscope(r), proposal=P_OK)) != "setting_out_of_bounds"]
check("A05 an enumeration value outside the allowed values, and wasm_enabled true (its bound is false in Phase 1), are out of bounds",
      not enum_bad and not in_bounds(S["extensions.wasm_enabled"], True) and in_bounds(S["extensions.wasm_enabled"], False)
      and not in_bounds(S["analysis.narrative_mode"], "free_prose"), enum_bad)
check("A06 orders between settings: breaker_consecutive below breaker_failures, or failures above consecutive, is out of bounds; 0 failures too (EC-181)",
      refused(lambda: update_setting(S["automation.breaker_consecutive"], Dec(20), Dec(4), "u1", EDITOR, proposal=P_OK, others={"automation.breaker_failures": 5})) == "setting_out_of_bounds"
      and refused(lambda: update_setting(S["automation.breaker_failures"], Dec(5), Dec(30), "u1", EDITOR, proposal=P_OK, others={"automation.breaker_consecutive": 20})) == "setting_out_of_bounds"
      and refused(lambda: update_setting(S["automation.breaker_failures"], Dec(5), Dec(0), "u1", EDITOR)) == "setting_out_of_bounds"
      and refused(lambda: update_setting(S["automation.breaker_failures"], Dec(5), Dec(3), "u1", EDITOR)) is None)
pr = S["movement_type.purchase_return.value_source"]
check("A07 a period_start setting (the purchase return option) changes only on a period's first day and never backdated; an immediate one never backdated (EC-190)",
      refused(lambda: update_setting(pr, "document", "preliminary_price", "u1", EDITOR, eff=date(2026, 11, 20))) == "setting_effective_date_invalid"
      and refused(lambda: update_setting(pr, "document", "preliminary_price", "u1", EDITOR, eff=date(2026, 12, 1))) is None
      and refused(lambda: update_setting(pr, "document", "preliminary_price", "u1", EDITOR, eff=date(2026, 11, 1))) == "setting_effective_date_invalid"
      and refused(lambda: update_setting(S["automation.max_active_rules"], Dec(200), Dec(100), "u1", EDITOR, eff=date(2026, 11, 15))) == "setting_effective_date_invalid")
check("A08 scopes: a key accepts only its declared scopes, and the regime, installation and rule-version scopes have no company command",
      refused(lambda: update_setting(S["automation.max_active_rules"], Dec(200), Dec(100), "u1", EDITOR, scope="product_category")) == "setting_scope_invalid"
      and refused(lambda: update_setting(S["documents.unit_name_max_length"], Dec(100), Dec(50), "u1", EDITOR, scope="regime")) == "setting_scope_invalid"
      and refused(lambda: update_setting(S["barcode.separator_suspect"], "stop_and_confirm", "trust_transport", "u1", EDITOR, scope="scanner_profile", proposal=P_OK)) is None)
check("A09 a narrower scope that loosens the company value is a loosening (a category reading day 00 as last day under a company reading first day)",
      compare(S["barcode.gs1.day00_policy.<expiry_ai>"], "first_day", "last_day") == "loosen"
      and refused(lambda: update_setting(S["barcode.gs1.day00_policy.<expiry_ai>"], "first_day", "last_day", "u1", EDITOR, scope="product_category")) == "proposal_required")
check("A10 the tainted read setting only narrows: literal is tighter than declared projections, so returning to the default is a proposal (rule 16)",
      compare(S["agents.tainted_reference_reads"], "declared_projections", "literal") == "tighten"
      and compare(S["agents.tainted_reference_reads"], "literal", "declared_projections") == "loosen")
check("A11 a person without edit on the setting's leaf cannot change it, even to tighten (leaf of rule 1)",
      refused(lambda: update_setting(S["automation.dispatch_paused"], False, True, "u1", {"configuration": "read"})) == "permission_denied")


# ======================================================================= A: the acting ceiling (rule 10)
def min_cases(rate_percent):
    return math.ceil(Dec(300) / Dec(str(rate_percent)))


def evidence_ok(n, unchanged, months, rate_percent, to_other_partner=0):
    if not in_bounds(S["auto_post.max_error_rate"], Dec(str(rate_percent))):
        raise ValueError("setting_out_of_bounds")
    return n >= min_cases(rate_percent) and unchanged >= math.ceil(n * (1 - Dec(str(rate_percent)) / 100)) and months >= 2 and to_other_partner == 0


grid = [Dec("0.1") * k for k in range(1, 21)]
exact = all((1 - float(p) / 100) ** min_cases(p) <= 0.05 for p in grid)
check("A12 N = ceil(3 / rate) cases with none changed would bound the error rate at the rate with 95% confidence, for every rate from 0.1% to 2% (exact binomial)",
      exact and min_cases(1) == 300 and min_cases(2) == 150 and min_cases(0.1) == 3000)


def upper_bound(changed, n, conf=0.95):
    """Exact one-sided upper bound of the error rate (Clopper-Pearson), by bisection on the binomial CDF."""
    def cdf(p):
        return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(changed + 1))
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > 1 - conf else (lo, mid)
    return hi


ub300, ub150 = upper_bound(3, 300), upper_bound(3, 150)
check("A12b with changed cases allowed the gate is an observed rate, not a 95% bound (3 of 300: about 2.6%; 3 of 150: about 5.1%), so rule 10 and the hard lock claim no bound (review S4)",
      0.025 < ub300 < 0.027 and 0.050 < ub150 < 0.052 and "it is not a 95% bound" in adr_text and "proven at 95%" not in adr_text, (round(ub300, 4), round(ub150, 4)))
check("A13 the default reproduces ADR-0051 rule 18 (300 proposals, 99% unchanged, two months), 2% needs 150, and a rate above 2% is refused",
      evidence_ok(300, 297, 2, 1) and not evidence_ok(299, 299, 2, 1) and not evidence_ok(300, 296, 2, 1) and evidence_ok(150, 147, 2, 2)
      and not evidence_ok(300, 297, 1, 1) and not evidence_ok(300, 300, 2, 1, to_other_partner=1) and refused(lambda: evidence_ok(500, 500, 3, 2.5)) == "setting_out_of_bounds")
check("A14 the evidence floor is scoped to learned or probabilistic matching paths; a deterministic bank_charge rule is governed by its determinism, cap and confirmation (ruling S1)",
      "is not a learned or probabilistic path" in adr_text and "learned or probabilistic matching path" in S["auto_post.max_error_rate"]["meaning"]
      and "exception" not in adr_text.split("6. Hard locks")[1].split("**Autonomy**")[0])


# ======================================================================= A: the gates of rules 8 and 9
def bank_charge_post(line, rule, company, rules_matched=1, open_item_match=False, evidence=None):
    """human_post or auto_post for a bank_charge rule's draft (rule 9); 'suggest' when the class does not apply."""
    codes = company["codes"].get(line["money_account"], [])
    if line["amount"] >= 0 or line.get("code") not in codes or line.get("counterparty_account"):
        return "suggest"
    if rules_matched != 1 or open_item_match:
        return "suggest"
    if not rule.get("auto_post"):
        return "human_post"
    ceiling = company["ceiling"]
    if ceiling == 0 or rule["amount_max"] > ceiling or -line["amount"] > rule["amount_max"]:
        return "human_post"
    ev = evidence or {}
    if ev.get("lines", 0) < company["min_lines"] or ev.get("months", 0) < company["min_months"] or ev.get("changed", 0) > 0:
        return "human_post"
    return "auto_post"


CO = {"codes": {"MA1": ["PMNT-CCRD-CHRG", "FEE01"]}, "ceiling": 50000, "min_lines": 6, "min_months": 3}
RULE = {"auto_post": True, "amount_max": 30000}
EVI = {"lines": 6, "months": 3, "changed": 0}
L0 = {"money_account": "MA1", "amount": -22000, "code": "FEE01"}
check("A15 a bank fee debit with a listed code, one rule, no open item and evidence of 6 lines over 3 months auto-posts (EC-182)",
      bank_charge_post(L0, RULE, CO, evidence=EVI) == "auto_post")
check("A16 ... but not a credit, an unlisted code, any counterparty account (a partner's or an unknown one, review S5), two rules, an open item that also matches, or the model's purpose alone",
      bank_charge_post(dict(L0, amount=22000), RULE, CO, evidence=EVI) == "suggest" and bank_charge_post(dict(L0, code="X"), RULE, CO, evidence=EVI) == "suggest"
      and bank_charge_post(dict(L0, counterparty_account="ACC-OF-P9"), RULE, CO, evidence=EVI) == "suggest"
      and bank_charge_post(dict(L0, counterparty_account="9704-UNKNOWN"), RULE, CO, evidence=EVI) == "suggest"
      and bank_charge_post(L0, RULE, CO, rules_matched=2, evidence=EVI) == "suggest" and bank_charge_post(L0, RULE, CO, open_item_match=True, evidence=EVI) == "suggest"
      and bank_charge_post(dict(L0, code=None, llm_purpose="bank_charge"), RULE, CO, evidence=EVI) == "suggest")
check("A17 ... and gets human_post above amount_max, with amount_max above the ceiling, at the default ceiling 0, below 6 lines or 3 months, or with a changed line",
      bank_charge_post(dict(L0, amount=-31000), RULE, CO, evidence=EVI) == "human_post" and bank_charge_post(L0, dict(RULE, amount_max=60000), CO, evidence=EVI) == "human_post"
      and bank_charge_post(L0, RULE, dict(CO, ceiling=int(default_of(S["cash.bank_charge.auto_post_ceiling"]))), evidence=EVI) == "human_post"
      and bank_charge_post(L0, RULE, CO, evidence=dict(EVI, lines=5)) == "human_post" and bank_charge_post(L0, RULE, CO, evidence=dict(EVI, months=2)) == "human_post"
      and bank_charge_post(L0, RULE, CO, evidence=dict(EVI, changed=1)) == "human_post" and bank_charge_post(L0, dict(RULE, auto_post=False), CO, evidence=EVI) == "human_post")


def llm_rule_post(match, accept):
    """auto_post or human_post for a confirm-mode match of a matching rule version (rule 8)."""
    if match["basis"] == "llm_suggestion":
        return "human_post"
    if match.get("origin") != "llm_proposed":
        return "auto_post" if match["auto_post_evidence"] else "human_post"
    ok = (accept and match["whole_reference_token"] and match["live_drafts"] >= 10 and match["live_unchanged_share"] >= Dec("0.99")
          and match["approver"] not in (match["proposer"], match["run_human"]) and match["evidence_counts_basis"] and match["auto_post_evidence"])
    return "auto_post" if ok else "human_post"


MT = {"basis": "company_rule", "origin": "llm_proposed", "whole_reference_token": True, "live_drafts": 12, "live_unchanged_share": Dec("1"),
      "approver": "u2", "proposer": "u1", "run_human": "u3", "evidence_counts_basis": True, "auto_post_evidence": True}
variants = [dict(MT, whole_reference_token=False), dict(MT, live_drafts=9), dict(MT, live_unchanged_share=Dec("0.98")), dict(MT, approver="u1"),
            dict(MT, approver="u3"), dict(MT, evidence_counts_basis=False)]
check("A18 LLM-originated rules: off by default and bounded false until spec 03 is reworded (human_post); if enabled later, they auto-post only when all five conditions hold; any one failing gives human_post (EC-183)",
      default_of(S["cash.auto_post.accept_llm_originated_rules"]) is False and not in_bounds(S["cash.auto_post.accept_llm_originated_rules"], True)
      and llm_rule_post(MT, False) == "human_post" and llm_rule_post(MT, True) == "auto_post"
      and all(llm_rule_post(v, True) == "human_post" for v in variants))
check("A19 an llm_suggestion draft never auto-posts, whatever the setting, and a rule a person wrote is unaffected by it (hard lock)",
      llm_rule_post(dict(MT, basis="llm_suggestion", origin=None), True) == "human_post" and llm_rule_post(dict(MT, origin="human"), False) == "auto_post")


def wrong_auto_post(rule_version):
    rule_version["outdated_by"] = "reversal"
    return {"kind": "auto_post_suspended", "owner": rule_version["owner"]}


rv = {"id": "prv1", "owner": "u5", "outdated_by": None}
item = wrong_auto_post(rv)
check("A20 a reversed system posting marks its rule version's evidence outdated and raises auto_post_suspended for the rule's owner (EC-184)",
      rv["outdated_by"] == "reversal" and item == {"kind": "auto_post_suspended", "owner": "u5"})


# ======================================================================= A: agents (rules 11, 12)
def today_wake_up(kind_declared, mode_off, origin_agent_run):
    return kind_declared and not mode_off and not origin_agent_run


def wake_up(kind_declared, configurable, wake_mode, mode_off, origin_agent_run, rule_matches=False):
    """Who starts the agent for a raised work item of a kind (rule 11): 'wake_up', 'rule' or None (people)."""
    if not kind_declared or mode_off or origin_agent_run:
        return None
    if not configurable or wake_mode == "always":
        return "wake_up"
    if wake_mode == "by_rule":
        return "rule" if rule_matches else None
    return None


combos = [(kd, cf, off, org) for kd in (True, False) for cf in (True, False) for off in (True, False) for org in (True, False)]
default_mode = S["agents.<agent_type>.wake_up_mode.<kind>"]["core_default"]
check(f"A21 under the default wake-up mode ({default_mode}) every combination of declared, configurable, agent off and agent chain starts exactly as today (no upgrade change)",
      default_mode == "always" and all((wake_up(kd, cf, default_mode, off, org) == "wake_up") == today_wake_up(kd, off, org) for kd, cf, off, org in combos))
check("A22 by_rule: only a matching rule starts the agent and other items stay with people; off: people only; never on an agent's chain (EC-185)",
      wake_up(True, True, "by_rule", False, False, rule_matches=True) == "rule" and wake_up(True, True, "by_rule", False, False) is None
      and wake_up(True, True, "off", False, False, rule_matches=True) is None and wake_up(True, True, "by_rule", False, True, rule_matches=True) is None
      and wake_up(True, False, "off", False, False) == "wake_up")


def effective_agent_mode(stored, below_threshold, action):
    if not below_threshold or action == "signal":
        return stored
    return "off" if action == "pause_new_runs" else "shadow" if stored == "assisted" else stored


check("A23 drift action: signal keeps the stored mode (today), pause_new_runs stops new runs, demote_to_shadow runs as shadow",
      effective_agent_mode("assisted", True, default_of(S["agents.<agent_type>.drift_action"])) == "assisted"
      and effective_agent_mode("assisted", True, "pause_new_runs") == "off" and effective_agent_mode("assisted", True, "demote_to_shadow") == "shadow"
      and effective_agent_mode("assisted", False, "pause_new_runs") == "assisted")


# ======================================================================= A: data processing (rules 15, 16)
def gateway(items, permissions, switch_on, never_send, seat, provider, region):
    """Rule 15: (sent items, outcome). An item is (table.field, label, value, required)."""
    out = []
    for field, label, value, required in items:
        permitted = any(p["data_class"] == label and p["seat_class"] == seat and p["provider"] == provider and p["region"] == region
                        and not p.get("suspended") for p in permissions)
        strip = label == "sensitive_personal" or (label == "personal" and (switch_on or not permitted or field in never_send))
        if strip:
            if required:
                return None, "routing_blocked"
            out.append((field, f"[personal:{field}]"))
        else:
            out.append((field, value))
    return out, "sent"


PERM = [{"data_class": "personal", "seat_class": "drafting", "provider": "cloud", "region": "r1"}]
ITEMS = [("partner.name", "personal", "Ann Example", False), ("item.code", "internal", "A-100", False)]
sent0, _ = gateway(ITEMS, [], False, [], "drafting", "cloud", "r1")
sent1, _ = gateway(ITEMS, PERM, False, [], "drafting", "cloud", "r1")
sent2, _ = gateway(ITEMS, PERM, False, ["partner.name"], "drafting", "cloud", "r1")
sent3, _ = gateway(ITEMS, PERM, True, [], "drafting", "cloud", "r1")
check("A24 one gate: without a permission personal values become placeholders, with one they are sent, never_send and the switch strip them (EC-186)",
      sent0[0][1] == "[personal:partner.name]" and sent1[0][1] == "Ann Example" and sent2[0][1] == "[personal:partner.name]" and sent3[0][1] == "[personal:partner.name]"
      and sent0[1][1] == "A-100")
check("A25 a step that needs a stripped value is not sent (routing_blocked); a suspended permission, another region or sensitive personal never covers",
      gateway([("partner.name", "personal", "x", True)], [], False, [], "drafting", "cloud", "r1")[1] == "routing_blocked"
      and gateway([("partner.name", "personal", "x", True)], [dict(PERM[0], suspended=True)], False, [], "drafting", "cloud", "r1")[1] == "routing_blocked"
      and gateway([("partner.name", "personal", "x", True)], PERM, False, [], "drafting", "cloud", "r2")[1] == "routing_blocked"
      and gateway([("x.y", "sensitive_personal", "x", True)], [dict(PERM[0], data_class="sensitive_personal")], False, [], "drafting", "cloud", "r1")[1] == "routing_blocked")
CLOSED = {"id", "code", "unit", "status", "category", "date", "quantity", "name_internal"}


def projection_ok(columns):
    return all(c in CLOSED for c in columns)


def list_item_candidates(run, catalog, key, setting):
    if run["tainted"] and setting == "literal":
        raise ValueError("tainted_read_out_of_scope")
    if run["tainted"]:
        run["calls"] += 1
        if run["calls"] > 10:
            raise ValueError("tainted_projection_cap_reached")
    rows = [r for r in catalog if key in r["code"] and not r.get("restricted_partner")]
    return [{k: r[k] for k in ("id", "code", "name_internal", "unit", "category", "status")} for r in rows[:20]]


CATALOG = [{"id": i, "code": f"BOLT-{i:03}", "name_internal": f"Bolt {i}", "unit": "H87", "category": "fasteners", "status": "active",
            "price": 10 + i, "restricted_partner": i % 7 == 0} for i in range(60)]
run = {"tainted": True, "calls": 0}
first = list_item_candidates(run, CATALOG, "BOLT", "declared_projections")
for _ in range(9):
    list_item_candidates(run, CATALOG, "BOLT", "declared_projections")
check("A26 a declared projection serves only closed-shape columns, at most 20 rows, no partner-restricted rows, and its eleventh call returns tainted_projection_cap_reached (EC-188)",
      projection_ok(first[0].keys()) and len(first) == 20 and "price" not in first[0] and all(r["id"] % 7 for r in first)
      and refused(lambda: list_item_candidates(run, CATALOG, "BOLT", "declared_projections")) == "tainted_projection_cap_reached"
      and not projection_ok(["id", "price"]) and not projection_ok(["id", "partner_id"]))
check("A27 with agents.tainted_reference_reads literal the tainted call returns tainted_read_out_of_scope; an untainted run is not capped",
      refused(lambda: list_item_candidates({"tainted": True, "calls": 0}, CATALOG, "BOLT", "literal")) == "tainted_read_out_of_scope"
      and len(list_item_candidates({"tainted": False, "calls": 99}, CATALOG, "BOLT", "literal")) == 20)


# ======================================================================= A: automation (rule 21)
def run_rule(events, limit=500, failures=5, window=60, consecutive=20):
    """Live executions of one rule in order; each event is (minute, outcome_if_run). Returns outcomes and the trip minute."""
    out, recent, row = [], [], 0
    per_hour = {}
    for minute, outcome in events:
        hour = minute // 60
        if per_hour.get(hour, 0) >= limit:
            out.append("rate_limited")
            continue
        per_hour[hour] = per_hour.get(hour, 0) + 1
        out.append(outcome)
        if outcome in ("refused", "failed", "partial"):
            recent.append(minute)
            row += 1
        elif outcome == "acted":
            row = 0
        recent = [m for m in recent if m > minute - window]
        if len(recent) >= failures or row >= consecutive:
            return out, minute
    return out, None


out, trip = run_rule([(i * 60 // 600, "acted") for i in range(600)])
check("A28 flood guard: 600 events in one hour give 500 executions and 100 rate_limited, and the breaker does not trip (EC-189)",
      out.count("acted") == 500 and out.count("rate_limited") == 100 and trip is None)
out2, trip2 = run_rule([(i, "failed") for i in range(5)])
out3, trip3 = run_rule([(i * 30, "failed") for i in range(40)], failures=50, window=5)
out4, trip4 = run_rule([(i, "failed") for i in range(4)] + [(70 + i, "failed") for i in range(4)])
check("A29 breaker: 5 failures within 60 minutes trip it; 20 in a row trip it at any rate; failures spread beyond the window do not",
      trip2 == 4 and trip3 == 19 * 30 and trip4 is None)
check("A30 the breaker cannot be off: no failures, window or consecutive value means never, and the bounds exclude 0",
      all(not in_bounds(S[k], Dec(0)) for k in ("automation.breaker_failures", "automation.breaker_window_minutes", "automation.breaker_consecutive",
                                                  "automation.max_executions_per_rule_per_hour")))


# ======================================================================= A: master data, narrative, barcodes, duplicates (rules 22, 25-27)
class Codes:
    def __init__(self):
        self.used, self.referenced, self.next = set(), set(), 1

    def assign(self, mode, typed=None, prefix="", pad=6):
        if mode == "manual" and not typed or mode == "sequence" and typed:
            raise ValueError("setting_scope_invalid")
        if typed:
            if typed.upper() in self.used:
                raise ValueError("product_code_taken")
            code = typed.upper()
        else:
            while True:
                code = f"{prefix}{self.next:0{pad}d}"
                self.next += 1
                if code not in self.used:
                    break
        self.used.add(code)
        return code

    def change(self, old, new_):
        if old in self.referenced:
            raise ValueError("product_code_immutable")
        if new_ in self.used:
            raise ValueError("product_code_taken")
        self.used.add(new_)
        return new_


cs = Codes()
c1 = cs.assign("sequence", prefix="FAS", pad=int(default_of(S["master_data.product_code.pad_width"])))
cs.used.add("FAS000002")
c2 = cs.assign("sequence", prefix="FAS")
c3 = cs.assign("manual", typed="widget-9")
cs.referenced.add(c3)
check("A31 product codes: the sequence skips codes in use, a manual duplicate returns product_code_taken, a referenced code is immutable, a deleted code is never reused (EC-193)",
      c1 == "FAS000001" and c2 == "FAS000003" and c3 == "WIDGET-9" and refused(lambda: cs.assign("manual", typed="Widget-9")) == "product_code_taken"
      and refused(lambda: cs.change(c3, "W-10")) == "product_code_immutable" and refused(lambda: cs.change(c1, "FAS000003")) == "product_code_taken"
      and default_of(S["master_data.product_code.assignment"]) == "sequence")


def narrative(install_max, company):
    order = direction_of(S["analysis.narrative_mode"])[1]
    if not in_bounds(S["analysis.narrative_mode"], install_max) or not in_bounds(S["analysis.narrative_mode"], company):
        raise ValueError("setting_out_of_bounds")
    return company if order.index(company) >= order.index(install_max) else install_max


check("A32 narrative mode: the default is claim_plan; a company may only lower the installation maximum; free_prose is out of bounds in Phase 1",
      narrative("claim_plan", "facts_only") == "facts_only" and narrative("facts_only", "claim_plan") == "facts_only"
      and refused(lambda: narrative("claim_plan", "free_prose")) == "setting_out_of_bounds" and default_of(S["analysis.narrative_mode"]) == "claim_plan")
EXPIRY_AIS, PRODUCTION_AIS = {"12", "15", "16", "17"}, {"11", "13"}


def read_date(ai, yymmdd, policy=None):
    pol = policy or (default_of(S["barcode.gs1.day00_policy.<expiry_ai>"]) if ai in EXPIRY_AIS else default_of(S["barcode.gs1.day00_policy.<production_ai>"]))
    y, m, d = 2000 + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    if d:
        return date(y, m, d)
    if pol == "reject":
        raise ValueError("gs1_invalid")
    if pol == "first_day":
        return date(y, m, 1)
    return (date(y, m, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def receive_lot(elements, fills_expiry):
    lot = {"expiry_date": None, "best_before_date": None}
    if "17" in elements:
        lot["expiry_date"] = read_date("17", elements["17"])
    if "15" in elements:
        lot["best_before_date"] = read_date("15", elements["15"])
        if fills_expiry and lot["expiry_date"] is None:
            lot["expiry_date"] = lot["best_before_date"]
    return lot


check("A33 day 00: expiry-type AIs default to the month's last day, production-type to its first, a reject category refuses (EC-191); first_day is the tighter reading",
      read_date("17", "270200") == date(2027, 2, 28) and read_date("11", "270200") == date(2027, 2, 1)
      and refused(lambda: read_date("17", "270200", "reject")) == "gs1_invalid" and read_date("17", "270215", "reject") == date(2027, 2, 15)
      and compare(S["barcode.gs1.day00_policy.<expiry_ai>"], "last_day", "first_day") == "tighten")
lot_d = receive_lot({"15": "270300"}, default_of(S["barcode.gs1.best_before_fills_expiry"]))
lot_t = receive_lot({"15": "270300"}, True)
check("A34 best before: by default (15) is stored as best_before_date and does not fill expiry; true restores the old reading; (17) always sets expiry",
      default_of(S["barcode.gs1.best_before_fills_expiry"]) is False and lot_d == {"expiry_date": None, "best_before_date": date(2027, 3, 31)}
      and lot_t["expiry_date"] == date(2027, 3, 31) and receive_lot({"17": "270310", "15": "270300"}, True)["expiry_date"] == date(2027, 3, 10))


def norm_number(n, mode):
    if mode == "digits_only":
        return re.sub(r"\D", "", n).lstrip("0")
    if mode == "alnum_casefold":
        return re.sub(r"[^0-9a-z]", "", n.casefold())
    return n


def duplicate_check(new_inv, history, st=None):
    st = st or {k.split(".")[-1]: default_of(S[k]) for k in S if k.startswith("intake.duplicate.")}
    for h in history:
        if h["seller"] == new_inv["seller"] and norm_number(h["number"], "alnum_casefold") == norm_number(new_inv["number"], "alnum_casefold"):
            return {"level": "key", "payment_blocked": True}
    for h in history:
        if h["seller"] != new_inv["seller"]:
            continue
        near_amount = abs(h["gross"] - new_inv["gross"]) <= int(st["amount_tolerance_minor_units"]) and abs((h["date"] - new_inv["date"]).days) <= int(st["date_window_days"])
        near_number = norm_number(h["number"], st["number_normalization"]) == norm_number(new_inv["number"], st["number_normalization"])
        if near_amount or near_number:
            return {"level": "near", "payment_blocked": st["near_outcome"] == "review"}
    return {"level": None, "payment_blocked": False}


HIST = [{"seller": "S1", "number": "INV-0042", "gross": 1250000, "date": date(2026, 10, 3)}]
check("A35 near duplicates: one minor unit and three days apart hold payment under the default review; advisory does not; the exact key always holds (EC-192)",
      duplicate_check({"seller": "S1", "number": "INV-0043", "gross": 1250001, "date": date(2026, 10, 6)}, HIST) == {"level": "near", "payment_blocked": True}
      and duplicate_check({"seller": "S1", "number": "INV-0043", "gross": 1250001, "date": date(2026, 10, 6)}, HIST,
                          {"date_window_days": 7, "amount_tolerance_minor_units": 1, "number_normalization": "digits_only", "near_outcome": "advisory"})["payment_blocked"] is False
      and duplicate_check({"seller": "S1", "number": "inv 0042", "gross": 1, "date": date(2026, 1, 1)}, HIST,
                          {"date_window_days": 0, "amount_tolerance_minor_units": 0, "number_normalization": "exact", "near_outcome": "advisory"}) == {"level": "key", "payment_blocked": True}
      and duplicate_check({"seller": "S1", "number": "X-42", "gross": 9, "date": date(2026, 1, 1)}, HIST)["level"] == "near"
      and duplicate_check({"seller": "S1", "number": "X-42", "gross": 9, "date": date(2026, 1, 1)}, HIST,
                          {"date_window_days": 7, "amount_tolerance_minor_units": 1, "number_normalization": "exact", "near_outcome": "review"})["level"] is None)
check("A36 the near check's settings are tighter when they catch more: a wider window or tolerance, digits-only numbers and review",
      compare(S["intake.duplicate.date_window_days"], Dec(7), Dec(14)) == "tighten" and compare(S["intake.duplicate.number_normalization"], "digits_only", "exact") == "loosen"
      and compare(S["intake.duplicate.near_outcome"], "review", "advisory") == "loosen")

# ======================================================================= D: database checks (--load)
if "--load" in sys.argv:
    import psycopg  # noqa: E402,F401
    from load_all import load_all  # noqa: E402
    dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = load_all(dsn, DOCS)
    check("D01 load_all.py loads every DDL file of design/ with the settings file", n_tables > 200, n_tables)
    c = conn(); c.autocommit = True
    X = c.execute

    def defn_params(r, **over):
        b = bounds_of(r)
        d, order = direction_of(r)
        dk = r["core_default"] if r["core_default"] in ("unset", "fail_closed") else "value"
        dv = None
        if dk == "value":
            v = default_of(r)
            dv = json.dumps(float(v) if isinstance(v, Dec) and r["value_type"] != "integer" else int(v) if isinstance(v, Dec) else v)
        p = {"setting_key": r["key"], "area": r["area"], "scopes": r["scope"].split(";"), "storage": r["storage"], "value_type": r["value_type"],
             "default_kind": dk, "core_default": dv, "min_value": b.get("min"), "max_value": b.get("max"), "allowed_values": b.get("values"),
             "direction": d, "direction_order": order, "leaf_code": r["leaf"], "change_effect": r["change_effect"], "outdates": r["outdates"], "source": r["source"]}
        p.update(over)
        return p

    DEF_SQL = """insert into setting_definition (setting_key, area, scopes, storage, value_type, default_kind, core_default, min_value, max_value, allowed_values,
                 direction, direction_order, leaf_code, change_effect, outdates, source, registry_version, recorded_at)
                 values (%(setting_key)s, %(area)s, %(scopes)s, %(storage)s, %(value_type)s, %(default_kind)s, %(core_default)s, %(min_value)s, %(max_value)s,
                 %(allowed_values)s, %(direction)s, %(direction_order)s, %(leaf_code)s, %(change_effect)s, %(outdates)s, %(source)s, '0.1.0', now())"""
    loaded, load_err = 0, []
    for r in SET:
        try:
            X(DEF_SQL, defn_params(r))
            loaded += 1
        except Exception as e:  # noqa: BLE001
            load_err.append((r["key"], str(e).splitlines()[0]))
    check(f"D02 all {len(SET)} catalog rows load into setting_definition under its checks (defaults within bounds, orders complete, fail-closed only for regime keys)",
          loaded == len(SET) and not load_err, load_err[:3])
    base = S["automation.max_active_rules"]

    def bad_def(name, match, **over):
        expect(name, lambda cx: cx.execute(DEF_SQL, defn_params(base, setting_key="lab.bad_" + new().hex[:8], **over)), True, match)
    bad_def("D03 a definition whose core default lies outside its bounds is refused", "ck_setting_definition_default_in_bounds", core_default="5000")
    bad_def("D04 an order direction that misses an allowed value is refused", "ck_setting_definition_order", value_type="enum", min_value=None, max_value=None,
            allowed_values=["a", "b", "c"], core_default='"a"', direction="order", direction_order=["a", "b"])
    bad_def("D05 fail_closed is refused for a key without a regime scope", "ck_setting_definition_fail_closed", default_kind="fail_closed", core_default=None)
    bad_def("D06 a direction that does not suit the type (true_tighter on an integer) is refused", "ck_setting_definition_direction_type", direction="true_tighter")
    bad_def("D07 an unknown scope is refused", "ck_setting_definition_scopes", scopes=["company", "planet"])

    I = {k: new() for k in ["u1", "u2", "co", "cp", "cat"]}
    t = str(I["co"])[-8:]
    X("insert into currency (code, minor_unit) values ('USD', 2) on conflict do nothing")
    for u in ("u1", "u2"):
        X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I[u], u + "s24" + t))
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','USD','UTC','l10n_test','test','warehouse',%s,'en')", (I["co"], "C24-" + t, I["u1"]))
    X("select set_config('nativeflows.company_id', %s, false)", (str(I["co"]),))

    VAL_SQL = """insert into setting_value (id, company_id, setting_key, scope_kind, scope_ref, placeholder_values, value_type, value, min_value, max_value, allowed_values,
                 direction, direction_order, replaced_value, change_kind, reason, effective_from, changed_by_user_id, change_proposal_id, approved_by_user_id,
                 registry_version, recorded_at)
                 values (%(id)s, %(company_id)s, %(key)s, %(scope_kind)s, %(scope_ref)s, %(ph)s, %(value_type)s, %(value)s, %(min_value)s, %(max_value)s, %(allowed_values)s,
                 %(direction)s, %(direction_order)s, %(previous)s, %(kind)s, 'lab', %(eff)s, %(by)s, %(proposal)s, %(approver)s, '0.1.0', now())"""

    def jd(r):
        v = default_of(r)
        return json.dumps(float(v) if isinstance(v, Dec) and r["value_type"] != "integer" else int(v) if isinstance(v, Dec) else v)

    PH = {"expiry_ai": "17", "production_ai": "11", "agent_type": "quotation", "kind": "inbound_message_matched", "point": "cash.lab_score",
          "function_or_kind": "cash.match_bank_line", "document_type": "supplier_invoice", "field": "total_amount"}

    def val(r, value, kind=None, **over):
        """A row whose copies, replaced value and kind the trigger fills from the definition and the value in force."""
        p = {"id": new(), "company_id": I["co"], "key": r["key"], "scope_kind": "company", "scope_ref": "", "value_type": r["value_type"],
             "value": json.dumps(value), "min_value": None, "max_value": None, "allowed_values": None, "direction": None, "direction_order": None,
             "ph": json.dumps({n: PH[n] for n in re.findall(r"<([a-z_]+)>", r["key"])}), "previous": None, "kind": kind, "eff": "2026-11-16", "by": I["u1"], "proposal": None, "approver": None}
        p.update(over)
        return p

    def D_good(name, fn):
        def run(cx):
            cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, False)

    def D_bad(name, match, fn):
        def run(cx):
            cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, True, match)
    X("insert into document (id, company_id, document_type, state, version, created_by_user_id, recorded_at) values (%s,%s,'change_proposal','draft',1,%s,now())",
      (I["cp"], I["co"], I["u1"]))
    X("insert into change_proposal (id, company_id, plan, plan_hash, reason, document_date, recorded_at) values (%s,%s,'{}',%s,'raise the limit','2026-11-16',now())",
      (I["cp"], I["co"], hashlib.sha256(b"cp").hexdigest()))
    X("update document set state = 'approved' where id = %s", (I["cp"],))     # the proposal is approved before its execution writes the value
    V1 = new()
    D_good("D08 a company value within its bounds is written (a tightening, no proposal)", lambda cx: cx.execute(VAL_SQL, val(base, 150, id=V1, previous="200")))
    D_bad("D09 the database refuses a value above its bounds (setting_out_of_bounds)", "ck_setting_value_in_bounds", lambda cx: cx.execute(VAL_SQL, val(base, 1001, proposal=I["cp"], approver=I["u2"])))
    D_bad("D10 ... a fractional value of an integer setting", "ck_setting_value_in_bounds", lambda cx: cx.execute(VAL_SQL, val(base, 150.5)))
    D_bad("D11 ... an enumeration value that is not allowed", "ck_setting_value_in_bounds",
          lambda cx: cx.execute(VAL_SQL, val(S["agents.tainted_reference_reads"], "everything")))
    D_bad("D12 ... and a boolean outside its allowed values (extensions.wasm_enabled true in Phase 1)", "ck_setting_value_in_bounds",
          lambda cx: cx.execute(VAL_SQL, val(S["extensions.wasm_enabled"], True, company_id=None, scope_kind="installation", approver=I["u2"])))
    agree, disagree = 0, []
    pct = S["auto_post.max_error_rate"]
    for k in ("automation.breaker_window_minutes", "auto_post.max_error_rate", "intake.trust.ocr_min_confidence", "cash.bank_charge.auto_post_ceiling"):
        r = S[k]
        bb = bounds_of(r)
        hi = float(bb["max"]) if bb["max"] is not None else float(bb["min"]) + 1e6
        for _ in range(25):
            v = round(random.uniform(float(bb["min"]) - (hi - float(bb["min"])), hi * 2 + 1), random.choice([0, 2]))
            v = int(v) if r["value_type"] == "integer" and random.random() < 0.7 else v
            pure = in_bounds(r, Dec(str(v)))
            try:
                with c.transaction():
                    X(VAL_SQL, val(r, v, proposal=I["cp"], approver=I["u2"], eff="2026-12-01"))   # with a proposal, so only the bounds decide; dated after the other probes
                db = True
            except Exception:  # noqa: BLE001
                db = False
            (disagree.append((k, v, pure, db)) if pure != db else None)
            agree += pure == db
    check(f"D13 property: on {agree + len(disagree)} random values over four settings, the database accepts exactly the values the registry's bound check accepts",
          not disagree, disagree[:4])
    D_bad("D14 a loosening without a change proposal is refused", "ck_setting_value_loosen",
          lambda cx: cx.execute(VAL_SQL, val(base, 300, approver=I["u2"])))
    D_bad("D15 a loosening approved by the person who submitted it is refused", "ck_setting_value_loosen",
          lambda cx: cx.execute(VAL_SQL, val(base, 300, proposal=I["cp"], approver=I["u1"])))
    D_good("D16 a loosening executed from an approved proposal, approved by another person, is written", lambda cx: cx.execute(
        VAL_SQL, val(base, 300, proposal=I["cp"], approver=I["u2"], previous="150")))
    D_bad("D17 setting values are never updated (append-only history)", "never updated or deleted",
          lambda cx: cx.execute("update setting_value set reason='x' where id=%s", (V1,)))
    D_bad("D18 ... or deleted", "never updated or deleted", lambda cx: cx.execute("delete from setting_value where id=%s", (V1,)))
    D_bad("D19 a value of an unregistered key is refused", "setting_scope_invalid",
          lambda cx: cx.execute(VAL_SQL, val(base, 10, key="automation.unknown_setting")))
    D_good("D20 an installation value has no company and is written under the installation setting", lambda cx: (
        cx.execute("select set_config('nativeflows.company_id', 'installation', true)"),
        cx.execute(VAL_SQL, val(S["analysis.narrative_mode"], "facts_only", company_id=None, scope_kind="installation"))))
    nm = S["analysis.narrative_mode"]
    D_bad("D20b S3: a company value looser than the installation value in force (claim_plan under facts_only) is refused", "looser than the installation value",
          lambda cx: cx.execute(VAL_SQL, val(nm, "claim_plan")))
    D_good("D20c ... and an equal company value is written", lambda cx: cx.execute(VAL_SQL, val(nm, "facts_only")))
    D_bad("D21 a company scope without a company is refused", "ck_setting_value_installation",
          lambda cx: cx.execute(VAL_SQL, val(base, 10, company_id=None)))
    D_bad("D22 a category value names its category (scope_ref)", "ck_setting_value_scope_ref",
          lambda cx: cx.execute(VAL_SQL, val(S["barcode.gs1.day00_policy.<expiry_ai>"], "reject", scope_kind="product_category")))
    D_good("D23 ... and is written with it", lambda cx: cx.execute(VAL_SQL, val(S["barcode.gs1.day00_policy.<expiry_ai>"], "reject", scope_kind="product_category",
                                                                              scope_ref=str(I["cat"]))))
    # review S2: the database derives the change kind; a label never decides it
    D_bad("D24b S2: a first value looser than the core default without a proposal is refused (the flood guard 1000 against 500)", "ck_setting_value_loosen",
          lambda cx: cx.execute(VAL_SQL, val(S["automation.max_executions_per_rule_per_hour"], 1000)))
    D_bad("D24c S2: the same value labelled tighten is refused (the label must equal the derived kind)", "differs from the derived",
          lambda cx: cx.execute(VAL_SQL, val(base, 900, kind="tighten")))
    D_bad("D24d S2: ... and labelled neutral", "differs from the derived", lambda cx: cx.execute(VAL_SQL, val(base, 900, kind="neutral")))
    D_bad("D24e S2: the first raise of the bank charge ceiling from 0 is a loosening and needs a proposal", "ck_setting_value_loosen",
          lambda cx: cx.execute(VAL_SQL, val(S["cash.bank_charge.auto_post_ceiling"], 50000)))
    D_good("D24f r2 S1: a row without a replaced value gets the value in force from the trigger (300, written by D16) and the kind tighten", lambda cx: (
        cx.execute(VAL_SQL, val(base, 250, id=(vf := new()))),
        None if cx.execute("select replaced_value, change_kind from setting_value where id=%s", (vf,)).fetchone() == (300, "tighten") else 1 / 0))
    D_bad("D24g S2: adding a charge code to a money account (a larger list for a subset_tighter key) is a loosening", "ck_setting_value_loosen",
          lambda cx: cx.execute(VAL_SQL, val(S["cash.bank_charge.codes"], ["FEE01"], scope_kind="money_account", scope_ref="MA1")))
    D_good("D24h S2: a tightening written without a label gets change_kind tighten from the database", lambda cx: (
        cx.execute(VAL_SQL, val(base, 120, id=(vt := new()))),
        None if cx.execute("select change_kind from setting_value where id=%s", (vt,)).fetchone()[0] == "tighten" else 1 / 0))
    # review round 2, S1: a forged replaced value no longer hides a loosening
    NIF = "is not the value in force"
    D_bad("D24n r2 S1: a first value looser than the default naming itself as replaced is refused (max_fuel 20,000,000)", NIF,
          lambda cx: cx.execute(VAL_SQL, val(S["extensions.<point>.max_fuel"], 20000000, previous="20000000")))
    D_bad("D24o r2 S1: a loosening naming a looser replaced value is refused (120 to 900 naming 1000)", NIF,
          lambda cx: cx.execute(VAL_SQL, val(base, 900, previous="1000")))
    D_bad("D24p r2 S1: the bank charge ceiling 500 naming 500 is refused", NIF,
          lambda cx: cx.execute(VAL_SQL, val(S["cash.bank_charge.auto_post_ceiling"], 500, previous="500")))
    D_bad("D24q r2 S1: a code added naming a larger list as replaced is refused", NIF,
          lambda cx: cx.execute(VAL_SQL, val(S["cash.bank_charge.codes"], ["FEE01"], scope_kind="money_account", scope_ref="MA1", previous='["FEE01", "FEE02"]')))
    D_bad("D24r r2 S1: a loosening with replaced value JSON null is refused", NIF, lambda cx: cx.execute(VAL_SQL, val(base, 900, previous="null")))
    wk = S["agents.<agent_type>.wake_up_mode.<kind>"]
    D_bad("D24s r2 N1: placeholder values that do not name the key's placeholders are refused", "do not name the placeholders",
          lambda cx: cx.execute(VAL_SQL, val(wk, "by_rule", scope_kind="agent_type", scope_ref="quotation", ph='{"zz": "1"}')))
    D_good("D24t ... and a wake-up mode naming agent_type and kind is written (by_rule, a narrowing)",
           lambda cx: cx.execute(VAL_SQL, val(wk, "by_rule", scope_kind="agent_type", scope_ref="quotation")))
    # review S3: copies are tied to the definition
    D_bad("D24i S3: a forged max_value (1e9) with a value of 999999 is refused", "differ from its definition",
          lambda cx: cx.execute(VAL_SQL, val(base, 999999, min_value=1, max_value=10 ** 9, direction="lower_tighter", proposal=I["cp"], approver=I["u2"])))
    D_bad("D24j S3: a company-only key at scope product_category is refused", "setting_scope_invalid",
          lambda cx: cx.execute(VAL_SQL, val(base, 100, scope_kind="product_category", scope_ref=str(I["cat"]))))
    D_bad("D24k S3: value_type boolean on an integer key is refused", "differ from its definition",
          lambda cx: cx.execute(VAL_SQL, val(base, True, value_type="boolean", allowed_values=["true", "false"], direction="lower_tighter")))
    D_bad("D24l S3: wasm_enabled true through forged allowed values is refused", "differ from its definition",
          lambda cx: cx.execute(VAL_SQL, val(S["extensions.wasm_enabled"], True, company_id=None, scope_kind="installation", allowed_values=["true", "false"],
                                             direction="false_tighter", approver=I["u2"])))
    D_bad("D24m S3: free_prose through forged allowed values is refused", "differ from its definition",
          lambda cx: cx.execute(VAL_SQL, val(nm, "free_prose", allowed_values=["facts_only", "claim_plan", "free_prose"], direction="order",
                                             direction_order=["free_prose", "claim_plan", "facts_only"], proposal=I["cp"], approver=I["u2"])))
    # review rounds 3-4: run as an application role with SELECT on definitions and SELECT and INSERT on values
    APP = "lab_t24_app"
    X(f"""DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP}') THEN CREATE ROLE {APP} NOLOGIN; END IF; END $$""")
    X(f"grant usage on schema nativeflows, types to {APP}")
    X(f"grant select on nativeflows.setting_definition to {APP}")
    X(f"grant select, insert on nativeflows.setting_value to {APP}")

    def as_app(fn):
        def run(cx):
            cx.execute(f"set local role {APP}")
            fn(cx)
        return run
    D_bad("D24t2 r4 S1: the application role cannot rewrite a definition (SELECT only)", "permission denied",
          as_app(lambda cx: cx.execute("update nativeflows.setting_definition set max_value = 1000000 where setting_key = 'automation.max_active_rules'")))
    D_good("D24t3 r4 S1: ... and still writes an honest tightening (the trigger needs no UPDATE on definitions)",
           as_app(lambda cx: cx.execute(VAL_SQL, val(S["automation.replay_min_events"], 25))))

    def temp_definition(cx):
        cx.execute("create temp table setting_definition on commit drop as select * from nativeflows.setting_definition")
        cx.execute("update pg_temp.setting_definition set max_value = 10000, direction = 'neutral' where setting_key = 'automation.max_active_rules'")
        cx.execute(VAL_SQL, val(base, 5000, proposal=I["cp"], approver=I["u2"]))
    D_bad("D24u r3 S1: as the application role, a temporary setting_definition with a wider bound and a neutral direction does not widen the bound (5000 refused against 1000)",
          "ck_setting_value_in_bounds", as_app(temp_definition))

    def temp_values(cx):
        cx.execute("create temp table setting_value (setting_key text, company_id uuid, placeholder_values jsonb, value jsonb, effective_from date, recorded_at timestamptz) on commit drop")
        cx.execute("insert into pg_temp.setting_value values ('analysis.narrative_mode', null, '{}', '\"free_prose\"', '2026-01-01', now())")
        got_ = cx.execute("select value from nativeflows.setting_installation_value('analysis.narrative_mode', '{}', '2026-12-31')").fetchone()
        if got_ != ("facts_only",):
            return
        cx.execute(VAL_SQL.replace("insert into setting_value", "insert into nativeflows.setting_value"), val(nm, "claim_plan"))
    D_bad("D24v r3 S1: as the application role, a temporary setting_value does not feed the definer function (it still returns facts_only), and claim_plan stays refused",
          "looser than the installation value", as_app(temp_values))

    def app_conn():
        c_ = conn()
        c_.execute(f"set role {APP}")
        c_.execute("select set_config('nativeflows.company_id', %s, false)", (str(I["co"]),))
        return c_
    rw = S["automation.replay_window_days"]

    def concurrent(cx):
        c2 = app_conn()
        try:
            c2.execute(VAL_SQL, val(rw, 40))          # holds the (company, key) lock, uncommitted
            cx.execute("set local lock_timeout = '1s'")
            cx.execute(VAL_SQL, val(rw, 45))
        finally:
            c2.rollback(); c2.close()
    D_bad("D24w r3 N2: as the application role, a second change of the same key in the company waits for the first one's lock", "lock timeout", as_app(concurrent))
    import threading, time  # noqa: E401,E402
    c2 = app_conn()
    c2.execute(VAL_SQL, val(rw, 50))                  # a tightening from 30, holding the lock
    res = {}

    def second():
        c3 = app_conn()
        try:
            with c3.transaction():
                c3.execute(VAL_SQL, val(rw, 45))      # tighter than 30, but looser than 50
            res["ok"] = True
        except Exception as e:  # noqa: BLE001
            res["err"] = str(e).splitlines()[0]
        finally:
            c3.close()
    th = threading.Thread(target=second)
    th.start()
    time.sleep(0.8)
    waited = th.is_alive()
    c2.commit(); c2.close()
    th.join(15)
    check("D24x r4 N2: the waiting change is compared with the first change's committed value (45 after 50 is a loosening and is refused without a proposal)",
          waited and "ck_setting_value_loosen" in res.get("err", ""), (waited, res))
    D_bad("D24 a value without a reason is refused", "ck_setting_value_reason", lambda cx: cx.execute(VAL_SQL.replace("'lab'", "' '"), val(base, 10)))
    rls = X("select relrowsecurity, relforcerowsecurity from pg_class where relname = 'setting_value' and relnamespace = 'nativeflows'::regnamespace").fetchone()
    pol = X("select string_agg(qual, ' ') from pg_policies where tablename = 'setting_value'").fetchone()[0] or ""
    pols = {r[0] for r in X("select policyname from pg_policies where tablename = 'setting_value'")}
    check("D25 setting_value has forced row-level security: the company policy with the installation exception and company_ids, and no other read policy (ADR-0017 rule 19)",
          rls == (True, True) and "installation" in pol and "company_ids" in pol and pols == {"company_policy", "company_ids_policy"}, (rls, sorted(pols)))
    fn = X("select prosecdef, proargnames, proargmodes from pg_proc where proname = 'setting_installation_value'").fetchone()
    outs = {n for n, m_ in zip(fn[1], fn[2]) if m_ == "t"} if fn else set()
    got = X("select value, effective_from from setting_installation_value('analysis.narrative_mode', '{}', '2026-12-31')").fetchone()
    check("D25b r2 S2: installation maxima are read through a security-definer function returning only key, value and effective date",
          fn and fn[0] is True and outs == {"setting_key", "value", "effective_from"} and got == ("facts_only", date(2026, 11, 16)), (fn and fn[0], sorted(outs), got))
    EP_SQL = """insert into extension_point (code, module, decision_kind, input_schema, output_schema, code_default, max_fuel_ceiling, max_memory_bytes_ceiling,
                deadline_ms_ceiling, registry_version, recorded_at) values (%s,'cash',%s,'{}','{}','0',%s,%s,%s,'0.1.0',now())"""
    D_good("D26 an extension point within the core ceilings is registered", lambda cx: cx.execute(EP_SQL, ("cash.lab_score", "score", 10000000, 8388608, 50)))
    D_bad("D27 an extension point at an approval decision is refused (hard lock)", "ck_extension_point_decision_kind",
          lambda cx: cx.execute(EP_SQL, ("cash.lab_approve", "approval", 10000000, 8388608, 50)))
    D_bad("D28 ... and so is a fuel ceiling above 50,000,000", "ck_extension_point_fuel", lambda cx: cx.execute(EP_SQL, ("cash.lab_fuel", "score", 60000000, 8388608, 50)))
    D_bad("D29 ... a memory ceiling above 16 MiB", "ck_extension_point_memory", lambda cx: cx.execute(EP_SQL, ("cash.lab_mem", "score", 10000000, 33554432, 50)))
    D_bad("D30 ... and a deadline above 250 ms", "ck_extension_point_deadline", lambda cx: cx.execute(EP_SQL, ("cash.lab_time", "score", 10000000, 8388608, 500)))
    PERM_SQL = """insert into data_processing_permission (id, company_id, data_class, seat_class, provider, processing_region, processing_country, is_cross_border,
                  approved_by_user_id, effective_from, purposes, provider_terms_ref, provider_retention_days, suspended_at, suspension_reason, recorded_at)
                  values (%s,%s,'personal','extraction_vision_personal','cloud',%s,'IE',true,%s,'2026-11-01',%s,'dpa-2026-09',0,%s,%s,now())"""
    D_good("D31 a vision permission names purposes and the provider's terms and retention", lambda cx: cx.execute(
        PERM_SQL, (new(), I["co"], "eu-west", I["u2"], ["supplier_invoice", "contact_card"], None, None)))
    D_bad("D32 a suspension needs its reason", "ck_data_processing_permission_suspended", lambda cx: cx.execute(
        PERM_SQL, (new(), I["co"], "eu-north", I["u2"], None, "2026-11-10T00:00:00Z", None)))
    D_bad("D33 an unknown purpose is refused", "ck_data_processing_permission_purposes", lambda cx: cx.execute(
        PERM_SQL, (new(), I["co"], "eu-south", I["u2"], ["marketing"], None, None)))
    D_good("D34 a permission suspended because the provider changed its terms is written with both", lambda cx: cx.execute(
        PERM_SQL, (new(), I["co"], "eu-east", I["u2"], None, "2026-11-10T00:00:00Z", "provider_terms_changed")))

    def cdef(name):
        return X("select pg_get_constraintdef(oid) from pg_constraint where conname = %s", (name,)).fetchone()[0]
    cols = {r[0] for r in X("select column_name from information_schema.columns where table_schema = 'nativeflows' and table_name = 'bank_statement_line'")}
    check("D35 bank_statement_line carries bank_transaction_code, and match basis bank_charge_rule is allowed (rule 9)",
          "bank_transaction_code" in cols and "bank_charge_rule" in cdef("ck_bank_statement_line_match_basis"))
    check("D36 automation_execution allows the outcome rate_limited without an error code (rule 21)",
          "rate_limited" in cdef("ck_automation_execution_outcome") and "rate_limited" not in cdef("ck_automation_execution_error"))
    lot_cols = {r[0] for r in X("select column_name from information_schema.columns where table_schema = 'nativeflows' and table_name = 'lot'")}
    check("D37 lot carries best_before_date, checked against the manufacture date (rule 26)",
          "best_before_date" in lot_cols and "best_before_date >= manufacture_date" in cdef("ck_lot_best_before"))
    X("drop owned by lab_t24_app"); X("drop role lab_t24_app")
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
