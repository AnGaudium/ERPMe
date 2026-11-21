Read-only review record of 2026-11-21 by Claude Opus 5.5: the costing design compared with SAP's practice. The SAP side is from the reviewer's knowledge and unverified. The author's six decisions of the same day on this comparison are in [decisions.md](../decisions.md) (costing note of 2026-11-21); the remaining points are the SAP comparison entry under "S2 closure (2026-11-21)" in [open-questions.md](../open-questions.md).

# Costing design against SAP practice (audit, 2026-11-21)

Scope: read-only audit of branch `s2-leftovers`. Sources read: ADR-0020 (all rules and
notes), ADR-0021, ADR-0035, ADR-0072, ADR-0068 (valuation parts), ADR-0011 (rules 6, 11, 16-18), ADR-0012 (rules 4,
10-16), ADR-0018 rule 3, ADR-0030 rules 1-4, ADR-0037 (costing parts), ADR-0044 rule 9, ADR-0009 rule 20,
ADR-0075 rule 2, `docs/catalogs/movement-types.csv`, spec 05, spec 08 "Costing", D6, and the open entries of
`docs/open-questions.md` on costing. No labs run. Nothing in the repository was changed.

Reference: the author's instruction of 2026-11-21. S/4HANA with the Material Ledger (ML) and actual costing
(price determination 3) sets the data model and methods; Business One only guides what a lean first release
contains. The SAP column below is the auditor's knowledge of the concept, not SAP documentation. Each SAP statement
has a confidence mark: H (high), M (medium), L (low). Treat any L line as a hypothesis to check before deciding on it.

Classes: `same`; `same concept, different name` (abbreviated `same-concept`); `deviation`; `not designed yet`.

## Summary

Topics: 39. Counts: `same` 7 · `same-concept` 10 · `deviation` 18 · `not designed yet` 4.

The 10 deviations that matter most, ranked by their effect on values and how far they are from the author's
instruction (one recommendation each):

1. **Preliminary valuation (topics 3, 4).** SAP posts every movement in the period at one fixed price per material
   (the standard price) and collects every difference in the ML. NativeFlows posts purchase receipts at document
   value and issues at a preliminary price. When the previous period has no actual price, that price can change
   inside the period (latest-receipt fallback, ADR-0020 rule 11). So stock value during the period is not
   quantity × price, and there is no per-item record of differences. Recommendation: **ask the author**. The
   architect's view: a fixed period price with collected differences fits D6 (periodic actual), but it changes
   ADR-0020 rules 4, 11 and 12.
2. **Price control (topic 1).** SAP sets S or V per material and valuation area, and the ML adds periodic actual on
   top. NativeFlows has one value, `periodic_average`, on the product (ADR-0018 rule 3; ADR-0020 rule 11).
   Recommendation: **keep NativeFlows' way for Phase 1 and record the reason** (D6; lean first release). Put the
   later per-area price control on SAP's key (material × valuation area), not on the product.
3. **Late costs for a locked period (topic 22).** SAP books a subsequent debit or credit in the current period: for
   V, to stock as far as stock covers it, the rest to price differences; for S with ML, as a current-period receipt
   difference. NativeFlows' interim `consumer_split` recomputes the locked periods and posts the difference to each
   past consumer's account (ADR-0021 rules 7, 8). Recommendation: **ask the author** (accounting rule; OQ on
   `landed_cost.closed_period_method`). SAP's way would be a third option that adds the cost to the current
   period's receipts.
4. **Late costs for an earlier period that is not locked (topic 23).** NativeFlows forces the document into the
   receipt's period, and interface price differences are dated back (ADR-0021 rule 6; ADR-0030 rule 2). SAP posts
   on the posting date entered, and the ML takes the cost into the period of that date. Recommendation: **adopt
   SAP's way** (a mechanism question; it removes the backdated accrual effect), confirmed together with item 3.
5. **Customer returns (topic 15).** NativeFlows values a return at the original delivery's issue cost, kept outside
   the average (`issue_return`; ADR-0020 rule 4 and 12 notes; delegated decision 2026-11-19, OQ-150). SAP's
   default (L) values a return receipt at the current valuation price and lets it enter the period's receipts.
   Recommendation: **ask the author**. The delegated decision and the "follow SAP" instruction now disagree.
   Check SAP's returns valuation first, because this SAP statement is low confidence.
6. **Exchange-rate differences between goods receipt and invoice (topic 8).** The ML keeps these separately and
   includes them in actual cost (M). In NativeFlows this is an open question (OQ "rate difference between goods
   receipt and purchase invoice"; ADR-0011 rule 6; ADR-0030 rule 4). Recommendation: **ask the author** (accounting
   rule), proposing SAP's treatment as the default.
7. **Planned delivery costs (topic 20).** SAP accrues freight and duty from purchase order conditions at goods
   receipt. NativeFlows has only costs allocated afterwards from `purchase_cost_clearing` (ADR-0021, "Revisit
   when"). Stock is undervalued between receipt and the cost invoice, and issues in that gap miss the cost until
   period end. Recommendation: **adopt SAP's way** as a later design item. Record now that Phase 1 omits it.
8. **Backdating window (topic 37).** SAP admits goods movements only in the current and the previous materials
   period. NativeFlows admits any period whose inventory area is not locked, and reruns costing for every later
   unlocked period (ADR-0012 rules 10, 16; ADR-0020 rule 14). Recommendation: **adopt SAP's way** as a company
   setting (a maximum number of open inventory periods behind the current one), so reruns stay bounded.
9. **Parallel currencies and valuations (topic 35).** The ML values stock in up to three currencies, each with its
   own actual costing (M), and can carry group and profit-center valuation (M). NativeFlows values inventory in
   company currency only (ADR-0011 rule 6). The group amount of stock and costing lines is not specified.
   Recommendation: **keep NativeFlows' way and record the reason** (B1 scope). Specify the group amount of costing
   adjustments before step 3.
10. **Value of a reversed material document (topic 36).** SAP reverses at the original document's value (H).
    NativeFlows leaves it to a flagged regime setting, interim the original value (ADR-0009 rule 20; ADR-0020
    rule 7; OQ "Value of a reversed material document"). Recommendation: **adopt SAP's way** as the core rule and
    close the open question with the author's confirmation.

Deliberate deviations with a reason in their ADR. They are not ranked above, but the author should know them:
- negative stock is never allowed (topic 12; Principle 9);
- every consumption is revalued (topic 11);
- order variances are not settled (topic 28; ADR-0035 Context);
- actual overhead goes through pools, not a costing sheet (topics 30, 31; ADR-0072 rule 21);
- abnormal cost and normal capacity (topic 29; IAS 2, the regime's choice);
- the `warehouse` valuation level (topic 2; spec 08);
- an exact solve instead of iteration (topic 6; ADR-0020 Options).

## Topic table

| # | Topic | SAP (confidence) | NativeFlows (rule) | Class; effect |
| --- | --- | --- | --- | --- |
| 1 | Price control and where set | Per material and valuation area in the material master: S (standard) or V (moving average). The ML with price determination 3 adds a periodic unit price (PUP), mostly with S (H). Whether V with price determination 3 is allowed in current S/4 releases: L | One value, `periodic_average`, on the product, the same for every area (ADR-0018 rule 3; ADR-0020 rule 11). Standard and moving average come after Phase 1 (spec 08; ADR-0020 "Revisit when") | deviation; one method for every item and area; no per-area choice. Deliberate (D6) |
| 2 | Valuation area level | Plant (usual) or company code, fixed in configuration; storage locations are never separate areas (H) | `company`, `site` (= plant, standard preset) or `warehouse` (ADR-0020 rule 2 and its ADR-0068 note; ADR-0068 rule 7); no change after posting (ADR-0020 rule 16) | deviation (additive); `site` matches SAP; `warehouse` has no SAP equivalent and adds a valuation event per internal move. Deliberate (spec 08, VN per-warehouse scope) |
| 3 | Preliminary valuation, purchased items | Every receipt and issue in the period at the standard price; GR at PO price posts the difference to price differences, collected in the ML (H). Next period's standard can be set from the previous PUP (M) | Issues at `preliminary_price`: N−1 actual; else latest receipt on or before the posting date; else purchase list; else last invoice; else manual (ADR-0020 rule 11 and notes). Purchase receipts post at document value (`value_source` `document`) | deviation; receipts carry actual value, so mid-period stock is not quantity × price, and the fallback price can change inside a period. Partly deliberate (spec 05 "receipt-versus-issue differences stay in inventory") |
| 4 | Preliminary valuation, produced items | Standard price from the released standard cost estimate; receipts from orders at standard (H) | Production receipts at the preliminary price: N−1 actual, else latest `production_output` receipt, else released estimate's unit cost (ADR-0020 rule 11; ADR-0035 rule 4; ADR-0072 rule 13) | deviation; the estimate is only a fallback, not the period price. Reason given in ADR-0072 rule 13 (one price per item and area) |
| 5 | Single-level price determination | PUP = (opening + receipts with their differences) ÷ (opening qty + receipt qty) per material and area; differences go to ending stock and consumption in proportion to quantity (H) | Actual average per area from opening plus receipts, including `receipt_addition` lines (ADR-0020 rule 12) | same |
| 6 | Multi-level price determination | Differences roll up through consumption to higher levels and through transfers; cycles are solved by iteration (M) | Strongly connected components in topological order, each solved exactly in rationals, over areas, transfers, orders, pools and WIP (ADR-0020 rule 12; ADR-0035 rule 6) | same-concept; exact, with no tolerance. Iteration rejected in ADR-0020 Options |
| 7 | Price differences in actual costing | Kept as an explicit difference amount per material and process category (H) | Not kept apart: actual value is in receipts, and revaluation posts the difference per offset key with a trace (ADR-0020 rule 12) | same-concept; per-item difference reports must be derived from traces |
| 8 | Exchange-rate differences | The ML keeps exchange-rate differences apart from price differences and includes them in actual cost (M) | Open: does the GR/invoice rate difference go to FX or to price difference and stock (OQ; ADR-0011 rule 6; ADR-0030 rule 4 status) | not designed yet |
| 9 | "Not distributed" differences | Differences that cannot go to stock or consumption (e.g. a quantity mismatch, negative stock); posted in closing to a price-difference account or carried forward (L on the target) | Degenerate cases keep the preliminary price; the residual goes per warehouse to `inventory_revaluation_offset` with a trace, interim and flagged (ADR-0020 rule 13) | same-concept; few cases, because stock cannot go negative |
| 10 | "Not allocated" differences | Consumption differences that cannot be passed on to the consumer, or that stay with the material when consumption is not revalued (M) | No such category: every consumer is revalued. On orders, leftover cost goes to COGS as `production_residual_cost` (ADR-0035 rule 10) | deviation (benign); no unallocated balance to explain |
| 11 | Revaluation of consumption | Optional; when on, consumption differences post to the consumer (COGS, cost center, order); when off, they stay on an ML offset account (M) | Always on, for every `revalued_issue`, `production_input` and transfer, each at its own offset key: sales, consumption, scrap, other issue, count shortage, free goods, quality sample (ADR-0020 rules 4, 12; movement-types.csv) | deviation; no "off" option. Deliberate (spec 05 "revalue inventory and COGS") |
| 12 | Negative stock | Allowed per plant, storage location and material when configured; differences then partly not distributed (H) | Never: `negative_stock` on any date from the posting date onward (ADR-0020 rule 10 and S2 note) | deviation; stricter. Deliberate (Principle 9) |
| 13 | GR/IR and invoice price differences | GR credits GR/IR at PO price; the IR clears it; the difference goes to stock (V, with coverage) or to price differences (S, collected in the ML) (H) | GR/IR at order price by unit positions; the difference goes as the regime's `price_difference` decides: to an account, or to stock through `landed_cost` `price_difference` (ADR-0030 rules 1-4; ADR-0021 rule 12) | same-concept; the target account is a regime setting |
| 14 | Purchase returns | Movement 122 reverses at the referenced receipt's value; it is a negative receipt in the ML (M) | Regime setting; interim seed: document value = the GR/IR debit, a negative receipt, no price difference (ADR-0020 rule 5 notes; ADR-0047 rule 13); landed cost share included by default (ADR-0063 note) | same; values agree under the interim seed, but the core requires a regime value |
| 15 | Customer returns | Return receipt valued at the current standard or moving price; enters the period as a receipt (L) | `issue_return`: the original delivery line's cost, outside the average, follows reruns (ADR-0020 rule 4, 5, 12 notes; OQ-150). The VN package still seeds (`document`, `receipt`) (OQ check_package) | deviation; returns never move the average. Deliberate (delegated 2026-11-19) |
| 16 | Transfer between areas, one step | Movement 301 at the issuing plant's price; the ML passes the issuing plant's actual cost to the receiver (M) | `transfer_out` at the issuing area's preliminary or actual price; `transfer_in` at the value that left; revalued in the solve (ADR-0020 rules 4, 6) | same |
| 17 | Two-step transfer, stock in transit | 303/305 or a stock transport order; stock in transit is a stock type, valued, usually in the receiving plant (M) | `transit` warehouse kind attached to a physical warehouse's area; `dispatch` and `receive` documents (ADR-0020 rule 1; ADR-0075 rule 2) | same-concept; which area owns transit is a per-warehouse setting, not fixed to the receiver |
| 18 | Physical inventory differences | 701/702 at the current valuation price; counted as consumption-type flows in the ML (L on the category) | Regime setting; seeds: shortage at preliminary price, revalued issue; surplus at preliminary price, receipt (ADR-0020 rules 5, 18 notes; ADR-0075 rule 15) | same-concept; the value source is a regime key instead of fixed |
| 19 | Scrap and internal consumption | 551 and 201 at the valuation price, to a cost center or order; revalued if consumption revaluation is on (H/M) | `scrap`, `internal_consumption`, `other_issue`, `quality_sample` as `revalued_issue` (movement-types.csv; ADR-0075 rules 1-6) | same |
| 20 | Planned delivery costs | PO conditions accrued to freight or customs clearing at GR, part of the receipt value (H) | None; costs wait in `purchase_cost_clearing` until a `landed_cost` allocates them (ADR-0021 rules 2, 3, "Revisit when") | not designed yet; receipt value is incomplete until the invoice |
| 21 | Unplanned delivery costs, same period | Entered at invoice; distributed to stock or price differences; in the ML part of receipt cost (H) | `landed_cost` allocates by value, quantity, weight or manual amounts; open mode adds `receipt_addition` before costing (ADR-0021 rules 4-6) | same-concept; a separate document, not an invoice field |
| 22 | Late invoice or cost, receipt period locked | Posted in the current period: V by stock coverage, rest to price differences; S/ML as a current-period difference (M) | `consumer_split` (interim): recompute the locked periods and post each consumer's share now; option `stock_coverage` (ADR-0021 rules 7, 8; ADR-0030 rule 2) | deviation; past COGS and consumption get the cost on their own accounts. Open OQ (VAS acceptance) |
| 23 | Late cost, receipt period earlier but not locked | Posted on its own date, in its own period (H) | Must be dated in the receipt's period (`landed_cost_period_mismatch`); interface price differences dated back (ADR-0021 rule 6; ADR-0030 rule 2) | deviation; creates the backdated accrual effect. Interim, flagged |
| 24 | Subcontracting | Components at the vendor as special stock, valued in the plant (541); GR consumes them (543) plus the service fee; in the ML a procurement alternative (H) | Processor as a physical warehouse with our stock; materials sent by transfer; service receipt backflushes `production_issue` and posts the fee to `production_cost_other` of a production order (ADR-0037 rules 1-6) | same-concept; at level `warehouse` the processor is its own area. SAP keeps it in the plant |
| 25 | Planned (preliminary) costing | Standard cost estimate per material; preliminary cost estimate per order (H) | `cost_estimate` per production version, released as the benchmark; costing sheet and costing lot size (ADR-0035 rule 14; ADR-0072 rules 6-9). No stored per-order planned cost | same-concept |
| 26 | Target cost and variance categories | Target = standard estimate × delivered qty; categories: input price, quantity, resource usage, remaining input, scrap, lot size, output price (H) | Target from the released estimate scaled to received qty; `GetProductionOrderVariance` with SAP's categories except output price (ADR-0035 rule 15) | same |
| 27 | Work in process | WIP at actual (debits minus deliveries) or at target, computed per period for orders not finally delivered (H) | WIP by units in process: `direct_material` (default), `equivalent_units`, `planned_cost`, by component (ADR-0035 rule 9 and notes) | deviation; a different method, partly assumption-driven. Deliberate (TT99 methods; flagged settings) |
| 28 | Settlement and variances | Order credited at standard at delivery; at period end variances settle to price differences and the ML rolls them into actual cost (H) | No variance posting; the solve values output at actual directly; WIP and pool steps in the settlement document (ADR-0035 rules 5, 11, 12, 15) | deviation; same end value under actual costing, fewer postings. Deliberate (ADR-0035 Context) |
| 29 | Abnormal cost, normal capacity | No IAS 2 abnormal-cost step; idle capacity shows as under-absorption on the cost center through capacity-based activity prices (M) | Abnormal cost at completion and unabsorbed fixed overhead above normal capacity go to COGS (ADR-0035 rules 7, 10) | deviation (additive); regime-flagged (ADR-0035 rule 18) |
| 30 | Overhead by costing sheet | Costing sheet in estimates and actual overhead on orders at period end, crediting cost centers; over- or under-absorption stays on the cost center (H) | Costing sheet for planned costing only (ADR-0072 rules 1, 6-9); actual overhead through pools allocated by driver; absorption shown only by `GetCostCenterAbsorption` (ADR-0072 rules 12, 21) | deviation; no absorption postings. Deliberate (seam in ADR-0072 rule 21; OQ standard cost) |
| 31 | Activity prices, cost-center absorption | Plan activity price charged at confirmation; actual price at period end; activity revaluation at actual in the ML (M) | Confirmations post nothing; pools allocated by actual quantities at period end; `activity_rate` only for estimates and projections (ADR-0035 rules 4, 7, 14; ADR-0072 rule 14) | deviation; no in-period activity cost on orders (projection only). Deliberate (linearity) |
| 32 | Co-products and by-products | Co-products by apportionment or equivalence numbers; by-product credited at a fixed price (H) | Co-products by `cost_coefficient` or relative sales value; by-product at the regime's `by_product` price list, final (ADR-0035 rules 11, 13) | same |
| 33 | Cost component split and roll-up | Up to 40 components; roll-up through levels; an actual cost component split per material in the ML (H/M) | 4 posting components plus up to 12 detailed ones, in estimates and per order and period (ADR-0072 rules 2-5); no actual component split per item and area | deviation; actual component split stops at the order, not carried through stock. 12 chosen for one report row (ADR-0072 rule 2) |
| 34 | Split valuation (valuation types, batches) | Valuation category and types per material; batch-level valuation uses the batch as the type (H) | Reserved nullable `valuation_type` on `stock_value` and material lines, CHECK-null in Phase 1 (ADR-0020 rule 17 notes; rule 8 note) | not designed yet; seam reserved |
| 35 | Parallel currencies and valuations | ML in up to 3 currencies, each actual-costed on its own; optional group and profit-center valuation (M) | Inventory value only in company currency (ADR-0011 rule 6); the group amount on costing lines is not specified | deviation; no group valuation, no actual cost in group currency |
| 36 | Reversal of material documents | Reversal movement (102, 262, 302 …) at the original document's value (H) | Regime setting, interim the original line's value; GR and delivery by return documents (ADR-0009 rule 20; ADR-0020 rule 7 and notes) | not designed yet (open OQ); the interim equals SAP |
| 37 | Backdated postings, closed periods | Only the current and the previous materials period are open; the ML closing shuts a period, and a rerun first reverses the closing (M) | Any unlocked inventory period accepts postings; costing of it and later unlocked periods goes stale and reruns post differences; locked never recosted (ADR-0012 rules 10, 12, 15, 16; ADR-0020 rule 14) | deviation; a wider window, longer rerun chains |
| 38 | Opening balances at migration | 561 with an external value; the ML treats it as the opening (M) | `opening_balance` at document value; opening value ÷ qty is the first preliminary price (ADR-0020 rule 11; ADR-0044 rule 9) | same |
| 39 | Ending inventory at period close | Closing revalues ending stock at the PUP; the next period starts from it or from a new standard (M) | Revaluation brings stock to the actual average; closing value is the next opening; N−1 actual becomes N's preliminary price (ADR-0020 rules 11, 12) | same-concept |

Class tally (39 rows):
- same 7: rows 5, 14, 16, 19, 26, 32, 38;
- same-concept 10: rows 6, 7, 9, 13, 17, 18, 21, 24, 25, 39;
- deviation 18: rows 1, 2, 3, 4, 10, 11, 12, 15, 22, 23, 27, 28, 29, 30, 31, 33, 35, 37;
- not designed yet 4: rows 8, 20, 34, 36.

Items for `docs/open-questions.md` (not written, read-only task): the SAP low-confidence statements in rows 1, 9,
15 and 18 need checking against SAP material before the author decides items 1, 2 and 5. The group amount of stock
and costing lines (row 35) has no rule.
