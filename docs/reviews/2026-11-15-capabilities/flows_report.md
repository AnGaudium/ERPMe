# Flow-walk review of ERPMe (ds-15-access @ 5536f9c) — reviewer report

Read-only. I read ADR-0043, 0055, 0047, 0048, 0051, 0045, 0046, 0024, 0036, 0029 in full (decision and rules), ADR-0052 rules 1–29, and targeted rules of ADR-0009, 0019, 0028, 0030, 0034, 0041, 0050, 0054. I also read the catalogs, the DS-19 TT99 package files, spec 09 and 14, and the probe sim's README and trace.
Not read: ADR-0049 (printing), ADR-0023 and ADR-0020 in detail, DS-04. Claims that depend on them are marked "not checked".

File:line references are to `docs/` in the repo. Names in backticks are the docs' own; "[not named]" means I could not find a name.

---

## Part A — Findings

### Blocking

**A1. Flow 3 cannot run from a customer e-mail as the author describes it.**
- Where: `adr/0051-agent-workflows.md:81`, `:111`, `:121`, `:124`; `open-questions.md:36`.
- Problem: a `quotation` run on an inbound e-mail starts tainted. Tainted runs do not configure ("In tainted runs configurable lines are left unresolved with their hints in the note") and skip L5 `write_text`. So "customer e-mail → LLM proposal → `EvaluateConfiguration`" has no path. The only configuring path is a run a person starts on their own internal note (`is_untrusted` false).
- Knock-on: flow 1's onboarding e-mail, once matched by `MatchInteraction`, raises `inbound_message_matched` and wakes the same tainted run.
- Fix: either the author answers open-questions:36 and a new ADR widens the tainted scope (ADR-0029 rule 14 requires one), or a note on ADR-0051 rule 14 states the simulated path: a salesperson records a `note` interaction and starts the agent on it. The simulator must show one of the two and say which.

**A2. Flow 6's agent branch has no designed entry.**
- Where: `adr/0051-agent-workflows.md:153`; `catalogs/work-item-kinds.csv:33`; `design/backlog.md:77`.
- Problem: `e_invoice_record` is "DS-24's pending table name". The command by which "a person imports an XML file through the package's reader" is not named. The reader interface is not named (compare `BankStatementReader`). Nothing says which command raises `supplier_invoice_received`, or how the "person confirms its supplier on the record" step is recorded.
- Fix: a note on ADR-0051 rule 20 (or a short ADR for the DS-24 intake seam) naming the table columns the agent reads, the import command, the reader interface, and the raise.

### Should-fix

**A3. Sales invoice path (`Issue` or `Post`) is undetermined for `l10n_vn`.**
- Where: `adr/0028-document-lifecycle-hardening.md:58`; `design/DS-19-vietnam-tt99/settings.yaml:44` (only `documents.issuance_without_delay` exists).
- Problem: "whether an e-invoice is required … is the regime's setting (DS-24)", but the setting has no key and no seed. The two paths differ in command, states (`issuing`), posting actor (`system` on behalf of the issuer, or the human) and INV-46.
- Fix: a note on ADR-0053 rule 8 naming the setting per document type and seeding it in DS-19. State that the simulation uses the stub adapter of ADR-0028 rule 12.

**A4. No DDL exists for most tables the six flows write.**
- Where: `adr/0055-approval-pools-and-stages.md:234` ("those tables have no DDL draft yet"); `design/README.md`.
- Problem: only DS-06, DS-15, DS-20, DS-35 and DS-56 have DDL. Missing: `document`, `document_version`, `policy_decision`, `approval`, `work_item`, `change_proposal`, `change_proposal_execution`, every commercial header and line, `demand_supply_line`, material documents, `purchase_order_line_gr_ir_layer`, `money_account`, `bank_statement(_line)`, `planned_order*`, `replenishment_request`, `production_order*`, `agent_run`, `tax_line`, `document_line_tax`, `document_line_price_step`, `posting_intent`.
- Fix: before the simulation, add a "simulation schema" design file under the owners (ADR-0047, 0048, 0024, 0042, 0043 notes) with at least keys and state columns. Otherwise the rebuilt sim invents `sim_docs` again.

**A5. Seeded policy never sends a person's document to a pool.**
- Where: `adr/0043-policy-and-approval.md:153-164`, `:173`; `design/DS-17-synthetic-dataset.md:49-66`.
- Problem: the seed has three rules (credit exceeded, `is_match_exceeded`, `general_journal`). A human `Submit` of `purchase_request`, `purchase_order`, `quotation` or `production_order` gets no rank and goes straight to `approved`. Pools `pr`, `po`, `mo`, and `sales` for quotations, are unreachable without company rules. DS-17 has no setup event for users, role assignments, policy rules or pool members, though EC-112 needs a "senior" threshold.
- Fix: a note on ADR-0055 rule 2, plus DS-17 setup events (`policy_rule_created`, `approval_pool_updated`, `user_registered`) and the sample thresholds the dataset uses.

**A6. Seeded stage members contradict "a planner approves".**
- Where: `adr/0055-approval-pools-and-stages.md:75-78`, `:90`; `adr/0051-agent-workflows.md:188`; `catalogs/role-template-levels.csv` (`production_planner`, `buyer` and `purchasing_manager` rows); `open-questions.md:105`.
- Problem: stage eligibility needs membership AND `Approve<Type>`, and a change proposal's approver also needs the target permissions. `accountant` and `chief_accountant` have `planning,read`, so they cannot hold `ConvertPlannedOrder`. No planner template is a member, and `production_planner` has `can_approve` false everywhere. Under the seed only `owner` can approve a planning proposal. The same holds for price-list proposals (`SetPriceListEntries` needs `price_list,edit`).
- Fix: a note on ADR-0055 rule 5 stating who approves `change_proposal` per target area, or seeding `purchasing_manager` and `sales_manager` as `general` stage members; then correct ADR-0051 rule 25's wording.

**A7. Seeded role templates violate seeded segregation rules.**
- Where: `catalogs/segregation-rules.csv:5` and `:6`; `catalogs/role-template-levels.csv` (`sales_manager`, `accountant`, `chief_accountant`).
- Problem: `sales_manager` holds `price_list,edit` and `sales` approve (`price_list_vs_sales_approval`). `accountant` holds `partner,edit` and `purchase_invoice,post` (`partner_vs_purchase_invoice`). Every such assignment returns `segregation_conflict_found`, and under `block` the templates cannot be assigned.
- Fix: a note on ADR-0054 rule 17 or 11 — change the templates or the rules.

**A8. Flow 6 needs three finance users, which no doc states.**
- Where: `catalogs/segregation-rules.csv:4`; `adr/0055-approval-pools-and-stages.md:93`.
- Problem: `purchase_invoice_vs_payment` (relation `settled_item`, always on) bars both the poster and the approver of the invoice from `PostBankPayment`. A mismatched invoice needs poster A and approver B, so the payment needs a third person with `banking,post`. `cashier` has bank documents at read only.
- Fix: a note on ADR-0054 rule 19 with the minimum cast; DS-17 must seed it.

**A9. A bank line "matched" to a draft contradicts INV-95.**
- Where: `adr/0048-cash-bank-receivables-payables.md:132` against `:249`.
- Problem: cascade steps 2–4 "draft … and record the match", while INV-95 requires every matched line to refer to a posted document. `match_state` has only `unmatched`, `matched`, `ignored`.
- Fix: a note on ADR-0048 rule 9 — add a proposal column (`proposed_document_id`, score, `match_basis`) and set `matched` at `Post`.

**A10. Credit condition on quotations: two ADRs disagree.**
- Where: `adr/0051-agent-workflows.md:127` against `adr/0047-commercial-documents-and-pricing.md:226` and `:66`.
- Problem: ADR-0051 says quotation `Submit` has "discount, margin, below-cost and credit conditions". ADR-0047 gives `is_credit_exceeded` to sales orders only.
- Fix: a note on ADR-0047 rule 22.

**A11. Whether a quotation needs the `customer` role is nowhere decided.**
- Where: `adr/0052-minimal-crm.md:46` delegates it to DS-22; ADR-0047 rule 3 is silent; `adr/0051-agent-workflows.md:110` requires the role only for the agent.
- Fix: a note on ADR-0047 rule 3, with the error code.

**A12. `CreatePartner` payload and partner sub-commands are undefined.**
- Where: `adr/0051-agent-workflows.md:98` ("as its payload allows"); `adr/0019-partners-and-crm-foundation.md:13-21`.
- Problem: only `CreatePartner`, `UpdatePartner`, `CreateContact`, `UpdateContact`, `CreatePartnerEmailDomain`, `CreatePartnerItem` and (in the segregation catalog) `CreatePartnerBankAccount` are named. There is no command or payload section for roles, `customer_profile`, `supplier_profile` or addresses. What a null `credit_limit` means for `is_credit_exceeded` is not stated in ADR-0019, ADR-0030 rules 6–7 or ADR-0047 rule 18; DS-20:248 allows NULL.
- Fix: a note on ADR-0045 rule 1.

**A13. "The approving human" is ambiguous with stages.**
- Where: `adr/0029-proposals-and-agent-safety.md:46`.
- Problem: the executor runs "on behalf of the approving human". With rank 20 there are two approvers. That human becomes the "converter" and writer of the drafted purchase requests, and so is excluded from approving them.
- Fix: a note on ADR-0055 rule 16 — the approver whose approval completed the plan.

**A14. Forecast storage and adjustment commands are unnamed.**
- Where: `adr/0024-planning.md:110-121`, `:217`.
- Problem: `RunForecast`, `ListForecast` and "forecast adjustments" exist, but no table names for the forecast run, forecast lines, adjustments or pegging rows, and no command for an adjustment.
- Fix: a note on ADR-0024 rules 11–12 and 20.

**A15. "Approve → send" for a quotation is not enforced by anything I read.**
- Where: `adr/0052-minimal-crm.md:264-267`.
- Problem: `SendOutboundMessage` checks delivery, consent, scope and actor, not the state of the linked or attached quotation. Whether a draft or pending quotation can be printed with audience `external` is ADR-0049's (not checked).
- Fix: a note on ADR-0052 rule 28 or ADR-0049 rule 28 — an external print or link requires the source document `approved`.

**A16. Where a goods-line price difference lands is described in three places.**
- Where: `adr/0047-commercial-documents-and-pricing.md:210`; `design/DS-19-vietnam-tt99/regimes/tt99/account_determination.csv:4`; `adr/0030-commercial-seams-and-imports.md:26-27`.
- Problem: the simulator must infer the journal: the invoice debits `purchase_cost_clearing` (33882) for the difference, and a `landed_cost` (`cost_type` `price_difference`, written `posted` inside the invoice's transaction) moves it to 152 or splits it to consumers.
- Fix: a worked TT99 example as a note on ADR-0047 rule 21.

### Nit

**A17.** `spec/09-mvp-scope.md:8`, `:12`, `:15` still list the product configurator and MRP as "Later" and planning as "pending". ADR-0046, ADR-0032 and ADR-0036 put them in Phase 1. Spec 09 is author-owned; raise an open question with proposed wording.

**A18.** Stale names: `adr/0051-agent-workflows.md:109` and `:233` still say `inbound_message` and `role:sales`; `adr/0019-partners-and-crm-foundation.md:58` too. Notes cover them. The author's "purchase requisition" is `purchase_request` everywhere.

**A19.** `adr/0055-approval-pools-and-stages.md:37`: pool `mo` holds `production_issue` but not `production_receipt` or `operation_confirmation`, which fall to `general`. State that this is intended.

**A20.** `adr/0047-commercial-documents-and-pricing.md:99` says purchase request drafts are "on behalf of the converter". For an agent-proposed conversion this is the proposal's approver (see A13). Say so.

---

## Part B — Step tables

Conventions used in every table:
- **Policy.** "Seed: none" means a human gets outcome `allowed` under the seeded rules (A5).
- **Events.** Document events follow ADR-0009 rule 22 (`<Type>Created`, `…Submitted`, `…Approved`, `…Posted`); the form is inferred where I did not see the literal name.
- **Approval stages.** Seeded stages in every pool are `standard` (min_rank 10, k 1: `accountant`, `chief_accountant`, `owner`) and `senior` (min_rank 20, k 1: `chief_accountant`, `owner`). Writers of any version are excluded.
- **Accounts.** TT99 accounts are from `account_determination.csv`; all are `unverified`.

### Flow 1 — Customer and contact

| Step | Command (module; rule) | Actor / mode | Approval | Tables | Events → consumers | Work items | Postings | LLM role |
|---|---|---|---|---|---|---|---|---|
| 1a Person creates partner | `CreatePartner` (`master_data`; ADR-0019 r1–3, ADR-0045 r1); `master_data_change`, proposal-bound for agents | Person, direct | None, unless a `direct_master_data_change` deny rule exists (ADR-0043 r12) | `partner`, `partner_role`, `customer_profile`, `partner_address`, `partner_email_domain` (via `crm` hook) | `PartnerCreated` → `crm` duplicate-search consumer writes `partner_search_key` | `partner_duplicate_suspected` if a candidate is found | — | — |
| 1b Person creates contact | `CreateContact` (`master_data`; ADR-0052 r4) | Person | None | `contact` | `ContactCreated` → same `crm` consumer | as 1a | — | — |
| 2 E-mail intake | `CreateAttachment` + `RecordInboundMessage`, then `RecordMailboxIntakeOutcome` (`crm`; ADR-0052 r12–15) | Job `mailbox_intake`, `system` on behalf of the mailbox owner; not an agent run | — | `inbound_message`, `interaction` (`is_untrusted` true), `interaction_content`, `interaction_participant`, `interaction_match_candidate` | `InteractionCreated`, `MailboxIntakeCompleted` → `agent_wake_up` | `interaction_unmatched` (owner `role:sales_clerk`, `days:1`) | — | None. Deterministic: sender authentication (RFC 8601), matching reply → contact address → domain |
| 3 Agent run starts | `StartAgentRun` (`agents`; ADR-0050 r15) | `system` on behalf of `workflow_owner_id`; scope `subject`; starts tainted; mode `assisted` | — | `agent_run` | `AgentRunStarted` | item claimed by the run | — | — |
| 4 D1 / L1 / L2 | no command (ADR-0051 r12) | `customer_onboarding` agent | — | run step records | — | — | — | L1 `classify_message` → `intent`, `language`. L2 `extract_partner` → kind, names, tax ID, addresses, contacts, each with `source_span`. Code checks spans, package tax ID validation, normalization; code adds the sender as first contact and the domain |
| 5 D2 propose | `CreateChangeProposal` (`documents`; ADR-0029 r1), step `customer_onboarding.propose`; draft only | Agent; proposal-bound | — | `document`, `document_version` (`is_tainted`), `change_proposal` (items `CreatePartner` role customer + `CreateContact` × n; server-computed diff and plan) | `ChangeProposalCreated` | draft link and note on the item; duplicate check redacted to code and count | — | None |
| 6 Submit | `SubmitChangeProposal` | Person. Agents never submit (ADR-0050 r30) | Policy point `submit`; floor 7 → rank 10; pool `general`, stage `standard` | `policy_decision` (with `approval_plan`), `document.state` | `ChangeProposalSubmitted` | `approval_pending` (owner `approval_stage`) | — | — |
| 7 Approve | `ApproveChangeProposal` | Person: stage member with `ApproveChangeProposal` and `CreatePartner`/`CreateContact`; not a writer; not the workflow owner (`segregation_of_duties`) | Stage `standard`, k = 1 | `approval` | `ChangeProposalApproved` → executing consumer | `approval_pending` resolved | — | — |
| 8 Execute | batch `CreatePartner`, `CreateContact`, then `CloseChangeProposal` (ADR-0029 r3) | Consumer, `system` on behalf of the approver, `expected_plan_hash` | — | as 1a/1b, plus `change_proposal_execution` | `PartnerCreated`, `ContactCreated` → `crm` duplicate search | `partner_duplicate_suspected` possible; `change_proposal_failed` on error | — | — |
| 9 Confirm match | `MatchInteraction` (`crm`; ADR-0052 r10) | Person | — | `interaction` match columns | `InteractionMatched` | resolves `interaction_unmatched`; raises `inbound_message_matched` (wakes the quotation agent, tainted) | — | — |

### Flow 2 — Price list

| Step | Command | Actor / mode | Approval | Tables | Events | Work items | Postings | LLM role |
|---|---|---|---|---|---|---|---|---|
| 1 Create list | `CreatePriceList` (`master_data`; ADR-0045 r2, r7) | Person with `price_list,edit` (`sales_manager`, `purchasing_manager`) | None for people. Agent: change proposal → `general` / `standard`; under the seed only `owner` is eligible (A6) | `price_list` | [not named] | — | — | — |
| 2 Lines and validity | `SetPriceListEntries` (one change per list) | Same | Same | `price_list_entry` (`minimum_quantity`, `start_date`, `end_date`; exclusion constraint → `price_list_entry_overlap`) | `PriceListEntriesSet` (DS-17 `price_list_published`) | — | — | — |
| 3 Extras and rates | `SetPriceListOptionExtras`; `SetPriceListCharacteristicRates` (ADR-0046 r15, r17) | Same | Same | `price_list_option_extra`, `price_list_characteristic_rate`; product-level `price_list_entry.product_id` | [not named] | — | — | — |
| 4 Assign to customer | `UpdatePartner` (profile `price_list_id`; payload undefined, A12) | Person | None | `customer_profile` | `PartnerUpdated` | — | — | — |
| 5 Lookup | query `GetPrice` → `master_data.contract.find_price(list, item, unit, quantity, date, values)` | Person or agent | — | none | — | — | — | None. Entered unit first, then inventory unit; configured order: item entry → product entry, + extras + rates, rounded once |

A list has no status or approval of its own; validity is per entry.

### Flow 3 — CPQ (only as currently designed; see A1)

| Step | Command | Actor / mode | Approval | Tables | Events | Work items | Postings | LLM role |
|---|---|---|---|---|---|---|---|---|
| 1 Request arrives | Flow 1 step 2, matched | `system` intake | — | as flow 1 | `InteractionCreated` | `inbound_message_matched` (`role:sales_clerk`) | — | — |
| 1′ Designed configuring path | `CreateInteraction` kind `note`, then `StartAgentRun` (subject) | Salesperson; the run is untainted | — | `interaction`, `agent_run` | `AgentRunStarted` | `agent_task` | — | — |
| 2 L1 / L2 | — (ADR-0051 r15) | `quotation` agent, scope `partner` (needs active `customer` role) | — | run steps | — | — | — | L1 `classify_message`. L2 `extract_request`: lines, stated quantity, `characteristic_hints`, spans |
| 3 D1 / L3 items | queries `partner_item_overview`, `item_overview` (untainted only) | Agent | — | — | — | — | — | Deterministic: partner code token → item code/barcode token → `rank_candidates` (≥ 92, lead ≥ 8). L3 `choose_item` among ≤ 5 offered handles |
| 4 L4 configure | query `EvaluateConfiguration` → `master_data.contract.evaluate_configuration(model_revision, values)` | Agent, **untainted runs only** | — | none | — | — | — | LLM proposes values by characteristic code; code evaluates; violations fed back, ≤ 3 rounds; every number must appear in a hint span; must end `is_complete` |
| 5 D2 draft | `CreateQuotation` (`sales`; ADR-0047 r3, r16), step `quotation.draft` | Agent, draft only; passes no price, discount or tax | — | `document`, `document_version`, `quotation`, quotation lines, `document_line_price_step`, `document_line_tax`, `product_configuration(+_value)` when complete | `QuotationCreated` | draft link and note | — | None. `sales.contract.price_line` (list → base → promotion → manual discount → net unit price → line amount → document discount); `tax.contract.compute_taxes` |
| 6 D3 checks | `GetCreditExposure`, `GetAvailableToPromise`, `GetConfigurationEstimate` (→ `production.contract.estimate_configuration`) | Agent | — | — | — | note | — | None |
| 7 L5 text | `CreateOutboundMessage` (`crm`), step `quotation.reply`; draft only; **untainted only** | Agent | — | `outbound_message`, `outbound_message_content`, `outbound_message_recipient` | — | link | — | Writes `cover_text`, `reply_subject`, `reply_body`; code checks every number equals a draft number; `GetOutboundContentCheck` |
| 8 Submit | `SubmitQuotation` | Salesperson | Policy `submit`, type `quotation`: `discount_percent`, `margin_percent`, `is_price_below_cost`, `is_price_outside_list` (credit: A10). Seed: none. With a company rule → pool `sales`, `standard` | `policy_decision`, `document.state` | `QuotationSubmitted` | `approval_pending` if ranked | — | — |
| 9 Approve | `ApproveQuotation` | Stage member with `ApproveQuotation` (`accountant` qualifies: `sales` `can_approve`); not a writer; not the human the run acted for | `standard`, k = 1 | `approval` | `QuotationApproved` | resolved | — | — |
| 10 Send | `SubmitOutboundMessage` + `SendOutboundMessage` (`outbound_send`); then `RecordOutboundMessageOutcome` | Person sends; external consumer `crm_mail_sender` records the outcome | Policy at the message's `Submit` only; Send adds none | `outbound_message_delivery`, `…_delivery_recipient`, outbound `interaction` | `OutboundMessageSendRequested` | `outbound_message_failed` on failure | — | — |

### Flow 4 — O2C

| Step | Command | Actor | Approval | Tables | Events → consumers | Work items | Postings (key → TT99) | Deterministic / LLM |
|---|---|---|---|---|---|---|---|---|
| 1 Order from quotation | `CreateSalesOrder` with `source_lines` (`sales`; ADR-0047 r2–4) | Person; origin reset, taint inherited through `derived_from_version_id` | — | `document`, `document_version`, `sales_order`, lines, price steps | `SalesOrderCreated` | — | — | Configuration re-evaluated under the revision valid on the new date (`configuration_invalid`); `quotation_expired` after validity |
| 2 Submit + credit check | `SubmitSalesOrder` (`is_policy_in_handler`; locks classes 1–8, then partner) | Person with `CreateItem` | Policy `submit` with `is_credit_exceeded`; seeded rule → rank 10 → pool `sales`, `standard` | `policy_decision`; `item`, `item_variant_value`, `variant_attribute_value`, `item_warehouse_planning` (`make_to_order`); `demand_supply_line` (demand) | `SalesOrderSubmitted`; `ConfiguredItemCreated` → `production` consumer releases the cost estimate | `approval_pending`; `configured_estimate_failed` on failure | — | `sales.contract.get_credit_exposure`; `inventory.contract.set_demand_hold` |
| 3 Approve (credit release) | `ApproveSalesOrder` | Stage member, not a writer | `standard`, k = 1 | `approval`; reservations (stock lines up to ATP; MTO lines reserve production output) | `SalesOrderApproved` | resolved | — | Holds re-evaluated |
| 4 MTO supply | Flow 5 steps 3–8 for the configured item, then `production_issue` and `production_receipt` | Planner, shop floor | Flow 5 | Flow 5 | — | — | Issue: Dr `production_consumption` 621 / Cr `inventory_posting` 152. Receipt: Dr `inventory_posting` 155 / Cr `production_output` 154 | `plan_production` |
| 5 Delivery | `CreateDelivery`, `PostDelivery` (`inventory`; ADR-0047 r5); movement `sales_issue` | Warehouse keeper | Policy `post`, human: allowed. `demand_on_hold` if held | `delivery` + lines, material document, `journal_entry`, `journal_line`, `demand_supply_line` open quantity | `DeliveryPosted` → `sales` consumer may run `CloseSalesOrder` as `system` | — | Dr `cost_of_goods_sold` 6321 / Cr `inventory_posting` 155 at preliminary price (released estimate as fallback) | — |
| 6 Invoice | `CreateSalesInvoice`; then `PostSalesInvoice`, or `IssueSalesInvoice` → `RecordSalesInvoiceEInvoiceOutcome` → consumer `PostSalesInvoice` (A3) | Accountant. With the e-invoice: `system` on behalf of the issuer posts | Policy at `post` or `issue`. Under `l10n_vn` the type may not wait: a rank becomes `human_only`, no pool | `sales_invoice` + lines, `document_line_tax`; `posting_intent`, e-invoice record (`tax`); at post `journal_entry`, `journal_line`, `open_item` × installments, `tax_line` | `EInvoiceAccepted`; `SalesInvoicePosted` | `e_invoice_rejected`, `e_invoice_posting_held`, `e_invoice_outage` on failures | Dr `receivable_reconciliation` 131 per installment / Cr `revenue_posting` 5112 (item group `product`), `output_tax` 33311 (`vat_out_10`); discounts `net` | `tax.contract.compute_taxes`; `EInvoiceValidator`; holds re-evaluated |
| 7 Statement import | `ImportBankStatement` (`cash`; ADR-0048 r8) | Person | — | `bank_statement`, `bank_statement_line` | [not named] | — | — | `BankStatementReader`; balance and gap checks |
| 8 Cascade | `match_bank_line` (pure). Steps 2–4 draft `bank_receipt` via `CreateBankReceipt` | `system` on behalf of the importer | Auto-post rule disabled by default | `bank_receipt` + lines (draft); line match (A9) | — | `bank_line_unmatched` (`role:accountant`, `days:2`) for the rest | — | Steps: already posted (95) → reference token (100 / 80 / 70) → account + amount (90 / 60) → subset (70) |
| 8′ Unmatched line | `RecordBankLineSuggestion` (`cash`, `is_draft_only`), step `bank_matching.suggest` | `bank_matching` agent, scope `subject`, tainted | — | untrusted fields on the line | `BankLineSuggestionRecorded` → `cash` consumer re-runs the cascade at step 2 and drafts with `match_basis` `llm_suggestion`, no score, tainted | item stays until a person posts or matches | — | L1 `read_description` → `reference_tokens`, `payer_name_text`, `stable_payer_token`, `purpose`. Never matches or scores |
| 9 Post receipt | `PostBankReceipt` | Accountant | Policy `post`, human: allowed; tainted drafts are human-post only | `journal_entry`, `journal_line` (`open_item_id`, `evidence_method` `bank_transfer`), `open_item` settled | `BankReceiptPosted`; `OpenItemSettled` → `sales` consumer clears credit holds; → `tax` consumer `tax_payment_evidence` | `bank_line_unmatched` resolved | Dr the money account's operational account (under 112, `cash_in_bank`; from `money_account.account_id`, no key) / Cr 131 | `GetAllocationProposal`; discount gross-up (r7) |

### Flow 5 — Demand planning

| Step | Command | Actor | Approval | Tables | Events → consumers | Work items | Postings | Deterministic / LLM |
|---|---|---|---|---|---|---|---|---|
| 1 History | `ImportSalesHistory` (import batch), or posted `sales_issue` | Person | — | `sales_history` | — | — | — | — |
| 2 Forecast | `RunForecast` (`planning`; ADR-0024 r10–13, r17) | Job on queue `jobs`, on behalf of the requester or `planning_owner_id` | — | forecast tables [not named, A14] | `ForecastCompleted` | — | — | 8-week moving average × seasonal or event index; `forecast_history_insufficient` under 52 weeks; daily spread; consumption within `forecast_consumption_days` |
| 3 MRP | `RunPlanning` with `planning_date` (ADR-0024 r14–21; ADR-0036 r1–7) | Same; regenerative; one per company | — | `planned_order` (`proposed`), `planned_order_component`, `planned_order_operation`, pegging rows, `planning_exception` | `PlanningCompleted` → consumer `planning_work_items` | `planning_exception` (owner `buyer`, due `required_date`); `capacity_overload` (owner `planning_owner`) | — | Netting per method; lot sizing; `production.contract.plan_production` (`backward`/`forward`/`fixed`); MTO per sales demand line |
| 4 Agent on an exception | `StartAgentRun` → `CreateChangeProposal`, step `planning.propose` (ADR-0051 r23–25) | `planning` agent; `may_read_untrusted: false`, never tainted; acts for the workflow owner | — | `agent_run`, `change_proposal` (items `UpdatePlannedOrder` / `FirmPlannedOrder` / `ConvertPlannedOrder`, or a parameter change) | — | note and draft link | — | D2 `candidate_actions` by code. L1 `explain` (analysis seat): `explanation` ≤ 1,200 characters, `recommended` among offered handles; every number must appear in the input |
| 5 Proposal approval | `SubmitChangeProposal`, `ApproveChangeProposal` | Planner submits; approver ≠ the human the run acted for; under the seed only `owner` qualifies (A6) | Floor 7 → rank 10; pool `general`, `standard` | `policy_decision`, `approval`, `change_proposal_execution` | `ChangeProposalApproved` → executor runs the items as `system` on behalf of the approver | `approval_pending` | — | — |
| 6 Firm / convert by a person | `FirmPlannedOrder`, `ConvertPlannedOrder` (verbs at level `edit`) | Planner or buyer, direct | No policy point (ADR-0043 r17) | `planned_order.state` `converted`; `replenishment_request` + lines via `inventory.contract.request_replenishment` | `PlannedOrderFirmed`, `PlannedOrderConverted`, `ReplenishmentRequested` (from `inventory`) | — | — | Grouping by supplier, warehouse and `conversion_window_days` |
| 7 Purchase requests | `CreatePurchaseRequest` (`purchasing` consumer of `ReplenishmentRequested`) | `system` on behalf of the converter | Own `Submit` later (flow 6) | `purchase_request` + lines (`origin_planned_order_id`), `demand_supply_line` (supply, from draft) | `PurchaseRequestCreated` | — | — | — |
| 8 Production orders | within `ConvertPlannedOrder`: `production.contract.create_production_order_from_plan` (mode `fixed`), same transaction, no event hop | `system` on behalf of the converter | Release = `SubmitProductionOrder` by a person. Seed: none → `approved`. With a rule → pool `mo` | `production_order` (draft), components (demand rows), output supply row (`origin_planned_order_id`, `for_demand_supply_line_id` for MTO) | `ProductionOrderCreated`, later `…Approved` | `subcontract_line_review` only for external operations | none until issue and receipt | — |

### Flow 6 — P2P

| Step | Command | Actor | Approval | Tables | Events → consumers | Work items | Postings (key → TT99) | Deterministic / LLM |
|---|---|---|---|---|---|---|---|---|
| 1 Request | `CreatePurchaseRequest` (person, or flow 5 step 7), `SubmitPurchaseRequest` | Buyer submits | Policy `submit`, `purchase_request`. Seed: none → `approved`. With a company rule → pool `pr`, `standard` (+ `senior` at rank 20). The converter and every editor are excluded as writers | `purchase_request`, lines, `demand_supply_line`, `policy_decision` | `PurchaseRequestSubmitted` / `…Approved` | `approval_pending` | — | — |
| 2 Approve | `ApprovePurchaseRequest` | Stage member with `purchasing` `can_approve` (`accountant` qualifies); not a writer | Pool `pr` | `approval` | `PurchaseRequestApproved` | resolved | — | — |
| 3 Order | `CreatePurchaseOrder` with `source_lines`, `SubmitPurchaseOrder`, (`ApprovePurchaseOrder`) | Buyer | Pool `po`. Seed: none | `purchase_order`, lines, price steps, supply rows; at approval `ordered_date` and `purchase_order_line_gr_ir_layer` | `PurchaseOrderApproved`; the request auto-closes via `ClosePurchaseRequest` as `system` | `approval_pending` if ranked | — | `purchasing.contract.price_line` (no promotions); `inventory.contract.set_order_line_gr_ir_price` |
| 4 Goods receipt | `CreateGoodsReceipt`, `PostGoodsReceipt` (`inventory`); movement `purchase_receipt` | Warehouse keeper; not a person who wrote or approved the order (`purchase_order_vs_goods_receipt`) | Policy `post`, human: allowed | `goods_receipt` + lines (position range), material document, `journal_entry`, `journal_line` (`purchase_order_line_id`) | `GoodsReceiptPosted` | `putaway_without_target` possible | Dr `inventory_posting` 152 (raw material) / Cr `gr_ir_clearing` 33881 = `round(V(R+q)) − round(V(R))` | `inventory.contract.post_gr_ir_positions`; receipt tolerance |
| 5a Invoice by a person | `CreatePurchaseInvoice` (`purchasing`; ADR-0047 r12) | Accountant | — | `purchase_invoice`, lines, `document_line_tax` (stated tax) | — | — | — | Duplicate key (regime: seller tax ID, form, symbol, number) → `duplicate_external_document` |
| 5b Invoice by the agent (A2) | `StartAgentRun` on `supplier_invoice_received` → `CreatePurchaseInvoice` (step `purchase_invoice.draft`) + `CreateChangeProposal` with `CreatePartnerItem` (step `purchase_invoice.mapping`) | `purchase_invoice` agent, scope `partner` (supplier by verified tax ID), tainted, draft only | Mapping proposal: `general` / `standard` | drafts as 5a (tainted); `change_proposal` | — | `supplier_invoice_received` (`role:accountant`, `days:2`) | — | D2 `map_lines` (`partner_item` → `supplier_item` → `rank_candidates`). L1 `choose_item` among ≤ 10 related items. D3 `select_order_line`. Quantities, prices and stated tax are copied from the record |
| 6 Submit + match | `SubmitPurchaseInvoice` | Accountant | Policy `submit` with `is_match_exceeded` (seeded: `standard` for every actor kind, also at `post`). Pool `po`, or `expense` when `is_direct_expense` | `policy_decision` | `PurchaseInvoiceSubmitted` | `approval_pending` if mismatched | — | Three-way match: `match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt` |
| 7 Approve | `ApprovePurchaseInvoice` | Stage member; not a writer; not the human the run acted for | `standard`, k = 1 | `approval` | `PurchaseInvoiceApproved` | resolved | — | — |
| 8 Post | `PostPurchaseInvoice` | Accountant; tainted → a person | Re-check when `policy_input_hash` changed | `journal_entry`, `journal_line`, `open_item` per installment, `tax_line`; `landed_cost` when there is a price difference | `PurchaseInvoicePosted` → `cash` consumer (prepaid schedule draft); the order may auto-close | `tax_condition_pending` when ≥ VND 5,000,000 and unpaid (`deductible_until_due`) | Dr `gr_ir_clearing` 33881 = `round(V(I+q)) − round(V(I))`; difference Dr `purchase_cost_clearing` 33882, then `landed_cost` to 152 (A16); Dr `input_tax` 1331 (`vat_in_10`) / Cr `payable_reconciliation` 331 | GR/IR by unit positions (INV-92) |
| 9 Payment | `CreateBankPayment` (line `settle`, `partner_bank_account_id`), `SubmitBankPayment`, `PostBankPayment` (`cash`; ADR-0048 r3) | A third finance user (A8). No money leaves ERPMe in Phase 1; the document records a payment already made | Policy inputs: amount, `is_direct_expense`, `is_bank_account_recent`, `is_rate_unusual`. Seed: none. Pool `general` (`expense` by selector) | `bank_payment` + lines, `journal_entry`, `journal_line` (`evidence_method` `bank_transfer`), `open_item` | `BankPaymentPosted`; `OpenItemSettled` → `tax_payment_evidence` | `tax_condition_pending` resolved by the system | Dr 331 / Cr the money account's operational account (112) | `GetAllocationProposal` |
| 10 Statement | Flow 4 steps 7–8; cascade step 1 "already posted", then `MatchBankLine` | Person or cascade | — | `bank_statement_line.match_state` | — | — | — | — |

---

## Part C — What the probe simulator assumed that the current design contradicts

**Flow 1**
1. Trace 1.05: the agent submits the change proposal. Design: agents create drafts only, and a person submits (ADR-0050 r30; ADR-0051 r13).
2. Trace 1.05/1.07: items `AddPartnerRole`, `CreatePartnerAddress`, `CreateCustomerProfile`, and a proposed credit limit. Design: only `CreatePartner` + `CreateContact`; L2 extracts no credit limit, payment term or price list.
3. Trace 1.06: the sales manager approves. Under ADR-0055's seed the `general` stage members are `accountant`, `chief_accountant` and `owner`; `sales_manager` is not a member and holds no `ApproveChangeProposal`.
4. Trace 1.07: "interaction_linked" on execution. Design: a person runs `MatchInteraction` afterwards. Intake was `RecordInboundInteraction`; the design has `RecordInboundMessage` with sender authentication, and no L1 `classify_message` ran.

**Flow 2**
5. Trace 2.01–2.02: `CreatePriceListEntry`, `CreatePriceListOptionExtra`, `CreatePriceListCharacteristicRate`. Design: the set commands `SetPriceListEntries`, `SetPriceListOptionExtras`, `SetPriceListCharacteristicRates`.
6. Trace 2.05: `UpdateCustomerProfile` does not exist in the docs.
7. The same person (the sales manager) maintains prices and approves the quotation (3.14); this conflicts with `price_list_vs_sales_approval`.

**Flow 3**
8. Trace 3.02–3.06: a tainted run on a customer e-mail configures and loops on `EvaluateConfiguration`. Design: tainted runs do not configure (A1).
9. Trace 3.12: the tainted run drafts the cover e-mail. Design: L5 is skipped in tainted runs.
10. Trace 3.09: items mapped by "catalog search". Design: tainted runs read only `partner_item_overview` and the partner's earlier lines.
11. A single "CPQ agent" with 3 LLM calls and no L1/L2/L3 split or source-span checks; the agent computed policy inputs (3.10). Design: policy evaluates at `Submit`.
12. Trace 3.15: `SendMessage`. Design: an `outbound_message` document with `SubmitOutboundMessage` + `SendOutboundMessage`, delivery rows, and the `crm_mail_sender` consumer.
13. Approval by "standard procedure (rank 10)" with one approver role. Design: pool `sales`, stage `standard`, eligibility = member + `ApproveQuotation` + not a writer.

**Flow 4**
14. Trace 4.09: `PostSalesInvoice` directly by a person. Design: undetermined until the e-invoice-required setting exists (A3); DS-17 expects the stub adapter and `issuing`.
15. Trace 4.07: production stub posting components straight into finished goods. Design: `production_issue` (621) and `production_receipt` (155 / 154) through a cost object.
16. Trace 4.12: one LLM call that "suggests". Design: `RecordBankLineSuggestion` → `BankLineSuggestionRecorded` → `cash` consumer re-runs the cascade at step 2 and drafts a tainted, unscored document.
17. Trace 4.13: `MatchBankLine` on drafts (see A9).
18. No `OpenItemSettled` consumers: credit-hold clearing and `tax_payment_evidence` are absent.

**Flow 5**
19. Trace 5.06: the planning agent only explains. Design: it also drafts a change proposal with `FirmPlannedOrder` / `ConvertPlannedOrder` / `UpdatePlannedOrder`, which a planner submits and another person approves.
20. The work item is created at the agent step. Design: `planning_work_items` raises `planning_exception` items first, and they trigger the agent.
21. Trace 5.07: the production planned order is only firmed, and the production order is a stub. Design: `ConvertPlannedOrder` writes the draft `production_order` in the same transaction, and a person releases it by `SubmitProductionOrder`.

**Flow 6**
22. Trace 6.01: the PO is created straight from a draft purchase request, with no `SubmitPurchaseRequest` and no `pr` pool. "Buyer creates and approves" contradicts the writer exclusion.
23. Trace 6.03–6.04: the supplier invoice arrives as e-mail text and the LLM extracts header, amounts and lines. Design: the agent never parses a raw document; it starts from a structured `e_invoice_record` with signature check, and the LLM only chooses an item among the supplier's related items.
24. No `CreatePartnerItem` mapping proposal (D5).
25. Trace 6.09 and 6.12: the accountant who posted the invoice drafts the payment, and the chief accountant who approved the invoice posts it. `purchase_invoice_vs_payment` refuses this with `segregation_of_duties`.
26. Price difference posted directly; no `landed_cost` through `purchase_cost_clearing`; no `tax_condition_pending`.

**Cross-cutting**
27. The policy stub used one procedure and one approver. The design now has `approval_plan` on `policy_decision`, stage rows on `approval`, one `approval_pending` item per current stage, and INV-224 to INV-226 and INV-230.
28. The sim's sources list predates ADR-0050 to 0055 and DS-15/DS-35 DDL. It has no users, role assignments, owner scope or delegation.

Relevant paths on gb10: `~/Projects/ERPMe/docs/adr/`, `~/Projects/ERPMe/docs/catalogs/`, `~/Projects/ERPMe/docs/design/DS-19-vietnam-tt99/`, `~/Projects/ERPMe-lab/sim/trace/trace.md`.
