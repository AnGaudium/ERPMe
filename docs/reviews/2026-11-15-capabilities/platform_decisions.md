# Architect decisions on the platform/safety holistic review (report: platform_report.md)
"accept" = apply the reviewer's proposed fix as notes on the named carriers (all ADRs accepted: notes at rule ends only).

- 1 dispatcher check order: accept the reviewer's 10-step list as a note on ADR-0008 r5 and a new DS-04 section; replay lookup returns the stored response with no further checks; strike agent simulation of human_only for runs under a tool list (notes ADR-0008 r2, ADR-0017 r14); EC-56 expects tool_not_allowed for an agent run and proposal_required for a consumer command with an origin run; one-line notes on ADR-0029 r4, ADR-0042 r9, ADR-0050 r29.
- 2 e-invoice completion Post: accept. Registered is_consequence_posting, evaluated as the issuer; floors 3-6 and the actor-kind point apply at Issue, not repeated at completion (ADR-0043 r5, r9; pointer ADR-0028 r7; ADR-0027 r12 list).
- 3 run_on_behalf_of owner rule: accept (ADR-0042 r7).
- 4 owner_role storage and resolution timing: accept (symbolic rule stored; holders and company_owner fallback resolved at read time by the registered visibility function; warehouse_role -> template warehouse_keeper) (ADR-0042 r2, r5, r7).
- 5 document_owner = created_by_user_id; attachment_rejected and import_duplicate_suspected use subject_owner with named column (ADR-0042 r7; catalog rows).
- 6 subject_owner/subject_assignee: kind registration names the column; move into the kind-rule list via note (ADR-0042 r1, r7).
- 7 agent work item open keys include agent_type (ADR-0050 r55; catalog rows).
- 8 agent_wake_up acts for workflow_owner_id: note on ADR-0013 r9.
- 9 registry attribute is_internal_only, refused on REST and MCP for every actor, outside the level expansion; apply to CompleteAgentRun, Record*EInvoiceOutcome, RecordInboundMessage, RecordOutboundMessageOutcome, RecordRenderOutcome, RecordMailboxIntakeOutcome, RunApprovalEscalation and the other system-only Record/Run commands (ADR-0008 r1, ADR-0054 r8).
- 10 table of agent and platform commands with leaf, minimum level, flags: accept; UpdateAgentTypeSetting at full; new workflow_owner_id must hold start_agent:<type>; leaf for delivery operations (RetryEventDelivery etc.); leaves for ClearTaint, ConfirmAutoPost, CreateAttachment, CreateListExport, GetApprovalProgress, ListPolicyDecision; CancelAgentRun permission instead of role identity (ADR-0054 r24, ADR-0050 r14; authorization-areas.csv, role-template-levels.csv).
- 11 agent_type_version declares field_classes (default none) and no record scope; declared permissions ARE the tool list (one concept) (ADR-0050 r12; note ADR-0054 r16).
- 12 AUTHOR, with interim seed: start_agent edit for sales_manager (quotation, customer_onboarding), chief_accountant (bank_matching, purchase_invoice), production_planner (planning), owner (data_migration); recommended workflow owner per agent type the same; add open question (ADR-0054 r11, catalog).
- 13 workflows set owner_employee_id from the partner's salesperson or buyer; the holder of the origin work item's claim gets read and edit on its linked drafts; a wake-up claim checks the kind declaration, not ownership (ADR-0054 r14, ADR-0042 r10, ADR-0051 note).
- 14 owner scope in the query layer: notes on ADR-0050 r45, r48, r51; aggregates marked is_owner_scoped false.
- 15 enumerate denial codes and which count toward the three-denial stop (ADR-0038 r5, ADR-0050).
- 16 audit_record.is_draft_only column + invariant (next free INV in 210-219 block or agent block) that audited commands of tainted runs were is_draft_only; ADR-0013 r11 enforced with is_draft_only for consumer commands on tainted events, CompleteAgentRun exempt (ADR-0038 r2, ADR-0050 r55, ADR-0013 r11).
- 17 change_proposal_execution context passed by the executing consumer; handler raises proposal_required without it; document-actors function returns the submitter (ADR-0029 r4, ADR-0054 r2).
- 18 AUTHOR; interim: small-company mode does not lift the bank-account writer rule (ADR-0054 r20; open question).
- 19 Issue from draft always evaluates, from approved only on hash or actor-kind change; a non-posting round ends at final approval; refuse Submit from any actor with an origin run (ADR-0029 r6, ADR-0055 r8; INV-82 wording).
- Nits 20-24: accept (stale-text notes; policy_no_eligible_approver status; bank_line_unmatched resolution; ADR-0022 duplicate work, ADR-0013 r6 queue agents; one rule for non-human corrections; budget day = company business day).
- Q1: add open question proposing spec 17 lines 15, 27, 37-41, 50 be marked "(After Phase 1)" (author-owned spec, do not edit).
