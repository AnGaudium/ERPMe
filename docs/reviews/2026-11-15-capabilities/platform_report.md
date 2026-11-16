# Platform and safety review (NativeFlows, ds-15-access @ 5536f9c)

Read-only; nothing was changed. The area is not clean: 2 Blocking, 17 Should-fix, 5 Nits. Line numbers are file lines under `docs/`.

Coverage: read in full were the rules of ADR-0008, 0009, 0013, 0017, 0029, 0038, 0042, 0043, 0050, 0054, 0055, spec 03, spec 17 and work-item-kinds.csv. ADR-0003, 0022, 0027, 0028, 0040, 0051, 0052, DS-04, DS-15 and the other catalogs were read only in the rules I needed or by grep. ADR-0004 and 0005 were only grepped for notes from 0050–0055. Of the lab, only `t10_agents.py` was grepped.

## Blocking

**1. The dispatcher has no single check order, and three orderings conflict.**
- Where: `adr/0008-…md:21` (rule 5), `:43` (rule 16); `adr/0042-…md:90`; `adr/0050-…md:211`, `:234`; `adr/0029-…md:55`; `adr/0054-…md:248`; `adr/0055-…md:88`.
- Each later ADR places its check relative to one neighbour only ("before policy", "first after its idempotency record", "before the command runs").
- (a) Replay: ADR-0008 rule 5 runs the checks before an idempotent replay. If stage eligibility (0055 rule 7, condition 6) is one of those checks, a replayed `Approve` returns `approval_already_given`, not the stored response. The same applies to the 0054 rule 19 pair check and to the claim check.
- (b) `proposal_required`: ADR-0029 says agent types need no permission on target commands, and `catalogs/edge-cases.csv:57` (EC-56) expects `proposal_required`. With permission first the agent gets `permission_denied`; with the tool list first (the order in lab `t10_agents.py:116-117`) it gets `tool_not_allowed`. EC-56 is unreachable for agent runs.
- (c) Simulating `human_only`: ADR-0008 rule 2 (`:18`) and ADR-0017 rule 14 (`:61`) let agents simulate `human_only` commands. ADR-0050 rules 29–30 keep them off every tool list and reject per call, so the simulation can never happen.
- (d) Claim check in simulate mode: it is placed "after the idempotency record", but simulations write none.
- Fix: one ordered list, as a note on ADR-0008 rule 5 and a section in DS-04:
  1. Credential and actor context.
  2. Run gates that need no subject state: `tool_not_allowed`, then `tainted_run_not_allowed`, then the tainted reference scope.
  3. `human_only` and `proposal_required`, by actor kind and origin run.
  4. Permission, including the `direct_master_data_change` deny.
  5. Record visibility: company, record scope, owner scope.
  6. Idempotency replay lookup, which returns the stored response with no further checks; otherwise the insert.
  7. Work item claim (skipped for shadow runs, same position in simulate mode).
  8. State-dependent authorization: ADR-0017 rule 16, 0054 rule 19, 0055 rule 7.
  9. Policy point and floors (inside the handler for `is_policy_in_handler`).
  10. Handler, audit, events.
- Also strike "agents may simulate them" for runs under a tool list, and change EC-56 to expect `tool_not_allowed` for an agent run and `proposal_required` for a consumer command with an origin run.
- Carrier: ADR-0008 rule 5, with one-line notes on ADR-0017 rule 14, ADR-0029 rule 4, ADR-0042 rule 9 and ADR-0050 rule 29.

**2. E-invoice completion `Post` by `system` is refused by ADR-0043's floors.**
- Where: `adr/0028-…md:74-76` against `adr/0043-…md:105-107`, `:114`, and `adr/0009-…md:102`.
- ADR-0028 rule 7.3 has a consumer run `Post<Type>` as `system` after `EInvoiceAccepted`, with "policy not asked again".
- ADR-0043 rule 9 checks floors 3–6 on every `Post`. Floor 5 gives `human_post` to a system posting of a document with an agent-written version. Floor 6 gives it to corrections by a non-human.
- A `Post` by another actor kind than the decision's is also a new policy point, with baseline `human_post`.
- `Post<CorrectionType>` is also registered `human_only`.
- Result: every e-invoiced credit note, debit note or sales return, and every agent-drafted e-invoiced invoice, ends in a held delivery and `Complete<Type>Posting`.
- The completion is not in rule 5's `is_consequence_posting` list.
- Fix: register the completion `Post` from `issuing` as `is_consequence_posting`, evaluated as the issuer. Floors 3–6 and the actor-kind point are applied at `Issue` and not repeated at completion. Name it as an ADR that lets `system` run a `human_only` command (ADR-0027 rule 12).
- Carrier: ADR-0043 rules 5 and 9; a pointer on ADR-0028 rule 7.

## Should-fix

**3. Owner rule `run_on_behalf_of` is undefined.**
- Where: `catalogs/work-item-kinds.csv:23`, `:29`; `adr/0042-…md:61-74`.
- For `agent_run_stopped` the subject is the agent type, so "the run" is ambiguous. ADR-0050 rule 55 (`:384`) says "the human of the first run raising it".
- Fix: add the kind rule `run_on_behalf_of` = `agent_run.on_behalf_of_id` of the subject run, or of the raising run when the subject is not a run; it is kept on re-raise.
- Carrier: ADR-0042 rule 7.

**4. `owner_role` storage and the time of resolution are unspecified.**
- Where: `adr/0042-…md:34-35`, `:56`, `:72-74`; `adr/0054-…md:160`.
- ADR-0042 rule 5 says the calling module computes the owner and applies the fallback. ADR-0054 says `role:<template>` and `company_owner` resolve through `role.template_code`, and that `work` never reads assignments.
- Layer-2 callers (`outbox`, `documents`, `policy`) cannot ask "does any active role have this template" without a new import.
- A company may have several roles with one template code.
- `warehouse_role` and the fallback text "the `owner` role" are not covered by the note.
- Fix: `work_item.owner_role` stores the symbolic rule (template code or `company_owner`) plus scope dimensions. Holders and the "no active role, so `company_owner`" fallback are resolved at read time by the registered visibility function. Only user-kind fallbacks are applied at raise. `warehouse_role` becomes template `warehouse_keeper`.
- Carrier: ADR-0042 rules 2, 5, 7.

**5. `document_owner` and `issuer` are ambiguous after ADR-0054 rule 14.**
- Where: `adr/0042-…md:66`; `adr/0054-…md:184-195`; `catalogs/work-item-kinds.csv:17`, `:35`.
- A document now has `owner_employee_id` (salesperson or buyer) and `created_by_user_id`. `document_owner` says "the human who created the document".
- It is also used on non-document subjects: `attachment` and `import_row`.
- Fix: `document_owner` = `created_by_user_id` (or the owner employee's user: choose one). Use `subject_owner` with a named column for `attachment_rejected` (uploader) and `import_duplicate_suspected` (batch creator).
- Carrier: ADR-0042 rule 7.

**6. `subject_owner` and `subject_assignee` do not say which column.**
- Where: `adr/0042-…md:72` (appended to the Fallback bullet, not the kind-rule list).
- Fix: kind registration names the subject's owner column; move both into the kind-rule list.
- Carrier: ADR-0042 rules 1, 7.

**7. Agent work item open keys collide across agent types.**
- Where: `adr/0050-…md:194`, `:384`; `catalogs/work-item-kinds.csv:29-30`; unique index in `adr/0042-…md:49` on (company, kind, open_key).
- `agent_budget_exhausted` is "per company, agent type and date", but its key is the business date only.
- `agent_run_stopped` has key `<outcome>:<date>`.
- A second agent type on the same day merges into the first type's item, with the first type's subject and owner.
- Fix: keys `<agent_type>:<date>` and `<agent_type>:<outcome>:<date>`, with a separate key for the company-wide cap.
- Carrier: ADR-0050 rule 55.

**8. The wake-up consumer's `on_behalf_of` contradicts ADR-0013 rule 9.**
- Where: `adr/0013-…md:28`; `adr/0050-…md:118-119`.
- Rule 9: consumer commands act for the event's human (for an inbound mail, the mailbox owner, per ADR-0052 rule 12).
- ADR-0050 rule 15: `StartAgentRun` from a wake-up acts for `workflow_owner_id`, and cites rule 9.
- Fix: note on rule 9 that `agent_wake_up` acts for the agent type setting's `workflow_owner_id`.
- Carrier: ADR-0013 rule 9.

**9. System-only commands are reachable by people.**
- Where: `adr/0054-…md:106`; `adr/0050-…md:140`.
- "Declare `full` on their leaf, so no ordinary role holds them" does not hold: `owner` has `full` everywhere, and `chief_accountant` and `it_administrator` have `full` on whole areas.
- Over REST they can run `CompleteAgentRun` (forge an outcome), `Record<Type>EInvoiceOutcome` ("always succeeds", then posts), `RecordInboundMessage`, `RecordOutboundMessageOutcome`, `RecordRenderOutcome`, `RunApprovalEscalation`.
- Fix: a registry attribute `is_internal_only`, refused on REST and MCP for every actor and outside the level expansion.
- Carrier: ADR-0008 rule 1; ADR-0054 rule 8.

**10. Agent commands have no declared registry attributes or leaf, and several platform commands have no leaf at all.**
- Where: `adr/0050-…md:109`, `:115`, `:153`; `catalogs/authorization-areas.csv:109`; `adr/0054-…md:94`.
- `StartAgentRun`, `CancelAgentRun`, `UpdateAgentTypeSetting` and `CreateAgentPromotionEvidence` have no stated `human_only`, minimum level or leaf. Leaf `agent` lists module `agent_runs`, but the commands are in `agents`.
- By verb, `edit` on `agent` gives every `start_agent:*` and `UpdateAgentTypeSetting`, including `workflow_owner_id`: whoever may start an agent can choose whose rights event runs use.
- `CancelAgentRun` "or the company's owner" is a role-identity test, the kind ADR-0054 removed elsewhere.
- No leaf is named for `ClearTaint`, `ConfirmAutoPost`, `RetryEventDelivery`, `SkipEventDelivery`, `ReplayEvents`, `CreateAttachment`, `CreateListExport`, `GetApprovalProgress`, `ListPolicyDecision` (zero hits in the areas catalog). ADR-0054 rule 7 says CI fails on a permission without a leaf.
- Fix: a table of these commands with leaf, minimum level and flags. `UpdateAgentTypeSetting` at `full`, and the new `workflow_owner_id` must hold `start_agent:<type>`. Add a leaf for delivery operations.
- Carrier: ADR-0054 rule 24; ADR-0050 rule 14.

**11. Agent type field classes and record scope are not declared.**
- Where: `adr/0017-…md:50`; `adr/0050-…md:96`, `:241`; `adr/0054-…md:214`.
- The intersection covers field classes and record scope, but an `agent_type_version` declares only permissions, and agent types get no assignments.
- ADR-0054 rule 16 also equates "declared permissions" with "the fixed tool list", while ADR-0050 treats them as two limits.
- Unless declared, the run inherits the human's `cost` and `margin`; the workflow owner is in practice the owner (finding 12).
- Fix: `agent_type_version` declares `field_classes` (default none) and no record scope. State whether declared permissions equal the tool list.
- Carrier: ADR-0050 rule 12.

**12. Only `owner` and `it_administrator` hold `start_agent` in the templates. (author)**
- Where: `catalogs/role-template-levels.csv:10`, `:34`, `:70`, `:202`; `adr/0054-…md:109`.
- Only `owner` and `it_administrator` reach `edit` on `agent`, so `workflow_owner_id` is effectively the owner.
- The hard floor then bars the owner from approving any agent draft, although the owner is a member of both seeded stages.
- A rank-20 agent draft needs an accountant plus a separate chief accountant, even in small-company mode.
- No sales or accounting role can start a run.
- Fix: decide which templates get `edit` on `agent` and name the recommended workflow owner per agent type.
- Carrier: ADR-0054 rule 11.

**13. Agent drafts may be unreachable to the people meant to handle them.**
- Where: `adr/0054-…md:185-186`; `adr/0051-…md:127`.
- A draft's `created_by_user_id` is the workflow owner.
- `owner_employee_id` comes from `salesperson_id` or `buyer_id`, which no workflow rule sets (no hit in 0050–0052).
- `sales_clerk` and `buyer` have owner scope own/own, so they cannot read or submit the draft linked to their own work item.
- Related: ADR-0042 rule 10 (`:95`) checks item ownership "on the human the run acts for". A workflow owner who does not hold the item's owner role cannot have the run claim it without `list_all_work_items`.
- Fix: workflows set the owner field from the partner's salesperson or buyer; or the person holding the origin work item's claim gets read and edit on its linked drafts. A wake-up claim checks the kind declaration, not ownership.
- Carrier: ADR-0054 rule 14; ADR-0042 rule 10.

**14. Owner scope is missing from the query layer.**
- Where: `adr/0050-…md:306`, `:315`, `:323-341`.
- ADR-0054 rule 15 says the views apply owner scope. Rule 48's session settings, rule 45's scope columns and rule 51's views carry none (`owner_employee_id`, `created_by_user_id`, the organization set).
- Aggregate views (`system_account_turnover`, `forecast_accuracy`, `stock_overview` value) are not marked `is_owner_scoped: false`.
- Only rule 31 got a note.
- Fix: notes on rules 45, 48, 51.
- Carrier: ADR-0050.

**15. Denial records and the denial count miss the new permission codes.**
- Where: `adr/0038-…md:49`, `:61`; `adr/0050-…md:249`.
- Not listed: `approver_not_eligible`, `approver_is_submitter`, `grant_exceeds_own_rights`, `segregation_conflict`, `organization_self_change`, `llm_routing_refused`, `work_item_claim_lost`.
- ADR-0055 rule 17 implies `Approve` refusals do write denials.
- Fix: enumerate which codes write denial records and which count toward the three-denial stop.
- Carrier: ADR-0038 rule 5.

**16. A tainted run's draft-only limit has no audit trace or invariant; consumer limits on tainted events have no mechanism.**
- Where: `adr/0038-…md:32`; `adr/0050-…md:210-211`; `adr/0013-…md:30`.
- `audit_record` stores `is_human_only` and `is_proposal_bound` as registered, but not `is_draft_only`. No invariant in `invariants.csv` says an audited command of a tainted run was `is_draft_only`.
- ADR-0013 rule 11 ("only drafts and work items") names no dispatcher check; INV-85 covers origin runs, not taint.
- Fix: add the column and an invariant. Enforce rule 11 with `is_draft_only` for consumer commands on tainted events, exempting `CompleteAgentRun`.
- Carrier: ADR-0038 rule 2; ADR-0050 rule 55; ADR-0013 rule 11.

**17. `UpdateAgentTypeSetting` gating does not fit the dispatcher rule.**
- Where: `adr/0050-…md:109`; `adr/0029-…md:55`.
- `proposal_required` here depends on the payload (setting `assisted`) and applies to people. ADR-0029 rule 4's dispatcher check keys on the actor.
- The handler has no stated way to know it runs inside a proposal execution.
- `approver_is_submitter` needs the submitter, which the document-actors function (0054 rule 2) does not return.
- Fix: the executing consumer passes a `change_proposal_execution` context; the handler raises `proposal_required` without it. Add the submitter to document actors.
- Carrier: ADR-0029 rule 4; ADR-0054 rule 2.

**18. Small-company mode against the bank-account rule. (author)**
- Where: `adr/0054-…md:256-257`; `adr/0029-…md:56`.
- The mode lifts the writer exclusion for people. ADR-0029 rule 4 says a bank account proposal is "approved by a human who wrote no version of it".
- Not stated which wins; open question line 38 touches it.
- Proposed: the bank-account rule is not lifted.
- Carrier: ADR-0054 rule 20.

**19. Policy points left unclear by ADR-0055 and 0053.**
- Where: `adr/0029-…md:75-79`; `adr/0055-…md:104-107`.
- (a) `Issue` is listed as an unconditional policy point, but ADR-0053 rule 8 allows `Issue` from `approved`, where ADR-0055 rule 11 re-evaluates only on a changed hash.
- (b) A round "ends with `Post` or `Issue`", so for non-posting types (orders, change proposals, unlock requests) it never ends, and INV-82 reads "the round the `Post` ended".
- (c) It is unstated whether a consumer on an agent chain may `Submit` a document; ADR-0029 rule 3's note covers proposals only.
- Fix: `Issue` from `draft` always evaluates, from `approved` only on a hash or actor-kind change. A non-posting round ends at final approval. Refuse `Submit` from any actor with an origin run.
- Carrier: ADR-0029 rule 6; ADR-0055 rule 8.

## Nits

**20.** Stale text without a note: `adr/0029-…md:46` ("whether a human may approve a proposal they wrote stays open") and `adr/0050-…md:109` ("the interim, which otherwise lets a person approve their own document"). Both are superseded by ADR-0055 rule 7, condition 5. Carrier: ADR-0029 rule 3; ADR-0050 rule 14.

**21.** `design/DS-04-command-envelope.md:358` still lists `policy_no_eligible_approver` with no word on whether `CreatePolicyRule` still returns it. Carrier: ADR-0043 rule 13.

**22.** `catalogs/work-item-kinds.csv:28`: `bank_line_unmatched` has resolution `person` with a `resolution_command` and `is_agent_resolvable` true. ADR-0042 rule 1 pairs a command with resolution `command`, and resolve commands are on no tool list. Carrier: ADR-0042 rule 1.

**23.** `adr/0022-…md:55` lists `work` twice in layer 2. `adr/0013-…md:21` (rule 6) omits queue `agents`, which is only in rule 13.

**24.** Corrections posted by non-humans are blocked three ways (registry `human_only` at `adr/0009-…md:102`, floor 6, tool list) with different reach for `system` and `integration`; keep one as the rule. "Per installation and day" (`adr/0050-…md:184`) does not say which day.

## Queued findings

**Q1 (local models): not a live contradiction in the ADRs.**
- ADR-0044's local-model sentence is at `:145` (not 139) and already has the note at `:149`.
- ADR-0050 rules 3, 5, 9 and ADR-0051 `:212` agree with "designed, not enabled; strip when the switch is on". Open question line 39 covers the decision.
- What remains is inside spec 17 (author): `:15` (fallback to a local model), `:27` (local embedding model), `:37-41` and `:50` ("seats listing a local model apply when the switch is on") read as Phase 1 beside `:24`.
- Proposed wording: mark those lines "(After Phase 1)".

**Q2 (owner rules): real.**
- `run_on_behalf_of` is missing: finding 3.
- `subject_owner` and `subject_assignee` are present in rule 7 but misplaced and under-specified: finding 6.
- `role:<template>` resolution has a storage and timing gap: finding 4.
- `document_owner` is ambiguous: finding 5.
- No `role:sales` or `approver_role` is left in the catalog; ADR-0019, 0051 and 0052 carry the rename notes.

**Q3 (check order): real.**
- No ordered list exists.
- No hard circularity: no check needs the output of a later one.
- There are three order conflicts (replay against state-dependent eligibility; `proposal_required` against permission and tool list; `human_only` simulation against the tool list) and one unplaced check (the claim in simulate mode).
- Proposed order: finding 1.
