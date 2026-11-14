# Shared foundation

These capabilities are built from the start: multi-company, configurable accounting regimes, multi-currency, multiple units of measure, approval engine, document lifecycle, data storage and extensibility. Every document, journal line and command depends on them, so adding them later is very expensive. "Built from the start" means the data model supports them from day one; the matching features and UI follow the scope labels.

## Multi-company

Every business table has `company_id` from day one, because adding it later means rewriting everything. Small Vietnamese businesses often have several tax IDs or dependent branches. A branch is an analytical dimension with its own document series and e-invoice symbol when needed. Consolidation and intercompany transactions come later, but the schema must not block them.

## Accounting regimes as configuration

An accounting regime (`accounting_regime`) is part of a localization package (see [Multi-country and localization packages](06-localization.md)): chart template, financial statement and book templates, FX rules and closing rules. The customer picks one when creating a company.

- **TT99/2025** (replaces TT200 from 2026-01-01) and **TT133** for small and medium businesses. Most target SMEs use TT133, but Build steps 1–9 use TT99 first because it is the complete and newest regime. TT133 is added in step 10 as the second regime of the Vietnam package, which also tests the regime mechanism. Whether TT133 is being replaced: unverified.
- TT99 lets a company design its own documents, books and detailed accounts under its internal accounting policy, so the package must be extensible by the customer.

## Multi-currency

- **Several currencies stored:** every document and journal line stores transaction currency, company currency (VND for a Vietnamese company) and optional group currency, with the rate applied. The GL and statutory reports use company currency; subledgers can be tracked in transaction currency.
- **FX rules are configuration of the accounting regime, never hard-coded:**
  - Transaction rate at recognition, including an approximate rate where the regime allows it.
  - Book rate at payment or settlement, by moving weighted average or specific identification.
  - Rate and accounts used for period-end revaluation.
  - Rate source: the commercial bank the company uses, fetched daily.
- **Balancing:** every journal entry balances in each transaction currency, in company currency and in group currency. Rounding differences from conversion go to a rounding line on a defined system account (DS-02 and DS-06 decide which).
- **Realized FX differences** on payment post to 515 or 635 (Vietnam).
- **Period-end revaluation** of foreign-currency monetary items. Receivables and payables are revalued per open item; cash, bank and loan balances are revalued at balance level. Advances to suppliers and from customers are non-monetary and are not revalued. **Verify against the original TT99 text** (Appendix II, accounts 413, 515, 635): secondary sources disagree on whether buy and sell rates are still separated or an average transfer rate is used, and whether differences still pass through 413 or go straight to 515/635. This rule must therefore live in the package configuration.
- **Inventory cost is always in company currency.** Foreign purchase prices convert at recognition. Import costs: see [Imports and purchase costs](08-l10n-vn.md#imports-and-purchase-costs).
- **Rate types are separate:** a foreign-currency invoice stores its invoice rate separately from the book rate; the customs duty rate is separate from the accounting rate.
- **For agents:** FX impact can be simulated before closing, and every difference can be explained.

## Units of measure

- (Phase 1) **UoM group per item** ([ADR-0018](../adr/0018-product-and-item-model.md): inventory unit and product units per product), in the style of Business One: stock unit, purchase unit, sales unit, with fixed item-specific factors (a carton is 24 bottles for one item and 12 for another).
- (After Phase 1) **Independent second unit (catch weight):** record the actual quantity in the second unit (e.g. kg) per movement, with no fixed conversion; price may be per second unit.
- **Convention:** stock and cost are always in the stock unit. Conversion happens in the command layer on document intake, so the costing engine never knows other units.
- **Barcode per packaging unit:** scanning a carton barcode converts to the stock unit.
- **Rounding:** rules per unit. Rounding differences must never silently land in cost.
- (Phase 1) **Lots and serials** are tracked in stock movements and carry no cost of their own.
- (Phase 1) **Bins and warehouse management** (author's decision 2026-11-14; [ADR-0023](../adr/0023-warehouse-management.md)).

## Approval engine

The policy engine decides whether an action needs approval and which procedure applies. The approval engine never evaluates conditions itself; it only executes the procedure the policy returns, so each rule is declared in one place. Both serve humans and agents.

- **Declarative approval procedures**, in the style of Business One:
  - Document type, initiating human or agent.
  - Conditions: amount, discount, credit limit exceeded, margin, price below cost, price outside price list.
  - (After Phase 1) Multiple levels, sequential or parallel, minimum approvers per level.
  - (After Phase 1) **Delegation and escalation:** delegate when absent, escalate when overdue. Pending approvals live in the shared work queue.
- **Approval channels:** Phase 1 approves on the web. (After Phase 1) Email notification with an authenticated link, mobile app, chat apps.
- **Agents prepare the approval file:** reason summary, comparison with history, risks. Agents never approve on a human's behalf.
- **Approval decisions are immutable,** carry a reason, attach to the document and bind to the hash of the document version; a new version invalidates the approval.
- The same approval engine serves documents, master data and promoting customizations to production. Phase 1 approves at one level by threshold.

## Document lifecycle, numbering and posting periods

- **Document states:** Draft (editable, versioned) → Pending approval → Approved → Posted (immutable) → Reversed.
- **Numbering:** drafts use a temporary ID. The official number is assigned only at posting, in the same transaction, from a gapless series table per document type, fiscal year of the posting date and branch.
- **Posting periods:**
  - Open: normal posting.
  - Soft-locked: only the chief-accountant role can post; agents cannot.
  - Locked: nobody can post. Reopening requires approval and leaves a trace.
- **Sequence:** periods are costed and closed strictly in sequence. A period cannot be locked while an earlier one is open.
- **Backdated documents** in an open period re-cost that period and the following open periods only. The costing engine posts adjustment documents and never edits old lines.
- **Close postings:** costing, FX revaluation and closing entries are posted by actor `system` on behalf of the human who triggered the close.
- **Arithmetic:** `Decimal` only. Precision for quantity, unit price, company currency and foreign currency is declared centrally.

## Data storage and synchronization

No full event sourcing. Use state tables, an append-only journal and a transactional outbox, written in one transaction. This decision governs every module and is fixed now.

- **Background jobs:** a technical queue on PostgreSQL (`SKIP LOCKED`, reading the outbox), separate from the business work queue.
- **Read models:** state explicitly which update synchronously and which asynchronously. Period-closing balances are stored.
- (After Phase 1) **Offline mobile app:** commands queue with idempotency keys. On stock conflicts the server rejects and creates a work item.

## Extensibility and upgrades

A partner's first question is "how do I customize for a customer without forking and still upgrade?"

- (After Phase 1) **User-defined fields and tables**, in the style of Business One UDF/UDT, declared as metadata. They appear automatically in command schemas, MCP and the self-describing layer.
- **Module boundaries:** modules call each other only through commands and events, checked automatically by import-linter. Plugins (after Phase 1) register before/after-command hooks and never write tables directly.
- **Command schemas are a public API:** versioned (semver) with a deprecation policy.
- **Upgrades for self-hosters:** automatic DB migrations, upgrade tests from version N-2, LTS releases, a Docker Compose deployment kit with backup and restore.
