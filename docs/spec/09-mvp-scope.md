# MVP scope and not-doing list

The MVP covers the full chain of a trading and manufacturing business, assembly included: CRM, purchasing, sales, inventory, production and accounting. The not-doing list is written down to hold the line, because an ERP always pulls toward doing everything.

| Area | In MVP | Later |
| --- | --- | --- |
| Partners and CRM | Phase 1: one partner with many roles, contacts, interaction timeline, email intake, quotations. After Phase 1: leads and opportunities, simple pipeline, activities and appointments, chat channels | Marketing automation, complex territories and targets, call center, call recording |
| Items | Items, UoM groups per item with fixed factors (stock, purchase, sales unit), item groups, price lists, product configurator (Phase 1, [ADR-0046](../adr/0046-product-configuration.md)) | Catch weight after Phase 1 |
| Sales | Quotation → order → delivery → invoice, returns, trade discounts, promotions, credit limit | POS, e-commerce, consignment |
| Purchasing | Purchase request → PO → goods receipt → invoice, returns, imports and landed cost | Tenders, blanket agreements |
| Inventory | Phase 1: multiple warehouses, lots and serials (tracked in stock movements, no cost of their own), barcode, stock count and differences; warehouse management (author's decision 2026-11-14; feature list proposed in [ADR-0023](../adr/0023-warehouse-management.md), pending the author's confirmation) | Wave picking (proposed for Phase 1, pending confirmation), slotting optimization |
| Production (Phase 1, [ADR-0032](../adr/0032-phase-1-scope-with-production.md)) | Multi-level bills of materials, routings and work centers, production orders and shop floor confirmations, assembly and disassembly orders, subcontracting, production costing (cost = components + allocated costs) | Advanced quality management beyond the core of [ADR-0070](../adr/0070-quality-management-core.md) (statistical process control, full CAPA and 8D, audits) |
| Accounting | Two-tier chart, Vietnam package (TT99 and TT133), basic US package, double-entry ledger, multi-currency and FX revaluation, cash, advances, AR/AP and netting, banking, VAT and 01/GTGT XML, e-invoicing, posting periods, statutory books, financial statements including B03 | Fixed assets and loans (right after MVP), consolidation |
| Costing | Periodic weighted average per warehouse or company, with preliminary price (previous costed period's average, or latest receipt price) | Moving average, FIFO, standard cost (revisit under TT99) |
| Planning | Phase 1 ([ADR-0024](../adr/0024-planning.md), [ADR-0036](../adr/0036-multi-level-mrp.md)): reorder point, min/max and time-phased netting per item and warehouse, multi-level MRP with bills of materials, transfer routes, weekly forecast with Tết-anchored event indices, planned orders converted to drafts, exceptions per buyer | — |
| Other | Approval engine, work queue, read-only query layer, data migration and opening balances | Payroll, HR, projects, helpdesk |

B03 (cash flow statement) is part of the mandatory annual statements, so it is in the MVP. For TT133 customers this needs confirmation (unverified).

The MVP is Phase 1; Phases 2 and 3 are post-MVP. **This scope is beyond one person if done at once**, so it is split into the phases in the [Roadmap](10-roadmap.md). "[Shared foundation](07-shared-foundation.md)" means the data model supports it from the start; the matching features and UI (catch weight, multi-level approval) may come in later phases.
