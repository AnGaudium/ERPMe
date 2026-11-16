"""Scenario: AI tuning and development of deterministic functions (ADR-0059), as pure functions and on the DDL drafts.

Run: python t23_ai_artifacts.py [--load]
  The pure checks (part A) always run. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there and loads every DDL file of design/, and the database checks (part D) run.
  NATIVEFLOWS_DOCS points at the docs/ tree (default ~/Projects/NativeFlows/docs); NATIVEFLOWS_LAB_DIR at lab.py and load_all.py
  (default: this file's directory).

A: the rules of ADR-0059 as lab functions: the lifecycle moves of each ladder, allowed and refused (rules 9, 12); pointers,
   rollback and demotion to the version in force before (rules 13, 21); the backtest window strictly after the drafting
   window, a person's default window, minimum case counts, window reuse and the drafting run's reads (rules 14-15);
   held-out cases assigned by hash, filtered from a drafting run's queries and aggregates, and checked by ID sets (rule
   16); evidence frozen by hash and promotion refused on a stale content, engine or baseline hash (rules 14, 19); the
   changed sample (rule 17); parameter bounds, safety caps and order constraints (rule 3); a reduced bank cascade that
   reproduces the worked example's figures (rule 5, S21), the parameters hash without the function version, tied matches
   and assisted states never acting, and re-arming only on evidence newer than a demotion (rules 4-6); the two-threshold
   scorer and its calibration, and the gate-field allowlist with LLM lineage (rule 20); demotion on override drift (rule
   21); matching rules in suggest and confirm mode with step 3-4 scores and caps (rule 10).
D: with --load, on all DDL: evidence rows immutable; the out-of-sample, minimum-count, preview, held-out and sample-size
   checks; transitions immutable and promotions naming evidence and a proposal; shadow outcomes unique and immutable; a
   breached monitor snapshot naming its demotion; golden labels append-only with is_held_out checked by hash.
Not covered: commands, the owning modules' real backtests, the monitor job, UI.
"""
import hashlib, itertools, json, os, random, sys, uuid
from datetime import date, timedelta
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import RESULTS, conn, expect, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
random.seed(59)


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def refused(fn):
    try:
        fn()
    except ValueError as e:
        return str(e)
    return None


# ======================================================================= lifecycle (rules 9, 12, 13, 21)
RANK = {"draft": 0, "backtested": 1, "shadow": 2, "assisted": 3, "active": 4}
LADDER = {   # required stages, stages not offered (rule 9)
    "cash.match_bank_line": ({"backtested", "shadow", "assisted"}, set()),
    "function_without_acting": ({"backtested", "shadow"}, set()),
    "decision_table": ({"backtested"}, {"assisted"}),
    "automation_rule": ({"backtested"}, {"assisted"}),
    "matching_rule": ({"backtested", "assisted"}, set()),
    "report_definition": ({"backtested"}, {"shadow", "assisted"}),
}


def move(kind, frm, to):
    """The triggers' generic rule plus the command's ladder rule; returns None or the refusal."""
    req, never = LADDER[kind]
    if frm == "retired":
        return "retired is final"
    if to == "draft":
        return "never back to draft"
    if to == "retired":
        return "drafts are deleted, not retired" if frm == "draft" else None
    if frm == "draft" and to != "backtested":
        return "leaves draft only to backtested"
    if to in never:
        return f"{kind} has no {to} stage"
    if to == "shadow" and frm in ("assisted", "active"):
        return None
    if RANK[to] <= RANK[frm]:
        return f"may not move from {frm} to {to}"
    skipped = {s for s in RANK if RANK[frm] < RANK[s] < RANK[to]}
    if skipped & req:
        return f"skips a required stage: {sorted(skipped & req)}"
    return None


class Artifact:
    """Pointers (rule 12), rollback (rule 13) and demotion to the version in force before (rule 21)."""
    def __init__(self, kind="cash.match_bank_line"):
        self.kind, self.versions, self.current, self.shadow, self.log, self.valid = kind, {}, None, None, [], set()

    def promote(self, vid, to, evidence_ok=True):
        err = move(self.kind, self.versions[vid], to) or (None if evidence_ok else "artifact_evidence_insufficient")
        if err:
            raise ValueError(err)
        prev_state = self.versions[vid]
        self.versions[vid] = to
        if prev_state == "shadow" and self.shadow == vid:
            self.shadow = None
        if to in ("assisted", "active"):
            self.log.append(("promoted", vid, self.current)); self.current = vid
        elif to == "shadow":
            self.shadow = vid

    def demote(self, vid):
        prev = next((p for m, v, p in reversed(self.log) if m == "promoted" and v == vid and p != vid), None)
        fallback = prev if prev is not None and self.versions.get(prev) in ("assisted", "active") and prev in self.valid else None
        self.current = fallback
        self.versions[vid] = "shadow"; self.shadow = vid
        self.log.append(("demoted", vid, fallback))
        return fallback

    def roll_back(self, vid):
        if vid is not None and self.versions.get(vid) not in ("assisted", "active"):
            raise ValueError("artifact_version_not_eligible")
        if vid is not None and vid not in self.valid:
            raise ValueError("artifact_invalid")
        self.log.append(("rolled_back", self.current, vid)); self.current = vid


# ======================================================================= evidence (rules 14-19)
def held_out(company, case):
    """Rule 16: first byte of SHA-256 of the UTF-8 text '<company>:<case>', canonical UUIDs, below 51."""
    return hashlib.sha256(f"{company}:{case}".encode()).digest()[0] < 51


def drafting_window(draft_date, declared=None):
    """Rule 15: every draft has one; a person's defaults to everything up to the draft's date."""
    return declared or (None, draft_date)


def evidence(version, engine, baseline, drafting, window, cases, run_reads, held_out_ids, figures, thresholds_ok,
             min_cases=1, earlier_windows=(), stage="backtest", steps_present=True):
    """CreateArtifactEvidence: frozen once; refuses a window not after drafting, look-ahead reads and missing steps."""
    if stage in ("backtest", "preview") and window[0] <= drafting[1]:
        raise ValueError("backtest_window_not_after_drafting")
    if not steps_present:
        raise ValueError("drafting_run_steps_missing")
    if any(d > drafting[1] for _, d in run_reads):
        raise ValueError("drafting_window_violated")
    seen = held_out_ids & {rid for rid, _ in run_reads}
    changed = sorted((c for c in cases if c["changed"]), key=lambda c: sha([sha(sorted(x["id"] for x in cases)), c["id"]]))[:20]
    reuse = sum(1 for a, b in earlier_windows if a <= window[1] and window[0] <= b)
    row = {"content_hash": version["hash"], "engine_version": engine, "baseline_hash": baseline, "case_count": len(cases), "min_case_count": min_cases,
           "data_window_hash": sha(sorted(c["id"] for c in cases)), "held_out_seen_count": len(seen), "window_reuse_count": reuse,
           "drafting_reads_hash": sha(sorted(r for r, _ in run_reads)), "changed_sample": [c["id"] for c in changed], "figures": figures, "stage": stage,
           "is_sufficient": stage in ("backtest", "live") and thresholds_ok and not seen and len(cases) >= min_cases}
    row["hash"] = sha(row)
    return row


def execute_promotion(ev, version, engine_now, baseline_now):
    """Rule 19: no figures re-read; only the hashes."""
    if not ev["is_sufficient"]:
        return "artifact_evidence_insufficient"
    if (ev["content_hash"], ev["engine_version"], ev["baseline_hash"]) != (version["hash"], engine_now, baseline_now):
        return "artifact_evidence_stale"
    return "executed"


def drafting_query(rows, company, run_is_drafting, aggregate=False, filterable=True, case_ref=None):
    """Rule 16: the query layer drops held-out cases for a drafting run, rows and aggregates alike; rows of other tables are
    filtered through their declared case-reference column."""
    if not run_is_drafting:
        return sum(r["amount"] for r in rows) if aggregate else rows
    if aggregate and not filterable:
        raise ValueError("held_out_filter_unavailable")
    kept = [r for r in rows if not held_out(company, r[case_ref] if case_ref else r["id"])]
    return sum(r["amount"] for r in kept) if aggregate else kept


# ======================================================================= parameters and the cascade (rules 3-6, 10, 20)
DECL = {   # cash.match_bank_line (rule 5): default, min, max, type, safety cap
    "already_posted_window_days": (5, 0, 10, "days", False), "subset_search_size": (6, 1, 8, "integer", False),
    "score_already_posted": (95, 0, 100, "score", False), "score_reference_exact": (100, 0, 100, "score", False),
    "score_reference_partial": (80, 0, 100, "score", False), "score_account_amount": (90, 0, 100, "score", False),
    "score_account_amount_tied": (60, 0, 60, "score", True), "score_account_subset": (70, 0, 100, "score", False),
    "cap_company_rule": (90, 0, 90, "score", True), "cap_counterparty_unverified_exact": (85, 0, 85, "score", True),
    "cap_counterparty_unverified_partial": (65, 0, 65, "score", True), "cap_paid_by_third_party": (60, 0, 60, "score", True),
    "show_min_score": (0, 0, 100, "score", False)}
ORDER = [("score_reference_exact", "score_reference_partial"), ("score_reference_partial", "score_account_subset"), ("score_account_amount", "score_account_subset")]


def effective(values=None):
    p = {k: d[0] for k, d in DECL.items()}
    p.update(values or {})
    return p


def check_values(values):
    p = effective(values)
    for k, v in values.items():
        d, lo, hi, typ, cap = DECL[k]
        if cap and (v is None or hi != d):
            raise ValueError("parameter_out_of_bounds: safety cap")
        if not lo <= v <= hi:
            raise ValueError(f"parameter_out_of_bounds: {k}={v}")
        if typ in ("integer", "days", "score") and v != int(v):
            raise ValueError(f"parameter_out_of_bounds: {k} is whole")
    for a, b in ORDER:
        if not p[a] > p[b]:
            raise ValueError(f"parameter_order_violated: {a} > {b}")
    return True


def params_hash(p):
    """Rule 4: function code and values; the function version is recorded beside it, not inside."""
    return sha({"function": "cash.match_bank_line", "values": dict(sorted(p.items()))})


def match_line(line, items, posted, accounts, p, rule_partner=None, rule_mode=None):
    """A reduced match_bank_line (ADR-0048 rule 9): steps 1, 3 and 4 over the tunable parameters, with company rules naming a
    partner; returns (partner, items, score, tied) or None. A suggest-mode rule match has no score."""
    for d in sorted(posted, key=lambda d: (abs((d["date"] - line["date"]).days), d["date"], d["id"])):
        if d["amount"] == line["amount"] and abs((d["date"] - line["date"]).days) <= p["already_posted_window_days"] and d["account"] == line["account"]:
            s = p["score_already_posted"]
            return (d["partner"], ("posted", d["id"]), s, False) if s >= p["show_min_score"] else None
    owners = [pid for pid, accs in accounts.items() if line["account"] in accs]
    partner = rule_partner or (owners[0] if len(owners) == 1 else None)
    if partner is None:
        return None
    mine = sorted((i for i in items if i["partner"] == partner), key=lambda i: (i["due"], i["id"]))
    exact = [i for i in mine if i["amount"] == line["amount"]]
    res = None
    if exact:
        tied = len(exact) > 1
        res = (partner, (exact[0]["id"],), p["score_account_amount_tied"] if tied else p["score_account_amount"], tied)
    else:
        pool = mine[:p["subset_search_size"]]
        for k in range(2, len(pool) + 1):
            hit = next((c for c in itertools.combinations(pool, k) if sum(i["amount"] for i in c) == line["amount"]), None)
            if hit:
                res = (partner, tuple(i["id"] for i in hit), p["score_account_subset"], False); break
    if res is None:
        return None
    if rule_partner is not None:
        if rule_mode == "suggest":
            return (res[0], res[1], None, res[3])
        cap = p["cap_company_rule"]
        if partner not in owners:
            cap = min(cap, p["cap_counterparty_unverified_exact"])
        res = (res[0], res[1], min(res[2], cap), res[3])
    return res if res[2] >= p["show_min_score"] else None


def may_auto_post(line, evidence_hash, evidence_outdated, floor, counts_account_rules=False):
    """Rule 6 through auto_post_eligibility: evidenced hash, active or core default, not tied, evidence not marked outdated,
    the floor; account-rule drafts also need evidence that counts account-rule proposals (rule 10)."""
    return (line["hash"] == evidence_hash and line["state"] in ("active", "core_default") and not line["tied"] and not evidence_outdated
            and not line.get("counterparty_unverified") and not line.get("paid_by_third_party")
            and (line.get("basis") != "company_rule_account" or counts_account_rules) and line["score"] is not None and line["score"] >= floor)


class PolicyRuleVersion:
    """Rule 6: stored evidence is set once; a demotion, rollback, invalidation or failed re-evaluation marks it outdated in its
    own transaction; EnablePolicyRule refuses outdated evidence or evidence whose recorded latest transition is not the latest."""
    def __init__(self):
        self.evidence, self.outdated_by = None, None

    def enable(self, evidence, latest_transition):
        if self.evidence is not None:
            raise ValueError("shadow_evidence is set once")
        if evidence.get("outdated") or evidence["latest_transition"] != latest_transition:
            raise ValueError("auto_post_evidence_outdated")
        self.evidence = evidence

    def mark_outdated(self, transition):
        if self.evidence is not None and self.outdated_by is None:
            self.outdated_by = transition


def reevaluation_result(proposals, floor, maximum, minimum_cases=50):
    """Rule 4: a re-evaluation passes on the acting figure only: of proposals at or above the floor and below the maximum, at least
    99% equal people's final results and none went to another partner; below the minimum, too_few_cases leaves the evidence unmarked."""
    acting = [p for p in proposals if p["score"] >= floor and p["amount"] < maximum]
    if len(acting) < minimum_cases:
        return "too_few_cases"
    right = sum(1 for p in acting if p["right"])
    other = any(p["other_partner"] for p in acting)
    return "passed" if F(right, len(acting)) >= F(99, 100) and not other else "failed"


def reevaluate_until_judged(acting_by_day, floor, maximum, start_days=60, max_days=180, minimum=50):
    """Rule 4: with too_few_cases the window widens in one step to the smallest window that holds `minimum` acting proposals,
    capped at max_days; if the cap still holds too few, the evidence stays unmarked (not_judged)."""
    res = reevaluation_result([p for d, p in acting_by_day if d < start_days], floor, maximum, minimum_cases=minimum)
    if res != "too_few_cases":
        return res, start_days
    acting = sorted(d for d, p in acting_by_day if p["score"] >= floor and p["amount"] < maximum)
    if len(acting) < minimum or acting[minimum - 1] + 1 > max_days:
        return "not_judged", max_days
    days = acting[minimum - 1] + 1
    return reevaluation_result([p for d, p in acting_by_day if d < days], floor, maximum, minimum_cases=minimum), days


def function_release_items(owners):
    """Rule 4: one artifact_function_changed item per owner, with the owner in its open key."""
    return sorted({(f"artifact_function_changed:{o}", o) for o in owners})


def match_account_rule(line, rules, p, natural_side):
    """Rule 10: an account rule scores cap_company_rule only for a whole, reference-shaped token and an amount on the account's
    natural side; several rules on a line suggest."""
    tokens = line["description"].split()
    hits = [r for r in rules if r["token"] in tokens and r["state"] in ("assisted", "active")]
    if not hits:
        return None
    if len(hits) > 1:
        return {"target": None, "score": None, "mode": "suggest"}
    r = hits[0]
    shaped = len(r["token"]) >= 4 and any(ch.isdigit() for ch in r["token"])
    side_ok = (line["amount"] < 0) == (natural_side[r["account"]] == "debit")      # an outflow lands on a debit-side expense account
    if r["state"] == "assisted" or not shaped or not side_ok:
        return {"target": r["account"], "score": None, "mode": "suggest"}
    return {"target": r["account"], "score": min(p["cap_company_rule"], p["cap_counterparty_unverified_exact"]), "mode": "confirm", "basis": "company_rule_account"}


TOOLS = {"ListBankStatementLine": True, "GetOpenItemOverview": True, "ListArtifactEvidence": False, "ListAutomationExecution": False,
         "GetAutoPostShadowEvaluation": False, "ListArtifactShadowOutcome": False}       # registered held-out filtered or not


FKS = {("payment", "bank_statement_line_id"): "bank_statement_line", ("payment_line", "payment_id"): "payment", ("settlement", "payment_line_id"): "payment_line"}
CASE_TABLES = {"bank_statement_line"}
DECLARED_PATHS = {"payment": ["bank_statement_line_id"], "payment_line": ["payment_id", "bank_statement_line_id"],
                  "settlement": ["payment_line_id", "payment_id", "bank_statement_line_id"]}


def schema_path_check(fks, declared):
    """Rule 3: every foreign key to a declared case table must be a declared case-reference path (a CI check derived from the schema)."""
    return sorted(f"{t}.{c}" for (t, c), target in fks.items() if target in CASE_TABLES and declared.get(t, [])[:1] != [c])


def drafting_toollist_ok(tool_list):
    """Rule 16: a CI check: a drafting agent type's tool list holds only held-out-filtered queries."""
    return [q for q in tool_list if not TOOLS.get(q, False)]


def calibrate(curve, target):
    ok = [t for t, prec, cov in sorted(curve) if prec >= target]
    return ok[0] if ok else None


FIELDS = {   # field: (declared gate field, computed from), and LLM outputs
    "amount": (True, []), "description": (False, []), "purpose": (False, ["llm:read_description"]),
    "purpose_bucket": (True, ["purpose"]), "match_score": (True, ["amount"]), "confidence": (False, ["llm:read_description"])}


def has_llm_lineage(f, seen=()):
    src = FIELDS.get(f, (False, []))[1]
    return any(s.startswith("llm:") or (s not in seen and has_llm_lineage(s, seen + (f,))) for s in src)


def registry_gate_check():
    """Rule 20: CI refuses is_gate_field on a field with LLM lineage, directly or through computation."""
    return sorted(f for f, (g, _) in FIELDS.items() if g and has_llm_lineage(f))


def gate_inputs_ok(inputs):
    return all(FIELDS.get(f, (False, []))[0] and not has_llm_lineage(f) for f in inputs)


def demote_needed(decisions, overrides, baseline, min_decisions=100, acted=None, baseline_acted=None):
    if decisions < min_decisions:
        return "too_few_decisions"
    rate = F(overrides, decisions)
    limit = max(2 * F(baseline), F(baseline) + F(5, 100))
    drift = acted is not None and baseline_acted is not None and abs(F(acted) - F(baseline_acted)) > F(10, 100)
    return "breached" if rate >= limit or drift else "within"


# ======================================================================= A: pure checks
print("== A: rules as lab functions")
check("A01 the bank cascade's parameter set climbs draft -> backtested -> shadow -> assisted -> active one stage at a time",
      all(move("cash.match_bank_line", a, b) is None for a, b in [("draft", "backtested"), ("backtested", "shadow"), ("shadow", "assisted"), ("assisted", "active")]))
check("A02 a function with an acting path may not skip shadow or assisted",
      "skips a required stage" in (move("cash.match_bank_line", "backtested", "active") or "") and "skips" in (move("cash.match_bank_line", "shadow", "active") or ""))
check("A03 a function without an acting path may skip assisted, never shadow",
      move("function_without_acting", "shadow", "active") is None and "skips" in (move("function_without_acting", "backtested", "active") or ""))
check("A04 a decision table goes backtested -> active (shadow optional) and has no assisted stage",
      move("decision_table", "backtested", "active") is None and move("decision_table", "backtested", "shadow") is None
      and "no assisted" in (move("decision_table", "shadow", "assisted") or ""))
check("A05 a matching rule needs assisted (suggest mode) before active (confirm mode)",
      "skips" in (move("matching_rule", "backtested", "active") or "") and move("matching_rule", "backtested", "assisted") is None and move("matching_rule", "assisted", "active") is None)
check("A06 a report definition goes backtested -> active only", move("report_definition", "backtested", "active") is None
      and "no shadow" in (move("report_definition", "backtested", "shadow") or ""))
check("A07 demotion: active or assisted back to shadow is allowed; active back to backtested or assisted is not",
      move("cash.match_bank_line", "active", "shadow") is None and move("cash.match_bank_line", "assisted", "shadow") is None
      and move("cash.match_bank_line", "active", "backtested") and move("cash.match_bank_line", "active", "assisted"))
check("A08 never back to draft, retired is final, drafts are deleted rather than retired",
      move("decision_table", "backtested", "draft") == "never back to draft" and move("decision_table", "retired", "active") == "retired is final"
      and move("decision_table", "draft", "retired") == "drafts are deleted, not retired" and move("decision_table", "active", "retired") is None)
check("A09 every ladder leaves draft only to backtested (draft -> shadow and draft -> active refused)",
      all(move(k, "draft", "shadow") == move(k, "draft", "active") == "leaves draft only to backtested" for k in LADDER))
art = Artifact(); art.versions = {"v1": "backtested", "v2": "backtested", "v3": "backtested"}; art.valid = {"v1", "v2", "v3"}
for to in ("shadow", "assisted", "active"):
    art.promote("v1", to)
check("A10 promoting to assisted moves the current pointer; shadow sets the shadow pointer and leaving shadow clears it", art.current == "v1" and art.shadow is None)
for to in ("shadow", "assisted", "active"):
    art.promote("v2", to)
art.roll_back("v1")
check("A11 rollback moves the pointer to an earlier active version at once, without evidence", art.current == "v1" and art.log[-1] == ("rolled_back", "v2", "v1"))
check("A12 rollback to a version never promoted is refused (artifact_version_not_eligible), to an invalid one too (artifact_invalid); to null is allowed",
      refused(lambda: art.roll_back("v3")) == "artifact_version_not_eligible"
      and (art.valid.discard("v2") or refused(lambda: art.roll_back("v2")) == "artifact_invalid") and (art.roll_back(None) or art.current is None))
check("A13 a promotion without sufficient evidence is refused", refused(lambda: art.promote("v3", "shadow", evidence_ok=False)) == "artifact_evidence_insufficient")
art2 = Artifact(); art2.versions = {"v0": "backtested", "v1": "backtested"}; art2.valid = {"v0", "v1"}
for v in ("v0", "v1"):
    for to in ("shadow", "assisted", "active"):
        art2.promote(v, to)
fb = art2.demote("v1")
check("A14 demotion falls back to the version in force before (the promotion's previous pointer) and keeps the demoted one in shadow",
      fb == "v0" and art2.current == "v0" and art2.versions["v1"] == "shadow" and art2.shadow == "v1")
art3 = Artifact(); art3.versions = {"v0": "backtested", "v1": "backtested"}; art3.valid = {"v1"}
for v in ("v0", "v1"):
    for to in ("shadow", "assisted", "active"):
        art3.promote(v, to)
check("A15 ... and to the core defaults when that version no longer passes its validity check", art3.demote("v1") is None and art3.current is None)
# -- windows, counts and reuse (rules 14-15)
V1 = {"hash": sha({"show_min_score": 61})}
D0, D1 = date(2026, 5, 1), date(2026, 7, 31)
cases = [{"id": f"L{i:04d}", "changed": i % 21 == 0} for i in range(4812)]
reads = [(f"R{i}", D0 + timedelta(days=i % 90)) for i in range(500)]
H0 = params_hash(effective())


def try_ev(**kw):
    a = dict(version=V1, engine="1.2.0", baseline=H0, drafting=(D0, D1), window=(date(2026, 8, 1), date(2026, 9, 30)), cases=cases, run_reads=reads,
             held_out_ids=set(), figures={"precision": [0.912, 0.961]}, thresholds_ok=True, min_cases=200)
    a.update(kw)
    try:
        return evidence(**a)
    except ValueError as e:
        return str(e)


E1 = try_ev()
check("A16 a backtest on 2026-08-01..09-30 after a drafting window ending 2026-07-31 is accepted and sufficient", isinstance(E1, dict) and E1["is_sufficient"])
check("A17 a window starting on the drafting window's last day is refused (backtest_window_not_after_drafting), an overlapping one too",
      try_ev(window=(D1, date(2026, 9, 30))) == "backtest_window_not_after_drafting" and try_ev(window=(date(2026, 7, 1), date(2026, 8, 31))) == "backtest_window_not_after_drafting")
check("A18 a run that read a row dated after its drafting window is refused (drafting_window_violated); gone steps refuse it (drafting_run_steps_missing)",
      try_ev(run_reads=reads + [("R-late", date(2026, 8, 2))]) == "drafting_window_violated" and try_ev(steps_present=False) == "drafting_run_steps_missing")
pw = drafting_window(date(2026, 10, 1))
check("A19 a person's draft without a declared window has one up to its draft date, so a backtest of September is refused and one of October 2-31 accepted",
      pw == (None, date(2026, 10, 1)) and try_ev(drafting=pw) == "backtest_window_not_after_drafting"
      and isinstance(try_ev(drafting=pw, window=(date(2026, 10, 2), date(2026, 10, 31))), dict))
check("A20 evidence below the minimum case count is never sufficient (empty included)",
      not try_ev(cases=cases[:199])["is_sufficient"] and not try_ev(cases=[])["is_sufficient"] and try_ev(cases=cases[:200])["is_sufficient"])
check("A21 previews are recorded and never sufficient; their windows count as reuse for later evidence",
      not try_ev(stage="preview")["is_sufficient"] and try_ev(earlier_windows=[(date(2026, 8, 1), date(2026, 8, 31)), (date(2026, 9, 15), date(2026, 10, 15)),
                                                                             (date(2025, 1, 1), date(2025, 2, 1))])["window_reuse_count"] == 2)
# -- held-out cases (rule 16)
company = "11111111-1111-7111-8111-111111111111"
ids = [str(uuid.UUID(int=i * 7919 + 1)) for i in range(10000)]
share = sum(held_out(company, x) for x in ids) / len(ids)
check("A22 the deterministic assignment holds out about one case in five (18% to 22% of 10,000)", 0.18 <= share <= 0.22, round(share, 4))
check("A23 the assignment is stable and depends on the company", all(held_out(company, x) == held_out(company, x) for x in ids[:200])
      and any(held_out(company, x) != held_out("22222222-2222-7222-8222-222222222222", x) for x in ids[:200]))
lines_ = [{"id": x, "amount": i + 1} for i, x in enumerate(ids[:300])]
held = {x for x in ids[:300] if held_out(company, x)}
got_rows = drafting_query(lines_, company, run_is_drafting=True)
check("A24 a drafting run's row query never returns a held-out case; an ordinary run sees them all",
      not ({r["id"] for r in got_rows} & held) and len(got_rows) == 300 - len(held) and len(drafting_query(lines_, company, False)) == 300)
check("A25 a drafting run's aggregate excludes held-out cases, and one that cannot be filtered is refused (held_out_filter_unavailable)",
      drafting_query(lines_, company, True, aggregate=True) == sum(r["amount"] for r in lines_ if r["id"] not in held)
      and refused(lambda: drafting_query(lines_, company, True, aggregate=True, filterable=False)) == "held_out_filter_unavailable")
pays = [{"id": f"PAY{i}", "line_id": r["id"], "amount": r["amount"]} for i, r in enumerate(lines_)]
check("A25b rows that point at a case are filtered through the declared case-reference column: no payment of a held-out line reaches a drafting run",
      not ({p_["line_id"] for p_ in drafting_query(pays, company, True, case_ref="line_id")} & held))
check("A25c the CI check refuses a drafting tool list with evidence, execution, shadow or auto-post evaluation reads, and accepts held-out-filtered queries only",
      drafting_toollist_ok(["ListBankStatementLine", "GetOpenItemOverview"]) == []
      and drafting_toollist_ok(["ListBankStatementLine", "ListArtifactEvidence", "GetAutoPostShadowEvaluation", "ListAutomationExecution"]) == ["ListArtifactEvidence", "GetAutoPostShadowEvaluation", "ListAutomationExecution"])
clean_reads = [(r["id"], D0) for r in got_rows]
check("A26 the ID-set check, second line: a drafting run whose reads came through the filter yields sufficient evidence",
      try_ev(run_reads=clean_reads, held_out_ids=held)["is_sufficient"])
leak = try_ev(run_reads=clean_reads + [(sorted(held)[0], D0)], held_out_ids=held)
check("A27 one held-out ID among the reads makes it insufficient, with held_out_seen_count 1 (held_out_case_seen)", leak["held_out_seen_count"] == 1 and not leak["is_sufficient"])
# -- frozen evidence and staleness (rules 14, 19)
E1b = try_ev()
check("A28 the same inputs freeze the same evidence hash; a changed case set changes the data window hash",
      E1b["hash"] == E1["hash"] and try_ev(cases=cases[:-1])["data_window_hash"] != E1["data_window_hash"])
check("A29 promotion executes when content, engine and baseline still equal the evidence's; an engine release, a changed baseline or content make it stale",
      execute_promotion(E1, V1, "1.2.0", H0) == "executed" and execute_promotion(E1, V1, "1.3.0", H0) == "artifact_evidence_stale"
      and execute_promotion(E1, V1, "1.2.0", params_hash(effective({"show_min_score": 10}))) == "artifact_evidence_stale"
      and execute_promotion(E1, {"hash": sha({"x": 1})}, "1.2.0", H0) == "artifact_evidence_stale")
check("A30 insufficient evidence never executes, whatever the hashes", execute_promotion(leak, V1, "1.2.0", H0) == "artifact_evidence_insufficient")
check("A31 at most 20 changed decisions are sampled, all of them changed, in the same order every time",
      len(E1["changed_sample"]) == 20 and all(int(c[1:]) % 21 == 0 for c in E1["changed_sample"]) and E1["changed_sample"] == E1b["changed_sample"])
# -- bounds, caps and order (rule 3)
check("A32 every core default lies within its bounds and meets the order constraints, and safety caps end at their defaults",
      check_values(effective()) and all(d[2] == d[0] for d in DECL.values() if d[4]))
check("A33 out of bounds is refused (window 11 days, subset size 9, a score of 101)",
      all(refused(lambda v=v: check_values(v)) for v in ({"already_posted_window_days": 11}, {"subset_search_size": 9}, {"score_account_subset": 101})))
check("A34 a safety cap may be lowered (60 -> 50), never raised (60 -> 61) or switched off (null); the tied score is one",
      check_values({"cap_paid_by_third_party": 50}) and refused(lambda: check_values({"cap_paid_by_third_party": 61}))
      and refused(lambda: check_values({"cap_paid_by_third_party": None})) and refused(lambda: check_values({"score_account_amount_tied": 95})))
check("A35 order constraints: a partial reference may not score above an exact one, nor a subset above a partial reference or an account-and-amount match (parameter_order_violated)",
      "parameter_order_violated" in (refused(lambda: check_values({"score_reference_partial": 100})) or "")
      and "parameter_order_violated" in (refused(lambda: check_values({"score_account_subset": 85})) or "")
      and "parameter_order_violated" in (refused(lambda: check_values({"score_account_amount": 70})) or ""))
p1 = effective({"show_min_score": 61})
check("A36 the parameters hash ignores key order and the function version (recorded beside it), and changes with any value",
      params_hash(p1) == params_hash(dict(random.sample(list(p1.items()), len(p1)))) and params_hash(p1) != H0 and "1.2.0" not in json.dumps({"v": dict(sorted(p1.items()))}))
# -- the worked example from the reduced cascade (rules 5, 18; review S21)
d0 = date(2026, 8, 10)
dataset = []
for i in range(4812):
    pid, acc = f"P{i}", f"ACC-{i}"
    if i < 3385:                                    # one exact item, people agree
        items = [{"id": f"I{i}a", "partner": pid, "amount": 100, "due": d0}]; label = (pid, (f"I{i}a",)); known = True
    elif i < 3385 + 138:                            # one exact item, people matched another document
        items = [{"id": f"I{i}a", "partner": pid, "amount": 100, "due": d0}]; label = (pid, (f"X{i}",)); known = True
    elif i < 3523 + 38:                             # tied: two equal items, people took the oldest
        items = [{"id": f"I{i}a", "partner": pid, "amount": 100, "due": d0}, {"id": f"I{i}b", "partner": pid, "amount": 100, "due": d0 + timedelta(1)}]
        label = (pid, (f"I{i}a",)); known = True
    elif i < 3523 + 230:                            # tied, people took the other one
        items = [{"id": f"I{i}a", "partner": pid, "amount": 100, "due": d0}, {"id": f"I{i}b", "partner": pid, "amount": 100, "due": d0 + timedelta(1)}]
        label = (pid, (f"I{i}b",)); known = True
    else:                                           # no partner owns the account
        items, label, known = [], None, False
    dataset.append(({"amount": 100, "account": acc, "date": d0}, items, {pid: {acc}} if known else {}, label))


def backtest(p):
    dec = right = 0
    for line, items, accounts, label in dataset:
        m = match_line(line, items, [], accounts, p)
        if m:
            dec += 1
            right += (m[0], m[1]) == label
    return dec, right


b0, b1 = backtest(effective()), backtest(p1)
cov0, cov1 = F(b0[0], 4812), F(b1[0], 4812)
prec0, prec1 = F(b0[1], b0[0]), F(b1[1], b1[0])
check("A37 the reduced cascade reproduces the example: the defaults propose 3,753 (78.0%) with 3,423 right (91.2%); version 1 proposes 3,523 (73.2%) with 3,385 right (96.1%)",
      b0 == (3753, 3423) and b1 == (3523, 3385) and round(float(cov0) * 100, 1) == 78.0 and round(float(cov1) * 100, 1) == 73.2
      and round(float(prec0) * 100, 1) == 91.2 and round(float(prec1) * 100, 1) == 96.1, (b0, b1))
check("A38 ... and the promotion thresholds hold: precision at least 95% and above the baseline, coverage loss 4.8 points within 5, 230 decisions changed",
      prec1 >= F(95, 100) and prec1 > prec0 and (cov0 - cov1) * 100 <= 5 and round(float(cov0 - cov1) * 100, 1) == 4.8 and b0[0] - b1[0] == 230)
# -- the cascade's acting rules (rules 5, 6)
accounts = {"P1": {"ACC-1"}, "P2": {"ACC-2"}, "P3": {"ACC-3"}}
items = [{"id": "I1", "partner": "P1", "amount": 100, "due": d0}, {"id": "I2", "partner": "P1", "amount": 100, "due": d0 + timedelta(1)},
         {"id": "I3", "partner": "P2", "amount": 70, "due": d0}, {"id": "I4", "partner": "P2", "amount": 30, "due": d0 + timedelta(2)},
         {"id": "I5", "partner": "P3", "amount": 55, "due": d0}]
posted = [{"id": "D1", "partner": "P3", "amount": 55, "date": d0 - timedelta(4), "account": "ACC-3"}]
P0 = effective()
tied = match_line({"amount": 100, "account": "ACC-1", "date": d0}, items, [], accounts, P0)
check("A39 a tied match is marked tied, scores the capped 60, and is never auto-posted whatever the floor",
      tied == ("P1", ("I1",), 60, True) and not may_auto_post({"hash": H0, "state": "core_default", "tied": True, "score": 60}, H0, False, 0))
check("A40 the subset step finds two items summing exactly within subset_search_size, and nothing with size 1; step 1 finds a receipt within the window",
      match_line({"amount": 100, "account": "ACC-2", "date": d0}, items, [], accounts, P0) == ("P2", ("I3", "I4"), 70, False)
      and match_line({"amount": 100, "account": "ACC-2", "date": d0}, items, [], accounts, effective({"subset_search_size": 1})) is None
      and match_line({"amount": 55, "account": "ACC-3", "date": d0}, items, posted, accounts, P0)[1] == ("posted", "D1"))
H1 = params_hash(p1)
line_h1_active = {"hash": H1, "state": "active", "tied": False, "score": 95}
line_h0 = {"hash": H0, "state": "core_default", "tied": False, "score": 95}
check("A41 auto-post needs the evidenced hash: a proposal under H1 is not auto-posted with evidence under H0",
      may_auto_post(line_h0, H0, False, 90) and not may_auto_post(line_h1_active, H0, False, 90))
check("A42 assisted never acts, and the line's own recorded state shows it",
      not may_auto_post(dict(line_h1_active, state="assisted"), H1, False, 90) and may_auto_post(line_h1_active, H1, False, 90))
prv = PolicyRuleVersion()
prv.enable({"hash": H0, "latest_transition": None}, latest_transition=None)
prv.mark_outdated("T-demotion")
check("A43 a demotion back to H0 marks the H0 evidence outdated in its own transaction: no auto-post, with no time compared",
      prv.outdated_by == "T-demotion" and not may_auto_post(line_h0, H0, prv.outdated_by is not None, 90))
prv2 = PolicyRuleVersion()
check("A43b EnablePolicyRule refuses evidence recorded before the latest transition, or marked outdated; a new rule version with evidence naming the latest transition is accepted",
      refused(lambda: prv2.enable({"hash": H0, "latest_transition": None}, latest_transition="T-demotion")) == "auto_post_evidence_outdated"
      and refused(lambda: prv2.enable({"hash": H0, "latest_transition": "T-demotion", "outdated": True}, latest_transition="T-demotion")) == "auto_post_evidence_outdated"
      and (prv2.enable({"hash": H0, "latest_transition": "T-demotion"}, latest_transition="T-demotion") or prv2.evidence is not None)
      and refused(lambda: prv.enable({"hash": H0, "latest_transition": "T-demotion"}, "T-demotion")) == "shadow_evidence is set once")
line_after_release = dict(line_h1_active, function_version="1.3.0")      # proposed after a release; evidence was created under 1.2.0
check("A44b a release raises one artifact_function_changed item per owner, the owner in its key, also for a company on core defaults (company_owner)",
      function_release_items(["company_owner", "chief_accountant", "chief_accountant"]) == [("artifact_function_changed:chief_accountant", "chief_accountant"),
                                                                                         ("artifact_function_changed:company_owner", "company_owner")])
check("A44 a function release leaves the hash and so the binding: a line recorded under 1.3.0 still meets evidence created under 1.2.0, the version being recorded beside the hash",
      may_auto_post(line_after_release, H1, False, 90) and line_after_release["function_version"] == "1.3.0" and line_after_release["hash"] == H1)
# -- two thresholds and calibration (rule 20)
curve = [(50, 0.81, 0.92), (60, 0.88, 0.85), (70, 0.95, 0.74), (80, 0.991, 0.55), (90, 0.997, 0.31)]
check("A45 calibration picks the lowest threshold meeting the target precision (95% -> 70, 99% -> 80) and off (None) when none does",
      calibrate(curve, 0.95) == 70 and calibrate(curve, 0.99) == 80 and calibrate(curve, 0.999) is None)
scores = [(random.randint(0, 100), random.random() < 0.9) for _ in range(2000)]
false_acts = [sum(1 for s, ok in scores if s >= t and not ok) for t in range(0, 101, 10)]
check("A46 raising the act threshold never adds a false act (monotone over 2,000 random scored cases); with act off nothing acts",
      all(a >= b for a, b in zip(false_acts, false_acts[1:])) and not any((lambda act: act is not None and s >= act)(None) for s, _ in scores))
check("A47 gate fields are an allowlist: a deterministic field passes; a field filled from an LLM output, directly or through computation, never does",
      gate_inputs_ok(["amount", "match_score"]) and not gate_inputs_ok(["purpose"]) and not gate_inputs_ok(["purpose_bucket"]) and not gate_inputs_ok(["confidence"])
      and not gate_inputs_ok(["description"]))
check("A48 the CI lineage check refuses purpose_bucket, declared a gate field though computed from an LLM output", registry_gate_check() == ["purpose_bucket"], registry_gate_check())
# -- monitoring and demotion (rule 21)
check("A49 the worked example: 263 overrides in 2,350 decisions (11.2%) against an evidenced 2.9% breaches max(5.8%, 7.9%); 150 stay within; under 100 nothing is judged",
      demote_needed(2350, 263, F(29, 1000)) == "breached" and demote_needed(2350, 150, F(29, 1000)) == "within" and demote_needed(99, 90, F(29, 1000)) == "too_few_decisions")
check("A50 an acted share that moves more than 10 points breaches even with few overrides", demote_needed(500, 1, F(2, 100), acted=F(40, 100), baseline_acted=F(25, 100)) == "breached")
check("A51 a small company's minimum (30 decisions) lets the monitor judge where 100 would not", demote_needed(40, 20, F(5, 100), min_decisions=30) == "breached")
# -- matching rules (rule 10)
acme = {"ACME": {"ACC-A"}}
acme_items = [{"id": "A1", "partner": "ACME", "amount": 500, "due": d0}]
line_a = {"amount": 500, "account": "ACC-A", "date": d0}
check("A52 a rule in assisted matches in suggest mode: steps 3-4 find the item, no score, so never auto-posted",
      match_line(line_a, acme_items, [], acme, P0, rule_partner="ACME", rule_mode="suggest") == ("ACME", ("A1",), None, False))
check("A53 in confirm mode steps 3-4 score the match (90) within cap_company_rule; a tied pair stays tied and never acts",
      match_line(line_a, acme_items, [], acme, P0, rule_partner="ACME", rule_mode="confirm") == ("ACME", ("A1",), 90, False)
      and match_line(line_a, acme_items + [{"id": "A2", "partner": "ACME", "amount": 500, "due": d0 + timedelta(3)}], [], acme, P0, rule_partner="ACME", rule_mode="confirm")[3])
check("A54 the counterparty cap applies when the paying account is not the partner's (90 capped to 85), and a lowered cap_company_rule lowers it further",
      match_line({"amount": 500, "account": "ACC-Z", "date": d0}, acme_items, [], acme, P0, rule_partner="ACME", rule_mode="confirm")[2] == 85
      and match_line(line_a, acme_items, [], acme, effective({"cap_company_rule": 75}), rule_partner="ACME", rule_mode="confirm")[2] == 75)

# two-step path property test: payment lines reach the bank line through their payment
lines2 = [{"id": str(uuid.UUID(int=900000 + i))} for i in range(400)]
pays2 = [{"id": f"PY{i}", "bank_statement_line_id": l["id"]} for i, l in enumerate(lines2)]
plines = [{"id": f"PL{i}-{k}", "payment_id": p["id"], "amount": 1} for i, p in enumerate(pays2) for k in range(random.randint(1, 3))]
pay_of = {p["id"]: p["bank_statement_line_id"] for p in pays2}
via = [dict(pl, case=pay_of[pl["payment_id"]]) for pl in plines]                 # the declared path payment_line -> payment -> line
kept_pl = drafting_query(via, company, True, case_ref="case")
check("A25d property test over 400 lines: a filtered query of payment lines, reached in two steps through their payment, returns no row tied to a held-out case",
      not any(held_out(company, pay_of[pl["payment_id"]]) for pl in kept_pl) and len(kept_pl) == sum(1 for pl in via if not held_out(company, pl["case"])))
check("A25e the schema-derived CI check: every foreign key to a case table is a declared case-reference column; an undeclared one is refused",
      schema_path_check(FKS, DECLARED_PATHS) == [] and schema_path_check({**FKS, ("refund", "bank_statement_line_id"): "bank_statement_line"}, DECLARED_PATHS) == ["refund.bank_statement_line_id"])
reev = [{"score": 95, "amount": 100, "right": i != 0 and i != 1, "other_partner": False} for i in range(412)]
check("A44c the worked example's re-evaluation passes on the acting figure: 410 of 412 proposals at or above the floor (99.5%), none to another partner",
      reevaluation_result(reev, 90, 20_000_000) == "passed")
check("A44d one proposal to another partner, or 98% right, fails it; under the minimum it is too_few_cases and leaves the evidence unmarked",
      reevaluation_result(reev[:-1] + [dict(reev[-1], other_partner=True)], 90, 20_000_000) == "failed"
      and reevaluation_result([dict(p, right=i % 50 != 0) for i, p in enumerate(reev)], 90, 20_000_000) == "failed"
      and reevaluation_result(reev[:20], 90, 20_000_000) == "too_few_cases")
quiet = [(d * 3, {"score": 95, "amount": 100, "right": True, "other_partner": False}) for d in range(60)]          # one acting proposal every 3 days
check("A44e a small company: 20 acting proposals in 60 days is too few; the window widens in one step to the smallest that holds 50 (148 days) and judges the release",
      reevaluate_until_judged(quiet, 90, 20_000_000) == ("passed", 148), reevaluate_until_judged(quiet, 90, 20_000_000))
check("A44f a company too quiet even at the 180-day maximum is not judged: the evidence stays unmarked and the owner's item says so",
      reevaluate_until_judged([(d * 5, q) for d, (_, q) in enumerate(quiet)], 90, 20_000_000)[0] == "not_judged")
fee = [{"token": "BKFEE01", "account": "bank_charges", "state": "active"}]
NAT = {"bank_charges": "debit"}
check("A55 an account rule: an outflow with the whole, reference-shaped token drafts to the account in confirm mode, capped (85 under the unverified-counterparty cap)",
      match_account_rule({"description": "MONTHLY BKFEE01", "amount": -12}, fee, P0, NAT) == {"target": "bank_charges", "score": 85, "mode": "confirm", "basis": "company_rule_account"})
check("A56 ... an inflow with the token (against the natural side), a token that is not reference-shaped, or two rules on one line only suggest",
      match_account_rule({"description": "BKFEE01 REFUND", "amount": 12}, fee, P0, NAT)["mode"] == "suggest"
      and match_account_rule({"description": "FEES", "amount": -5}, [{"token": "FEES", "account": "bank_charges", "state": "active"}], P0, NAT)["mode"] == "suggest"
      and match_account_rule({"description": "BKFEE01 ACMEPAY-7781", "amount": -5}, fee + [{"token": "ACMEPAY-7781", "account": "bank_charges", "state": "active"}], P0, NAT)["mode"] == "suggest")
acct_line = {"hash": H0, "state": "core_default", "tied": False, "score": 85, "basis": "company_rule_account"}
check("A57 account-rule drafts whose counterparty account a partner owns are auto-posted only when the auto-post evidence counts account-rule proposals",
      not may_auto_post(acct_line, H0, False, 80) and may_auto_post(acct_line, H0, False, 80, counts_account_rules=True))
check("A58 a draft under the unverified (or third-party) cap carries the flag and is never auto-posted, account rules included, whatever the evidence counts",
      not may_auto_post(dict(acct_line, counterparty_unverified=True), H0, False, 80, counts_account_rules=True)
      and not may_auto_post(dict(line_h0, paid_by_third_party=True, score=95), H0, False, 60))

# ======================================================================= D: database checks (--load)
if "--load" in sys.argv:
    import psycopg  # noqa: E402,F401
    from load_all import load_all  # noqa: E402
    dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = load_all(dsn, DOCS)
    check("D01 load_all.py loads every DDL file of design/ with the configuration file", n_tables > 200, n_tables)
    c = conn(); c.autocommit = True
    X = c.execute
    I = {k: new() for k in ["u", "co", "ps", "pv1", "ev1", "tr1"]}
    t = str(I["co"])[-8:]
    X("insert into currency (code, minor_unit) values ('USD', 2) on conflict do nothing")
    X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I["u"], "u23" + t))
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','USD','UTC','l10n_test','test','warehouse',%s,'en')", (I["co"], "C23-" + t, I["u"]))
    X("select set_config('nativeflows.company_id', %s, false)", (str(I["co"]),))
    H = hashlib.sha256(b"y").hexdigest()
    X("insert into parameter_set (id, company_id, function_code, owner_user_id, recorded_at) values (%s,%s,'cash.match_bank_line',%s,now())", (I["ps"], I["co"], I["u"]))
    X("""insert into parameter_set_version (id, company_id, parameter_set_id, version, function_version, parameters_hash, content_hash, registry_version, drafted_by_kind, drafted_by_id,
         on_behalf_of_id, drafting_window_from, drafting_window_to, recorded_at) values (%s,%s,%s,1,'1.2.0',%s,%s,'1.0.0','human',%s,%s,'2026-05-01','2026-07-31',now())""",
      (I["pv1"], I["co"], I["ps"], H, H, I["u"], I["u"]))

    def ev_row(cx, eid=None, stage="backtest", win_from="2026-08-01", sufficient=True, seen=0, sample=None, cases=4812, minimum=200, reuse=0):
        cx.execute("""insert into artifact_promotion_evidence (id, company_id, artifact_kind, artifact_id, artifact_version_id, stage, content_hash, engine_version, baseline_hash,
                      drafting_window_from, drafting_window_to, evaluation_window_from, evaluation_window_to, case_count, min_case_count, window_reuse_count, data_window_hash,
                      held_out_case_count, held_out_seen_count, figures, changed_sample, thresholds, is_sufficient, created_by_user_id, recorded_at)
                      values (%s,%s,'parameter_set',%s,%s,%s,%s,'1.2.0',%s,'2026-05-01','2026-07-31',%s,'2026-09-30',%s,%s,%s,%s,60,%s,'{}',%s,'{}',%s,%s,now())""",
                   (eid or new(), I["co"], I["ps"], I["pv1"], stage, H, H, win_from, cases, minimum, reuse, H, seen, json.dumps(sample or []), sufficient, I["u"]))

    def D_bad(name, match, fn):
        def run(cx):
            cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, True, match)

    def D_good(name, fn):
        def run(cx):
            cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, False)
    D_good("D02 backtest evidence on a window after the drafting window, above its minimum, is written", lambda cx: ev_row(cx, eid=I["ev1"]))
    D_bad("D03 evidence rows are never updated (frozen)", "never updated or deleted", lambda cx: cx.execute("update artifact_promotion_evidence set is_sufficient=false where id=%s", (I["ev1"],)))
    D_bad("D04 ... or deleted", "never updated or deleted", lambda cx: cx.execute("delete from artifact_promotion_evidence where id=%s", (I["ev1"],)))
    D_bad("D05 the database refuses a backtest window that starts on the drafting window's last day (out of sample)", "ck_artifact_promotion_evidence_out_of_sample",
          lambda cx: ev_row(cx, win_from="2026-07-31"))
    D_bad("D06 ... and a preview's too", "ck_artifact_promotion_evidence_out_of_sample", lambda cx: ev_row(cx, stage="preview", win_from="2026-07-31", sufficient=False))
    D_good("D07 live evidence over a shadow period is not bound by the drafting window", lambda cx: ev_row(cx, stage="live", win_from="2026-07-15"))
    D_bad("D08 sufficient evidence reaches its minimum case count (empty evidence is never sufficient)", "ck_artifact_promotion_evidence_minimum",
          lambda cx: ev_row(cx, cases=0))
    D_bad("D09 a minimum of zero is refused", "ck_artifact_promotion_evidence_min_case_count", lambda cx: ev_row(cx, minimum=0))
    D_bad("D10 a preview is never sufficient", "ck_artifact_promotion_evidence_stage_sufficient", lambda cx: ev_row(cx, stage="preview"))
    D_good("D11 a preview is recorded as insufficient, with its window reuse", lambda cx: ev_row(cx, stage="preview", sufficient=False, reuse=2))
    D_bad("D12 evidence whose drafting run saw a held-out case is never sufficient", "ck_artifact_promotion_evidence_held_out", lambda cx: ev_row(cx, seen=1))
    def reeval(cx, version=False, kind="system", user=None, stage="reevaluation"):
        cx.execute("""insert into artifact_promotion_evidence (id, company_id, artifact_kind, artifact_id, artifact_version_id, function_code, stage, content_hash, engine_version,
                      baseline_hash, drafting_window_to, evaluation_window_from, evaluation_window_to, case_count, min_case_count, window_reuse_count, data_window_hash, figures,
                      thresholds, is_sufficient, created_by_kind, created_by_user_id, recorded_at)
                      values (%s,%s,'parameter_set',%s,%s,'cash.match_bank_line',%s,%s,'1.3.0',%s,'2026-09-30','2026-10-01','2026-11-30',300,200,0,%s,'{}','{}',false,%s,%s,now())""",
                   (new(), I["co"], I["ps"] if version else None, I["pv1"] if version else None, stage, H, H, H, kind, user))
    D_good("D12b a re-evaluation of a company's core defaults has no artifact version, names the function, and is written by the monitor job", lambda cx: reeval(cx))
    D_bad("D12c only a re-evaluation may lack a version", "ck_artifact_promotion_evidence_subject", lambda cx: reeval(cx, stage="backtest", kind="human", user=I["u"]))
    D_bad("D12d only a re-evaluation may be written by the system; other evidence names its person", "ck_artifact_promotion_evidence_creator",
          lambda cx: reeval(cx, version=True, stage="live"))
    D_bad("D13 the changed sample holds at most 20 decisions", "ck_artifact_promotion_evidence_sample", lambda cx: ev_row(cx, sample=[f"L{i}" for i in range(21)]))

    def transition(cx, move_, evidence=None, proposal=None, frm="shadow", to="assisted", tid=None):
        cx.execute("""insert into artifact_transition (id, company_id, artifact_kind, artifact_id, artifact_version_id, move, from_state, to_state, evidence_id, change_proposal_id,
                      actor_kind, actor_id, on_behalf_of_id, recorded_at) values (%s,%s,'parameter_set',%s,%s,%s,%s,%s,%s,%s,'system',%s,%s,now())""",
                   (tid or new(), I["co"], I["ps"], I["pv1"], move_, frm, to, evidence, proposal, I["u"], I["u"]))
    D_bad("D14 a promotion names evidence and an approved change proposal", "ck_artifact_transition_promoted", lambda cx: transition(cx, "promoted", evidence=I["ev1"]))
    D_good("D15 a backtested move from draft names its evidence", lambda cx: transition(cx, "backtested", evidence=I["ev1"], frm="draft", to="backtested"))
    D_bad("D16 a demotion goes from assisted or active to shadow only", "ck_artifact_transition_demoted", lambda cx: transition(cx, "demoted", frm="active", to="backtested"))
    D_good("D17 a demotion from active to shadow is recorded", lambda cx: transition(cx, "demoted", frm="active", to="shadow", tid=I["tr1"]))
    D_bad("D18 a deprecation finding changes no state", "ck_artifact_transition_deprecation", lambda cx: transition(cx, "deprecation_found", frm="active", to="shadow"))
    D_bad("D19 transitions are never updated", "never updated or deleted", lambda cx: cx.execute("update artifact_transition set reason='x' where id=%s", (I["tr1"],)))

    def snapshot(cx, result, tid=None, overrides=263):
        cx.execute("""insert into artifact_monitor_snapshot (id, company_id, artifact_kind, artifact_id, artifact_version_id, window_from, window_to, decision_count, override_count,
                      baseline_override_rate, thresholds, result, transition_id, recorded_at) values (%s,%s,'parameter_set',%s,%s,'2026-11-11','2026-12-10',2350,%s,0.029,'{}',%s,%s,now())""",
                   (new(), I["co"], I["ps"], I["pv1"], overrides, result, tid))
    D_bad("D20 a breached snapshot names the demotion it caused", "ck_artifact_monitor_snapshot_breach", lambda cx: snapshot(cx, "breached"))
    D_good("D21 ... and is accepted with it", lambda cx: snapshot(cx, "breached", tid=I["tr1"]))
    D_bad("D22 overrides never exceed decisions", "ck_artifact_monitor_snapshot_overrides", lambda cx: snapshot(cx, "within", overrides=2351))

    def shadow(cx, case):
        cx.execute("""insert into artifact_shadow_outcome (id, company_id, artifact_kind, artifact_id, artifact_version_id, case_table, case_id, shadow_outcome, current_outcome,
                      current_hash, recorded_at) values (%s,%s,'parameter_set',%s,%s,'bank_statement_line',%s,'{}','{}',%s,now())""", (new(), I["co"], I["ps"], I["pv1"], case, H))
    CASE = new()
    shadow(c, CASE)
    D_bad("D23 one shadow outcome per version and case", "duplicate key", lambda cx: shadow(cx, CASE))
    D_bad("D24 shadow outcomes are never updated", "never updated or deleted", lambda cx: cx.execute("update artifact_shadow_outcome set shadow_outcome='[]' where case_id=%s", (CASE,)))

    def label(cx, lid, case, held=None):
        flag = held_out(str(I["co"]), str(case)) if held is None else held
        cx.execute("""insert into golden_case_label (id, company_id, function_code, case_table, case_id, expected, is_held_out, labelled_by_user_id, labelled_on, recorded_at)
                      values (%s,%s,'cash.match_bank_line','bank_statement_line',%s,'{"partner_id": "x"}',%s,%s,'2026-10-01',now())""", (lid, I["co"], case, flag, I["u"]))
    L1, L2, LC = new(), new(), new()
    label(c, L1, LC)
    D_bad("D25 is_held_out must equal the hash assignment (a database check)", "ck_golden_case_label_held_out",
          lambda cx: label(cx, new(), new_c := new(), held=not held_out(str(I["co"]), str(new_c))))
    held_case = next(x for x in (new() for _ in range(200)) if held_out(str(I["co"]), str(x)))
    D_good("D26 a held-out case is labelled with is_held_out true, matching the database's hash", lambda cx: label(cx, new(), held_case))
    D_bad("D27 one current label per case", "ux_golden_case_label_current", lambda cx: label(cx, new(), LC))
    D_bad("D28 a label's expected outcome never changes (append-only)", "append-only", lambda cx: cx.execute("update golden_case_label set expected='{}' where id=%s", (L1,)))
    D_good("D29 a correction retires the old label (retired_at set once) and records a new one", lambda cx: (
        cx.execute("update golden_case_label set retired_at=now() where id=%s", (L1,)), label(cx, L2, LC)))
    D_bad("D30 retired_at is set once", "append-only", lambda cx: cx.execute("update golden_case_label set retired_at=now() + interval '1 day' where id=%s", (L1,)))
    D_bad("D31 labels are never deleted", "never deleted", lambda cx: cx.execute("delete from golden_case_label where id=%s", (L2,)))
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
