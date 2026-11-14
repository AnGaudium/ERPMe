# Design validation lab (2026-11-14)

The author asked for a project database on the build server, to test the design's data flows before any product code exists. This folder records what the lab ran and what it found.

The lab code is design evidence, not product code. It follows none of ADR-0022's conventions and is never imported by the product.

## Setup

- PostgreSQL 18, the version ADR-0006 and ADR-0022 require, in a separate container bound to localhost.
- Python with psycopg. The connection string comes from `ERPME_LAB_DSN`, and the password from `PGPASSWORD`.
- Each SQL scenario loads `00_stubs.sql` and then DS-06, unchanged and in file order, into a clean schema.

The scripts are in [lab/](lab/):

| File | What it does |
| --- | --- |
| `00_stubs.sql` | Schemas, domains (ADR-0006 rule 8), and minimal stubs for tables that other design items define |
| `load_ds06.py` | Orders DS-06's statements by table dependency and reports external references |
| `lab.py`, `t01_journal.py` | 13 posting scenarios against the DS-06 triggers |
| `t02_subledger.py` | 6 scenarios on the `cost_object` gated kind after subledger activation |
| `t03_cost_object_area.py` | 4 scenarios: cost-object lines in area `inventory`, the company check, append-only activation rows |
| `costing_solver.py` | First solver prototype: stock and production nodes, uniform WIP share (L-05) |
| `costing_lab2.py` | Full production costing model of ADR-0035 over two periods (L-06) |

## Findings

| ID | Finding | Status |
| --- | --- | --- |
| L-01 | DS-06 created `journal_entry`, `cost_object` and `fixed_asset`, which reference `company`, before `company`, so the file did not load in order | Fixed in DS-06: master tables first; the file loads as is |
| L-02 | The DS-06 triggers behave as designed: balance at commit, append-only rows, no lines added later, locked area, signs and storno, receivable lines need partner and open item, open item match and identity, inventory dimensions and material line | Confirmed, 13 of 13 |
| L-03 | `journal_line_check_insert` read only the catalog control kind. After `ActivateSubledger`, gated kinds must carry their dimensions, and lines dated before `effective_from` must be rejected (ADR-0025 rule 4) | Fixed in DS-06 with `subledger_activation`. Tested for `cost_object`; the `fixed_asset` and `loan` branches are the same code, untested |
| L-04 | DS-06 comments said `cost_object` is Phase 2 and owned by `ledger` | Fixed (ADR-0032; ADR-0034 rule 15) |
| L-05 | First prototype: stock and production nodes with co-products by coefficient, a by-product, a transfer, a rework self-loop, and WIP as one uniform share of all cost. One global elimination. Value was conserved, and the result equals fixed-point iteration to 10⁻¹⁸⁸. It had no pools, no normal capacity, no abnormal cost, and none of ADR-0035's WIP methods | Narrowed; superseded by L-06 |
| L-06 | Second prototype, the model of ADR-0035, over two periods. Every check passed and value was conserved exactly in both periods | Basis of ADR-0035 |
| L-07 | Review of the L-03 fix: the activation row was read before the area-state lock, cost objects of another company were accepted, and activation rows could change. Cost-object lines were in area `general`, so late pool postings would not make the inventory costing stale | Fixed in DS-06 and tested (`t03_cost_object_area.py`, 4 of 4) |

L-06 covered:
- pools fed by indirect materials at solved prices, split into fixed and variable parts;
- normal capacity, an idle pool, and both activity and constant bases;
- `direct_material` and `equivalent_units` WIP with partial receipts, and an order with no receipt;
- `planned_cost` WIP capped by re-solving;
- WIP carried into the next period by cost component;
- abnormal consumption assessed at completion;
- a late cost on a completed order sent to cost of goods sold;
- a by-product, and co-products by coefficient;
- a rework self-loop;
- a singular strongly connected component keeping preliminary prices;
- outputs rounded to the minor unit by largest remainder, summing exactly (one order's output split; the WIP tie-out of ADR-0035 rule 12 and node residuals are not exercised);
- a by-product worth more than its order: outputs clamped to zero by solving again, with a negative residual;
- abnormal consumption assessed cumulatively across periods (issued 58 against 55 required).

What L-06 shows:
- **Linear.** One period is linear in the stock-node prices once these are quantities or constants: allocation weights, units in process, completion shares and normal capacities. Allocation by solved material cost is not linear; ADR-0035 therefore allocates by material at preliminary prices.
- **WIP across periods.** WIP is well defined across periods only when it is recorded by cost component; ADR-0035 adds `production_order_period_cost`.
- **Planned WIP.** It needs a cap, applied by solving again, when it exceeds the order's cost.
