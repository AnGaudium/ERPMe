# ADR-0069: Business unit dimension

Status: proposed (2026-11-17) under ADR-0005 (builder Claude Opus 5.5).
Design items: DS-06 (universal journal), DS-20 (master data), DS-22 (commercial documents), DS-28 (settings), DS-33 (analysis), DS-04 (errors), DS-16 and DS-17. Related decisions: D5; the author's request of 2026-11-17. Principles 6, 7, 13. ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0010, ADR-0012, ADR-0014, ADR-0015, ADR-0018, ADR-0022, ADR-0027, ADR-0035, ADR-0045, ADR-0047, ADR-0048, ADR-0050, ADR-0060, ADR-0063, ADR-0068.

## Decision

The author's decision of 2026-11-17: a **business unit** splits activity into lines of business. It is an analysis dimension, not a legal or organizational entity: no numbering, currency or books of its own. A company keeps a tree of business units in `master_data`. Every journal line gains a nullable `business_unit_id` (ADR-0014 rule 9: a new dimension is a nullable column added by ADR). At posting, `ledger` fills it on profit-and-loss lines by a fixed order, first match wins: the line's explicit unit, then the defaults of the item's product, the cost center, the project, the document header, the site and the company. The line records which source won, and one derivation trace per entry records every candidate. Two company settings set the fallback unit and whether a P&L line may stay without one. Phase 1 reports P&L and gross margin per unit. A balance sheet per unit (document splitting) and the allocation of shared costs come later, on the column that is already on every line.

### Rules

**The business unit**

1. `business_unit` (owner `master_data`, company data, `master_data_change`, change-tracked; agents propose changes, ADR-0029 rule 2): `id`, `company_id`, `code`, `name`, `parent_id`, `is_active`, `recorded_at` ([DS-20-master-data.sql](../design/DS-20-master-data.sql)).
   - **Code.** Unique in the company. It cannot change once a journal line, a master record, a document or the company default names the unit (`business_unit_invalid`), because group reporting matches units across companies by `code`.
   - **Tree.** `parent_id` names a unit of the same company. The command refuses a cycle (`business_unit_invalid`). Any unit may receive postings; a roll-up sums a unit and its descendants.
   - **Nothing else.** No legal role, branch, numbering, currency or ledger. Branches stay the legal and tax unit (ADR-0009) and sites the physical one (ADR-0068).
2. Active and inactive units:
   - **New references.** Master data, document headers and lines may name only an active unit of their company, otherwise `business_unit_invalid`.
   - **Deactivation** is refused with `business_unit_in_use` while an active cost center, product, open project, active site or `ledger.business_unit.default` names the unit, so derivation never meets an inactive default.
   - **Drafts.** A draft that names a unit deactivated since is refused at posting with `business_unit_invalid`.
3. Commands and queries (module `master_data`, leaf `organization`): `CreateBusinessUnit`, `UpdateBusinessUnit` (`master_data_change`, `is_proposal_bound`), `ListBusinessUnit`, `GetBusinessUnit`.

**The dimension**

4. `journal_line` gains two nullable columns:
   - **`business_unit_id`**, a key to `business_unit` within the company.
   - **`business_unit_source`**, the step that set it: `line`, `item`, `cost_center`, `project`, `document`, `site`, `company_default`, `reversal` or `closing`. It is null exactly when the unit is null.
   - **Index:** `(company_id, business_unit_id, posting_period_id)` where the unit is set.
5. **Only profit-and-loss lines carry a unit in Phase 1.** A P&L line is a line whose system account has `account_type` `income` or `expense` (ADR-0010 rule 3), read from the line's `system_account_id`. Balance-sheet lines never carry one, `income_summary` and retained earnings included, and a unit stated on one is refused with `business_unit_invalid`. A per-unit balance sheet half filled would mislead, so it waits for document splitting.
6. Not carried, each for a reason:
   - **Material document lines.** They hold quantity and stock value, which are balance sheet. The P&L journal line that posts a movement, cost of goods sold for example, carries the unit and refers to its material line.
   - **Open items.** Receivables and payables per unit need document splitting (later). An open item reaches the units of its origin document's P&L lines through that document.
   - **Tax lines** (ADR-0041): balance sheet.

**Defaults on master data and documents**

7. Nullable `business_unit_id` defaults, each naming an active unit of the same company:
   - **`product.business_unit_id`.** In the derivation, "the item's unit" is its product's unit, read through the item, as item group and valuation class are (ADR-0018 rule 3). Variants share a line of business, so a unit per item would only be repeated. Item group was rejected because it already drives revenue and cost accounts (ADR-0015 rule 7), and a split by unit would multiply groups and determination rows.
   - **`cost_center.business_unit_id`** and **`project.business_unit_id`** (ADR-0045 rule 9).
   - **`site.business_unit_id`**, on the table of ADR-0068.
8. Documents:
   - **Headers.** Every commercial document header of ADR-0047 carries a nullable `business_unit_id` that a person or an agent sets: quotation, sales order, delivery, return from customer, sales invoice, sales return, credit and debit note, purchase request, purchase order, goods receipt, service receipt, return to supplier, purchase invoice, purchase return, and supplier credit and debit note.
   - **Copying.** `Create<Type>` with `source_lines` copies the source header's unit into an empty header. It can be changed until posting. Sources with different units leave the header empty unless the command states one (ADR-0047 rule 2).
   - **Lines.** The lines on which a person assigns an account carry an explicit `business_unit_id`: purchase invoice lines, payment `account` lines and general journal lines (ADR-0048 rule 15).
   - **Sales lines** have no line unit in Phase 1: the product and the header decide. A generic service product left without a unit lets the header decide.

**The derivation**

9. `ledger` derives the unit at posting, inside the posting transaction, for every P&L line of the entry. First match wins:
   1. the explicit unit of the document line;
   2. the unit of the line's item (its product);
   3. the unit of the line's cost center;
   4. the unit of the line's project;
   5. the document header's unit;
   6. the unit of the site of the line's warehouse (a transit or goods-sent warehouse through its valuation warehouse, ADR-0068);
   7. `ledger.business_unit.default`, or none.

   Inputs:
   - **From the posting module:** the explicit line unit and the header unit, in its posting request.
   - **From master data:** the other candidates, through the hook `business_unit_defaults`, which `ledger` declares, `master_data` registers and `app` wires (ADR-0022 rule 2). `ledger` and `master_data` share layer 3, so no import is added.

   The function `ledger.contract.derive_business_unit` is pure. A conflict, such as an item unit that differs from the cost center's, is not an error: the first match wins and the trace keeps the losing values.
10. **Account determination.**
    - **Order.** The derivation runs after ADR-0015 has chosen the account, because it needs the account's system account type.
    - **Independence.** It never feeds account determination. A business unit is not a determinant (ADR-0015 rule 3), so one set of determination rows serves every unit.
11. Two kinds of lines copy their unit instead of deriving it:
    - **Reversals.** A reversal document repeats the original's lines (ADR-0014 rule 8) with their units, source `reversal`.
    - **Closing entries.** They close each P&L account per business unit, and each closing line takes the unit of the balance it closes, source `closing` (ADR-0012 rule 18).

    Every other document derives anew, corrections included (ADR-0009 rule 23).
12. The trace:
    - **When.** One `derivation_trace` per journal entry with at least one P&L line, in a company that has at least one `business_unit` row. A company without units skips the derivation entirely: no trace, every unit null.
    - **Content.** `rule_code` `business_unit_derivation`, `rule_version` `1`. `inputs` holds the header unit, the setting row in force and the master rows read. `steps` holds, per line number, the seven candidates in order, each a unit or null. `result` holds, per line number, the unit and the source.
    - **Link.** It is named by the new nullable `journal_entry.business_unit_trace_id`. `journal_line.derivation_trace_id` stays costing's (ADR-0027 rule 3).
    - **Visible before posting.** The trace is part of the posting plan (ADR-0008 rule 12), so a simulation shows each line's unit and why.
    - **Scope.** The author's 2026-11-17 decision makes this derivation a trace writer under ADR-0027 rule 4. That is the author's scope decision.

**Policy**

13. Settings (ADR-0063 rule 1; [settings.csv](../catalogs/settings.csv)), area `ledger`, scope `company`, leaf `company_setting`, effect `immediate`, outdates `none`:
    - **`ledger.business_unit.default`:** the `code` of an active unit of the company. Core default `unset`; direction `neutral`. It needs the new value type `code`: one code whose table the bounds name (`business_unit`), checked by the command.
    - **`ledger.business_unit.required_on_profit_and_loss`:** boolean, default `false`, `true_tighter`.
14. The requirement:
    - **The check.** While the requirement is true, the posting logic rejects a P&L line that has no unit after the derivation, with `business_unit_missing`. The rejection comes in the simulation and in the execution. `details` names the line, its system account, the candidates tried and the commands that fill one.
    - **Exempt:** reversal and closing lines (rule 11), so documents posted before the setting can still be reversed and closed.
    - **Where.** The check is posting logic, not the trigger, like the control-account setting (ADR-0014 rule 10).
    - **The fallback warning.** Realized exchange differences, rounding lines and bank charges without a cost center find a unit only through the company default. `UpdateCompanySetting` therefore returns the check result `business_unit_default_unset` when the requirement is true and no default is set.

**Never retroactive**

15. Posted lines never change (ADR-0014 rule 13):
    - **Read at posting.** The derivation reads master data and settings as they stand in the posting transaction. A later change to a product, cost center, project, site, header or company default affects only later postings, as a changed determination row does (ADR-0015 rule 12). Nothing re-derives posted lines.
    - **Moving posted amounts** to another unit takes a general journal on the same account, with explicit units on both lines and the approval of ADR-0048 rule 15.
    - **The tree is not frozen.** It is read when a query runs, so re-parenting a unit regroups history, as a reorganized report should.

**Reporting and deployment**

16. Analysis (ADR-0060 rules 5, 34):
    - **The dimension `business_unit`:** kind `entity`, column `business_unit_id`, a tree over `parent_id` with a `business_unit_path` column, low cardinality, label `internal`.
    - **Facts:** `journal_line_overview` and `system_account_turnover`, whose grain gains the unit (ADR-0050 rule 53).
    - **Grouping** uses the posted value only. Balance-sheet lines and P&L lines without a unit form the member `none`.
    - **Measures.** `net_revenue`, `cost_of_goods_sold`, `gross_profit` and the other P&L measures answer per unit with no new measure.
17. **CRM-only deployments.** `business_unit` lives in `master_data`, so quotations and sales orders carry a unit without `ledger`. The derivation and the two settings belong to `ledger` and are absent there.
18. **Later, as seams** (backlog):
    - **Balance sheet per unit (document splitting).** Derivation extends to balance-sheet lines with splitting rules; `open_item` may then gain the column.
    - **Allocation of shared costs.** Allocation documents post P&L lines with explicit units.

    Neither needs a migration of posted lines.
19. Catalog rows:
    - **Settings:** 2 definitions.
    - **Dimension:** `business_unit`; with ADR-0068's `site` and `payment_method`, the catalog then holds 25 dimensions.
    - **Errors** (DS-04): `business_unit_missing` and `business_unit_in_use` (precondition), `business_unit_invalid` (validation).
    - **Check result:** `business_unit_default_unset`.
    - **Authorization:** the leaf `organization` also covers business units.
    - **Invariants and edge cases:** INV-820 to INV-823 and EC-270 to EC-273 below.
    - **DDL:** [DS-20-master-data.sql](../design/DS-20-master-data.sql) (the table and the master data defaults), [DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql) (journal columns), [DS-22-09-42-commercial-inventory.sql](../design/DS-22-09-42-commercial-inventory.sql) (headers and purchase invoice lines), [DS-05-platform.sql](../design/DS-05-platform.sql) (payment lines), [DS-28-settings.sql](../design/DS-28-settings.sql) (value type `code`).

## Context

- **The ask.** Companies with several lines of business want P&L and margin per line without separate legal entities. Nothing in the design did this: no business unit, profit center or segment. Cost centers answer "who spent", not "which business earned".
- **Practice.** In SAP S/4HANA the profit center, rolled up to a segment, plays this role. Revenue and cost of goods take it from the material per plant, and expenses from the cost center. A balance sheet per profit center needs document splitting. Dynamics 365 uses a financial dimension "Business unit" with default values on master records.
- **Constraints.** A dimension, not an entity (the author, 2026-11-17). A new dimension is a nullable column added by ADR (ADR-0014 rule 9). Accounts are found by ADR-0015 alone. Derived values are explained (Principle 6). Settings live in one registry (ADR-0063). The CRM-only profile must not depend on `ledger` (author, 2026-11-17).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Product-level default, read through the item (chosen) | One value for all variants; same place as item group and valuation class | No per-variant unit; none is needed |
| Item-level default | Finest grain | Repeated on every variant; easy to leave inconsistent |
| Item group default | Few rows | Couples account groups to business units; more determination rows |
| Units on P&L lines only in Phase 1 (chosen) | Every per-unit figure shown is complete | No per-unit balance sheet until splitting |
| Derive on every line | Column filled everywhere | Receivables, tax and stock per unit would be partial and misleading |
| Source on the line, candidates in one trace per entry (chosen) | "Where from" needs no join; one trace row per entry; costing keeps `derivation_trace_id` | A new entry column |
| One trace per line in `derivation_trace_id` | Reuses the column | Collides with costing traces; one row per line |
| Derivation in `ledger` through a master data hook (chosen) | One function for every posting module; no import across layer 3 | A hook to wire |
| Each posting module derives | No hook | Seven copies of one order |

## Constraints that come with the decision

- DS-06: the journal columns, `journal_entry.business_unit_trace_id`, the P&L-only check in posting logic, INV-820 to INV-822.
- DS-20 and ADR-0068: the table, the master data defaults, the hook `business_unit_defaults`.
- DS-22, DS-05: header and line columns; copying by ADR-0047 rule 2.
- DS-28: value type `code`. DS-33: the dimension and the `system_account_turnover` grain.
- DS-12 (closing): closing per account and unit.
- Lab: `tNN_business_unit.py` checks that the order is deterministic, that conflicts resolve to the first match, that reversals copy, that the trace reproduces every line's unit, and that the requirement and its exemptions hold.

## Revisit when

- A company needs a balance sheet, receivables or cash per unit: document splitting (rule 18).
- Shared costs must reach units in Phase 1 reports: allocation (rule 18).
- A product's unit must differ by site, as SAP's per-plant profit center: a site-specific default on the product.
- A sales line needs its own unit against its product's.
- A company needs different accounts per unit: a determinant in ADR-0015.

## Documents updated

- **ADRs** (notes tagged "ADR-0069, proposed 2026-11-17"): ADR-0014 rules 1, 9; ADR-0015 rule 3; ADR-0012 rule 18; ADR-0018 rule 3; ADR-0022 rule 2; ADR-0027 rule 4; ADR-0045 rule 9; ADR-0047 rule 2; ADR-0048 rule 15; ADR-0050 rule 53; ADR-0060 rule 34; ADR-0063 rules 1, 29.
- **Catalogs:** [settings.csv](../catalogs/settings.csv), [analysis-dimensions.csv](../catalogs/analysis-dimensions.csv), [authorization-areas.csv](../catalogs/authorization-areas.csv), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv).
- **Design files:** DS-20, DS-06, DS-22-09-42, DS-05, DS-28 (rule 19); [DS-04-command-envelope.md](../design/DS-04-command-envelope.md) (errors, check result); DS-16, DS-17; the architecture overview and core; [backlog.md](../design/backlog.md) (the two seams).
- **Glossary:** [00-reading-guide.md](../spec/00-reading-guide.md): business unit, business unit source.
- **Index and log:** [README.md](README.md); [step-log.md](../runbook/step-log.md).

## Edge cases and invariants

**Invariants** (DS-16; block INV-820 to INV-829, INV-820 to INV-823 taken; first step 1):

- **INV-820** `business_unit_profit_and_loss_only` (ledger): every journal line with a unit has a system account of type `income` or `expense`; `business_unit_source` is null exactly when the unit is null.
- **INV-821** `business_unit_derivation_reproducible` (ledger): for every entry with a `business_unit_trace_id`, each line's unit and source equal the trace's result. That result is the first non-null candidate of the line's steps, or the copied unit for `reversal` and `closing` lines.
- **INV-822** `business_unit_required` (ledger): no P&L line other than a reversal or closing line was posted without a unit while `ledger.business_unit.required_on_profit_and_loss` was true.
- **INV-823** `business_unit_tree` (master_data): every unit's parent belongs to its company and the tree has no cycle; every active cost center, product, open project and active site, and the company default, names an active unit of the company.

**Edge cases** (DS-17; block EC-270 to EC-279, EC-270 to EC-273 taken; first step 5):

- **EC-270** `business_unit_conflict_first_match`: a delivery's cost-of-goods line for a product of unit A, from a site of unit B, on an order whose header names C: the line gets A with source `item`, and the trace lists B and C.
- **EC-271** `business_unit_required_missing`: with the requirement on and no default, a payment's realized exchange difference is rejected with `business_unit_missing`; after a default is set it posts with source `company_default`.
- **EC-272** `business_unit_default_not_retroactive`: a product's unit changes from A to B; the reversal of an earlier invoice keeps A (source `reversal`), a new invoice gets B, and analysis shows both.
- **EC-273** `business_unit_expense_line`: a purchase invoice expense line with a cost center of unit A gets A; a second line with an explicit unit D gets D with source `line`.
