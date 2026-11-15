# ADR-0037: Subcontracting

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-55 (new). Related decisions: D6. Principles 2, 6, 12, 13. ADR-0005, ADR-0009, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0020, ADR-0022, ADR-0023, ADR-0024, ADR-0027, ADR-0028, ADR-0029, ADR-0030, ADR-0032, ADR-0033, ADR-0034, ADR-0035, ADR-0036. Research: [reference systems](../research/2026-11-14-production/01-reference-systems.md) ("Subcontracting"), [Vietnamese rules](../research/2026-11-14-production/02-vietnam-rules.md) ("Processing").

## Decision

Subcontracting, gia công in Vietnamese, has two directions. This ADR designs them differently:

| Direction | This ADR |
| --- | --- |
| **We subcontract** (thuê gia công): we send our materials to a processor and receive the processed goods | Designed in full. Assembly-type manufacturers, the Phase 1 target (ADR-0032), outsource operations such as plating, painting or machining |
| **We process for a customer** (nhận gia công): the customer's materials come to us | Seams only, plus a requirements list. It makes customer-owned stock flow through availability, planning, issue and costing. Whether it enters Phase 1, with customs reporting for processing, is the author's question (open question). If it does, a follow-up item designs it on these seams |

Outsourced work runs on the production core:
- A production order has an external operation.
- Components are moved, still ours, to a warehouse that stands for the processor.
- The service is bought on a purchase line tied to the operation.
- A service receipt records progress, consumes the components at the processor, posts the service cost to the order and can receive the output.

### Rules

**We subcontract: locations and materials**

1. A processor location is a `physical` warehouse with `processor_partner_id` (ADR-0020 rule 1 gets the column), not bin-managed. A company has at most one active location per processor.
   - **Ownership.** Stock there is ours and valued, in the area the company's valuation level gives (ADR-0020 rule 2).
   - **Inventory key.** Its stock lines use a new inventory key `inventory_at_processor_posting`, with the inventory leaves and determinants valuation class and warehouse. A regime can therefore show stock at processors on its own account. TT99: the same accounts as ordinary stock ([ADR-0039](0039-vietnam-package-tt99.md) rule 8).
   - **Accounting at sending.** Interim, flagged: materials stay inventory until the service receipt consumes them, as in SAP. TT99 describes 154 at sending (research note 02). Choosing that is the author's (open question), and it would need the transfer to post per order.
   - **Sending.** Materials go there by an ordinary transfer, moving quantity and value (ADR-0020 rule 6). No invoice is issued for materials sent to a domestic processor (Decree 254/2026/NĐ-CP Art. 7, unverified). Whether an internal transport document is needed is the regime's setting (DS-24).
   - **Allowed movements.** Only transfers in and out, production issues and returns, count differences and opening balances (stock at processors at cut-over) may post at a processor location. Anything else is rejected with `movement_not_allowed_at_processor`.
2. External operations (ADR-0033 rule 10):
   - **The operation.** It names `service_item_id` (a `service` product) and `default_supplier_id`. On the order, `production_order_operation` holds the chosen supplier.
   - **Components.** Components assigned to the operation have the supplier's processor location as their issue warehouse. They are demand lines there, so planning supplies them through a transfer route from the production warehouse to that location. A missing route raises `planning_parameter_missing` (ADR-0034 rule 9 and ADR-0036 rule 1 get notes).
   - **Backflush.** ADR-0034 rule 2's backflush-warehouse rule gets an exception: such components are consumed at the processor location by the service receipt (rule 5). Serial-tracked components are issued there manually.
   - **Whole-item subcontracting.** A routing whose only operation is external.
3. Lead time:
   - **The value.** An external operation's duration is `supplier_processing_days` of the supplier's `supplier_item` for the service item, on the supplier's calendar, plus the transit days of the routes to the processor and back (ADR-0024 rules 2, 3). Without a `supplier_item`, its routing durations apply, on the production warehouse's calendar.
   - **Where it applies.** Order scheduling (ADR-0034 rule 3) and `plan_production` both use this duration.
   - **Use.** `plan_production` (ADR-0036 rule 3) receives these values with the structures it loads.
   - **Load.** External operations load no work center.
4. Buying the service:
   - **Drafting.** Releasing an order emits its approval event (ADR-0009 rule 22). A `purchasing` consumer drafts one purchase request line per external operation (ADR-0024 rule 22 pattern, actor `system`), for the service item and the operation's planned quantity at the supplier's price. The line carries `production_order_operation_id`, a typed line reference that ADR-0028 rule 2 reserves to the author under B3, so it is flagged (open question).
   - **Repeat release.** A re-release drafts nothing twice: the consumer's key is the operation.
   - **Changes to the order.** A change of G updates a draft line, or creates a work item when an order line exists. `Cancel` and technical completion cancel open draft lines, or create a work item for open order lines.
   - **Changing supplier.** Choosing another supplier after release is a change order on the production order (ADR-0034 rule 8): component issue warehouses move to the new location, and staged stock moves by transfer.

**We subcontract: the service receipt**

5. `service_receipt` is a posting document type owned by `purchasing`, for purchase order lines that carry `production_order_operation_id`.
   - **Reversibility.** It records a supplier's delivery, so it follows `goods_receipt`'s flagged interim (ADR-0009 rule 19; ADR-0027 rule 13): reversible while no invoice refers to it, otherwise corrected by a correction document.
   - **Scope.** Its record scope uses the processor location as the warehouse dimension (ADR-0017 rule 9), and it emits the ADR-0009 document events.
   - **Fields.** Yield, scrap, `is_final`, and, for automatic receipt, the output lot.
   - **Posting, in one transaction:**
     - progress, through `production.contract.record_operation_progress` (ADR-0034 rule 12);
     - the backflush of the operation's components at the processor location, by cumulative progress and rounded up, as `production_issue` with the order's cost object. `record_operation_progress` computes and posts it and stores the generated lines in the production-owned `operation_progress_component`, keyed by the calling posting document, as for confirmations. `service_receipt` holds only its own lines.
     - the service cost: debit `production_cost_other` (order), credit GR/IR clearing at the order price with `purchase_order_line_id` (ADR-0030 rules 3–5), key `production_external_service`;
     - when the operation is the order's last, of either control, and the version sets automatic receipt, the output into the production warehouse (ADR-0034 rule 13 gets a note).
   - **Missing stock.** Too little stock at the processor rejects the receipt with `negative_stock`.
   - **Reversal.** Refused once an invoice refers to the receipt. Otherwise it reverses, in this order: the automatic receipt, the backflush, the cost and the progress.
   - **Agents.** A receipt drafted from a processor's delivery note is tainted (ADR-0029 rule 10), so a human posts it. Simulation applies as for any command.
6. Afterwards:
   - **Invoice differences.** The invoice clears GR/IR at the order price (ADR-0030 rule 4). A service has no pending receipt adjustment, so a difference posts straight to the order's `production_cost_other` while the order is not closed, and after close to the price-difference account, never the stock-bound path, since a service has no receipt lines. Both are interim and flagged. After close the difference posts without a valuation class, so it reaches the generic price difference row ([ADR-0039](0039-vietnam-package-tt99.md) rule 8).
   - **Actual consumption.** When the processor reports actual consumption, a `production_issue` or return at the processor location adjusts the order.
   - **Leftovers** come back by transfer.

**We process for a customer: seams and requirements**

7. Seams reserved now, so the follow-up needs no change to stock rows, order lines or demand lines. A contract reference on stock document lines and a value source would still be added:
   - **Columns.** `owner_partner_id` on `production_order_component`, `production_order_output` and `demand_supply_line`. This extends ADR-0030 rule 8's axis, which already covers stock rows, material lines, warehouse movements, reservations and tasks. The `demand_supply_line` column is flagged for the author under B3 (ADR-0028 rule 2).
   - **Phase 1 default.** Every row has a null owner, so nothing changes for own stock.
8. Requirements for the follow-up design, if the author brings it into Phase 1:
   - **Per owner.** Available to promise, reservation, netting and pick removal run per owner. An issue line's owner chooses a quantity-only customer movement type, or `production_issue`.
   - **Costing.** Order quantities are read by order line, whatever the costing role. Customer components are valued at zero and left out of price-based drivers, estimates and abnormal cost. The order's output share posts debit cost of goods sold, credit `inventory_work_in_process`.
     - **Timing.** At receipt, or held in 154 until the fee revenue: the author's choice.
   - **Documents and catalogs.**
     - customer material receipt and delivery documents with a contract reference;
     - count differences, scrap and transfers of customer stock;
     - a value source `none` and its movement types.
   - **Customs.**
     - a regime per processing contract, not per company;
     - customs codes per item;
     - contract norms and their precedence over bills of materials;
     - actual norms and quantity ledgers as derived queries in the customs unit;
     - leftover and report deadlines as regime settings;
     - the year-end disclosure of materials held for others (DS-26).

   Note: "held in 154" reads "held in work in process (e.g. 154 in TT99)" ([ADR-0053](0053-core-neutrality.md) rule 14).

**Checks and catalogs**

9. Catalog changes, version 0.x. The transaction keys become 46 (ADR-0015):

   | Key | Accounts | Control kind | Determinants |
   | --- | --- | --- | --- |
   | `production_external_service` | `production_cost_other` | `cost_object` | none |
   | `inventory_at_processor_posting` | the inventory leaves | `inventory` | valuation class, warehouse |

10. Catalog rows reserved in the production range (ADR-0033 rule 16):
    - **INV-111:** every material line at a processor location has one of the allowed movement types of rule 1.
    - **INV-112:** every `operation_progress_component` line written for a service receipt refers to a component line of the same order and to a material line with movement type `production_issue` at that order's processor location.
    - **Edge cases:**
      - whole-item subcontracting, with a service receipt that consumes components and receives output;
      - a processor's actual consumption above the backflush;
      - an invoice difference before and after the order closes;
      - a supplier change after release;
      - a reversal of a service receipt.
11. Commands and errors:
    - **Commands.** Document commands follow ADR-0009. Posting a service receipt is effect class `posting`, under policy as a purchase document (DS-28).
    - **Errors and check results:** `movement_not_allowed_at_processor`, `negative_stock` (existing), and `service_receipt_without_operation` for a line without `production_order_operation_id`.

## Context

Research note 01 describes subcontracting in SAP (special stock at the vendor, consumption at receipt, subsequent adjustment), Odoo (subcontracting bills of materials, resupply routes) and Dynamics 365 (service items on route operations). Research note 02 gives the Vietnamese accounting:
- materials sent out stay ours and the processing fee adds to cost;
- materials received for processing are not our inventory and are disclosed;
- invoice and customs rules.

Direction 1 reuses the production core:
- processor locations as warehouses;
- transfers;
- external operations;
- service purchase lines;
- the service receipt as the consumption trigger.

The first review showed that direction 2 touches availability, planning, issue and costing everywhere. Designing it in full for a scope the author has not confirmed would add risk, so this ADR reserves its seams and lists what the follow-up must decide.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Processor as a warehouse with our stock (chosen) | Transfers, balances and valuation already exist | One warehouse per processor |
| Special stock type at vendor | SAP's model | A new stock axis beside owner and warehouse |
| Both directions in full now | Complete | Direction 2 reaches into every netting and costing rule, for an unconfirmed scope |
| Direction 2 as seams plus requirements (chosen) | No structural rework later; scope stays the author's | A follow-up design if confirmed |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0015 (key count 46);
  - ADR-0020 rule 1 (`processor_partner_id`, the processor inventory key);
  - ADR-0024 rule 22 (service lines drafted by a consumer);
  - ADR-0028 rule 2 (the flagged reference and owner columns);
  - ADR-0030 rule 8 (owner axis on order lines and demand lines, reserved);
  - ADR-0033 rule 10 (external operation fields);
  - ADR-0009 rule 19 (service receipt reversibility);
  - ADR-0034 rules 2, 3, 9, 12 and 13 (backflush exception, external operation scheduling, processor demand lines, generated lines of progress, automatic receipt on the last operation's final progress);
  - ADR-0035 rule 19 (the keys of this ADR, 46 in total);
  - ADR-0036 rules 1 and 3 (processor routes; external lead times).
- **Catalogs:** two transaction keys.
- **DS-04:** `movement_not_allowed_at_processor`, `service_receipt_without_operation`.
- **DS-22:** the `service_receipt` document; service purchase lines with `production_order_operation_id`.
- **DS-24:** the transport document setting.
- **DS-09, DS-16, DS-17, DS-19:** the warehouse column and movement restriction; reserved INV-111, INV-112 and edge cases; the regime mapping of the processor key.
- **Glossary:** processor location, external operation, service receipt.
- **Open questions:**
  - processing for customers in Phase 1;
  - accounting at sending;
  - invoice differences before and after close;
  - the flagged columns.

## Revisit when

- The author brings processing for customers into Phase 1.
- A processor needs a portal or dropship flows.

## Documents updated

- **ADRs:** [docs/adr/0015-account-determination.md](0015-account-determination.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0028-document-lifecycle-hardening.md](0028-document-lifecycle-hardening.md), [docs/adr/0030-commercial-seams-and-imports.md](0030-commercial-seams-and-imports.md), [docs/adr/0033-production-master-data.md](0033-production-master-data.md), [docs/adr/0034-production-orders-and-shop-floor.md](0034-production-orders-and-shop-floor.md), [docs/adr/0036-multi-level-mrp.md](0036-multi-level-mrp.md): notes.
- **Catalogs:** [docs/catalogs/transaction-keys.csv](../catalogs/transaction-keys.csv).
- **Design:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
