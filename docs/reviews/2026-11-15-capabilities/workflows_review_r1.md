# Review r1 of ADR-0058 "Configurable workflows" and ADR-0059 "AI tuning and development of deterministic functions" — verdict: NOT YET

1 blocking, 21 should-fix, 14 nits. Base: holistic-review at 32e7b1c, with `apply_workflows.py` applied (65 writes over 32 files).
File:line refer to the review copy: "0058" = `adr/0058-configurable-workflows.md`, "0059" = `adr/0059-ai-tuning-and-development-of-deterministic-functions.md`, "DDL" = `design/DS-28-34-configuration-artifacts.sql`, "DS-05" = `design/DS-05-platform.sql`, "DS-04" = `design/DS-04-command-envelope.md`, "t22" = `lab/t22_workflows.py`.

What I ran:
- `load_all.py` on a fresh `nativeflows_lab_rv58`: 305 tables.
- `t22_workflows.py --load`: 87/87 pass. `t23_ai_artifacts.py --load`: 76/76 pass. Each on a freshly created database.
- My own probes against the loaded DDL and the lab's pure functions (results cited in S6, S8, S19, N2, N11).
- Cleanup done: `nativeflows_lab_rv58` dropped, `/tmp/rv58` deleted, repo untouched (`git status` clean, HEAD 32e7b1c). This file is the only file written.

## Blocking

**B1. A rule reads, stores and shows values outside its owner's and its readers' record scope and field classes (0058:45 rule 4, 0058:75-80 rule 9, 0058:83 rule 10, 0058:90-92 rule 11, 0058:140 rule 23; ADR-0017 rules 9-10; spec 03 rule 4; ADR-0050 rule 12 note).**
- The consumer reads the condition source under its own registered permissions (ADR-0013 rule 4, ADR-0017 rule 13). Rule 9 re-checks only the owner's permission for the action command. Nothing checks that the owner may read the triggering subject (record scope) or the condition fields (field class). Rule 4 excludes only `is_untrusted`, `sensitive_personal` and `is_llm_derived` fields.
- So an owner without the `margin` class or without the branch can activate "notify me when a sales order with margin below 5% is approved" and get an oracle on data they cannot read.
- `automation_execution.condition_results` stores the value read (only personal values are hashed). `ListAutomationExecution`, the agent view `automation_execution_overview`, `GetAutomationReplay` and the frozen replay diff ("order number and amount") return those values with no field-class or scope filter. ADR-0017 rule 10 says a field of a class the actor lacks is omitted from every response; an agent type with no `field_classes` would see cost and margin through the view.
- Fix:
  - at validation and at each execution, require the owner to hold the query permission of the condition source and every field class of the fields the version uses; evaluate only subjects inside the owner's record scope (outside: no match, not an error);
  - mark each stored condition value with its field's class and filter it in `ListAutomationExecution`, the view, the replay and the evidence diff by the reader's classes and scope (or store class-protected values as hashes, like personal ones);
  - add an invariant and an edge case (owner without `margin`; reader without the branch), and a t22 check.

## Should-fix

**S1. Segregation of duties is weaker than for ordinary consumers, and the owner is assigned without consent (0058:62 rule 8, 0058:76-78 rule 9, 0058:167 rule 27, 0058:211 example).**
- A rule's draft counts only the owner as writer. The version's drafter (who wrote the literals of the payload template) and the human of the triggering event (whose document fills the payload) are not writers, so either may approve the draft. An ordinary consumer draft is on behalf of the event's human (ADR-0013 rule 9), who then cannot approve (ADR-0055 rule 7 condition 5).
- `CreateAutomationRule` and `UpdateAutomationRule` name any user as owner; the owner neither submits nor approves, and an owner change on an active rule is a plain `master_data_change`. A drafter can therefore borrow a colleague's rights for drafts, and block that colleague from approving them.
- Fix: writers of a rule-made draft are the owner, the version's drafter (and the human its drafting run acted for) and the triggering event's human. The owner must be the activation's submitter or approver, or accept by a command of their own; an owner change runs through the same proposal and re-checks the new owner's rights.

**S2. An owner who leaves the company, and any slow persistent failure, never trips anything (0058:77 rule 9, 0058:110-112 rule 16, work-item-kinds.csv:48; ADR-0054 rule 3; ADR-0007 rule 10).**
- "Owner gone" covers only a deactivated account. A user whose role assignments in the company ended stays active (ADR-0054 rule 3, shared users), so no `owner_inactive` follows; every execution is `refused`.
- The breaker needs 5 refusals within 60 minutes. A rule that fires three times an hour is refused forever with no work item.
- When it does trip, `automation_rule_disabled` goes to `subject_owner:owner_user_id`, the person who can no longer open the company. ADR-0042 rule 7's fallback covers only deactivation.
- The window is counted on `recorded_at` (DDL:123), which ADR-0007 rule 10 forbids as a condition unless declared a technical timer, as ADR-0013 rule 7 does.
- Fix: disable with `owner_inactive` when the owner is deactivated or no longer linked to the company; trip the breaker on N consecutive refused or failed live executions (clock-free), keeping the window only as an addition declared a technical timer; fall back to `company_owner` when the owner cannot read the item.

**S3. Refusals that are by design count toward the breaker, and rule 10 contradicts EC-160 on atomicity (0058:79-80 rule 9, 0058:85 rule 10, 0058:199 EC-160, edge-cases.csv:115).**
- Rule 10: a non-retryable error "rolls back that rule's savepoint and records `refused`", so the rule is all-or-nothing. EC-160: "the draft is created tainted and the agent start is refused", a partial result, and the DDL has no outcome for it.
- A rule with `start_agent` that sometimes meets a tainted or agent-chain event is refused each time by design; five such events in an hour disable it for every other event.
- "Each action runs in a savepoint" and "that rule's savepoint" also disagree in the same bullet.
- Fix: decide the taint and agent-chain exclusions before acting, per action, as `skipped` entries in `action_results` that do not count toward the breaker; keep the rule atomic for real refusals and failures; restate EC-160 and INV-674 accordingly.

**S4. `start_agent` is refused on exactly the subjects it is meant for, and its acting human is stated two ways (0058:57 rule 7, 0058:79 rule 9, 0058:187 INV-670, DS-04:68; ADR-0050 rules 15-16 and the new rule 16 note; open-questions.md candidates).**
- Rule 9 refuses `start_agent` on a tainted event or an outside-content subject. The named candidates, `inbound_message_matched` and `supplier_invoice_received`, are outside content, so a configurable trigger there could never start an agent. ADR-0050 rule 16 already allows a wake-up on a tainted item because the run starts tainted and can only draft.
- Rule 9 and INV-670 say every action, `StartAgentRun` included, runs on behalf of the rule's owner. The note on ADR-0050 rule 16 says it acts for the setting's `workflow_owner_id` and that the owner "also needs `start_agent:<agent_type>`", a requirement that appears nowhere in ADR-0058.
- Fix: allow `start_agent` on tainted and outside-content subjects (the run starts tainted, ADR-0050 rule 15) and keep only the agent-chain refusal; state in rule 9 that the run acts for the workflow owner, that both the workflow owner and the rule owner need `start_agent:<agent_type>`, and correct INV-670 and DS-04 step 2.

**S5. `raise_work_item` and `notify` have no permission the owner can hold (0058:70-71 rule 8, 0058:76 rule 9, 0058:172 rule 27, 0058:190 INV-673; ADR-0008 rule 1 note).**
- `RaiseAutomationWorkItem` is `is_internal_only`. No role holds an internal-only command at any level. So "the command's own permission checked against the owner's current rights" is either always false or not checked, and INV-673 cannot be evaluated for these two actions.
- Fix: register a capability (for example `raise_automation_work_item` on the leaf `configuration`) that the owner must hold at each execution, and name it in rule 9 and INV-673.

**S6. The rule graph misses edges, so the cycle and depth check is not complete (0058:46 rule 4, 0058:51 rule 5, 0058:105-109 rule 15; t22:174-216).**
- Commands declare the event types they emit, not discriminator values. The lab treats an emitted `WorkItemRaised` without a value as matching only undiscriminated triggers. Probe: rule A on `WorkItemRaised[automation_task]` drafts a purchase request, and a consumer of `PurchaseRequestCreated` raises a work item: `activation_check` returns no finding; the same rule without a discriminator is refused as a cycle.
- System jobs on a schedule start a new chain at depth 0 and are not in the graph, so a rule whose draft a scheduled job later reacts to loops once per schedule with fresh depth and a fresh same-target guard.
- It is not stated whether an agent run's tool calls inherit the chain of `AgentRunStarted` or start one, so INV-671 cannot be checked for them.
- Fix: emit declarations carry the discriminator values (a missing value is a wildcard that reaches every value); scheduled jobs that act on rows created by commands declare edges like consumers; state the chain rule for agent tool calls (inherit) in rule 12 and DS-04; add the probe above to t22.

**S7. The graph and validity checks are not repeated where the active set changes (0058:112 rule 16, 0058:144-146 rule 24, 0059:110 rule 13, 0059:155 rule 21).**
- Execution of an activation checks only content hash, registry version and this artifact's current version. Two candidates that each pass against the active set, approved in parallel, can both execute and form a cycle or exceed depth 3 (INV-675).
- `EnableAutomationRule` re-enables the same version with no check, also after `upgrade_invalid`, and after other rules were activated while it was disabled. Whether disabled rules stay in the graph is not said.
- `SetArtifactCurrentVersion` and the monitor's automatic rollback move the pointer to an older `active` version. The upgrade check validates only current and shadow versions, so the target may reference removed fields, break changed bounds, or close a cycle.
- Fix: run validity and the graph check (not the evidence) at execution, at enable, at rollback and at demotion; a failing target is refused with `artifact_invalid`, and the monitor falls back to core defaults or none. Keep disabled rules in the graph.

**S8. The completeness check is not tractable at the stated limits, and evaluation outside the domain is undefined (0058:118 rule 18, 0058:125-126 rule 19; t22:336-366).**
- The grid has one cell per combination of row bounds. 60 rows over 4 numeric inputs already give 214,358,881 cells (probe); 500 rows over 6 inputs give up to 1001^6, about 10^18. "Exact and fast" does not hold, and the activation validator can hang.
- A null input, a code value added to the company list after the version froze, and a number outside the declared range match no row; nothing says what the rule or decision point then does.
- Fix: check completeness by recursive splitting over the rows (subtract each row's box from the domain; stop at the first uncovered box), with a hard work bound that refuses the version (`artifact_invalid`, reason `decision_table_too_complex`); keep the overlap check pairwise, which is exact for boxes. Define evaluation outside the domain and on null as error `decision_table_no_match`: the execution is `failed`, a decision point falls back to its code default. Add a t22 timing case at 500 rows and 6 inputs.

**S9. How a rule binds a decision table, and what `content_hash` covers, is not defined (0058:52 rule 5, 0058:64 rule 8, 0058:150 rule 25, 0059:118 rule 14, 0059:199 INV-677).**
- Rules 5 and 8 say a rule names a decision table version (pinned). Rule 25 says clearing a table's pointer disables the rules that use it (bound to the pointer). If pinned, a table's `active` state means nothing to rules; if bound to the pointer, a new table version changes a rule's behaviour without the rule's replay diff, and the stale check does not see it.
- `content_hash` is never defined: which columns, whether tests, child rows, copied bounds and referenced table versions are inside. INV-677 and the stale check depend on it.
- Fix: choose one binding (recommended: by table code to the version in force, each evaluation recording the version, with the table's activation replaying every rule and decision point that uses it). Define `content_hash` per kind as SHA-256 of canonical JSON of the content columns, sorted child rows and tests, excluding lifecycle columns.

**S10. The out-of-sample rule has three holes (0059:125-126 rule 15, 0059:108 rule 13, 0059:190 rule 27, DDL:292-293).**
- A person's draft "declares its window, or has none"; with none the database check passes trivially (probe: sufficient backtest evidence with no drafting window and 0 cases is accepted). A person who types in values tuned on the evaluation window, their own or an assistant's, is not caught.
- The evaluation window is chosen by the person who creates the evidence, as often as they like, and `GetArtifactBacktest` previews it without a record. Nothing shows the approver earlier insufficient attempts or earlier use of the same window, the overfitting the ADR cites from AlphaEvolve.
- "A row dated after the window" is undefined for rows without a business date and for derived rows (current balances, evidence, shadow outcomes and monitor snapshots of earlier versions, which hold results of the later window).
- Fix: a version without a declared window is treated as drafted up to its creation date; evidence records the number of earlier evidence rows and previews for the same artifact whose windows overlap, and the proposal shows it; each readable table declares its as-of date column, reads of evidence, shadow outcomes and snapshots count by their evaluation window, and undated current-state reads are listed in the bundle.

**S11. Held-out cases are not kept from the generator (0059:128-131 rule 16, 0059:30 rule 1).**
- Only labels are hidden. The held-out case itself (the line and the person's final match, which is the label in practice) is ordinary data inside the drafting window.
- Code computes candidates "by a grid search" over resolved history, and runs read aggregates. Neither leaves row references, so the ID-set intersection cannot see them; fitting on held-out cases makes "held-out golden ≥ 95%" in-sample.
- Ordinary queries do not exclude held-out cases, so a run that lists lines hits one by accident and its version can never get sufficient evidence (EC-166 as the normal case).
- Fix: every drafting-side computation (the fit, the preview, aggregates and row queries of a drafting run) excludes cases whose hash byte is below 51, labelled or not, enforced at the query layer for agent types that declare draft commands of artifact kinds; the ID-set check stays as the second line.

**S12. "No gate reads an LLM-derived field" is not enforceable as written (0059:149 rule 20, 0058:45 rule 4, 0059:205 INV-683).**
- The mark is per field, set by registration. A document field is written by people and by agent drafts alike, so either every draftable field is marked (no condition fields remain) or only suggestion fields are (agent-chosen values in drafts steer rules).
- Nothing derives the mark, and derivation is not transitive: a deterministic field computed from a marked field is unmarked.
- Fix: define `is_llm_derived` as a field whose only writer is an LLM step's output; derive it in CI from the output schemas and the payload fields they fill; propagate it to fields computed from a marked field; state that agent-drafted document values are covered by ADR-0029 rule 12 and by taint, not by this mark.

**S13. The cascade's parameters loosen guards that ADR-0048 rule 9 holds through fixed scores (0059:48-66 rule 5, 0059:89-90 rule 10, 0059:225 example; ADR-0048 rule 9).**
- `score_account_amount_tied` (60), `score_account_subset` (70) and `score_reference_partial` (80) may be raised to 100. A tied match is an ambiguity; decision 14 and rule 10 say ambiguity always suggests, yet a tuned set can lift it above an auto-post floor.
- No order between parameters is declared, so partial may exceed exact.
- Today a company rule only names the partner and steps 3-4 score the match (t08 B15: 90, 60 or 70). Rule 10 gives a confirm-mode rule match a flat `score_company_rule` 90, which raises tied and subset matches, and does not say that the `counterparty_unverified` and `paid_by_third_party` caps apply, although a description token is as untrusted as a reference.
- Fix: declare the tied score a safety cap (or a suggest pass with no score); declare order constraints in the function's declaration (partial ≤ exact, tied ≤ untied, subset ≤ single), checked with the bounds; a company rule keeps naming the partner only, steps 3-4 score it, `score_company_rule` is a cap on that score, and the counterparty caps apply.
- For the author, not new here: an approved rule whose token an LLM read can feed a scored match and so an auto-post (spec 03 rule 1, "a match an LLM contributed to"). The base design already has this path; this ADR makes it explicit. It belongs in open-questions.md.

**S14. `parameters_hash` does not identify a version, and the auto-post binding has two silent effects (0059:46 rule 4, 0059:67-70 rule 6, 0059:204 INV-682, DDL:208, DS-05:1017).**
- The effective hash includes the function version, so after a function release it equals no stored `parameter_set_version.parameters_hash`; a decision's hash can no longer be traced to its version.
- Every release that bumps `cash.match_bank_line` switches auto-post off until 300 proposals over two statement months exist again, with no work item.
- "Proposals made while the current version is `assisted` are not auto-posted" cannot be checked: the line stores only the hash, which is the same when the version later becomes `active`.
- Fix: store on the version a `values_hash` (function code and values) and define the effective hash as SHA-256 of (function version, values hash), recording both on the decision; raise a work item for the policy rule's owner when the hash in force leaves the evidenced one; record `match_parameter_set_version_id` and the version's state on the line (or define the rule from `artifact_transition`).

**S15. Acting paths re-arm without a person (0059:69 rule 6, 0059:110 rule 13, 0059:155 rule 21, 0059:223 example).**
- After an automatic demotion, proposals run under H0 again and auto-post resumes by hash equality, on evidence that predates the period under H1, at the moment the monitor has just measured drift.
- One person with `full` can do the same by rollback, with effect class `other`.
- Fix: after a demotion, a rollback or a fallback to core defaults, the acting path stays off until the policy rule's owner confirms (a work item resolved by a command), or until the stored evidence's window is recent within a company setting. Flag the choice for the author.

**S16. Thresholds are per artifact kind, not per function (0059:133-141 rule 18, 0059:72 rule 8; ADR-0052 rule 17).**
- "200 cases over 28 days, 100 live cases over 10 business days" fits bank lines. `crm.find_partner_duplicates` and planning parameters share the kind `parameter_set`; a small company cannot reach those counts, so the duplicate threshold that is a plain setting today becomes untunable.
- Fix: the tunable declaration carries its own neutral thresholds and stage list, which the company settings override per function code; keep `crm.duplicate_name_threshold` a setting until its `backtest`, `compare` and `monitor` are designed.

**S17. `matching_rule` and `report_definition` are on the lifecycle without a carrier that fits the accepted flows (0059:83-84 rule 9, 0059:90-91 rule 10, 0059:93 rule 11, 0059:225 example; ADR-0051 rule 19; ADR-0049 rule 11; ADR-0029 rule 3).**
- The consumer "drafts a rule as today", which is a change proposal draft, and the draft "waits" for a later line; then a second proposal raises "the version" to `assisted`. Two carriers for one rule, and a waiting proposal meets `change_proposal_ttl_days` (14): the example waits 29 days.
- A report definition's create proposal "is its promotion", with evidence of a render and a hand-checked cell, but `CreateArtifactEvidence` needs a version that exists only after the proposal executes, and no command records the hand check.
- Fix: the consumer writes a `bank_matching_rule` version in `draft` by a draft-only command (tainted), and the only proposal is `SetArtifactVersionState`; restate the note on ADR-0051 rule 19. Take `report_definition` and `analysis_definition` off the Phase 1 ladder, as rule 9 already does for pricing rules, until their owners design draft versions.

**S18. Layer-2 commands need layer-5 validators (0058:26-27 rule 1, 0058:143-146 rule 24, 0059:33 rule 2, 0059:69 rule 6; ADR-0022 rule 2).**
- `SetArtifactVersionState`, `SetArtifactCurrentVersion` and `EnableAutomationRule` belong to `configuration` (layer 2); the validators and the graph check they must run belong to `automation` (layer 5). No hook is declared, so this is an upward import.
- The `human_post` on a hash mismatch is a policy floor that needs `cash`'s data; ADR-0051 rule 18's evidence hook does not provide it.
- Fix: move the pure validators (rule validity, graph check, table check) into `configuration`'s contract, leaving replay, evidence, monitor and upgrade jobs in `automation`; or declare hooks wired by `app`. Extend the auto-post hook with the eligibility answer, or let `cash` withhold the post.

**S19. DDL guards (DDL:251, 256, 408-451, 477-503).** Probes on the loaded schema:
- A version can be inserted directly as `active` or `shadow`, and a pointer set to it: the change trigger runs only on UPDATE and DELETE. Add a BEFORE INSERT check that `state = 'draft'`.
- Retiring a shadow version leaves `shadow_version_id` naming a retired version (INV-678): the in-force check reads only `current_version_id`. Refuse leaving `shadow` while the shadow pointer names the version.
- `ck_parameter_set_value_cap` is not null-safe: with a null default, `max_value = default_value` is null and any maximum passes. Use `NOT is_safety_cap OR (default_value IS NOT NULL AND max_value = default_value)`.
- A safety cap may be nullable with value null ("off"), which removes the cap. Add `NOT is_safety_cap OR (NOT is_nullable AND value IS NOT NULL)`.
- `draft → active` in one update skips `backtested`, which every ladder requires. Allow only `backtested` from `draft`.
- Add each case to t22 or t23.

**S20. `artifact_invalidated` for a deprecated reference has no subject (0058:151 rule 25, 0059:113 rule 13, work-item-kinds.csv:49).** Its subject is an `artifact_transition`, but a deprecation changes nothing and writes no transition; a check result is a command result, not a work item. Fix: a kind `artifact_reference_deprecated` with the artifact as subject, or a transition move `deprecation_found` with no state change.

**S21. The L1 example's figures do not compute (0059:219).** Baseline: 78.0% of 4,812 lines is about 3,753 decisions, 91.2% right, about 3,423. The candidate drops 168 drafts (94 right) and changes 44 matches (39 had been right): at most about 3,295 right of 3,585, which is 91.9%, not 96.0%. The evidence also shows the shorter window losing 39 right matches for 5 wrong ones, yet it is promoted. Fix: recompute the example from one consistent set of counts, preferably the reduced cascade of t23, and assert it there.

## Nits

- **N1.** DS-05:692, 746: `causation_depth` has `DEFAULT 0`, so a writer that forgets it resets the depth silently. Drop the default, and add `automation_rule_version_id IS NULL OR causation_depth >= 1` on both tables.
- **N2.** DDL:97-117: a `depth_exceeded` execution is accepted at depth 0 (probe); add `outcome <> 'depth_exceeded' OR causation_depth = 3`. `origin_agent_run_id` has no key to `agent_run`, unlike the version tables.
- **N3.** DS-04:68: step 2 is "gates that need no subject state", but the new refusal reads whether the subject's effective version is tainted; say the consumer passes the flag it computed when reading the facts. `tainted_run_not_allowed` precedes it, so `automation_action_not_allowed` is unreachable for a hold on a tainted event.
- **N4.** 0058:134: an event whose business date precedes the new version's `effective_from` is evaluated by no version and leaves no record. Say so, or let the previous version take it.
- **N5.** 0059:129, DDL:354: the byte encoding of (company ID, case ID) is not defined (the DDL comment uses `company_id:case_id`). Define it, and hold `is_held_out` by a check with `sha256`, so INV-685's second half is database-held.
- **N6.** Glossary (spec/00-reading-guide.md:479): "Bank matching rule" still says "proposal-bound"; L1/L2/L3, circuit breaker, hold interface, watched fields and configurable trigger are missing.
- **N7.** authorization-areas.csv: the leaf `configuration` (module `configuration`) also holds commands of module `automation`; confirm that the leaf-per-module check allows it. Rule 3's declaration (0059:39-43) lacks the function's leaf, which `RecordGoldenCaseLabel` needs.
- **N8.** 0058:50: say whether `CreateChangeProposal` may be automation-allowed, and restrict `create_draft` to commands that create (not updates or deletes of drafts).
- **N9.** INV-680 reads run steps that are dropped after 400 days (ADR-0050 rule 19); scope it to retained steps, or freeze a hash of the read references in the evidence. Refuse evidence when the drafting run's steps are gone.
- **N10.** 0059:155: "the previous version in state `active`" should be the version that was in force before (the promotion's `previous_current_version_id`), if still eligible.
- **N11.** DDL:12-14: the fourteen tables have no row-level security in the loaded schema (`relrowsecurity` false; `policy_rule` has it). This follows the other design files, but t22's D02 could assert it once the pattern is written out.
- **N12.** 0058:111: say that the breaker's `DisableAutomationRule` runs under the consumer's registered permission, not the owner's, since the owner may be the one who lost rights.
- **N13.** 0058:87, work-item-kinds.csv:46: the work item's subject is the `automation_execution` row, written after the actions; say the ID is allocated first.
- **N14.** 0059:7, 170: "X1 to X10" omits X5 (calibrated abstention), which rule 20 in fact covers; name it. Decision 14 names partner and item matching; rule 10 gives them one clause and rule 9 lists no kind for item mappings. Say which existing artifacts (item mappings, planning parameters) stay outside the lifecycle and why.

## Confirmed sound

- All 21 decisions have a rule (decision 14 in part, N14; decision 9 as a mechanism with no trigger configurable yet, flagged). INV-670 to INV-685, EC-156 to EC-166, the five work item kinds and the DS-04 codes are unique, and the blocks do not collide with the parallel drafts (INV up to 669, EC up to 155).
- Automation-allowed implies draft-only and excludes posting, master data, outbound, `human_only`, proposal-bound and the lifecycle verbs; configuration and automation commands are excluded, so no rule changes a rule. No scripts, expressions or SQL in any artifact (spec 16 holds).
- Depth counts automation actions only, and that is enough: consumer hops keep chain and depth, so at most three automation actions occur per chain however many consumers sit between; the same-target index and the depth checks hold in the database (probes P6, P8).
- No agent wakes an agent: `start_agent` is refused on events with an origin agent run, and ADR-0029 rule 12's intersection applies to drafts in an agent's chain.
- Notices on tainted subjects carry only the rule's literal text and typed condition fields, never untrusted text; the reading is flagged in open-questions.md.
- Hit policies `unique` and `monotone` with idempotent, commutative, associative aggregators are order-free; the pairwise overlap test is exact; the worked table example checks out step by step.
- Idempotency keys per rule version, event and action; one execution per version, event and mode; a replayed delivery cannot duplicate, and `effective_from` stops `ReplayEvents` from running new rules on old events.
- Approver is neither submitter nor drafter nor the drafting run's human; evidence rows, transitions, shadow outcomes and snapshots are immutable; labels append-only; the strict out-of-sample check and the held-out check hold in the database for declared windows.
- Stale evidence (content hash, engine version, baseline) blocks reuse of one bundle for two raises, because the baseline changes with the first.
- Safety caps on the three counterparty scores can only be lowered when declared with a non-null default; `show_min_score` and the act threshold stay separate, with act in the policy rule and off by default; no confidence field exists (ADR-0050 rule 35).
- No Vietnam-specific value in the core text; retention may only be lengthened by a package. Accepted ADRs are changed by dated notes only. No customer information.
- Composite keys on (company_id, id), pointers keyed to their own artifact, `company_id` NOT NULL on all fourteen tables.
