# MVP scope and not-doing list

The MVP covers the full chain of a trading and assembly business: CRM, purchasing, sales, inventory, assembly and accounting. The not-doing list is written down to hold the line, because an ERP always pulls toward doing everything.

| Area | In MVP | Later |
| --- | --- | --- |
| Partners and CRM | Phase 1: one partner with many roles, contacts, interaction timeline, email intake, quotations. After Phase 1: leads and opportunities, simple pipeline, activities and appointments, chat channels | Marketing automation, complex territories and targets, call center, call recording |
| Items | Items, UoM groups per item, item groups, price lists | Product configurator; catch weight after Phase 1 |
| Sales | Quotation → order → delivery → invoice, returns, trade discounts, promotions, credit limit | POS, e-commerce, consignment |
| Purchasing | Purchase request → PO → goods receipt → invoice, returns, imports and landed cost | Tenders, blanket agreements |
| Inventory | Multiple warehouses, bins, lots and serials, barcode, stock count and differences | Wave picking, slotting optimization |
| Assembly (Phase 2) | Multi-level BOM, assembly and disassembly orders, cost = components + allocated costs | MRP, routing, operations, shop floor, quality |
| Accounting | Two-tier chart, Vietnam package (TT99 and TT133), basic US package, double-entry ledger, multi-currency and FX revaluation, cash, advances, AR/AP and netting, banking, VAT and 01/GTGT XML, e-invoicing, posting periods, statutory books, financial statements including B03 | Fixed assets and loans (right after MVP), consolidation |
| Costing | Periodic weighted average per warehouse or company, with preliminary price | Moving average, FIFO, standard cost (revisit under TT99) |
| Other | Approval engine, work queue, read-only query layer, data migration and opening balances | Payroll, HR, projects, helpdesk |

B03 (cash flow statement) is part of the mandatory annual statements, so it is in the MVP. For TT133 customers this needs confirmation (unverified).

The MVP is Phases 1 and 2; Phase 3 is post-MVP. **This scope is beyond one person if done at once**, so it is split into the phases in the Roadmap. "Shared foundation" means the data model supports it from the start; the matching features and UI (catch weight, multi-level approval, serials, multi-level BOM) may come in later phases.
