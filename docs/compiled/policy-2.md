Module: policy    Chunk: 2 of 4    Source ADRs: ADR-0043, ADR-0051, ADR-0055
Build step(s): 2, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `policy` compiled spec, chunk 2: rule-set check, change proposals, approvals, auto-post confirmation, seeds, commands, approval pools

## Purpose

This chunk states the part of `policy` law on: documents that may not wait, the monotonicity check of a company's rule set, change proposals, approvals, auto-posts with their confirmation and shadow evidence, the seeded templates, the period unlock and the other policy points, the commands and queries on rules and procedures, the bank cascade's follow-up and auto-post evidence, and the tables, owners and seed of approval pools. `policy` is a layer 2 module; it imports no layer-4 module and reads evidence only through hooks that `app` wires (R231, R237). The policy table, its evaluation and the floors are in chunk 1; stages, plans and rounds in chunk 3; the auto-post gateway and the settings in chunk 4.

## Entities and tables

DDL: `docs/design/DS-15-access.sql` (the pool tables), `docs/design/DS-05-platform.sql` (the other `policy` tables).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `approval_pool` | A company's group of document types that share approval stages (R238) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company` | `policy` |

Named by rules of this chunk, with their rows in other chunks: `approval_pool_document_type`, `approval_stage`, `approval_stage_member`, `approval_procedure`, `policy_rule`, `policy_rule_version`, `policy_decision`, `auto_post_confirmation`.

Reads: `approval`, `document`, `document_version`, `change_proposal` (`documents`); `role`, `user_account` (`permissions`); `work_item` (`work`); `period_unlock_request` (`periods`); `setting_value`.

## Commands and queries

Authorization: the function area `policy` under `administration` (catalog `authorization-areas.csv`) covers policy rules, approval procedures and approval pools, policy decisions and `ConfirmAutoPost` at `post` (the rule's owner only). The level of a verb is the catalog's (`Create`, `Update`: `edit`; `Enable`, `Disable`: `full`; `List`, `Get`: `read`; `Confirm`: `post`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreatePolicyRule` | `human_only`; area `policy` | not stated | Creates a rule; the rule set is checked (R202, R227) | not stated | `policy_rule_invalid` |
| `UpdatePolicyRule` | `human_only`; area `policy` | not stated | Writes a new version of a rule; the rule set is checked (R202, R227) | not stated | `policy_rule_invalid` |
| `EnablePolicyRule` | `human_only`; area `policy` | not stated | Enables a rule; for a rule that lets `system` or `integration` post it records the shadow evidence on the rule version (R212-R217) | not stated | `policy_rule_invalid`, `shadow_evidence_insufficient`, `auto_post_evidence_outdated`, `auto_post_checker_missing` |
| `DisablePolicyRule` | `human_only`; area `policy` | not stated | Disables a rule; the rule set is checked (R202) | not stated | `policy_rule_invalid` |
| `CreateApprovalProcedure` | `human_only`; area `policy` | not stated | Creates a named rank and re-runs the pool checks (R227) | not stated | not stated |
| `UpdateApprovalProcedure` | `human_only`; area `policy` | not stated | Changes a named rank and re-runs the pool checks (R227) | not stated | not stated |
| `ListPolicyRule` | query; area `policy` | not stated | Lists policy rules (R228) | none | not stated |
| `ListApprovalProcedure` | query; area `policy` | not stated | Lists approval procedures (R228) | none | not stated |
| `ListPolicyDecision` | query; area `policy` | not stated | Lists policy decisions (R228) | none | not stated |
| `GetPolicyEvaluation` | computed query, people only; area `policy` | action, type, actor kind, input | Returns the evaluation for the given input (R228) | none | not stated |

Rows in other chunks: `ConfirmAutoPost` (R211; ADR-0029.R13) in chunk 1; `CreateApprovalPool`, `UpdateApprovalPool` and `RunApprovalEscalation` (ADR-0055.R17) in chunk 3. Commands of other modules named here: `Approve<Type>`, `Reject<Type>` and `Submit` (`documents`), `UnlockPostingPeriod` (`periods`), `UpdateCompanySetting`.

Hooks and contract functions, not registry commands: the evidence hook that `policy` declares, on which `cash` registers `GetAutoPostShadowEvaluation` and `production` registers `GetProductionImportShadowEvaluation` (R212); the hook `auto_post_checker` (R217); `policy.contract.mark_auto_post_evidence_outdated`, called through the hook `artifact_in_force_changed` (R214); the selector, the plan and the stage reader that `policy` registers with the dispatcher (R237).

Error codes bound to no command of this table: `proposal_required` (the dispatcher, R205), `approval_stage_unsatisfiable` (pools, procedures and `Submit`, R208), `approver_is_submitter` (R210), `approval_pool_invalid` (R239).

## Rules

### Documents that may not wait

R201. For a document that may not wait (`is_approval_hold_allowed: false`) a rank becomes `human_post` and the stored outcome is `human_only` (ADR-0009.R12, interim). For a type with `is_approval_hold_allowed: regime` this applies while `documents.issuance_without_delay` is true for the document's date; while it is false the type follows the ordinary approval path (ADR-0053.R8).
Source: ADR-0043.R10

### Monotonic rule set

R202. Saving, enabling or disabling a rule checks the company's whole rule set for each future effective date in it. The set must be monotonic for every action, document type and actor kind:
- Riskier inputs are a larger amount, a larger discount, a smaller margin, and true booleans.
- Stricter decisions are compared per dimension, with denied above everything, rank by procedure rank, and the posting control level `free` < `confirm` < `human` (human post, else confirmation, else free). Confirmation and human post form one level, because moving from "allowed with confirmation" to "a person posts" is stricter although confirmation drops.
- The test: a riskier input must never give a less strict decision in any dimension.
- It is evaluated at every combination of breakpoints of the numeric conditions (each bound, and one smallest step below it: a minor unit for amounts, 0.000001 for percents, within each condition's domain, so margins below zero are included) and both values of each boolean.
- A set that fails is rejected with `policy_rule_invalid`, naming the inputs.
Source: ADR-0043.R11

R203. A deactivated owner suspends only the rules that allow a non-human actor (ADR-0017.R12; ADR-0042). Restrictive rules stay in force, and an `owner_suspended` work item asks the company's owner to reassign them.
Source: ADR-0043.R11

### Change proposals

R204. The `Submit` of a change proposal (ADR-0029.R1 to ADR-0029.R5) always requires at least the lowest-rank procedure. The approver must be eligible for the current stage of the proposal's approval plan (ADR-0055.R7) and hold the target commands' permissions and every field class the proposal changes (ADR-0029.R3), and segregation of duties applies.
Source: ADR-0043.R12

R205. A rule with `action` `direct_master_data_change`, a `command_type`, and `effect` `deny` for `human` is checked by the dispatcher before the command runs. Only `deny` is allowed for this action. It writes no decision row, only the error. The bank-account rule is such a rule: it is seeded (R220) and cannot be disabled, and the command that changes a partner's bank account returns `proposal_required` (ADR-0029.R4; the floor of ADR-0043.R9.N3).
Source: ADR-0043.R12

R206. A loosening of a registered setting is a change proposal with the item `UpdateCompanySetting`, approved by a person holding the setting's leaf at `full` who is neither the submitter nor a writer. Tightening never needs one (ADR-0063.R3). Before go-live the setup path of ADR-0063.R3.N2 accepts, without a proposal, a loosening of a key whose `outdates` is `none` (ADR-0067.R9); that path never applies to an `auto_post.*` key (ADR-0065.R8).
Source: ADR-0043.R12.N1

### Approvals

R207. `Approve<Type>` and `Reject<Type>` are human actions (ADR-0017.R15). Each writes an immutable `approval` row (version, decision, reason, actor, on whose behalf, `decided_at`, `policy_decision_id`). A pending approval is the work item `approval_pending` (ADR-0042.R17).
Source: ADR-0043.R13

R208. Who may approve is stage eligibility (ADR-0055.R7 to ADR-0055.R9). Writers of any version are excluded by default (flagged; small companies: ADR-0054.R20). Segregation of duties, which covers documents an agent wrote on the approver's behalf, applies to every company; the small-company mode records its exceptions: the human-writer lift of ADR-0055.R7, the segregation-pair exceptions of ADR-0054.R20, and the agent-draft lift of ADR-0067.R16 (R209). `approval_stage_unsatisfiable`, on pools, procedures and at `Submit`, is the one satisfiability check (ADR-0055.R4). `CreatePolicyRule` and `UpdatePolicyRule` do not return `policy_no_eligible_approver`; that code is retired.
Source: ADR-0043.R13, ADR-0043.R13.N1, ADR-0043.R13.N2

R209. In the small-company mode the owner or chief accountant, eligible for the stage, may approve an untainted draft (never tainted, or cleared by `ClearTaint`, a self-clearance included) that an agent wrote for them from an event or schedule, as a recorded segregation exception of kind `own_agent_draft_approval` reviewed in the period review; a run the approver started by their own act stays refused. This holds under the reading of spec 03 rule 5 decided by the author's delegation to the chief architect (ADR-0054.R20; ADR-0067.R16).
Source: ADR-0043.R13.N3

R210. A proposal promoting an agent type to assisted mode must be approved by a person other than its submitter (`approver_is_submitter`), so a one-person company cannot promote an agent until the author decides (ADR-0050.R14).
Source: ADR-0043.R13

### Auto-posts and confirmation

R211. `is_confirmation_required` applies only to `post` and `issue` by `system` or `integration` actors. Each such posting adds evidence to one `auto_post_unconfirmed` work item per rule and window; `auto_post.confirmation_cadence` sets the window (`period` by default), and the item is due at the window's end, due rule `named_by_raiser` (ADR-0042; ADR-0065.R7, ADR-0065.R8, ADR-0065.R22). `ConfirmAutoPost` (a list) may be run only by the owner on the rule's latest version, so a reassignment moves the duty. `INV-87` covers every `system` and `integration` posting with confirmation required.
Source: ADR-0043.R14, ADR-0043.R14.N5

R212. A rule that lets `system` or `integration` post is enabled only by `EnablePolicyRule` with the shadow-mode evidence recorded (ADR-0003.R8; DS-34). A rule with empty `actor_kind` that allows is treated the same. The evidence comes through an evidence hook that `policy` declares and `app` wires, and is stored on the rule version (`policy_rule_version.shadow_evidence`). `cash` registers `GetAutoPostShadowEvaluation` on it. `production` registers `GetProductionImportShadowEvaluation` for `integration` postings of `operation_confirmation` by the production import, which also needs `production.mes_import.auto_post` (ADR-0064.R25).
Source: ADR-0043.R14, ADR-0043.R14.N3

R213. `EnablePolicyRule` returns `shadow_evidence_insufficient` below the evidence floor. The floor is the setting `auto_post.max_error_rate` (default 1%, at most 2%): at least ceil(3 / rate) proposals with at least (1 - rate) posted unchanged; the default gives 300 proposals at 99% (ADR-0051.R18; ADR-0063.R10). `bank_charge` rules have their own capped evidence (ADR-0063.R9).
Source: ADR-0043.R14, ADR-0043.R14.N2

R214. The evidence hook also answers `auto_post_eligibility` for a `system` posting of a cascade draft. The posting is eligible when all of these hold; otherwise it gets `human_post`:
- its line carries the parameters hash the stored evidence names;
- it was proposed while the parameter set's state in force was `active` or `core_default`;
- it is not a tied match;
- it carries no `counterparty_unverified` or `paid_by_third_party` flag;
- the rule version's evidence is not marked outdated (`shadow_evidence_outdated_by`, set by `policy.contract.mark_auto_post_evidence_outdated` through the hook `artifact_in_force_changed`, in the same transaction as a demotion, rollback, invalidation or failed re-evaluation of the parameter set).
Source: ADR-0043.R14.N1

R215. The stored evidence names the function code with the hash. Account-rule drafts also need evidence that counts account-rule proposals. `EnablePolicyRule` refuses outdated evidence (`auto_post_evidence_outdated`). `GetAutoPostShadowEvaluation` counts only proposals made under one hash and names it with the parameter set's latest transition (ADR-0059.R2, ADR-0059.R6, ADR-0059.R10).
Source: ADR-0043.R14.N1

R216. The evidence hook returns, with its figures, the registered setting keys and values the evidence was judged under. `EnablePolicyRule` stores the keys in `policy_rule_version.evidence_setting_keys` and the values in `shadow_evidence.settings`. A rule version with evidence lists at least one key, and the keys are set once with the evidence (ADR-0063.R3).
Source: ADR-0043.R14.N4

R217. R211 to R216 are generalized into the auto-post gateway (ADR-0065). Each document type that may be auto-posted has a checker registered through the hook `auto_post_checker`; `EnablePolicyRule` for a rule that lets `system` or `integration` post a type with no checker returns `auto_post_checker_missing`. Every gateway decision is a `policy_decision` row with `auto_post_decision` (`auto_post`, `require_human`, `reject`), its mode, reason, checker version, plan hash, `as_of_date` and evidence (columns `auto_post_mode`, `auto_post_reason_code`, `auto_post_checker_code`, `auto_post_checker_version`, `auto_post_plan_hash`, `auto_post_as_of_date`, `auto_post_evidence`). The evidence a rule version stores names the checker version and the decision table version, and a mismatch gives `require_human` (ADR-0065.R6, ADR-0065.R8, ADR-0065.R14).
Source: ADR-0043.R14.N5

R218. A reversal of a `system` posting or of a gateway posting, or a confirmation recording it wrong, marks the evidence of every enabled rule version for that document type outdated, not only its own, and raises `auto_post_suspended` (ADR-0063.R9, ADR-0063.R10; ADR-0065.R16).
Source: ADR-0043.R14.N2, ADR-0043.R14.N5

### Seeded templates

R219. The core seeds each company with the procedures `standard` (rank 10) and `senior` (rank 20), which are named ranks, and with approval pools whose stages are `standard` (minimum rank 10, roles `accountant`, `chief_accountant` and `owner`) and `senior` (minimum rank 20, roles `chief_accountant` and `owner`); rank 20 then needs two people (ADR-0055.R2, ADR-0055.R5).
Source: ADR-0043.R15, ADR-0043.R15.N1

R220. The core seeds each company with these rules:
- the bank-account rule of R205;
- for action `submit` and actor kind `human`, `require_approval` with `standard` when `is_credit_exceeded` (ADR-0030.R7); non-human actors already need approval at submit by the baseline;
- `standard` approval for both `submit` and `post` of a purchase invoice, for every actor kind, when `is_match_exceeded` (ADR-0047.R14);
- `standard` approval for `submit` and `post` of `general_journal`, for every actor kind (ADR-0048.R15);
- `standard` approval at `submit` of every document type, for every actor kind, when `is_cost_unknown` (ADR-0047.R22);
- `quality.deviation`: `require_approval` with `standard` at `submit` of `inspection_lot`, actor `human`, when `is_quality_deviation` (ADR-0070.R13).
Source: ADR-0043.R15, ADR-0043.R15.N2, ADR-0043.R15.N4

R221. The core seeds no thresholds and no rule that lets a non-human post; those are the company's and the author's (open question). Auto-acceptance of an inspection lot needs a company's own `allow` rule for `system`; no preset seeds one (ADR-0070.R13, ADR-0070.R14).
Source: ADR-0043.R15, ADR-0043.R15.N4

R222. The operating preset `quickflows` seeds, for actor `human` at `submit` and `post` of every document type, rules that require `standard` from an amount the implementer enters (`risk_amount`) and when `is_credit_exceeded`, `is_cost_unknown` or `is_price_below_cost` is true. Below the amount and without those flags a person posts from draft (ADR-0009.R11). The seeds of R219 and R220 stay. A preset never seeds a rule that allows a non-human actor (ADR-0067.R3, ADR-0067.R6, ADR-0067.R15).
Source: ADR-0043.R15.N3

### Period unlock and other policy points

R223. `UnlockPostingPeriod` (`human_only`, ADR-0012) takes the ID of an approved `period_unlock_request`. That is a non-posting document (period, area, reason) whose `Submit` is a policy point, which always requires at least the lowest-rank procedure.
Source: ADR-0043.R16

R224. The unlock closes the `period_unlock_request` in the same transaction, so one request unlocks once, and records the request's `policy_decision_id` in its audit record (ADR-0038.R2).
Source: ADR-0043.R16

R225. Other policy points:
- Matchings (`open_item_matching`, ADR-0026.R9) are documents with the usual points.
- Stock counts post through the usual points (ADR-0023.R18).
- The release of a production order is `submit` of type `production_order` (ADR-0034.R5); there is no `release` action.
- No policy point exists in Phase 1, and defaults apply, for the automatic conversion of planned orders and automatic release (ADR-0024.R22; ADR-0036) and for further record-scope dimensions (ADR-0017.R9). Flagged.
Source: ADR-0043.R17, ADR-0043.R17.N1

### Commands, queries and invariants of rules and procedures

R227. The rule commands are `CreatePolicyRule`, `UpdatePolicyRule` (a new version), `EnablePolicyRule` and `DisablePolicyRule`; the procedure commands are `CreateApprovalProcedure` and `UpdateApprovalProcedure`. All are `human_only`, effect class `master_data_change`, change-tracked (ADR-0038.R3) and on no agent tool list. One person may change policy alone (open question). `CreateApprovalPool` and `UpdateApprovalPool` join these commands with the same registration. `CreateApprovalProcedure` and `UpdateApprovalProcedure` re-run the pool checks, because a rank or its activity changes what the stages must cover (ADR-0055.R4, ADR-0055.R17).
Source: ADR-0043.R18, ADR-0043.R18.N1

R228. The queries are `ListPolicyRule`, `ListApprovalProcedure` and `ListPolicyDecision`. `GetPolicyEvaluation` (action, type, actor kind, input; computed) is for people only, like `ListAllowedCommand` (ADR-0040.R8).
Source: ADR-0043.R18

R229. The invariants of ADR-0043 are:
- `INV-82`, restated by stages and rounds (ADR-0055.R18): every posted document whose decision requires a rank has the required approvals on that version;
- `INV-202`: the enabled rule set passes the check of R202;
- `INV-203`: every enabled rule that allows a non-human actor has an owner and a maximum, and confirmation at post and issue.
Source: ADR-0043.R19, ADR-0043.R19.N1

### Bank cascade follow-up and auto-post evidence

R230. A `cash` consumer of `BankLineSuggestionRecorded` runs `match_bank_line` once more, with the suggested tokens added as reference tokens at step 2 only, under step 2's guards: each token must be a whole token of the description and reference-shaped, at least four characters with a digit or the package's pattern for its invoice numbers (ADR-0048.R9), and all the items its tokens name must belong to one partner. If it finds items of exactly one partner, it drafts the receipt or payment as ADR-0048.R9 does, as `system` on behalf of the run's human (ADR-0013.R9), marked `match_basis` `llm_suggestion` and with no score. The draft carries the run as its origin, so it is tainted (ADR-0029.R8, ADR-0029.R12) and a person posts it (ADR-0043.R9, floors 3 and 5). Its data never returns to the run.
Source: ADR-0051.R18

R231. Auto-post applies only to cascade matches with a score and no LLM contribution, under an enabled rule (ADR-0048.R9; R211 to R218). Its shadow evidence is `GetAutoPostShadowEvaluation` (module `cash`; document types, score floor, amount maximum, date range): of the cascade's proposals at or above the floor and below the maximum in the range, the share that people posted unchanged. `EnablePolicyRule` for such a rule obtains that result through an evidence hook that `policy` declares and `cash` registers for its document types, wired by `app` (layer 6), so `policy` imports no layer-4 module. It stores the result and is rejected with `shadow_evidence_insufficient` unless the evidence covers the proposals that `auto_post.max_error_rate` requires (its default gives 300 proposals with at least 99% posted unchanged; ADR-0063.R10), over at least two statement months, with no proposal posted to another partner.
Source: ADR-0051.R18, ADR-0051.R18.N3

R232. The guards of step 2 stay on the re-run: a suggested token counts only as a whole, reference-shaped token of the description. A reference the payer wrote in another form is not a whole token of the description, is refused, and the line stays for a person. The effect of a suggestion is therefore its stable payer token, which feeds the matching-rule proposals of ADR-0051.R19, and its purpose classification, shown to the person who matches the line. The token re-run is one pure call, and the shadow comparator of ADR-0051.R19 is defined on it. Whether the agent earns its cost in Phase 1 is an open question.
Source: ADR-0051.R18.N1

R233. The evidence counts only proposals made under one `parameters_hash` and names it with the parameter set's latest transition. A later parameter set version, demotion, rollback or invalidation marks the stored evidence outdated in its own transaction, and re-arming needs a new rule version with new evidence (ADR-0059.R6). Evidence counts proposals of approved LLM-originated rules only while `cash.auto_post.accept_llm_originated_rules` is true (ADR-0063.R8).
Source: ADR-0051.R18.N2, ADR-0051.R18.N3

R234. Every unattended posting goes through the auto-post gateway of ADR-0065, whose instances are the bank cascade (unchanged), the production import and the purchase invoice. The `llm_suggestion` drafts of R230 still never auto-post. `cash.auto_post.accept_llm_originated_rules` is not bounded false; its default is false (ADR-0065.R12, ADR-0065.R20).
Source: ADR-0051.R18.N4

### Approval pools

ADR-0055 keeps the policy table of ADR-0043 and adds what happens after the rank is known: pools group document types, each pool has ordered stages, and all stages whose minimum rank is at most the decision's rank are required in sequence. Procedures stay as named ranks. Stages, plans, execution and escalation are stated in chunk 3.

R235. `policy` (layer 2) owns `approval_pool`, `approval_pool_document_type`, `approval_stage` and `approval_stage_member`, beside `approval_procedure` (ADR-0043.R1). `approval_stage.escalation_role_id`, `approval_stage_member.role_id` and `approval_stage_member.user_account_id` are database references to `role` and `user_account`, which `permissions` owns. They are keys only: `policy`'s code never reads assignments; who holds a role is answered by `permissions`' effective-rights function (ADR-0054.R2).
Source: ADR-0055.R1

R236. Approval rows stay `documents`' (ADR-0043.R1). Each person's decision at a stage is one immutable `approval` row (ADR-0009.R11), extended by ADR-0055.R9; the glossary calls it an approval step. There is no second table for steps: one row per decision is what `INV-17` and `INV-82` read. The approval work item and its owner column `work_item.owner_approval_stage_id` are `work`'s (ADR-0042.R2).
Source: ADR-0055.R1

R237. Evaluation runs through registered functions, as in ADR-0054.R2: each module registers functions with the dispatcher and `app` wires them. `policy` registers the selector, the plan and the stage reader; `permissions` effective rights, delegations and the segregation checks; `documents` the document actors and the counted approvals. The dispatcher combines them for `Submit`, `Approve` and `Reject` (ADR-0055.R6 to ADR-0055.R8), and `work` filters approval items through a registered visibility function (ADR-0055.R12). Beyond the existing imports of ADR-0022.R2, `work`, `documents`, `permissions` and `policy` import nothing from each other.
Source: ADR-0055.R1

R238. `approval_pool` is company data with `code`, `name`, `basis` and `is_active`. The core seeds these pools in every company, each with the document types of its default row:
- `pr`: `purchase_request`;
- `po`: `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`, `gr_ir_write_off`;
- `sales`: `quotation`, `sales_order`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note`;
- `mo`: `production_order`;
- `consumption`: `internal_consumption`, `other_issue`, `scrap`, `stock_count`, and `production_issue`, because an issue above requirement may wait for approval (`is_above_requirement`, ADR-0034.R5);
- `expense`: `advance_settlement`, `general_journal`; and by selector, payments and purchase invoices with `is_direct_expense`;
- `general`: every other type that can wait for approval: payments without expense lines, receipts, `change_proposal`, `period_unlock_request`, `write_off`, and the rest;
- `quality`: `inspection_lot` (ADR-0070.R13).
Source: ADR-0055.R2, ADR-0055.R2.N1, ADR-0055.R2.N3

R239. Companies may add pools (for example `payment`) and change the mapping with `UpdateApprovalPool`. The seeded mapping is interim (open question). `general` is the pool of last resort (ADR-0055.R3), so it cannot be deactivated (`approval_pool_invalid`).
Source: ADR-0055.R2

R240. Types that may not wait never reach a pool (ADR-0055.R15). Shop-floor facts never wait: `operation_confirmation`, `production_receipt` and `service_receipt` are registered `is_approval_hold_allowed: false`. For `sales_invoice`, `sales_return`, `credit_note` and `debit_note` this depends on the regime: `is_approval_hold_allowed` is derived from the regime setting `documents.issuance_without_delay` on the document date (ADR-0053.R8). The core default lets them wait, so they keep their `sales` mapping; where a package sets the setting true, ADR-0055.R15 applies and the mapping is unused. The pool design itself holds no country rule.
Source: ADR-0055.R2, ADR-0055.R2.N1

R241. The core seed stays minimal. Under the seed of R220, a person's `Submit` of a purchase request, purchase order, quotation or production order matches no rule, gets no rank and goes straight to `approved`, so pools `pr`, `po`, `mo` and, for quotations, `sales` are reached only through company rules. The core seeds no thresholds; the `vn_*` profiles of DS-17 add sample company rules and stage members through setup events.
Source: ADR-0055.R2.N2

## Invariants

The statement is that of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-202` | `policy_rule_set_monotonic` | day | The enabled policy rule set of each company passes the save-time monotonicity check for every future effective date. | R202 |

Named by rules of this chunk, with their rows in other chunks: `INV-82` (R229, R236), `INV-203` (R229) and `INV-87` (R211) in chunk 1; `INV-17` (R236) in chunk 4.

## Settings

None: the settings `auto_post.max_error_rate` (R213, R231) and `auto_post.confirmation_cadence` (R211) have their rows in chunk 4, with `cash.auto_post.accept_llm_originated_rules` (R233, R234), whose leaf is `policy`.

Reads: `documents.issuance_without_delay` (`documents`; ADR-0053.R8), `production.mes_import.auto_post` (`production`; ADR-0064.R25).

## Conflicts

CONFLICT ADR-0043.R10: the rule's closing sentence citing ADR-0053.R8 governs types registered `regime`; R201 states the hold by the setting `documents.issuance_without_delay` on the document's date.
CONFLICT ADR-0043.R12: ADR-0029.R4 confirms the bank-account proposal for every company and ADR-0043.R9.N3 makes it a floor, so R205 drops "while ADR-0029 rule 4's interim stands"; ADR-0055.R5 and ADR-0055.R7 govern who approves a change proposal: the stage's eligibility, not "that procedure's role" (R204).
CONFLICT ADR-0043.R12.N1: the later note ADR-0063.R3.N2 (ADR-0067.R9) adds the setup path before go-live for keys whose `outdates` is `none`, and ADR-0065.R8 keeps every `auto_post.*` key out of it; stated in R206.
CONFLICT ADR-0043.R13: ADR-0043.R13.N1 and ADR-0055.R7 govern; the approver's eligibility is the stage's, and the interim that let a person approve their own document is not restated (R208).
CONFLICT ADR-0043.R13.N1: the note replaces the small-company interim of its rule by stage eligibility with writers excluded (ADR-0055.R7), and names `approval_stage_unsatisfiable` as the check; stated in R208.
CONFLICT ADR-0043.R13.N2: the note retires `policy_no_eligible_approver` on the rule commands; ADR-0055.R4 governs the satisfiability check, stated in R208.
CONFLICT ADR-0043.R14: ADR-0043.R14.N2 turns the fixed evidence figures into the setting `auto_post.max_error_rate` (R213); ADR-0043.R14.N5 replaces "per rule and period" by the window of `auto_post.confirmation_cadence` (R211) and widens the outdating to every enabled rule version of the document type (R218); ADR-0065.R22 makes the `auto_post_unconfirmed` item due at the end of its window (R211).
CONFLICT ADR-0043.R15: ADR-0043.R15.N1 and ADR-0055.R5 govern; the approver roles belong to the seeded stages, not to the procedures, which are named ranks without a role (DDL of `approval_procedure`), so R219 states no role on a procedure.
CONFLICT ADR-0043.R17: ADR-0043.R17.N1 corrects the citation for the release of a production order to ADR-0034.R5 (R225).
CONFLICT ADR-0043.R19: ADR-0043.R19.N1 and ADR-0055.R18 govern `INV-82`, which is read by stages and rounds and not by one approval of a procedure's rank (R229).
CONFLICT ADR-0051.R18: the fixed 300 proposals at 99% are the default of the setting `auto_post.max_error_rate` under ADR-0051.R18.N3 (ADR-0063.R10); R231 states the threshold through the setting.
CONFLICT ADR-0051.R18.N4: the note lifts the false bound of the LLM-originated setting and generalizes the Decision sentence to the gateway; ADR-0065.R12 and ADR-0065.R20 govern, stated in R234.
CONFLICT ADR-0055.R2: ADR-0055.R2.N1 governs the seeded mapping; pool `mo` holds `production_order` only and `production_issue` is in `consumption` (R238); ADR-0055.R2.N3 adds the pool `quality`.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0043.R10 | R201 |
| ADR-0043.R11 | R202, R203 |
| ADR-0043.R12 | R204, R205 |
| ADR-0043.R12.N1 | R206 |
| ADR-0043.R13 | R207, R208, R210 |
| ADR-0043.R13.N1 | R208 |
| ADR-0043.R13.N2 | R208 |
| ADR-0043.R13.N3 | R209 |
| ADR-0043.R14 | R211, R212, R213 |
| ADR-0043.R14.N1 | R214, R215 |
| ADR-0043.R14.N2 | R213, R218 |
| ADR-0043.R14.N3 | R212 |
| ADR-0043.R14.N4 | R216 |
| ADR-0043.R14.N5 | R211, R217, R218 |
| ADR-0043.R15 | R219, R220, R221 |
| ADR-0043.R15.N1 | R219 |
| ADR-0043.R15.N2 | R220 |
| ADR-0043.R15.N3 | R222 |
| ADR-0043.R15.N4 | R220, R221 |
| ADR-0043.R16 | R223, R224 |
| ADR-0043.R17 | R225 |
| ADR-0043.R17.N1 | R225 |
| ADR-0043.R18 | R227, R228 |
| ADR-0043.R18.N1 | R227 |
| ADR-0043.R19 | R229 |
| ADR-0043.R19.N1 | R229 |
| ADR-0048.R9.N7 | ref: ADR-0048.R9.N7 |
| ADR-0050.R50 | ref: ADR-0050.R50 |
| ADR-0051.R18 | R230, R231 |
| ADR-0051.R18.N1 | R232 |
| ADR-0051.R18.N2 | R233 |
| ADR-0051.R18.N3 | R231, R233 |
| ADR-0051.R18.N4 | R234 |
| ADR-0055.D0 | Approval pools |
| ADR-0055.R1 | R235, R236, R237 |
| ADR-0055.R2 | R238, R239, R240 |
| ADR-0055.R2.N1 | R238, R240 |
| ADR-0055.R2.N2 | R241 |
| ADR-0055.R2.N3 | R238 |
