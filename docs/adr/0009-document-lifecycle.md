# ADR-0009: Document lifecycle

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Design item: DS-05. Related decisions: D4, D5. Principles 1, 3, 5, 6, 8, 9. ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008. Amended before its first merge (2026-11-14) by the author's decision on corrections (rules 1, 2, 19, 20, 23), reviewed by Claude Fable 5.2: a posted document is corrected by a correction document; internal document types can be reversed; whether unreferenced outside-party documents may be reversed is flagged. Amended by [ADR-0028](0028-document-lifecycle-hardening.md) (line identity, change orders, e-invoiced documents, approval context).

## Decision

Every document has one row in a shared `document` table (type, company, state, version, number) plus its own typed header and line tables sharing that `id`. Each document type declares whether it posts. Posting types move `draft → (pending_approval →) approved → posted → reversed`, or `draft → posted` when the policy needs no approval; non-posting types (orders, quotations, requests) share the states `draft`, `pending_approval`, `approved`, `closed` and `canceled`, and their further behavior belongs to DS-22. Every change to an unposted document creates a new version with a hash; an approval binds to that version, and a new version voids it. Posting assigns the official number from a gapless series in the same transaction and makes the document immutable. A posted document is corrected by a correction document that refers to it (a return, a credit note, an adjustment or replacement invoice); internal document types, which no outside party holds, can instead be reversed by a reversal document. Points that are business or legal rules (when orders are numbered, what happens when a document that may not wait for approval needs one, number format and order, how a reversal posts, whether outside-party documents nothing refers to yet may be reversed, who posts corrections) are flagged configuration with open questions for the author.

### Rules

**Documents and types**

1. Every document has a row in `document` with `id`, `company_id`, `document_type`, `state`, `version`, `number` (null until numbered), `branch_id` (nullable), `reversal_of_id` (nullable) and `correction_of_id` (nullable, rule 23). Its typed header table (e.g. `goods_receipt`) has the same `id` as primary key and foreign key to `document`; its lines are in `<header>_line` (ADR-0004 rule 10), each with a `line_number` unique within the document. Versions, approvals, numbering, reversals, work items and audit records refer to `document.id`. Line numbers are line identity; references and immutability of referenced lines: [ADR-0028](0028-document-lifecycle-hardening.md) rules 1–3. Agent-drafted documents also carry `origin_work_item_id`, `workflow_step` and `draft_ordinal` ([ADR-0030](0030-commercial-seams-and-imports.md) rule 11).
2. Each document type is registered once with: `document_type` (a glossary noun, `snake_case`), `is_posting` (it posts to the journal or stock), `is_approval_hold_allowed` (rule 12), `is_reversible` (rule 19, default false) and its numbering (rule 15). The registry generates its commands from the verb list: `Create`, `Update`, `Delete`, `Submit`, `Approve`, `Reject`, `Cancel`; `Post` and, if reversible, `Reverse` for posting types; `Close` for non-posting types. `Submit`, `Approve` and `Reject` are not generated for types with `is_approval_hold_allowed: false`. Types also declare `is_change_order_allowed` and `is_e_invoice_capable` ([ADR-0028](0028-document-lifecycle-hardening.md) rules 4, 6). Per-type commands added: `Issue<Type>`, `Reopen<Type>`, `Recall<Type>`, `Complete<Type>Posting`, `CancelChange<Type>`; `RecordEInvoiceOutcome` is one command in `tax` ([ADR-0028](0028-document-lifecycle-hardening.md)).
3. Which document types exist and their fields are decided by the DS items that own them (DS-06, DS-09, DS-22, DS-25). Documents created by system jobs (costing adjustments, FX revaluation, closing entries; DS-09, DS-10, DS-12) are ordinary documents created and posted through the same commands by actor `system` (ADR-0008 rule 2). Attachments (module `attachments`, [ADR-0027](0027-cross-cutting-ownership.md)), the supplier's own number on incoming documents (DS-22, DS-24), field permissions and personal data inside version content (DS-15), and documents between companies (after Phase 1) are outside this ADR. `open_item_matching` and the open-item rules are [ADR-0026](0026-open-item-core.md).

**States of posting types**

4. States are stored in `document.state` (ADR-0004 rule 14). For posting types (E-invoiced types add `issuing` (draft → issuing → posted | draft); orders with change orders add `change_state`; an approved document may be resubmitted (approved → pending_approval) after `approval_context_changed` ([ADR-0028](0028-document-lifecycle-hardening.md) rules 4, 6)):

| From | To | Command |
| --- | --- | --- |
| — | `draft` | `Create<Type>` |
| `draft`, `pending_approval`, `approved` | `draft` (new version) | `Update<Type>` |
| `draft` | `pending_approval` or `approved` | `Submit<Type>` (rule 11) |
| `pending_approval` | `approved` / `draft` | `Approve<Type>` / `Reject<Type>` |
| `draft` (policy allows without approval), `approved` | `posted` | `Post<Type>` |
| `posted` | `reversed` | `Reverse<Type>` (posts the reversal document) |
| `draft`, `pending_approval`, `approved` | `canceled` | `Cancel<Type>` |
| `draft` (never submitted, not referenced) | row deleted | `Delete<Type>` |

5. Any other transition is rejected with `invalid_state_transition`, naming the current state and the commands allowed from it. `posted`, `reversed` and `canceled` are final. `issuing` is not final; allowed commands in it: [ADR-0028](0028-document-lifecycle-hardening.md) rule 6.

**Non-posting types**

6. Non-posting types use the states `draft`, `pending_approval`, `approved`, `closed` and `canceled`, with the same `Create`, `Update`, `Submit`, `Approve`, `Reject`, `Cancel` and `Delete` rules as rule 4. An order is in force only once `approved` (by an approver, or directly through `Submit` when the policy needs no approval), so a live order is never a draft. `Close` moves an `approved` document to `closed`: it ends further activity on a document that has had some; `Cancel` ends one that has had none. What an `Update` of an approved order that is partly fulfilled does, and whether an order closes automatically when fulfilled, are decided by DS-22, which owns the commercial state machines. Updating an approved order with change orders: [ADR-0028](0028-document-lifecycle-hardening.md) rules 4–5 (replaces the delegation to DS-22).
7. `Delete` and `Cancel` are rejected with `document_referenced` when another document refers to the document (e.g. a delivery to an order); which references count (e.g. from canceled or reversed documents) is decided by DS-22. Fulfilment progress (quantities delivered or invoiced) is computed from the referring documents, never stored as a state. Superseded in part: the open delivery or receipt quantity of a stock line is stored once, in `demand_supply_line`; invoiced and fulfilled progress stay computed ([ADR-0031](0031-design-simplifications.md) rule 5). Documents in `issuing` count as fulfilling ([ADR-0028](0028-document-lifecycle-hardening.md) rule 9).
8. When and by which date a non-posting document gets its number is an open question for the author. Interim, flagged rule: it is numbered when it first becomes `approved`, from the series of the fiscal year that contains its `document_date`, and keeps its number if canceled.

**Versions**

9. `Create` writes version 1. Every `Update` writes the next version and returns the document to `draft`, voiding any submission or approval. Each version is a row in `document_version` (`id`, `document_id`, `version`, `content`, `version_hash`, `recorded_at`, `actor_kind`, `actor_id`, `on_behalf_of_id`, `agent_run_id`, `origin_agent_run_id`; ADR-0017 rule 16), unique on (`document_id`, `version`). `content` is the canonical JSON (ADR-0008 rule 12 forms) of the header fields and the lines ordered by `line_number`, without IDs of the document and its lines, `state`, `version`, `number` and system timestamps; `version_hash` is its SHA-256. For posting types `posting_date` is a document field set by `Create` or `Update` and is part of the content, so changing it voids an approval. `Post` carries `posting_date` explicitly (ADR-0007 rule 8), and it must equal the document's field; otherwise the command is rejected with `posting_date_mismatch`, so the approved content stays bound. The typed rows are authoritative; an invariant (DS-16) checks that the current version's `content` equals the content computed from them. Exception: change orders keep the version in force and write a pending version ([ADR-0028](0028-document-lifecycle-hardening.md) rule 4). Versions also carry an immutable `is_tainted` and a nullable `derived_from_version_id`; a human clears taint with an immutable `taint_clearance` row ([ADR-0029](0029-proposals-and-agent-safety.md) rules 8, 9).
10. Every command that changes a document (`Update`, `Submit`, `Approve`, `Reject`, `Post`, `Close`, `Cancel`, `Delete`, `Reverse`) carries `version`, the version the client last read, and locks the `document` row first. If `version` is not current, the command is rejected with `version_conflict`, naming the current version. Commands on a pending change carry `pending_version` ([ADR-0028](0028-document-lifecycle-hardening.md) rule 4).

**Approval**

11. `Submit` asks the policy engine (DS-28) and stores its outcome in a `policy_decision` row bound to the current `document_version_id` (Principle 3 outcomes: allow, deny, approval required, human only). Allow: the document becomes `approved` without an approver. Approval required: it becomes `pending_approval`. Deny: the command is rejected with `policy_denied`. Human only: as allow, but only a human may post it. `Post` from `draft` asks the policy the same way and is rejected with `approval_required` if an approval is needed. An approval is an immutable `approval` row: `document_version_id`, decision (`approved` or `rejected`), `reason` (required), `actor_kind`, `actor_id`, `on_behalf_of_id`, `decided_at`. `Post` of an `approved` document uses what is bound to its current version (an `approved` approval row, or an allow or human-only `policy_decision`) and does not ask the policy again; `Post` from `draft` asks the policy and stores the decision the same way. How the policy applies to `Reverse`, which binds to the original's last version, is decided by DS-28. Who may approve, including segregation of duties, is DS-15 and DS-28. Approval context: [ADR-0028](0028-document-lifecycle-hardening.md) rule 14. Policy is evaluated once at the policy points of [ADR-0029](0029-proposals-and-agent-safety.md) rule 6, which replaces this rule's separate statement; decision fields: rule 7.
12. A document type whose issuance has a legal deadline (e.g. a sales invoice issued as an e-invoice) is registered with `is_approval_hold_allowed: false`, because the approval queue must not delay issuance ([08-l10n-vn.md](../spec/08-l10n-vn.md#e-invoicing-and-tax)). What happens when the policy requires approval for such a document is an open question for the author. Interim, flagged rule: the outcome is treated as human only, so a human posts it directly and no agent can. Which types carry the flag is set by DS-22 and DS-24. For e-invoiced types the policy is asked at `Issue` ([ADR-0028](0028-document-lifecycle-hardening.md) rule 7).

**Posting, immutability and numbering**

13. `Post<Type>` runs the period checks (DS-12), assigns the number, writes the journal entry, the material document or both (DS-06, DS-09), and sets `state = posted` and `posted_at`, in one transaction. E-invoiced types post by a consumer on acceptance, with the plan frozen at `Issue` ([ADR-0028](0028-document-lifecycle-hardening.md) rule 7).
14. Database triggers make documents in a final state (`posted`, `reversed`, `canceled`, `closed`) immutable: every `INSERT`, `UPDATE` and `DELETE` on their header and line rows, and every change to their `document` row, is rejected, except `Reverse` changing `document.state` from `posted` to `reversed` and nothing else. `document_version`, `policy_decision` and `approval` rows are never updated or deleted. A reversal document, like every document, is inserted as `draft` and posted in the same transaction, so the trigger never blocks it. Data that arrives after posting (e-invoice form, symbol and number from DS-24) is stored in its own tables that refer to the document. DS-06 adds the same protection to journal and material document rows. The same immutability applies in `issuing` ([ADR-0028](0028-document-lifecycle-hardening.md) rule 6).
15. Numbers come from `numbering_series` rows keyed by (`company_id`, `document_type`, `fiscal_year_id`, `branch_id`), unique with `NULLS NOT DISTINCT`, with `prefix`, `next_value` and `format`. A company configures, per document type, a prefix, whether series are per branch, and a format; the series row for a fiscal year is created on first use from that configuration. Format placeholders are `{prefix}`, `{branch_code}`, `{fiscal_year_code}` and `{counter:N}` (zero-padded to at least N digits, never wrapping). `document` has a unique constraint on (`company_id`, `document_type`, `number`). The counter is read and incremented only through the numbering lock helper (ADR-0008 rule 10), inside the transaction that numbers the document, so a rolled-back posting leaves no gap and postings of one series are serialized. Lock helpers take stock locks before numbering locks; a deadlock between batches is returned as the retryable `concurrent_update`.
16. The default format, whether numbers must follow posting dates when documents are backdated, and whether reversals use the original type's series are user-visible rules and open questions for the author. Interim, flagged rules: format `{prefix}/{fiscal_year_code}/{counter:6}`, or `{prefix}/{branch_code}/{fiscal_year_code}/{counter:6}` for branch series; numbers follow posting order; reversals use their type's series.
17. Drafts are referred to by `id`. Numbers of e-invoices are assigned by the e-invoice process (DS-24) and stored by it (rule 14).

**Reversal**

18. `Reverse<Type>` is `human_only` (ADR-0008 rule 2). It carries the original's `version` and an explicit `posting_date`, creates a reversal document of the same type and company with `reversal_of_id` pointing to the original (unique, so a document is reversed at most once, in full), posts it with its own number through the same period checks as any document, and sets the original to `reversed`, in one transaction. It emits `<Type>Posted` for the reversal document and `<Type>Reversed` for the original. Preconditions when later documents depend on the original (a matched invoice, an allocated payment, consumed stock) are set by DS-09, DS-22 and DS-25. Preconditions for documents whose open items were settled: [ADR-0026](0026-open-item-core.md) rule 11.
19. `is_reversible` is set per document type (default false) by the DS item that owns the type, within these rules. Author's decision, 2026-11-14: a posted document is corrected by correction documents (rule 23); only internal document types can be reversed. E-invoiced types are posted only on acceptance ([ADR-0028](0028-document-lifecycle-hardening.md) rule 6). `production_issue`, `operation_confirmation` and `production_receipt` are internal and reversible ([ADR-0034](0034-production-orders-and-shop-floor.md) rules 11–13).
    - Internal types, reversible: manual journal entries and stock documents between the company's own warehouses (transfers, stock counts). A transfer accompanied by an internal transport e-document cannot be reversed until that legal point is answered (open question); DS-24 adds this as a `Reverse` precondition.
    - Documents the company records from or issues to an outside party (goods receipts, deliveries, payments, purchase invoices): whether they may be reversed while nothing refers to them, as SAP and Business One allow, or only corrected, is an open question for the author. Interim, flagged rule: reversible while no document that is not reversed or canceled refers to them.
    - Sales invoices and every document issued as an e-invoice: never reversible; corrected by adjustment or replacement invoices ([08](../spec/08-l10n-vn.md#e-invoicing-and-tax)).
    - Documents created by system jobs (costing adjustments, FX revaluation, closing entries): reversibility is decided by DS-09, DS-10 and DS-12.
    - For every reversible type, `Reverse` is rejected with `document_referenced` while a document that is not reversed or canceled refers to the document.
20. Whether the reversal posts negative amounts (storno) or swapped debit and credit, which posting date it defaults to when the original period is locked, and the value of a reversed material document are accounting rules: configuration of the localization package, flagged until the author decides (existing open questions). The core provides both reversal methods.
21. A reversal document cannot itself be reversed; to restore a transaction, a new document is created. Interim rule, listed as an open question for the author.

**Events**

22. Every transition emits an event `<Type><event form>` through the outbox (`GoodsReceiptPosted`, `SalesOrderClosed`; ADR-0004 rule 22, DS-13).

**Correction documents**

23. A correction document is an ordinary posting document of a correction type (`sales_return`, `purchase_return`, `credit_note`, `debit_note`, adjustment or replacement invoice) whose `correction_of_id` points to the posted, not reversed, original of the same company. A reversal document cannot be the original of a correction.
    - It is created from the original in one command: `Create<CorrectionType>` takes `correction_of_id` and the lines to correct and copies their data from the original, so the user or agent changes only what differs.
    - `correction_of_id` is set at `Create`, never changed, and part of the version content (rule 9), so an approval binds to it.
    - An original may have several correction documents, each correcting part of it (some lines, a quantity, a price). Limits on the cumulative correction (e.g. returns never above the quantity delivered) are set by DS-22 and checked by a DS-16 invariant.
    - A correction document is itself a posted document and may be corrected the same way.
    - It goes through the same states, approval, period checks and numbering as any document; it posts in an open period even when the original's period is locked.
    - A correction that fully offsets its original undoes a posted document, which the spec reserves to humans ([14-agent-workflows.md](../spec/14-agent-workflows.md)). Who may post correction documents is an open question for the author. Interim, flagged rule: agents may create and submit correction drafts; only a human may post them (`Post<CorrectionType>` is registered `human_only`, ADR-0008 rule 2).
    - Which correction types each document type allows, their fields and their accounting and stock effect (including the cost of a sales return, an existing open question) are decided by DS-09, DS-22 and DS-24.

## Context

DS-05 is needed by DS-06 (journal), DS-09 (inventory), DS-12 (periods), DS-22 (commercial documents) and DS-28 (approval). Constraints:

- States draft → pending approval → approved → posted (immutable) → reversed; numbering at posting from a gapless series per document type, fiscal year of the posting date and branch ([07-shared-foundation.md](../spec/07-shared-foundation.md#document-lifecycle-numbering-and-posting-periods)).
- Posted documents are immutable; a posted document is corrected by a correction document, or, for internal documents, reversed by a reversal document; open commercial documents can be edited and every edit creates a new version (Principle 5). Approvals are immutable, carry a reason and bind to the hash of the document version (07, approval engine). The policy engine returns allow, deny, an approval procedure, or human only (Principle 3).
- Orders do not post; e-invoice issuance is never delayed by approval (backlog DS-05; [08-l10n-vn.md](../spec/08-l10n-vn.md)). DS-22 owns the state machines of commercial documents (backlog).
- Closing periods and reversing posted documents are human only ([14-agent-workflows.md](../spec/14-agent-workflows.md)).
- ADR-0005: business and legal rules go to the author; among correct technical options, the one easiest for AI agents wins.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Shared `document` table plus typed tables (chosen) | One place for state, version, number; real foreign keys for approvals, versions, work items | Two rows per document |
| Polymorphic references `(document_type, document_id)` without a shared table | One row per document | No foreign keys; every query must know the type's table |
| One generic table for all document headers | One table | Untyped columns; loses the per-type schema that commands and agents rely on |
| Version snapshots as canonical JSON in one table (chosen) | One hash rule for every type; approvals compare one value | Content duplicated per version |
| Optimistic concurrency by `version` on every changing command | No locks held while a person edits; conflicts are explicit | Clients must send the version |
| Orders in force while in `draft` | One step fewer | A live order would stay deletable and editable without trace of release |
| Number from a PostgreSQL sequence | Fast | Sequences survive rollback and leave gaps |
| Post-posting review for documents that may not wait for approval | Issuance never blocked | Relaxes an approval the policy asked for; a business decision for the author |

## Constraints that come with the decision

- DS-04: errors `invalid_state_transition` (precondition), `version_conflict` (conflict), `document_referenced` (precondition) in the catalog; the numbering helper and lock order.
- DS-06: journal and material document rows protected like rule 14; both reversal methods supported.
- DS-09, DS-22, DS-25: reversal preconditions; DS-22: commercial state machines beyond rule 6.
- DS-12: period checks at posting and reversal.
- DS-13: one event per transition.
- DS-15, DS-28: who may submit, approve and post; segregation of duties; policy outcome per document type.
- DS-16: invariant that version content matches the typed rows.
- DS-22, DS-24: correction document types (return, credit note, debit note, adjustment and replacement invoices), their `Create…` commands from an original and their accounting effect; e-invoice numbers in their own tables; `is_approval_hold_allowed` for invoice types.
- Glossary: states `canceled` and `closed`, verb `Close`, the registry flags.

## Revisit when

- (Triggered: [ADR-0028](0028-document-lifecycle-hardening.md) added the state `issuing` and change states.)

- Posting throughput of one numbering series is measurably limited by the counter row lock on the medium replay.
- A document type needs a state outside rules 4 and 6.

## Documents updated

- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): document state row; verb `Close`; rows for document type, its flags, document version, approval and numbering series.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): three error codes.
- [docs/design/backlog.md](../design/backlog.md): DS-05 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): numbering of non-posting documents; approval for documents that may not wait; number format and order; reversing outside-party documents; internal transport e-documents; who posts corrections; reversing a reversal; the three reversal questions linked to rule 20.
- [docs/spec/02-principles.md](../spec/02-principles.md): Principle 5 wording on corrections.
- [docs/spec/08-l10n-vn.md](../spec/08-l10n-vn.md), [docs/spec/14-agent-workflows.md](../spec/14-agent-workflows.md): wording on corrections.
- Glossary rows for reversal document and correction document; the note on Cancel.
- [docs/spec/05-accounting-inventory-core.md](../spec/05-accounting-inventory-core.md): document principle row.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
