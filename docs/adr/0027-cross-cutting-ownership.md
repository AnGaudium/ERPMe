# ADR-0027: Ownership of cross-cutting entities and consistency fixes

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-45 (new). Related decisions: D14. Principles 6, 7, 8, 10. Build principles B1, B2, B3. ADR-0004, ADR-0005, ADR-0008, ADR-0009, ADR-0012, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0017, ADR-0019, ADR-0020, ADR-0021, ADR-0022, ADR-0023, ADR-0024, ADR-0026, DS-16, DS-17. Assessment findings A-4, A-5, A-6, A-7 (except d, which goes with F12), A-8, F10, F11, F-3, P-1, P-2, X-2, X-3, L-1 to L-7 ([design assessment 1](../reviews/2026-11-14-design-assessment/README.md)).

## Decision

Before step 1 code freezes the platform modules, every entity that several modules refer to gets one owning module, in a layer that every module referring to it may import (ADR-0022 rules 2, 7).

**Ownership.**
- Agent runs, work items and attachments move to layer 2.
- `derivation_trace` gets one generic schema.
- `company`, `branch` and stubs of `cost_center` and `project` are defined now.
- The step 3 stock documents get names and an owner.

**What else this ADR fixes.**
- It lists which read models are synchronous and which asynchronous.
- It sets one complete lock order.
- It names owners for customs, e-invoice, export, management reporting and the close computations.
- It closes the catalog and glossary inconsistencies the assessment found.
- It adds the agent-safety invariants, with the data they need named.

### Rules

**Modules added to layer 2** (ADR-0022 rule 2)

1. Three platform modules:

   | Module | Owns | Why layer 2 |
   | --- | --- | --- |
   | `agent_runs` | `agent_type` (declared permissions, data labels, budgets) and `agent_run` (actor context, on-behalf-of, taint, spend, outcome), with columns designed by DS-32 | `document_version`, `outbox_event` and `permissions` refer to runs (ADR-0009 rule 9; ADR-0013 rule 2; ADR-0017 rule 16). The LLM runtime stays in layer 5 `agents` |
   | `work` | `work_item`, claims, due dates and links (DS-29) | Work items are created from layers 3–4 (ADR-0023 rule 21; ADR-0024 rule 21; ADR-0013 rule 8) |
   | `attachments` | `attachment` and `attachment_link` (rule 2) | E-invoice XML, bank files, e-mails, customs scans, product images and print PDFs are stored once and linked from any module |

   Within layer 2, `documents` and `permissions` may import the `agent_runs` contract, and `agent_runs` imports neither of them, so there is no cycle. `documents` may also import the `attachments` contract to check scan state at `Post`; `attachments` imports neither ([ADR-0038](0038-audit-and-observability.md) rule 14). `registry` also imports `policy` and `work`; `documents`, `outbox`, `permissions`, `attachments`, `agent_runs` and `policy` import `work`; layers 3–4 raise and resolve work items through `work.contract` ([ADR-0042](0042-work-queue.md) rules 5–6; [ADR-0043](0043-policy-and-approval.md) rule 1).

   The columns of `agent_type`, `agent_type_version`, `agent_type_setting`, `agent_run`, `agent_run_step`, `agent_budget_usage` and `agent_promotion_evidence` are in [ADR-0050](0050-agent-runtime-and-query-layer.md) rules 12, 14, 18, 19 and 23.
2. Attachments:
   - **Identity and storage.** An `attachment` is unique per (`company_id`, SHA-256). It records media type, size, storage key, data label and source kind. The bytes live in an object store, never in the database (DS-37).
   - **Data labels.** A second upload of the same bytes in the same company reuses the row and keeps the stricter data label.
   - **Links.** `attachment_link` holds attachment, target table and target ID. It is checked by an invariant (INV-83), because its reference is polymorphic.
   - **Deletion.** Erasure of a data subject (ADR-0019) removes that subject's links. Bytes are deleted only when no link remains and retention allows. Links to posted accounting documents stay as voucher evidence ([ADR-0038](0038-audit-and-observability.md) rule 15).
   - **Details.** DS-36 owns retention, scanning and limits: [ADR-0038](0038-audit-and-observability.md) rules 13–15.

**Derivation trace**

3. `derivation_trace` is owned by `ledger` and written through `ledger.contract.write_derivation_trace` in the caller's transaction. It holds:
   - `rule_code` and `rule_version`;
   - `inputs`: typed references to lines, price rows, tax rate rows, `regime_setting` key and `effective_from`, applied rates and open items;
   - `steps`: ordered exact intermediate values;
   - `result`, `recorded_at`, and the `command_id` of the command that wrote it (ADR-0008).

   A line refers to it by `derivation_trace_id` (ADR-0014 rule 5). It is not OpenTelemetry's `trace_id`.
4. Writers follow spec 10's lean scope ("cost trace only for costing"): costing (ADR-0020) and landed cost (ADR-0021) write traces. Whether FX conversion, pricing (DS-22) and tax (DS-23) also write traces in Phase 1 is the author's decision, because it is a scope question (ADR-0005 item 2; open question). The generic schema lets them be added without change.

   Interim, with the open question on trace scope: prices are explained by the `document_line_price_step` rows on each line, part of its content, and pricing writes no `derivation_trace` rows ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 16).

**Master records**

5. Master records needed by step 1, owned by `master_data` (DS-20):
   - **`company`:** `code`, `legal_name`, `tax_id`, `company_currency` (ADR-0011 rule 6), `time_zone` (ADR-0007), `localization_package` and `accounting_regime` (ADR-0016 rule 2), `legal_form` (null where the package declares none, [ADR-0039](0039-vietnam-package-tt99.md) rule 5), `valuation_area_level` (ADR-0015 rule 8), `fiscal_calendar_owner_id` and `fiscal_year_lead_days` (ADR-0012 rule 3), `is_active`.
   - **`branch`:** `company_id`, `code`, `name`, `tax_id` for dependent units where the regime uses one, `address`, `is_active`.
   - **Stubs:** `cost_center` and `project` are created as stubs (`id`, `company_id`, `code`, `name`), because `journal_line` refers to them from step 1. DS-20 completes them by step 2.

   Their DDL, completed, is in DS-20-master-data.sql ([ADR-0045](0045-master-data-and-price-lists.md) rules 1, 8, 9).
6. Employee references (`salesperson_id`, `buyer_id`) point to partners with the `employee` role (ADR-0019 rule 3). The DS-06 DDL and ADR-0014 rule 9 are corrected.

**Stock documents and other owners**

7. The step 3 stock document types are owned by `inventory`. Their fields, reversibility flags (ADR-0009 rule 19) and the link from `transfer_order` to `stock_transfer` (one step, or two through transit) go in a DS-09 "stock documents" deliverable, written before step 3. The production documents are owned by `production` ([ADR-0034](0034-production-orders-and-shop-floor.md)). Account opening balances use `opening_balance_entry` and open items `opening_open_item_entry`, owned by `imports` ([ADR-0044](0044-data-migration-and-export.md) rules 7, 8).
   - **Posting types:**
     - `goods_receipt`, `delivery`, `stock_transfer`, `stock_count`;
     - `internal_consumption`, `other_receipt`, `other_issue`, `scrap`;
     - `return_to_supplier`, `return_from_customer`;
     - `opening_balance`, matching the movement type of the same name. Account opening balances have their own type in DS-21.
   - **Non-posting demand document:** `transfer_order`.
   - **Order references.** Lines of `goods_receipt`, `delivery` and the return types have nullable order-line reference columns (`purchase_order_line_id`, `sales_order_line_id`), reserved in the step 3 design (typed line references, [ADR-0028](0028-document-lifecycle-hardening.md) rule 2). Commercial documents at step 5 fill them, and the core table does not change (B3). Before step 5, `needs_reference` is satisfied by a free-text reference.
   - **Correction types.** The return stock documents may carry `correction_of_id` to the receipt or delivery they correct (ADR-0009 rule 23); the DS-09 deliverable decides. The commercial correction types `purchase_return` and `sales_return` refer to them.
8. Owners of entities that had none:

   | Entity | Owner |
   | --- | --- |
   | `customs_declaration` and its tax rows | `purchasing`, step 5 (ADR-0021 rule 10) |
   | E-invoice records and intents | `tax` (DS-24); `tax` also owns `document_line_tax` computation, the subledger `tax_line` with its adjustments, and filed `tax_return` snapshots ([ADR-0041](0041-tax-engine.md)). A sales document requests issuance through `tax.contract.request_e_invoice` synchronously, which writes the e-invoice record and its intent; the external consumer then issues it asynchronously, and the document posts on acceptance ([ADR-0028](0028-document-lifecycle-hardening.md) rule 7). Imports go downward (as ADR-0024 rule 22) | 
   | Audit records | `audit` (layer 2, DS-36), with one row per executed command: `command_type`, `actor_kind`, `actor_id`, `agent_run_id`, `idempotency_key` (needed by INV-81); also `origin_agent_run_id`, `on_behalf_of_id` and `policy_decision_id` ([ADR-0029](0029-proposals-and-agent-safety.md) rule 15). Full columns, changes and denials: [ADR-0038](0038-audit-and-observability.md) rules 1–8 |
   | Full data export (spec 15) | DS-21, as `ExportCompanyData`: a company package with master data, documents with all versions, journal and material lines, open items, stock, attachments and audit rows, one JSON Lines file per table plus the attachment files. It is not the import batch format; contents, exclusions and download: [ADR-0044](0044-data-migration-and-export.md) rule 17 |
   | Management reporting | DS-33 semantic views; statutory reports stay DS-26 |
   | Bad-debt provisions and prepaid amortization | DS-25, as close tasks |
   | Inventory write-down to net realizable value | DS-09, as a close task |

   ADR-0012 rule 17's "DS-26" for these computations is corrected.

**Read models**

9. Read models and when they update:

   | Read model | Updated |
   | --- | --- |
   | `stock_quantity`, `stock_value` | In the posting transaction, through the stock lock helper |
   | Open item cache (ADR-0026) | In the posting transaction |
   | `stock_reservation`, `demand_supply_line` | In the document's transaction, through posting interfaces |
   | Numbering counters | In the posting or approval transaction |
   | `account_period_balance` | When a period's `general` area is locked; open periods are computed from lines (ADR-0014 rule 18) |
   | Work items, notifications, e-invoice intents, timeline entries, search indexes | Asynchronously, by outbox consumers |
   | Semantic views (DS-33) | Views over the tables above |

**Locks**

10. The complete lock order, per command, supersedes the lists in ADR-0022 rule 10, ADR-0023 rule 10 and ADR-0026 rule 14. Within each class, rows are locked in ascending ID unless stated.
    1. Documents: the command's own, and the documents it refers to (the order a delivery fulfills, the receipt a landed cost targets, the original of a reversal or correction, the production order of a shop-floor document; [ADR-0034](0034-production-orders-and-shop-floor.md) rule 19).
    2. Period area state rows, share lock.
    3. The planning state row (planning runs only), or the company's `production_structure` row (releases of bills of materials and routings, production version and production setting saves, deactivations; [ADR-0033](0033-production-master-data.md) rule 8).
    4. Warehouse task rows.
    5. Handling unit rows, parent first.
    6. `stock_value` rows, ascending by item and warehouse ID.
    7. `stock_quantity` rows.
    8. Bin rows.
    9. Partner rows (credit check, DS-22).
    10. Open item rows. The ledger locks all of an entry's items before inserting any line.
    11. Numbering counters.
    12. `event_subject` rows.

    The idempotency record is taken first (ADR-0008 rule 16) and held to commit. Account rows locked by the first-posting trigger (ADR-0014 rule 12) are taken in line order after the open items and before numbering counters. They are outside the helper's assertion, because they are locked once per account in its life. Work item claims run in their own transactions. For a command of an agent run bound to a work item, that item row follows `FOR KEY SHARE` (claims, assignments and lease expiry take it `FOR UPDATE`); work item rows raised by a command are the last class, in (`kind`, `open_key`) order ([ADR-0042](0042-work-queue.md) rules 5, 9).

    Exception: credit hold updates on other orders' demand rows, made inside a `sales` command that holds the partner lock, take no class 1 lock of those orders; a hold is a single flag that does not conflict with their other changes ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 18).

**Catalog and glossary consistency**

11. ADR-0015 rule 2 gets one exception, kept as data: a column `has_regime_alternatives` in `transaction-keys.csv` marks keys that share a system account's code while listing alternatives that are a regime choice under rule 4 (`price_difference`, `fx_gain_unrealized`, `fx_loss_unrealized`). CI reads that column. ADR-0015's key count becomes 38. Note: the column also marks keys that do not share a system account's code, whenever the listed accounts are alternatives a regime or company chooses between (`cash_surplus`, `cash_shortage`, `bank_charge`, `production_abnormal_cost`, `production_unabsorbed_overhead`) ([ADR-0053](0053-core-neutrality.md) rule 6).
12. Glossary fixes:
    - one definition of preliminary price, and one row for company and branch;
    - the stock quantity row with bin, status and handling unit;
    - verbs Erase and Request;
    - naming: date validity is `start_date` and `end_date`, dated settings use `effective_from`, and points in time end in `_at`. ADR-0019 rule 9's `valid_from` becomes `started_at`, which pairs with `ended_at`;
    - `product.buyer_id` is the planning buyer, and `supplier_profile.buyer_id` the default on supplier documents;
    - `human_only` means "never an agent", and "never an integration" stays interim while ADR-0008 rule 2's open question on integrations stands. A system job may run such a command on behalf of a human only where an ADR says so (e.g. ADR-0011 rule 20).
13. Reversibility of `goods_receipt` and `delivery` follows ADR-0009 rule 19's flagged interim: reversible while unreferenced. Their flags are set by the DS-09 stock documents deliverable. ADR-0020 rule 7 is aligned.
14. E-mail intake (ADR-0019 rule 14) runs on the `integrations` queue as actor `system`, on behalf of the mailbox owner. Its declared permissions are only the commands that record an inbound interaction and its attachments. Actor `integration` stays reserved for integration clients (ADR-0017 rule 1). One command batch per message, `RecordMailboxIntakeOutcome`, and intake as deterministic code, not an agent run: [ADR-0052](0052-minimal-crm.md) rule 12.
15. Planning (ADR-0024): requested runs act on behalf of the requester, scheduled runs on behalf of `planning_owner_id` (rule 17). Forecast history of goods sold from `goods_sent` warehouses is attributed to their valuation warehouse. The transfer into the `goods_sent` warehouse stays excluded as dependent demand, so nothing is counted twice (rule 10).
16. INV-07: the counters of all documents that hold a number, in any state, are exactly 1 to `next_value` − 1, each once. This widens the invariant to non-posting documents and never weakens it. It is flagged, because it rests on ADR-0009 rule 8's interim.
17. New invariants:
    - **INV-57:** per demand line, the reserved amounts of open and picked reservations never exceed the line's open quantity. First step 3, for transfer orders.
    - **INV-63:** each `demand_supply_line` open quantity equals its source line's quantity minus fulfilled and closed quantities, recomputed from the referring documents. First step 3.
    - **INV-80:** no outbox event that is tainted and whose command has effect class `posting`, `master_data_change` or `outbound_send` (a new registry attribute of every command, ADR-0008 rule 1) has a non-human actor. First step 5, when agents start. Taint laundered through stored drafts (F4) stays a requirement on DS-32. Settled by [ADR-0029](0029-proposals-and-agent-safety.md) rules 8–11.
    - **INV-81:** no audit row of a command registered `human_only` has actor kind `agent`, or `integration` while the interim holds. First step 1, flagged.
    - **INV-82:** for every posted document whose latest policy decision on the posted version has outcome `approval_required`, an `approved` approval row exists on that version. Documents under ADR-0009 rule 12's human-only posting store the outcome `human_only` and are outside this check. First step 5, flagged with rule 12.
    - **INV-83:** every `attachment_link` points to an existing row of its target table, within the attachment's company (area `platform`).

    New group: 80–89, agent safety and platform integrity.
18. Counts and maps: `docs/README.md`, `docs/design/README.md` and `docs/prompts/runbook-session.md` list design items DS-01 to DS-45.
19. The open question on closing to 911 and 421 every period keeps the agent's interim decision. A new unchecked item asks the author to verify the rule against the TT99 text, because unverified rules stay open (reading guide rule 4; ADR-0012 rule 18).
20. A-7(d), a GR/IR invariant, is deferred to the GR/IR line-reference work before step 5 (assessment F12).

## Context

The independent assessment found:
- entities referenced across modules with no owner, or with an owner in a higher layer (A-4, F10);
- a trace table needed from step 1 with no schema (F11);
- master records used as foreign key targets but never defined (A-5);
- step 3 documents without names (F-3);
- a transfer order without an owner (P-1);
- outputs without owners (X-2, X-3);
- an incomplete lock list (A-8);
- missing safety invariants (A-7);
- catalog and glossary drift (A-6, L-1 to L-7).

All of these are technical (ADR-0005), except the scope of derivation traces, which is left to the author.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Layer-2 homes for runs, work items and attachments (chosen) | Every referrer imports downward | Three more modules |
| Keep them in `agents` (layer 5) | Fewer modules | Lower layers would import upward |
| One generic `derivation_trace` (chosen) | One way to explain any value | Typed references need care |
| A trace table per domain | Simple per domain | One reader per value type; violates "one way" |
| Rename the three keys | Rule 2 unchanged | Renames across many ADRs |
| Exception list in CI code | Quick | Hidden rule; a catalog column is data agents can read |

## Constraints that come with the decision

- **Accepted ADRs, notes or alignments:**
  - ADR-0009 rule 3, ADR-0012 rule 17, ADR-0014 rule 9, ADR-0015 rule 2 and its count, ADR-0019 rules 9, 12 and 14, ADR-0020 rule 7;
  - ADR-0022 rules 2 and 10, ADR-0023 rule 10, ADR-0024 rules 10 and 17, ADR-0026 rule 14.
- **Registry:** an effect class on every command, required with no default (ADR-0008 rule 1 note; DS-04).
- **DS-06:** `company`, `branch`, stubs for `cost_center` and `project`, `derivation_trace`; the employee reference fixed; header and RLS notes.
- **DS-16:** INV-07 restated; INV-57, INV-63, INV-80..83 added; group 80–89.
- **Backlog:**
  - DS-09: stock documents and write-down.
  - DS-11 and DS-22: customs in `purchasing`.
  - DS-20: master records.
  - DS-21: export.
  - DS-24: e-invoice in `tax`.
  - DS-25: provisions and prepaid.
  - DS-29: `work`.
  - DS-32: runtime only.
  - DS-33: management reporting.
  - DS-36: audit row per command and attachments.
- **Catalogs:** `transaction-keys.csv` gets the column `has_regime_alternatives`.

## Revisit when

- Attachment volume or retention needs a store per company.
- The author decides the trace scope.

## Documents updated

- **ADRs** (notes): [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0014-universal-journal.md](0014-universal-journal.md), [docs/adr/0015-account-determination.md](0015-account-determination.md), [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0026-open-item-core.md](0026-open-item-core.md).
- **Design and catalogs:** [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv), [docs/catalogs/transaction-keys.csv](../catalogs/transaction-keys.csv), [docs/design/backlog.md](../design/backlog.md).
- **Maps:** [docs/README.md](../README.md), [docs/design/README.md](../design/README.md), `docs/prompts/runbook-session.md`.
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md), covering the trace scope and the 911/421 verification.
- [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
