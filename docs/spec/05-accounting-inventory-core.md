# Accounting and inventory core modeled on SAP

The accounting and inventory core follows SAP's long-proven model: S/4HANA for the data model, Business One for SME scope and leanness. Learn the concepts and the organization; do not copy SAP documentation and do not use SAP trademarks in the product. Learning from ERPClaw (an open ERP designed for agents, built ERPNext-style) was considered and rejected: its source code showed the ledger and inventory core are not correct enough (amounts stored as strings, original lines mutated on cancellation, no revaluation after backdated documents, sales returns received at selling price).

| Concept | Applied as | Why |
| --- | --- | --- |
| Document principle | Every posting is a document with header and lines. No deletion, no edit; only reversal by a reversal document, which passes the same period checks as any document | Already Principle 5 |
| Universal journal | One journal-line table carrying every dimension: company, account, partner, item, warehouse, cost center, project, amounts in several currencies. AR/AP subledgers and inventory value are views over this table | Subledgers reconcile to the GL by construction, not by reconciliation |
| Material and accounting documents | Quantity movements are material documents, values are accounting documents, linked one-to-one in the same transaction | Inventory and GL never drift |
| Several currencies per line | Transaction currency, company currency, optional group currency | Foreign-invested companies report to a parent |
| Two-tier chart of accounts | A fixed system chart in the core and an operational chart per company; each operational account points to exactly one system account (many-to-one) | Core, agents, management reports and consolidation work only with system accounts; companies detail freely. Same pattern as D365 F&O and SAP |
| Automatic account determination | Transaction key (inventory posting, offsetting entry, GR/IR clearing, price difference, cost of goods sold…) × item valuation class × valuation area → account | Every automatic posting has one deterministic source of accounts |
| Movement types | A configuration table decides whether a stock movement increases or decreases stock, how quantity and value update, and which transaction keys apply | Purchase receipt, sales issue, transfer, assembly issue and return are configuration, not separate code |
| GR/IR clearing account | Goods receipt credits the clearing account; the invoice clears it; price differences go to inventory value or a price-difference account | Three-way match on both quantity and price |
| Price control per item | Standard price or moving average during the period | Used as the preliminary price |
| Period-end actual costing | At period end compute the actual periodic unit cost, solving all warehouses and BOM levels together, then revalue inventory and COGS | This is VAS periodic weighted average; the existing costing engine maps onto it |
| Delivery costs and subsequent debits | Landed cost goes to inventory value for the quantity still on hand; the share for quantity already issued goes to price difference or COGS | Landed cost stays correct even when goods are partly sold |
| Posting periods | Open and close per company and per account type; special periods for year-end adjustments | Complements the three period states |
| Open-item FX revaluation | Revalue each unpaid invoice; how the difference is booked is set by the localization package | Matches the AR/AP subledger and each country's rules |
