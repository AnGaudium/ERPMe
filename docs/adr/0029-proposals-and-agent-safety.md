# ADR-0029: Change proposals and agent safety

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-47 (new). Related decisions: D2, D12. Principles 2, 3, 4, 12. ADR-0004, ADR-0005, ADR-0008, ADR-0009, ADR-0012, ADR-0013, ADR-0017, ADR-0019, ADR-0022, ADR-0023, ADR-0024, ADR-0027, ADR-0028; spec 03, 07, 14, 17. Assessment findings A-2/F3, A-3, F4, F6/X-1, F15/C-5, F16 ([design assessment 1](../reviews/2026-11-14-design-assessment/README.md)).

## Decision

Agents propose; people or policy approve. Today the design enforces this only for documents. This ADR closes the remaining gaps before the first agent (after step 4):

1. **Change proposals.** Changes that are not documents go through one carrier, a `change_proposal` document: master data, mappings, bank accounts, planning parameters, price lists, forecast adjustments.
   - **Server-side content.** The server computes the content: the exact commands, a before-and-after diff, the target's expected version, and the plan.
   - **Document lifecycle.** The proposal uses the existing document states, policy, approval and segregation of duties.
   - **Execution.** A consumer executes it after a human approval.
   - **Agents never run such commands directly**, and agent types need no permission on them.
2. **One policy hook** at a fixed set of policy points. Each decision records its rule, whether it allowed action without a human, and whether a confirmation is required. The table, defaults and floors (including change proposals always needing approval): [ADR-0043](0043-policy-and-approval.md) rules 7–12.
3. **Taint on data.** Taint is an immutable property of each document version, inherited by the versions and documents derived from it. A human can clear it explicitly in an immutable clearance record (interim, flagged). Fields from outside content are marked `is_untrusted`, and a run that is given such data becomes tainted.
4. **Consumers.** Consumers acting on an agent's events are limited to the same intersection of rights that limits the agent.
5. **Auto-post.** An auto-post is a posting by a system job allowed by a policy rule that requires confirmation. The rule's owner confirms it in an immutable record before the period is locked.

The hard floor on what a tainted run may read stays the literal spec 03 rule 1 until the author decides (open question).

### Rules

**Change proposals**

1. `change_proposal` is a non-posting document type owned by `documents` (layer 2).
   - **Content.** It holds `items`: an ADR-0008 rule 20 batch, so a single change is a one-item list. Each item records:
     - its command type, schema version and payload;
     - the target record and its expected version: `expected_version`, the SHA-256 of the record's canonical JSON (ADR-0008 rule 12 forms), absent when the command creates the record;
     - the before-and-after values per field.

     The proposal also holds the simulated plan of the whole batch with its `plan_hash`, evidence references (attachments, interactions, derivation traces, the agent run), the reason and a `document_date`.
   - **Commands.** `CreateChangeProposal` and `UpdateChangeProposal` compute diff, expected versions and plan on the server; the caller never supplies them.
   - **Permissions.** The proposer needs the permission `CreateChangeProposal`. The human the proposer acts for, or the proposer when human, must hold each target command's permission (ADR-0017 rule 13).

   Note: a change proposal may not target `employee_profile.department_id`, `manager_partner_id` or `user_account_id`; it is refused with `employee_organization_command_required` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 6).

   Note (catalog review, 2026-11-15): "ADR-0029 rule N" citations refer to this Rules section, not to the numbered summary under Decision.
2. Allowed targets:
   - commands whose `effect_class` (ADR-0027 rule 17) is `master_data_change`;
   - commands registered `is_proposal_bound` (a new registry attribute, ADR-0008 rule 1).

   Never allowed: `human_only` commands, commands of effect class `posting` or `outbound_send`, and change-proposal commands.

   Every allowed-target command takes an optional `expected_version`. A caller that gives it gets `target_changed` when the record's current hash differs; the executing consumer always gives it. DS-20 builds this into the master data commands at step 2, and the owner of each `is_proposal_bound` command builds it into that command.
3. Lifecycle, with ADR-0009's non-posting states and rule 22 events:
   - **Approval.** `draft → pending_approval` by `Submit` (a policy point). `Approve` or `Reject` by a human. `Reject` returns the proposal to `draft`, and `Cancel` ends it.
   - **Who may approve.** The approver must hold the target permissions and every field class the proposal changes (ADR-0017 rule 10), and sees the plan filtered by their field classes. The human for whom the originating run acted cannot approve (`segregation_of_duties`, ADR-0017 rule 16, which scans every version). Whether a human may approve a proposal they wrote stays ADR-0017 rule 17's open question.
   - **Execution.** A transactional consumer of `ChangeProposalApproved` executes the items as one command batch (ADR-0008 rule 20). It runs as actor `system`, on behalf of the approving human, with key `<consumer>:<event id>:1`, the stored `plan_hash` as `expected_plan_hash` (an exception to ADR-0013 rule 9, which otherwise runs internal calls without one), and each item's `expected_version`. The batch runs inside a savepoint of the delivery transaction.
   - **Success.** The consumer writes an immutable `change_proposal_execution` row (proposal version, audit row of each item, `executed_at`), and runs `CloseChangeProposal`, which moves the proposal to `closed`. The audit record IDs come from the dispatch result ([ADR-0038](0038-audit-and-observability.md) rule 1).
   - **Failure.** A retryable error (`concurrent_update`, `timeout`) rolls back the delivery and is retried (ADR-0013 rule 8). On any non-retryable error, such as `plan_hash_mismatch` or `target_changed`, the consumer rolls back to the savepoint and runs `UpdateChangeProposal` as `system`, which commits with the delivery. That writes the next version with the error and the new plan, voids the approval (ADR-0009 rule 9), returns the proposal to `draft`, and creates a work item.
   - **Expiry.** A system job cancels proposals that are not approved within `change_proposal_ttl_days`, with reason `expired` (company setting, interim default 14).
   - **Query.** `ListChangeProposal`.

   Agents and the consumers acting on their chains create proposals as drafts only; a person submits them, and a person other than the human the run acted for approves them ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 30; [ADR-0051](0051-agent-workflows.md) rules 13, 19, 22, 25).

   Note: "whether a human may approve a proposal they wrote" is answered by [ADR-0055](0055-approval-pools-and-stages.md) rule 7, condition 5: no writer of any version approves. The small-company mode lifts that for humans, but never rule 4's bank-account rule ([ADR-0054](0054-users-roles-and-authorizations.md) rule 20 note).

   Note: with approval stages, the approving human is the approver whose approval completed the plan ([ADR-0055](0055-approval-pools-and-stages.md) rule 16 note).

   Note ([ADR-0062](0062-product-engineering-workflow.md), proposed 2026-11-15): a draft structure may refer to a proposal item by its stable `change_proposal_item.id`. Reordering items keeps their IDs; an update that would remove or replace a referenced item is refused (`proposal_item_referenced`). Consumers read each executed item's result from its audit record (`change_proposal_execution_item.audit_record_id`) ([ADR-0062](0062-product-engineering-workflow.md) rule 14).
4. Agent calls: Policy may make people propose too, through a deny-only `direct_master_data_change` rule ([ADR-0043](0043-policy-and-approval.md) rule 12).
   - **Scope.** The dispatcher rejects an allowed-target command with `proposal_required` when it comes from an agent actor, or from any actor carrying an `origin_agent_run_id`. The executing consumer carries none, because the human `Approve` reset the origin (ADR-0013 rule 2). This applies in both simulate and execute mode. The error's fix names `CreateChangeProposal`.
   - **Humans.** A human with the permission may run such a command directly, unless policy (DS-28) requires a proposal for humans too.
   - **Bank accounts.** Interim, flagged: a change of a partner's bank account always goes through a proposal, also when a human starts it, approved by a human who wrote no version of it.
   - **Imports.** Human-run DS-21 import batches are outside the carrier.

   A person's direct `UpdateAgentTypeSetting` that sets `assisted` returns `proposal_required`: promotion of an agent type always goes through a proposal ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 14).

   Note: the sentence on this rule's first line after "Agent calls:" ("Policy may make people propose too, ...") is a later note spliced into the heading; it is not part of the lead-in to the list below and reads as a note at the rule's end. The accepted text stays where it is.

   Note: `proposal_required` is step 3 of the dispatcher's check order, after the tool list and before permission ([DS-04](../design/DS-04-command-envelope.md#dispatcher-check-order)). An agent run never reaches it, because allowed-target commands are on no tool list ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 29 note), so its direct call gets `tool_not_allowed`; a consumer command carrying an origin run gets `proposal_required` whatever its permissions (EC-56). A requirement that depends on the payload, such as `UpdateAgentTypeSetting` setting `assisted`, is the handler's: the consumer executing an approved proposal passes `change_proposal_execution` (the proposal's ID and version) in the handler context, and the handler returns `proposal_required` without it, for people too ([DS-04](../design/DS-04-command-envelope.md) handler context; [ADR-0054](0054-users-roles-and-authorizations.md) rule 2 note).
5. These rules use the carrier:
   - `partner_item` mappings (ADR-0019 rule 6);
   - tax ID differences (ADR-0019 rule 18);
   - planning parameters, lead times and forecast adjustments (ADR-0024 rules 1, 12, 23);
   - price lists (DS-20);
   - putaway rules, pick-face levels and count plans (ADR-0023 rule 21);
   - agent changes to planned orders: `UpdatePlannedOrder`, `FirmPlannedOrder`, `ConvertPlannedOrder` ([ADR-0036](0036-multi-level-mrp.md) rule 12);
   - technical completion and reopening of production orders ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 17);
   - releases of bills of materials and routings, production versions, work centers and production settings ([ADR-0033](0033-production-master-data.md) rule 2).
   - CRM: new partners and contacts from e-mail with their domains, matches, interactions and follow-up tasks, summaries, complaints and processing bases ([ADR-0052](0052-minimal-crm.md) rules 10, 16, 19, 20, 23, 31).

   Also the promotion of an agent type to assisted mode (`UpdateAgentTypeSetting`, with a frozen evidence snapshot); its approver must differ from its submitter (`approver_is_submitter`) ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 14).

   Note: for price lists the carrier binds agents and chains carrying an origin agent run (rule 4). A person with the permission runs `SetPriceListEntries` and the other price-list commands directly, unless the company adds a `direct_master_data_change` deny rule for them ([ADR-0043](0043-policy-and-approval.md) rule 12); the core seeds only the bank-account rule ([ADR-0043](0043-policy-and-approval.md) rule 15). Dual control on prices is an open question for the author.

   Note ([ADR-0058](0058-configurable-workflows.md), proposed 2026-11-15): also the activation and promotion of configuration and decision artifacts: `SetArtifactVersionState` raising a version, with frozen evidence; and the owner change of an automation rule with a version in force. The approver is neither the submitter (`approver_is_submitter`) nor the version's drafter nor the human the drafting run acted for (rules 9, 24; [ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md) rule 13).

**Policy hook**

6. The dispatcher evaluates policy (DS-28) once per command at these policy points, and the handler stores the `policy_decision`: Also a policy point: `Post` of an approved document by an actor of another kind than its decision's ([ADR-0043](0043-policy-and-approval.md) rule 9).
   - `Submit` of any document, including change proposals;
   - `Post` from `draft`;
   - `Issue` (ADR-0028 rule 7);
   - `Post` of an approved document, only when its `policy_input_hash` changed (ADR-0028 rule 14).

   This replaces ADR-0008 rule 5's "before a handler that posts" and ADR-0009 rule 11's separate statement. A replayed command (ADR-0008 rule 18) does not evaluate policy again. A handler whose policy inputs are read under locks calls the hook through `context.evaluate_policy(input)` after taking them, e.g. the credit check; such commands are registered `is_policy_in_handler`, and the dispatcher skips its own evaluation and asserts that the hook ran exactly once ([ADR-0030](0030-commercial-seams-and-imports.md) rule 7).

   Note: the sentence on this rule's first line after the colon ("Also a policy point: ...") is a later note spliced into the lead-in; the list below completes the lead-in, and that sentence adds one more policy point. The accepted text stays where it is.

   Note: `Issue` from `draft` is always a policy point; `Issue` from `approved` ([ADR-0053](0053-core-neutrality.md) rule 8) is one only when its `policy_input_hash` changed or its actor kind differs from the decision's, like `Post` of an approved document ([ADR-0055](0055-approval-pools-and-stages.md) rule 11). `Submit` from any actor carrying an origin agent run is refused before policy with `origin_run_submit_not_allowed` (step 3, [DS-04](../design/DS-04-command-envelope.md#dispatcher-check-order)): rule 3's note on proposals holds for every document.
7. A `policy_decision` records: It also stores `required_rank`, `human_post` and every matching rule with its version ([ADR-0043](0043-policy-and-approval.md) rules 7–8).
   - the outcome: `allowed`, `approval_required`, `human_only` or `denied`;
   - the `policy_rule_id`;
   - `is_confirmation_required`;
   - the required approval procedure and the `policy_input_hash` (ADR-0028 rule 14).

   `is_auto_allowed` is derived, not stored: outcome `allowed` with a non-human actor.

   Note: the sentence on this rule's first line after the colon ("It also stores ...") is a later note spliced into the lead-in; the list below completes the lead-in, and that sentence adds stored fields. The accepted text stays where it is.

**Taint on data**

8. Taint on versions:
   - **When a version is tainted.** `document_version.is_tainted` is set at insert and never changed. It is true when:
     - a run tainted at that time wrote the version, directly or as the origin of a consumer chain (ADR-0013 rules 9, 11); or
     - the version it derives from had effective taint (rule 9) when it was written. That is the previous version, the version in force for a change (ADR-0028 rule 4), or, for version 1, the source document version it was created from. `document_version.derived_from_version_id` (nullable) stores the last two, so the derivation is checkable.
   - **Clearing.** `ClearTaint` (`human_only`, reason required) writes an immutable `taint_clearance` row: `document_version_id`, human actor, reason, `cleared_at`. The human for whom the tainted run acted cannot clear it (`segregation_of_duties`). Clearing never changes field attributes or read-taint.
   - **Status of this rule.** Interim, flagged: it changes the untrusted-content mechanism (ADR-0005 item 7; open question).

   A version whose content copies a value from an `is_untrusted` field is written tainted, for example a matching-rule proposal built from a token an agent read in a bank description ([ADR-0051](0051-agent-workflows.md) rule 19).

   Note: a version written from source lines of other documents (a document created by copying, [ADR-0047](0047-commercial-documents-and-pricing.md) rule 2) is tainted when any source line's document version had effective taint when it was written, on `Create` and on every `Update` that adds source lines; `derived_from_version_id` names the first, and INV-88 also reads the others through the lines' typed references. Handlers of `inventory` and `production` that create documents from source lines set it the same way ([ADR-0023](0023-warehouse-management.md) rule 16).
9. Effective taint means `is_tainted` with no clearance on that version. A version written later by a tainted run is tainted again.
10. Run taint: Work items carry `is_tainted` as an OR over their raises ([ADR-0042](0042-work-queue.md) rule 5).
    - **`is_untrusted`.** A schema attribute separate from data labels (spec 17). It is set on fields filled from outside content: e-mail bodies, supplier e-invoice free text, bank statement texts and `interaction_summary` (ADR-0019 rule 20).
    - **When a run becomes tainted.** When the query layer (DS-33) returns to it any of: an `is_untrusted` field; a row of an effectively tainted version; a work item created from a tainted event; or an attachment from outside content.
    - **Views.** DS-33 views omit `is_untrusted` fields unless they are asked for, so listing documents does not taint a run.
    - **Master data.** Master data changed by an approved proposal is not tainted, because the human approval is the trust boundary.

    The dispatcher applies run taint to every query result returned to a run, and commits `agent_run.tainted_at` before it returns the data ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 25).

    Note: the sentence on this rule's first line after "Run taint:" ("Work items carry `is_tainted` ...") is a later note spliced into the heading; it reads as a note at the rule's end. The accepted text stays where it is.

    Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): value trust: an extraction field's normalized value is not untrusted when it fits its type's closed shape and passed every rule of the extraction's latest rule run from a deterministic reader, or a person confirmed it and its shape passed; its raw text and evidence are always untrusted; free text, URLs, e-mails, phones, codes and units that resolve to no record, vision values before confirmation, and every field of an extraction with a failed or mismatched signature or with suspected hidden text are untrusted. Trust is computed when the field is read, never stored on it, and means that the value carries no instruction, not that it is true. This is a reading of spec 03 rule 1, interim until the author answers ([ADR-0057](0057-document-intake-and-extraction.md) rule 17).
11. No policy decision for a non-human actor is `allowed` on an effectively tainted version or proposal. A tainted version is posted, sent or executed only by a human, or after a human approval. Whether a human may post a tainted draft without approval when policy requires none stays ADR-0017 rule 17's open question.

    Note: aligned with [ADR-0043](0043-policy-and-approval.md) rule 9, floor 3: on an effectively tainted version a non-human `Submit` gets at least the lowest-rank approval, and a non-human `Post` or `Issue` gets `human_post` even after an approval. "After a human approval" covers only what an approval lets proceed without a posting: change proposals executed by their consumer (rule 3) and documents with no posting step.

**Consumers**

12. A consumer command for an event with `origin_agent_run_id` (ADR-0013 rule 9) runs with the intersection of the consumer's registered permissions, the agent type's permissions and those of the human the run acted for. Such a consumer command never has effect class `posting` or `master_data_change`: it creates drafts, work items and change proposals only. A consumer that needs more drafts a document or a change proposal. ADR-0017 rule 13 is narrowed accordingly.
    - ADR-0013 rule 11 still caps tainted events.
    - A human command resets the origin (ADR-0013 rule 2). The executing consumer of a human approval is therefore not narrowed.

**Auto-post**

13. Definition and confirmation: Confirmation is by the owner on the rule's latest version, for `system` and `integration` postings ([ADR-0043](0043-policy-and-approval.md) rule 14).
    - **Definition.** An auto-post is a posting by actor `system` whose decision is `allowed` with `is_confirmation_required`, set by the policy rule that allowed it. An example is a deterministic bank match (spec 14).
    - **What is not an auto-post.** Close jobs (costing, FX revaluation, closing entries) are close tasks confirmed through the close (ADR-0012) and set no confirmation.
    - **Wording.** "Agent auto-post" in spec 03 rule 6 and ADR-0012 rule 13 means an auto-post as defined here, so its meaning is unchanged. Agents themselves only draft (ADR-0003 R8), and tainted runs never post (spec 03 rule 1).
    - **Confirmation.** `ConfirmAutoPost` takes a list and is run by the policy rule's owner. It writes immutable `auto_post_confirmation` rows: unique `policy_decision_id`, `confirmed_by_id`, `confirmed_at`.
    - **Close task.** The required close task (ADR-0012 rule 13) blocks `LockPostingPeriod` while any auto-post of the period is unconfirmed.
    - **Thresholds.** The thresholds are DS-28's and the author's.

    Note: the sentence on this rule's first line after "Definition and confirmation:" ("Confirmation is by the owner ...") is a later note spliced into the heading; it details the bullet **Confirmation.**. The accepted text stays where it is.

**Tainted read scope**

14. The only behavior is the literal spec 03 rule 1: a tainted run reads only records scoped to its related partner. No setting widens it, because spec 03 lets no policy, threshold or setting relax a hard floor.
    - **Recommendation to the author** (open question; ADR-0005 item 7): for quotations, also let such a run read the shared catalog, that partner's price list and available to promise, never other partners' records or `cost` and `margin` fields. Widening needs an ADR after the author decides.
    - **Outbound check.** The outgoing-message gate (ADR-0019 rule 17, module `crm`) rejects a customer draft that refers to another partner's records, or carries `cost` or `margin` fields, with `outbound_content_out_of_scope`. It only tightens, so it applies now.

    [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 27 reads the literal rule as: scope rows, the run's work item, the drafts it or an earlier run of the same item wrote, and reference data (flagged, open question). [ADR-0051](0051-agent-workflows.md) rule 10 gives the effects on the quotation and purchase invoice workflows; the same question is asked for purchase invoices.

    The outbound check also runs in draft plans through `GetOutboundContentCheck` ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 36). Runs on subjects that are outside content start tainted, and after taint no out-of-scope row may enter a prompt or a command input ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 15, 25). The CRM's outbound checks, and `tainted_read_out_of_scope` for its timeline and duplicate queries outside the scope partner: [ADR-0052](0052-minimal-crm.md) rules 16, 18, 28.

    Note: for a generated file the outbound check reads the attachment's `generated_kind`, `generated_audience` and `generated_subject_document_id`: only an external print of a document of the message's partner passes ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 29).

**Audit and checks**

15. Audit rows (ADR-0027 rule 8) also record `origin_agent_run_id`, `on_behalf_of_id` and `policy_decision_id`. Full columns: [ADR-0038](0038-audit-and-observability.md) rule 2.
16. Invariants:
    - **INV-84:** no policy decision with outcome `allowed` for a non-human actor concerns a document version (change proposals included) that was effectively tainted at the time of the decision.
    - **INV-85:** no audit row with actor `system` and an origin agent run has effect class `posting` or `master_data_change`. Outbound sends are covered by INV-80 and the automatic-send list (ADR-0019 rule 17). The intersection itself (rule 12) is a DS-16 hard-floor property test.
    - **INV-86:** no audit row of an allowed-target command (rule 2) has actor `agent` or an origin agent run.
    - **INV-87:** every posting by actor `system` whose decision has `is_confirmation_required`, in a locked period, has an `auto_post_confirmation` row.
    - **INV-88:** every version written by a run tainted at its `recorded_at`, or whose origin run was, or whose previous or `derived_from_version_id` version was effectively tainted when it was written, has `is_tainted` true. This needs `agent_run.tainted_at` from DS-32.

    Edge cases:
    - **EC-56:** an e-mail asks to change a bank account. The agent's direct attempt is rejected with `proposal_required`. A proposal approved by a second human succeeds.
    - **EC-57:** an injected instruction copied into a draft and edited by a human stays tainted. A run given that draft becomes tainted.
    - **EC-58:** auto-posts block the period lock until confirmed.

## Context

The assessment found six gaps:

- **A-2, F3:** approvals bound only to document versions, while agents propose master data, mappings and parameters.
- **A-3:** the policy call point was stated twice.
- **F4:** taint lived only on events, and a human edit laundered it.
- **F6, X-1:** auto-post was undefined.
- **F15, C-5:** a tainted run's read scope contradicted the quotation workflow.
- **F16:** consumers acted beyond the agent's rights.

All of this is technical design under ADR-0005, except three points flagged for the author: the read-scope hard floor, taint clearing and the bank account rule.

SAP practice, concepts only: change documents and dual control for sensitive fields. ERPMe uses one carrier that reuses the document machinery, so agents learn one way to propose anything.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One `change_proposal` with server-computed diff, expected versions and plan (chosen) | Reuses document states, policy, approval, SoD; binds what runs; agents need no target permissions | Execution is a separate, asynchronous step |
| A draft state on every master data table | Local | Every table needs versioning; no common approval |
| Immutable `is_tainted` plus a clearance record (chosen) | Respects ADR-0009 rule 14; checkable | Clearing is deliberate work |
| Taint on events only (old) | Simple | Laundered by any edit |
| Policy rule may widen consumer rights | Flexible | Policy decides approval, not rights; a confused deputy |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0008 rules 1 (`is_proposal_bound`) and 5 (the replaced sentence);
  - ADR-0009 rules 9 and 11;
  - ADR-0012 rule 13;
  - ADR-0013 rules 9 and 11;
  - ADR-0017 rule 13;
  - ADR-0019 rules 6, 17, 18 and 20;
  - ADR-0023 rule 21;
  - ADR-0024 rules 1, 12 and 23;
  - ADR-0027 rules 8 and 17.
- **DS-04:** errors `proposal_required`, `target_changed`, `outbound_content_out_of_scope`. The commands (`CreateChangeProposal`, `UpdateChangeProposal`, `CloseChangeProposal`, `ClearTaint`, `ConfirmAutoPost`) and the query `ListChangeProposal` are registered by `documents`.
- **Columns and tables:** `document_version.is_tainted` and `derived_from_version_id` (ADR-0009 rule 9 note); `taint_clearance`, `change_proposal_execution` and `auto_post_confirmation`, owned by `documents`, with their DDL written when that module is built.
- **DS-16:** INV-84 to INV-88; the consumer intersection hard-floor test.
- **DS-17:** EC-56 to EC-58; events `bank_account_change_requested` and `auto_post_confirmed`; log schema 0.3.0.
- **Other design items:**
  - DS-28: policy points, rules, auto-post thresholds, proposals for humans.
  - DS-32: `agent_run.tainted_at`, run taint.
  - DS-33: taint on read, views without untrusted fields.
  - DS-34: workflows draft proposals.
  - DS-20: `expected_version` on master data commands.
  - DS-22: handlers that create a document from another set `derived_from_version_id`.

## Revisit when

- Proposal volume needs approval by rule rather than one by one.
- The author settles the read scope, taint clearing or the bank account rule.

## Documents updated

- **ADRs:** [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md), [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0013-outbox-and-events.md](0013-outbox-and-events.md), [docs/adr/0017-permission-envelope.md](0017-permission-envelope.md), [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md): notes.
- **Design and catalogs:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv), [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md), on the tainted read scope, taint clearing, and bank account dual control including one-person companies.
- [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
