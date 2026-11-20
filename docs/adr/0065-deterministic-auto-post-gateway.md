# ADR-0065: Deterministic auto-post gateway (maker-checker)

Status: proposed (2026-11-16) under ADR-0005 (builder Claude Opus 5.5).
Design items: DS-28 (policy), DS-34 (agent workflows and evidence), DS-04 (errors). Related decisions: D2, D12. Principles 2, 3, 12, 13. ADR-0004, ADR-0005, ADR-0007, ADR-0008, ADR-0013, ADR-0020, ADR-0022, ADR-0029, ADR-0041, ADR-0042, ADR-0043, ADR-0047, ADR-0048, ADR-0050, ADR-0051, ADR-0057, ADR-0058, ADR-0059, ADR-0063, ADR-0064; spec 03, 14.

## Decision

The author's design draft "Deterministic Policy Engine (Maker-Checker Gateway)" of 2026-11-16 asks for a checker that lets the system post a draft without a person when deterministic rules pass. The author directed that every number is set by the customer and that an agent-assisted tool helps build the rules. On tainted drafts the author answered (2026-11-16): allow it, configured by the customer. The chief architect's decisions D1 to D10 of 2026-11-16 are applied here.

**One gateway, inside `policy`.** The auto-post path of ADR-0043 rule 14 already evaluates unattended postings as `system` with an owner, a maximum, confirmation and shadow evidence. Until now only the bank cascade could use it (ADR-0043 rule 5). This ADR generalizes it: any document type whose owning module declares an *auto-post checker* can be auto-posted through the same path. The gateway is a pure function of `policy` (layer 2). It calls domain checker functions that modules register through a hook, wired by `app`, the pattern of the existing evidence hooks. No new module is added.

**Maker and checker.** An agent or a deterministic import makes a draft. The dispatcher simulates the posting. The gateway checks the draft and its simulation and returns one of three decisions: `auto_post`, `require_human` or `reject`. Every decision writes a `policy_decision` row with the checker's evidence. An `auto_post` posts as `system` in a new transaction, pinned to the simulated plan hash and business date, and the policy rule's owner confirms it as every auto-post is confirmed today.

**Customer configuration, core code.** Thresholds are registered settings with bounds, directions and safe core defaults (ADR-0063). Logic over several variables lives in typed decision tables (ADR-0058). The checker code holds no customer constant. A company starts with auto-post `off` for every document type.

**Hard rules.** No LLM in the checker. Fail closed: anything unknown gives `require_human`. The gateway never changes a draft. The posting runs as `system` and must reproduce the simulated plan. Confirmation stays.

**Tainted drafts, by the author's decision.** A draft with values an LLM read from outside content may be auto-posted only when the company and the document type both enable it (default off, a loosening that another person approves), the drafting agent type is in the new agent mode `active` on evidence, the checker passes, and every value the checker relies on carries a verification result. The author delegated the rewording of spec 03 rule 1 on 2026-11-19; it was applied on 2026-11-21 as the single permitted edit to spec 03 (review note, 2026-11-21).

**Evidence before enabling, and fast demotion.** A document type runs in shadow first. It goes live only on evidence meeting `auto_post.max_error_rate` and through a change proposal that another person approves. One confirmed wrong auto-post suspends the document type at once.

**First instance: the purchase invoice.** The bank cascade and the production import become instances of the same gateway and keep their behavior.

### Rules

**The gateway**

1. Ownership and the hook (D1):
   - **`policy`** owns the gateway: the pure function `policy.contract.evaluate_auto_post`, the generic rules of rule 5, the decision record (rule 6) and the internal command `RecordAutoPostDecision` (rule 21).
   - **Hook.** `policy` declares the hook `auto_post_checker`. A module registers, per document type it owns, one checker implementation; `app` (layer 6) wires it. `policy` imports no module above it (ADR-0022 rule 2; ADR-0043 rule 1).
   - **Inputs that `policy` cannot read itself** are passed in by the dispatcher (`registry`), which already reads them for the actor context: the generic settings of rule 8 with their values and sources (`registry.contract.get_setting`), the draft version's effective taint, the agent run that wrote it, that run's agent type, behavior hash and effective mode (ADR-0050 rule 14), and the simulation result.
   - **The runner** is the system job `RunAutoPostGateway` of module `automation` (layer 5), which already imports `registry` for dispatch and the contracts of layers 3 and 4 (ADR-0058 rule 1). It is not an automation rule: it runs no company-composed action, and its only posting path is a gateway decision (rule 13).
2. Checker declaration (registry vocabulary, DS-04): each checker declares, with a version:
   - `document_type` and `actor_kind` (`system`, or `integration` for an import);
   - `runner`: `gateway_job` (rule 3) or `own` (the module's existing trigger, rule 20);
   - `rules`: the ordered list of its rule codes, each with the decision it gives on failure (`require_human` or `reject`) and the values it reports;
   - `facts`: the input schema of its decision point `auto_post.<document_type>` (ADR-0058 rule 18), every fact a registered gate field (ADR-0059 rule 20), with the code default `require_human` for `decision_no_match`;
   - `accepts_tainted` (true or false), and the plan fields whose amounts and quantities need a verification result (rule 10);
   - `allowed_check_codes`: check results that do not stop an auto-post (empty for every Phase 1 checker);
   - its evidence function (rule 14) and the settings keys it reads.

   The registry refuses two checkers for one document type. The placeholder `<document_type>` of rule 8's keys lists the document types whose checker declares `runner: gateway_job`; in Phase 1 that is `purchase_invoice` only.
3. Position in the flow (D2), for checkers with `runner: gateway_job`:
   - **Candidates.** `RunAutoPostGateway` runs every 5 minutes (a declared technical timer; the business date is fixed per run, ADR-0007 rule 17) per company and document type whose `auto_post.<document_type>.mode` is `shadow` or `live`. A candidate is a draft of that type whose latest version was written by a non-human (an agent run that has ended, a consumer, an integration or a system job), with no gateway decision for that version yet. A version a person wrote is never a candidate: a person posts it.
   - **Simulate.** For each candidate, in its own transaction, the job simulates `Post<Type>` as `system` on behalf of the owner of the enabled policy rule that allows the posting (spec 03 rule 3), or of the company's owner when none is enabled. The simulation returns the plan, `plan_hash`, the check results, `as_of_date` (ADR-0007 rule 15 note) and the gateway's decision, computed at the policy point after the handler has built the plan, as for commands registered `is_policy_in_handler` (DS-04 check order, step 9).
   - **Execute.** When the decision is `auto_post` and the mode is `live`, the job executes `Post<Type>` in a new transaction with `expected_plan_hash` set to the simulated hash and `as_of_date` set to the simulated date. The gateway is evaluated again inside that execution on the same inputs; the `policy_decision` row commits with the posting.
   - **Otherwise** (`require_human`, `reject`, shadow mode, a refused execution, an error) the job writes the decision with `RecordAutoPostDecision` in a transaction of its own and raises `auto_post_review` unless the mode is `shadow`.
   - **A new chain.** The job starts its own causation chain with no origin agent run. The passed checker decision is the trust boundary, as a person's command resets the origin (ADR-0013 rule 2). So ADR-0029 rule 12 and INV-85 stand as written: no consumer on an agent's chain posts. The decision's evidence names the run that wrote the draft.
4. The three decisions:
   - **`auto_post`:** the posting runs as `system` (rule 3). The decision's outcome is `allowed` with `is_confirmation_required`, so it joins `auto_post_unconfirmed` (ADR-0043 rule 14).
   - **`require_human`:** the stored outcome is `human_only`. `auto_post_review` names the first failed rule in the checker's order and the values involved, for example "`price_outside_auto_post_tolerance`: unit price 5.0% above the order price, tolerance 1.0%". A person may post the draft under their own policy decision.
   - **`reject`:** the stored outcome is `denied` for `system`. `auto_post_review` names the reason; the draft is wrong as it stands (a simulation error such as `duplicate_external_document`, or a checker rule declared `reject`), and a person corrects or cancels it. The gateway never cancels or changes it.
   - **Once per version.** The gateway decides a version once. A new version of the draft is a new candidate when its writer is a non-human.
5. Evaluation (D2, D4). `evaluate_auto_post` evaluates every rule below and records each outcome; the decision is the strictest outcome (`reject` above `require_human` above `auto_post`), so it never depends on rule order. The reason code is the first failure in this order:
   1. `auto_post_rule_not_allowed`: the policy table's decision for this `system` posting (ADR-0043 rules 7–9, floors included except as rule 12 states) is not `allowed` with confirmation, for example no enabled rule, an amount above the rule's `amount_company_max`, or an approval that the seeded `is_match_exceeded` rule requires. In mode `shadow` the missing enabled rule for `system` is not a failure, because rule 15 enables that rule only after the shadow evidence exists: the floors and every other policy rule are evaluated as if a rule allowing `system` to post the document type with confirmation were enabled, and the amount is bounded by item 4 (review note, 2026-11-21);
   2. `auto_post_simulation_error` (`reject`): the simulation returned an error;
   3. `auto_post_check_result`: the plan carries a check result not in the checker's `allowed_check_codes`;
   4. `auto_post_amount_above_maximum`: the posting's amount in company currency is above `auto_post.<document_type>.max_amount_company`;
   5. `auto_post_currency_not_allowed`: the document currency is neither the company currency nor in `auto_post.<document_type>.allowed_currencies`;
   6. the tainted-draft rules of rule 10 (`auto_post_tainted_not_enabled`, `auto_post_agent_not_active`, `auto_post_value_unverified`);
   7. `auto_post_evidence_mismatch`: in `live` mode, the checker version or the decision table version in force differs from what the enabled rule's stored evidence names, or that evidence is outdated (rule 14);
   8. the checker's own rules, in its declared order, and its decision table (rule 9);
   9. `auto_post_input_missing`, `auto_post_checker_error`, `auto_post_decision_no_match`: fail-closed outcomes (rule 7).
6. The decision record (D2). Every gateway decision is one `policy_decision` row with action `post` (or `issue`), the actor evaluated (`system` or `integration`), the stored outcome of rule 4, and:
   - `auto_post_decision`, `auto_post_mode` (`shadow` or `live`), `auto_post_reason_code` (null for `auto_post`);
   - `auto_post_checker_code` and `auto_post_checker_version`;
   - `auto_post_plan_hash` and `auto_post_as_of_date`, from the simulation;
   - `auto_post_evidence` (JSON): the settings read, each with key, value and source (ADR-0063 rule 1); the decision table and parameter set versions with their content hashes; every rule's code, outcome and values; the verification basis of every amount and quantity the plan uses (rule 10); the draft's taint, the run that wrote it, its agent type, behavior hash and effective mode; the enabled policy rule version and its evidence reference.

   The audit record of the posting names the decision (ADR-0029 rule 15). A shadow decision is stored with outcome `human_only`, because in shadow `system` may not post. The DDL is DS-05's (rule 22).

**Hard rules**

7. The gateway's hard rules (D4), cross-cutting hard locks in the sense of ADR-0063 rule 6:
   - **No LLM in the checker.** Neither the gateway nor a checker calls the LLM gateway, starts an agent run or reads model output other than the draft's own values. Checker code lives in the core or a package, reviewed like other code (ADR-0059 rule 24).
   - **Fail closed.** An unknown case, missing reference data, an unmatched decision table row, a setting without a value in force, a stale input or any exception gives `require_human`, never `auto_post`.
   - **Read-only.** The gateway and checkers never write. They never change a draft's value to make it pass; only the posting command writes, and only the simulated plan.
   - **System execution.** The posting runs as `system` on behalf of the enabled rule's owner, never as the person who started the agent, and its audit record names the decision.
   - **Plan check.** The execution must reproduce `expected_plan_hash` with the pinned `as_of_date`. A different plan returns `plan_hash_mismatch` (ADR-0008 rule 13); nothing posts, and the job records `require_human` with reason `auto_post_plan_changed`.
   - **Confirmation.** Every gateway posting is an auto-post under ADR-0043 rule 14 and ADR-0029 rule 13: the rule's owner confirms it with `ConfirmAutoPost`, unconfirmed auto-posts block the period lock, and INV-87 holds. The window of one `auto_post_unconfirmed` item follows `auto_post.confirmation_cadence` (rule 8).

**Configuration**

8. Settings (D3, D10), registered in [settings.csv](../catalogs/settings.csv) with `source` naming this ADR, leaf `policy`, change effect `immediate`:

   | Key | Default | Bounds | Direction | Outdates |
   | --- | --- | --- | --- | --- |
   | `auto_post.<document_type>.mode` | `off` | `off`, `shadow`, `live` | `order:live<shadow<off` | none |
   | `auto_post.<document_type>.max_amount_company` | 0 | 0 and above | lower tighter | `auto_post` |
   | `auto_post.<document_type>.allowed_currencies` | empty (company currency only) | currency codes | subset tighter | `auto_post` |
   | `auto_post.<document_type>.allow_tainted` | false | true, false | false tighter | `auto_post` |
   | `auto_post.<document_type>.require_verified_values` | true | true, false | true tighter | `auto_post` |
   | `auto_post.allow_tainted_drafts` | false | true, false | false tighter | `auto_post` |
   | `auto_post.confirmation_cadence` | `period` | `period`, `week`, `day` | `order:period<week<day` | none |
   | `auto_post.purchase_invoice.min_supplier_invoices` | 10 | 3 to 1,000 | higher tighter | `auto_post` |
   | `auto_post.purchase_invoice.price_tolerance_percent` | 0 | 0 to 10 | lower tighter | `auto_post` |
   | `auto_post.purchase_invoice.quantity_tolerance_percent` | 0 | 0 to 10 | lower tighter | `auto_post` |
   | `auto_post.purchase_invoice.require_full_receipt` | true | true, false | true tighter | `auto_post` |

   - **Change path** (ADR-0063 rule 3): tightening is immediate by one person holding `edit` on `policy`; loosening is a change proposal approved by another person holding `policy` at `full`. So turning a document type to `shadow` or `live`, raising its maximum, adding a currency, enabling tainted drafts and switching verification off each need a second person, and a one-person company cannot do any of them. The setup path of ADR-0067 rule 9 never applies to an `auto_post.*` key, `cash.auto_post.*` included (review note, 2026-11-21).
   - **Amounts** are in company currency; the core gives no other value than 0, because an amount depends on the currency (as `cash.bank_charge.auto_post_ceiling`).
   - **The author's numbers** (more than 5 earlier invoices, below 50,000,000, 1%) are examples only. The core defaults above are safe because the mode starts `off` and the maximum at 0.
   - **Evidence.** A loosening of a key with `outdates: auto_post` marks the stored evidence of every enabled rule version that lists the key outdated (ADR-0063 rule 3 note), so a looser checker re-arms only on new evidence.
   - **Confirmation cadence.** `period` keeps today's behavior: one `auto_post_unconfirmed` item per rule and posting period. `week` and `day` make the window the ISO week or the business date; the item is due at the window's end. The close task blocks the period lock as before.
9. Decision tables at the decision point (D3; ADR-0058 rules 18–20):
   - **Where.** Each checker declares the decision point `auto_post.<document_type>`, whose inputs are its facts and whose output is a `code` from `auto_post`, `require_human`, `reject`, with the declared order `auto_post < require_human < reject`. Hit policy `unique`, or `monotone` with aggregator `max` over that order, so the strictest row wins.
   - **In force.** The gateway uses the table's current version only when its state is `active` (ADR-0059 rule 12: `assisted` is never in force where the system acts). With no table, or none `active`, the checker's rules alone decide. In shadow mode the table's shadow version, when there is one, is evaluated as well and recorded.
   - **Outcomes.** `decision_no_match` and `decision_input_out_of_domain` give `require_human` (`auto_post_decision_no_match`); a table output `auto_post` never lifts a failed checker rule, because the decision is the strictest outcome (rule 5).
   - **Evidence.** A change of the table version in force marks the gateway evidence that names the earlier version outdated, through the hook `artifact_in_force_changed` (ADR-0059 rule 6), in the same transaction.

**Tainted drafts**

10. Tainted drafts (D5, the author's decision of 2026-11-16). A draft is tainted for the gateway when its version is effectively tainted (ADR-0029 rules 8–9) or was written by an agent run, or the document carries an origin agent run (ADR-0043 rule 9, floors 3 and 5). It is auto-posted only when all of these hold; otherwise the decision is `require_human`:
    1. `auto_post.allow_tainted_drafts` is true for the company (`auto_post_tainted_not_enabled`);
    2. `auto_post.<document_type>.allow_tainted` is true and the checker declares `accepts_tainted` (`auto_post_tainted_not_enabled`);
    3. the agent type of the run that wrote the version is in effective mode `active` for this document type (rule 11; `auto_post_agent_not_active`);
    4. the checker passes (rules 5, 19);
    5. every value the checker relies on has a declared verification basis: `trusted` (ADR-0057 rule 17's value trust, or a structured field that ADR-0051 rule 20 does not mark untrusted), `cross_checked` (a deterministic comparison confirmed it, such as the three-way match of rule 19 within tolerance), or `llm_read_only` (an LLM step's output or an untrusted field with no such confirmation). The checker records the basis of each value in the evidence.

    While `auto_post.<document_type>.require_verified_values` is true, every amount and quantity the posting uses must be `trusted` or `cross_checked` (`auto_post_value_unverified`). A company may set it false only through a change proposal; the bases are still recorded. Trust means a value carries no instruction, not that it is true (ADR-0057 rule 17), which is why the checker's cross-checks run on trusted values too.

    Note ([ADR-0067](0067-quickflows-operating-presets.md), 2026-11-17 (proposed)): a version cleared only by the human its tainting run acted for, which the small-company mode allows ([ADR-0029](0029-proposals-and-agent-safety.md) rule 8 note), still counts as tainted here, and such versions never count as evidence for mode `active` ([ADR-0067](0067-quickflows-operating-presets.md) rule 17).
11. Agent mode `active` (ADR-0050 rule 14; the ADR-0059 lifecycle's last state for agent types):
    - **Meaning.** `active` is `assisted` plus one thing: the type's drafts of the document types named at promotion may pass the gateway as tainted drafts. The agent still only drafts; floor 4 of ADR-0043 rule 9 and the tool list rules are unchanged.
    - **Declared.** An agent type version names the document types it may draft for the gateway (`auto_post_document_types`). Setting `active` for a version that names none returns `agent_mode_not_declared`. The next version of the `purchase_invoice` agent type names `purchase_invoice`.
    - **Promotion.** `UpdateAgentTypeSetting` to `active` runs only from an approved change proposal that another person approves (`approver_is_submitter`, also in the small-company mode), from a type already promoted to `assisted` with the same behavior hash and seat models. It names one `agent_promotion_evidence` row per document type, with target mode `active`, computed by `CreateAgentPromotionEvidence` from `GetAgentDraftAcceptance`: the type's drafts of that document type under the promoted behavior hash and seat models over at least two calendar months, at least N = ceil(3 / `auto_post.max_error_rate`) of them, at least (1 − rate) posted unchanged by people (the version the run wrote was posted with no later version), and none posted to another partner. Otherwise `shadow_evidence_insufficient`. The executing transaction records the document types in `agent_type_setting.active_document_types`.
    - **Effective mode.** Computed as today (ADR-0050 rule 14): a version or seat model change makes it `shadow`. Also, while an `agent_quality_below_threshold` item is open for the type, an `active` type counts as `assisted` for the gateway, whatever `agents.<agent_type>.drift_action` says, because drift that touches an acting path always suspends it (ADR-0063 rule 12).
    - **Lowering** `active` to `assisted` or below is direct, by one person, at once.
12. Floors and the hard-floor text:
    - **Floors 3 and 5** of ADR-0043 rule 9 give `human_post` for a non-human posting of a tainted or agent-written version. For a `system` posting whose gateway decision is `auto_post` with every condition of rule 10 met, they are satisfied by the gateway instead: the decision is `allowed` with confirmation. In every other case they apply unchanged. Floors 4 and 6, permissions, segregation of duties and `human_only` commands are untouched.
    - **INV-84** is restated: no policy decision with outcome `allowed` for a non-human actor concerns an effectively tainted version, except a live gateway decision `auto_post` under rule 10, which INV-761 checks.
    - **Spec 03.** Spec 03 says that no policy, threshold or customer setting relaxes rule 1. The author's decision of 2026-11-16 allows this path; the author delegated the rewording of rule 1 on 2026-11-19, and it was applied on 2026-11-21 as the single permitted edit to spec 03: rule 1 now names the deterministic auto-post gateway of this ADR as part of the rule, and the lead-in says the gateway is not a relaxation (review note, 2026-11-21).
    - **LLM-originated bank rules.** Under the same decision `cash.auto_post.accept_llm_originated_rules` is no longer bounded false: its bounds become true and false, default false. Rule 8 of ADR-0063 keeps its five conditions, and `llm_suggestion` drafts still never auto-post (ADR-0063 rule 6).
    - **Tainted read scope** (ADR-0029 rule 14) is unchanged: this decision lets a checked draft post; it widens no run's reads.
13. Automation rules still never approve or post (D6). ADR-0058 rule 3 stands unchanged: no automation rule submits, approves, posts or issues. The gateway is a policy decision on a draft at the policy point of `Post<Type>`, evaluated by core code with settings and a decision table at a module decision point, not an automation rule, so the rule needs no exception. A decision table used here only outputs a decision; it runs no action.

**Evidence, enabling and demotion**

14. Shadow mode and evidence (D7):
    - **Shadow.** In mode `shadow` the job evaluates every candidate and records the decision (rule 6) without posting or raising `auto_post_review`.
    - **The evidence function** of a checker is an evidence hook in the pattern of `GetAutoPostShadowEvaluation` (ADR-0043 rule 14). For the purchase invoice it is `GetPurchaseInvoiceAutoPostShadowEvaluation` (module `purchasing`): over a date range, the shadow decisions `auto_post` under one checker version and one decision table version, and of those drafts the share that people posted unchanged (the evaluated version posted with no later version, not canceled, not reversed by the evidence date). Drafts still open are not counted.
    - **Floor.** At least N = ceil(3 / `auto_post.max_error_rate`) such decisions over at least two calendar months, at least (1 − rate) posted unchanged, none posted to another supplier (ADR-0063 rule 10's rule of three; 300 at 99% with the default). Below it `EnablePolicyRule` returns `shadow_evidence_insufficient`.
    - **Bound.** `EnablePolicyRule` stores the evidence with the checker version, the decision table version and content hash, and the setting keys the evidence was judged under (`evidence_setting_keys`, ADR-0043 rule 14 note). A gateway decision in `live` whose checker version or table version differs gets `require_human` (`auto_post_evidence_mismatch`).
    - **No checker, no system posting.** `EnablePolicyRule` for a rule that allows `system` or `integration` to post or issue a document type with no registered checker returns `auto_post_checker_missing`.
15. Enabling a document type, in order:
    1. A person proposes the thresholds, mode `shadow` and, where wanted, the tainted settings, in one change proposal of `UpdateCompanySetting` items; another person approves it (rule 8).
    2. The gateway runs in shadow until the evidence floor is met.
    3. The rule's owner creates a policy rule that allows `post` of the document type for actor kind `system`, with `amount_company_max` and `is_confirmation_required` (ADR-0043 rule 3), and enables it with `EnablePolicyRule`, which stores the shadow evidence.
    4. A person proposes `auto_post.<document_type>.mode` `live`; a second person approves it.
16. Demotion (D7):
    - **One wrong auto-post suspends the type.** A reversal of a gateway posting, or a confirmation recording it wrong (ADR-0043 rule 14), marks in the same transaction the evidence of every enabled rule version that allows `system` or `integration` to post that document type outdated, and raises `auto_post_suspended` for each such rule's owner (ADR-0063 rule 10, extended from the rule to the document type). Later candidates get `require_human` (`auto_post_evidence_mismatch`) until a new rule version is enabled on new evidence.
    - **Stop at once.** Any person holding `edit` on `policy` sets the mode to `shadow` or `off` immediately; lowering an agent type from `active` is immediate too (rule 11).
    - **Drift.** An artifact demotion of the decision table, a new table version in force, a loosened setting and a new checker version all outdate or mismatch the evidence (rules 8, 9, 14).

**Agent-assisted rule building**

17. Deterministic tools (D8). The numbers of a proposal come from code, never from a model (ADR-0063 rule 6):
    - **`ListAutoPostCase`** (module `automation`, query, held-out filtered, ADR-0059 rule 16): the cases of a document type in a date range, one per posted, canceled or reversed draft, with the checker's facts as of its decision, the human outcome (posted unchanged, posted changed, canceled, reversed) and no free text.
    - **`EvaluateAutoPostBacktest`** (computed, held-out filtered): for candidate settings values and candidate decision table rows over an evaluation window that starts after the drafting window (ADR-0059 rule 15), the decisions the gateway would have taken on each case, the expected auto-post rate, the error rate (auto-posts whose drafts people changed, canceled or reversed), the changed decisions against the settings and table in force, and the result on held-out golden cases.
    - **`ListAutoPostThresholdCandidate`** (computed): candidate threshold sets computed by code from the case distribution (the observed variances and amounts at fixed quantiles), each with its backtest figures.
18. The `auto_post_advisor` agent type (D8), a drafting agent type on the runtime of ADR-0050:
    - **What it does.** A person starts it for a document type. It reads the tools of rule 17, chooses among the threshold candidates code gave it and writes the explanation. It drafts a decision table version for the decision point (`CreateDecisionTableVersion`) and a change proposal with `UpdateCompanySetting` items (`CreateChangeProposal`), both drafts, with the backtest attached as evidence.
    - **What it never does.** It never submits, approves, enables or changes a setting, a table state, a policy rule or an agent mode; those commands are on no agent tool list (ADR-0050 rule 30). Its tool list holds only held-out filtered queries (ADR-0059 rule 16).
    - **The lifecycle is ADR-0059's.** A person reviews the drafts; the table version moves draft, backtested (evidence from `EvaluateAutoPostBacktest`, stored by `CreateArtifactEvidence`), shadow, active through an approved change proposal; the settings change through another person's approval; the gateway then runs in shadow (rule 15), and a person enables. The table's monitoring and demotion follow ADR-0059 rule 21, and the gateway's demotion follows rule 16 of this ADR.
    - **Taint.** Posted invoices drafted by agents are tainted versions, so its runs become tainted; it only drafts, and its drafts are written tainted and submitted by a person (ADR-0059 rule 13). It is an agent type that may read outside content for the budget pool (ADR-0050 rule 22 note).
    - **Its declared values** (budgets, seats, evaluation suite) come with its first agent type version (DS-34), within the company's settings. Leaf `agent_auto_post_advisor` (ADR-0054 rule 24).

**Instances**

19. The purchase invoice (D9), the first checker, `purchasing.purchase_invoice_auto_post` version 1 (actor `system`, `runner: gateway_job`, `accepts_tainted: true`). Its rules, in order, each failing to `require_human` unless marked:
    Which party each rule reads: the order match (`supplier_differs_from_order`), the supplier history and the `partner_item` lookup use the ordered-from supplier (`partner_id`); the duplicate check uses the invoicing party (ADR-0074 rule 4) (review note, 2026-11-21).

    1. `supplier_differs_from_order` (`reject`): a referenced purchase order belongs to another supplier than the invoice;
    2. `line_kind_not_matchable`: a line is not a `goods` line with an order line, or a `service` line with a service receipt (expense and landed-cost lines have no deterministic cross-check);
    3. `line_item_not_mapped`: a line's item is not the item that the supplier's approved `partner_item` or `supplier_item` row gives for the source record line's seller code, a lookup the checker repeats; an item an LLM chose (ADR-0051 rule 21, step L1) is `llm_read_only`;
    4. `supplier_history_below_minimum`: the supplier has fewer posted, unreversed purchase invoices in the company than `auto_post.purchase_invoice.min_supplier_invoices`;
    5. `price_outside_auto_post_tolerance`: a line's net unit price per inventory unit differs from the GR/IR price of the positions it reaches (ADR-0047 rules 13–14 note) by more than `auto_post.purchase_invoice.price_tolerance_percent`;
    6. `quantity_outside_auto_post_tolerance`: the invoiced net exceeds the received net by more than `auto_post.purchase_invoice.quantity_tolerance_percent`, or is invoiced before receipt;
    7. `order_not_fully_received`: while `auto_post.purchase_invoice.require_full_receipt` is true, a referenced order line's received net is below its ordered quantity;
    8. `duplicate_suspected`: the near-duplicate check (ADR-0057 rule 15; ADR-0063 rule 27) suspects the invoice; an exact duplicate key already fails the simulation (`duplicate_external_document`, so `reject`).

    Open check results also stop it through rule 5 (`match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt`, `tax_amount_differs_from_computed`), and the seeded `is_match_exceeded` rule requires an approval, so rule 5's first rule fails too. Bases: quantities and prices of a record with a passed signature are `trusted`; within tolerance of the order and receipt they are also `cross_checked`; the item is `trusted` only through rule 3. On a failure the work item reads, for example, "price 5% above PO" with the line, the order line, both prices and the tolerance.
20. The bank cascade and the production import are instances of the same gateway, with `runner: own`, and keep their behavior:
    - **Bank cascade.** `cash` registers checkers for `bank_receipt`, `bank_payment`, `cash_receipt` and `cash_payment` (actor `system`, `accepts_tainted: false`) whose rules are today's `auto_post_eligibility` conditions (ADR-0043 rule 14 note; ADR-0059 rule 6) and the `bank_charge` gates (ADR-0063 rule 9), with `GetAutoPostShadowEvaluation` as their evidence function. Their trigger stays the cascade (ADR-0048 rule 9; ADR-0051 rule 18), their settings stay `cash.*` and `auto_post.max_error_rate`, and `llm_suggestion` drafts stay out (ADR-0063 rule 6).
    - **Production import.** `production` registers a checker for `operation_confirmation` (actor `integration`, `accepts_tainted: false`) whose rules are ADR-0064 rule 25's (no check result at all, `production.mes_import.auto_post` true), with `GetProductionImportShadowEvaluation` as its evidence function. Its trigger stays `ImportOperationConfirmation`.
    - **What changes for them:** their decisions are written in the gateway's columns (rule 6), and they share the hard rules of rule 7 and the document-type suspension of rule 16. The placeholder `<document_type>` of rule 8 does not list them, so the generic settings do not apply to them.

**Commands, catalogs and DDL**

21. Commands and queries:

    | Command or query | Module | Effect class | Notes |
    | --- | --- | --- | --- |
    | `RunAutoPostGateway` | `automation` | `other` | System job every 5 minutes per company and document type in `shadow` or `live`; `is_internal_only`; dispatches `Post<Type>` as `system` (rule 3) |
    | `RecordAutoPostDecision` | `policy` | `other` | `is_internal_only`; writes a `require_human`, `reject` or shadow decision and raises `auto_post_review` |
    | `GetPurchaseInvoiceAutoPostShadowEvaluation` | `purchasing` | query | Evidence function registered through the hook (rule 14); on no agent tool list |
    | `GetAgentDraftAcceptance` | `agents` | query | Figures for an `active` promotion (rule 11); on no agent tool list |
    | `EvaluateAutoPostGateway` | `policy` | query | Computed, for people: the decision a draft would get now, with every rule's outcome; on no agent tool list |
    | `ListAutoPostCase`, `EvaluateAutoPostBacktest`, `ListAutoPostThresholdCandidate` | `automation` | query | Held-out filtered (rule 17) |

    `UpdateAgentTypeSetting` gains the mode `active` (rule 11). `EnablePolicyRule` gains `auto_post_checker_missing` (rule 14). `ConfirmAutoPost` follows the cadence of rule 8.
22. Catalog rows:
    - **Settings:** 11 definitions (rule 8), added to [settings.csv](../catalogs/settings.csv); `cash.auto_post.accept_llm_originated_rules` gets bounds `true|false` (rule 12).
    - **Errors** (DS-04): `auto_post_checker_missing` (precondition), `agent_mode_not_declared` (validation).
    - **Gateway reason codes** (recorded in `policy_decision.auto_post_reason_code`, not errors): the codes of rules 5, 7 and 10, and the checker's codes of rule 19.
    - **Work item kind:** `auto_post_review` (module `policy`, subject `document`, `role:accountant`, `days:1`, resolved by the system when the version is posted, canceled or replaced). `auto_post_unconfirmed` is now due at the end of its confirmation window (`named_by_raiser`, rule 8).
    - **Registry vocabulary** (DS-04): the auto-post checker declaration (rule 2).
    - **Authorization area:** `agent_auto_post_advisor` under `agent` (ADR-0054 rule 24).
    - **DDL** ([DS-05-platform.sql](../design/DS-05-platform.sql)): `policy_decision` gains `auto_post_decision`, `auto_post_mode`, `auto_post_reason_code`, `auto_post_checker_code`, `auto_post_checker_version`, `auto_post_plan_hash`, `auto_post_as_of_date` and `auto_post_evidence`, with a check that ties them to the stored outcome; `agent_type_setting.mode` accepts `active`, with `active_document_types`; `agent_promotion_evidence` gains `target_mode` and `document_type`. Checkers are registry declarations in code, not a table.
    - **Invariants** INV-760 to INV-764 of the block INV-760 to INV-789, INV-84 restated, and **edge cases** EC-220 to EC-228 of the block EC-220 to EC-239 (section Edge cases and invariants).

## Context

The author's draft of 2026-11-16 describes a maker-checker gateway: an agent makes a draft, deterministic code checks it, and a clean draft posts without a person. NativeFlows already has most of the pieces, but only for one path:

- **The auto-post path** of ADR-0043 rule 14 evaluates unattended postings as `system`, under an enabled rule with an owner, a maximum, confirmation and shadow evidence, with evidence hooks registered by `cash` and `production`. ADR-0043 rule 5 says the bank cascade is the only unattended workflow posting.
- **The evidence floor** `auto_post.max_error_rate` and the rule of three (ADR-0063 rule 10), the asymmetric change path and the hard locks (ADR-0063 rules 3, 6).
- **Decision tables** at module decision points (ADR-0058 rules 18–20) and the artifact lifecycle with held-out cases, evidence and drift (ADR-0059).
- **Value trust** (ADR-0057 rule 17) and the three-way match facts (ADR-0047 rules 13–14; ADR-0020).
- **The pinned business date** `as_of_date` and execution with `expected_plan_hash` (design hardening of 2026-11-16).

What was missing is a generic checker per document type and an answer for tainted drafts. Spec 03 rule 1 forbids auto-posting what an LLM contributed to, and spec 03 says no setting relaxes it. The purchase invoice agent's drafts are always tainted, because the run reads a supplier's e-invoice record (ADR-0051 rule 20). So a gateway without the author's decision could never post a single agent-drafted invoice. The author decided to allow it under customer configuration.

SAP's logistics invoice verification posts incoming electronic invoices in the background when they match the order and receipt within the company code's tolerance keys, and otherwise parks them or posts them blocked for payment. NativeFlows keeps the SAP idea (tolerances against order and receipt decide) and adds what an AI-native system needs: the shadow evidence before enabling, value bases for model-read values, and fast demotion.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Generic gateway in `policy`, checkers registered through a hook (chosen) | One path for every unattended posting; reuses rule 14's owner, maximum, confirmation and evidence; no new module | The gateway needs inputs `policy` cannot read, passed in by the dispatcher |
| A new `auto_post` module | A clear home | Duplicates `policy`'s rules and evidence; D1 forbids it |
| One checker module per document type, each with its own path | Local | Several unattended paths with different safeguards |
| Gateway as an automation rule action | Configurable | ADR-0058 rule 3 forbids rules that post; the gateway would need an exception |
| Runner in the owning module, as a consumer of the draft event | No polling | The consumer carries the origin agent run, and ADR-0029 rule 12 forbids it to post |
| Runner `RunAutoPostGateway` in `automation`, a new chain (chosen) | One runner; no origin run; `automation` already dispatches | Polling every 5 minutes |
| Tainted drafts never auto-posted (spec 03 as written) | Strictest | Agent-drafted invoices could never post; the author decided otherwise |
| Tainted drafts per document type, with value bases and an `active` agent mode (chosen) | The author's decision; each loosening by a second person; values an LLM read must be confirmed by code | A new agent mode and more evidence |
| "Active" read as gateway evidence bound to the agent's behavior hash, with no new mode | No mode change | D5 names the agent type's state; the evidence would mix the checker's and the agent's quality |
| Thresholds as a parameter set (ADR-0059 L1) | Lifecycle for free | D3 makes them settings; settings already have bounds, directions and the change path |
| Checkers as a table | Visible as data | Checkers are code; the registry's declarations already serve as reference data |

## Consequences

- **For companies:** auto-post becomes available per document type, off by default; each step towards it (shadow, live, tainted drafts) is a proposal another person approves, and any person with the leaf can stop it at once.
- **For agents:** nothing they can do changes. Agents still only draft; the `active` mode only marks their drafts as eligible.
- **For auditors:** each auto-post has one `policy_decision` row with the settings, table versions, rule outcomes and value bases; confirmation by the rule's owner stays.
- **For the build:** the gateway, the decision columns and `RecordAutoPostDecision` land with `policy` at step 5; the runner, the purchase invoice checker and the advisor with the purchase invoice agent and auto-post at step 6 (DS-34). The cascade and import checkers are refactors of designed hooks.
- **Behavior changes:** none by default. Every new setting's default reproduces today's behavior (auto-post off, tainted drafts off, confirmation per period). The only change to an existing row is the lifted bound of `cash.auto_post.accept_llm_originated_rules`, whose default stays false.
- **For the author:** nothing open on spec 03 rule 1: the rewording was delegated on 2026-11-19 and applied on 2026-11-21 (review note, 2026-11-21).
- **Revisit when:** a second document type asks for the gateway; evidence shows the purchase invoice rules too strict or too loose; the delegated wording of spec 03 rule 1 proves wrong in use.

## Documents updated

- **ADRs** (notes tagged "ADR-0065, 2026-11-16 (proposed)"): [ADR-0029](0029-proposals-and-agent-safety.md) rules 13, 14, 16; [ADR-0043](0043-policy-and-approval.md) rules 1, 5, 9, 14; [ADR-0047](0047-commercial-documents-and-pricing.md) rule 14; [ADR-0048](0048-cash-bank-receivables-payables.md) rule 9; [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 14; [ADR-0051](0051-agent-workflows.md) rules 18, 22; [ADR-0057](0057-document-intake-and-extraction.md) rule 17; [ADR-0058](0058-configurable-workflows.md) rule 3; [ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md) rules 6, 16; [ADR-0063](0063-configurable-policy-settings.md) rules 6, 8, 29; [ADR-0064](0064-production-agent.md) rule 25.
- **Catalogs:** [settings.csv](../catalogs/settings.csv), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [authorization-areas.csv](../catalogs/authorization-areas.csv), [role-template-levels.csv](../catalogs/role-template-levels.csv), the [catalogs README](../catalogs/README.md).
- **Design files:** [DS-04-command-envelope.md](../design/DS-04-command-envelope.md) (errors, check order, registry vocabulary), [DS-05-platform.sql](../design/DS-05-platform.sql), [DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [architecture-overview.md](../design/architecture-overview.md), [architecture-core.md](../design/architecture-core.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md): the author's decision on tainted auto-post recorded as answered; the spec 03 rule 1 wording answered by the author's delegation (2026-11-19) and applied (2026-11-21).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md).
- **Changed in review:** `docs/spec/03-agent-safety.md`, lead-in and rule 1 only, as delegated by the author on 2026-11-19 and applied on 2026-11-21 (review note, 2026-11-21).
- **Not changed:** the rest of `docs/spec/`, including the glossary; the glossary rows for the gateway's terms come with acceptance.

## Edge cases and invariants

**Invariants** (DS-16; block INV-760 to INV-789, INV-760 to INV-764 taken; area `safety`; first step 6):

- **INV-760** `auto_post_gateway_decided`: every posting by `system` or `integration` of a document type with a registered checker has a `policy_decision` with `auto_post_decision` `auto_post` and mode `live`, a checker code and version, evidence in which every rule passed, and an `auto_post_plan_hash` equal to the posted plan's hash; its policy rule version was enabled with evidence that names that checker version and decision table version and was not outdated on the posting date.
- **INV-761** `auto_post_tainted_gated`: every gateway posting of a tainted draft (rule 10) happened while `auto_post.allow_tainted_drafts` and `auto_post.<document_type>.allow_tainted` were true on its date, with the drafting agent type's effective mode `active` for that document type at the behavior hash its evidence covered, and, while `require_verified_values` was true, no amount or quantity of the plan with basis `llm_read_only`.
- **INV-762** `auto_post_gateway_without_model`: no LLM call or agent run has a causation chain that `RunAutoPostGateway` started, and no gateway decision's evidence names a model output other than the draft's own values.
- **INV-763** `wrong_auto_post_suspends_document_type`: every reversal of a gateway posting, and every confirmation recording one wrong, marked in the same transaction the evidence of every enabled rule version allowing `system` or `integration` to post that document type outdated.
- **INV-764** `agent_active_evidenced`: every `agent_type_setting` in mode `active` names document types its promoted agent type version declares, each covered by sufficient `agent_promotion_evidence` with target mode `active` at the promoted behavior hash, from a proposal approved by a person other than its submitter.
- **INV-84** restated (rule 12): no policy decision with outcome `allowed` for a non-human actor concerns a document version that was effectively tainted at the time of the decision, except a live gateway decision `auto_post` under rule 10.

**Edge cases** (DS-17; block EC-220 to EC-239, EC-220 to EC-228 taken; first step 6):

- **EC-220** `purchase_invoice_auto_post`: an agent-drafted invoice of a supplier with enough history matches its fully received order exactly; with the type `live`, tainted drafts enabled and the agent `active`, the gateway posts it as `system` and an `auto_post_unconfirmed` item asks the rule's owner to confirm.
- **EC-221** `purchase_invoice_price_variance`: a line 5% above the order price, tolerance 1%; the decision is `require_human`, and `auto_post_review` names `price_outside_auto_post_tolerance` with both prices.
- **EC-222** `tainted_auto_post_disabled`: the same clean invoice with `auto_post.allow_tainted_drafts` false gets `require_human` (`auto_post_tainted_not_enabled`); a direct change to true returns `proposal_required`.
- **EC-223** `llm_chosen_item_not_verified`: a line whose item the LLM chose among candidates gets `require_human` (`line_item_not_mapped`); after the mapping proposal is approved, the next invoice of that supplier posts.
- **EC-224** `plan_changed_before_execution`: the goods receipt is reversed between simulation and execution; the execution returns `plan_hash_mismatch`, nothing posts, and the decision is `require_human` (`auto_post_plan_changed`).
- **EC-225** `wrong_auto_post_suspends_document_type`: the owner confirms one auto-posted invoice as wrong; every enabled purchase invoice auto-post rule's evidence is outdated, `auto_post_suspended` is raised, and the next clean invoice gets `require_human`.
- **EC-226** `gateway_fail_closed`: a decision table in force has no row for the case, and another case lacks the supplier's history because the setting has no value in force; both get `require_human`.
- **EC-227** `advisor_drafts_only`: the advisor proposes thresholds and a table from six months of invoices; it drafts a table version and a change proposal and cannot submit, approve or enable them; its tool list excludes held-out cases.
- **EC-228** `duplicate_invoice_rejected`: an agent drafts an invoice whose supplier invoice key is already posted; the simulation returns `duplicate_external_document`, the decision is `reject`, and the draft stays for a person.
