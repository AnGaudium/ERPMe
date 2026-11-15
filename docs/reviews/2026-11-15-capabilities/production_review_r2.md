# ADR-0064 Production agent (DS-57): review round 2

Reviewer: Claude Fable 5.2 (independent, ADR-0005), 2026-11-15. Target: `drafts/ds-production/` after round 1 (`ds-production.bak-r1` for comparison).

**Verdict: REVISE** (0 blocking, 2 should-fix, 4 nits).

## Test results

Copy of base-integrated in `/tmp`, `apply_production.py` applied (rc 0, 51 writes over 27 files), a fresh database per script.

| Check | Result |
| --- | --- |
| t25 `--load` | 96 / 96 |
| t12 `--load` | 190 / 190 |
| t15 `--load` | 146 / 146 |
| t16 `--load` | 99 / 99 |
| t20 `--load` | 184 / 184 |
| t21 `--load` | 93 / 93 |
| t22 `--load` | 140 / 140 |
| t13 on the standard load | 24 / 24 |
| check_package (tt99) | RESULT PASS |

Probes (after t25 `--load`):
- S1 trigger: a transferred row with another item or warehouse than its source is refused (`reservation_transfer_invalid`); changing or clearing the link after insert is refused (`reservation_transfer_link_immutable`). The lot branch was read, not run: the fixture has no lot. An `UPDATE` of `item_id` on a linked row after insert is accepted (N1).
- A blank `external_reference` is now refused.
- S4 ordering, with the lab's own `candidates()`: see S1 below.

Cleaned up: database dropped, `/tmp/rv64*` removed. base-integrated untouched; no git run.

## Round 1 items

Closed: B1 (four existing open questions extended, none added, DS-52 stays open), S2, S3, S5, S6, S7, N1 to N11. The new "Reservation transfer" glossary row in place of editing the Transfer verb row is accepted. S1 and S4 are closed except for the two points below.

The three new import evidence settings (300 drafts, 99%, 2 months; bounds 150, 98%, 1 month; loosening by proposal, outdating the evidence) are sound and are listed for the author in the agent values question.

## Blocking

None.

## Should-fix

**S1. The cap of 7 drops whole candidate kinds, and the donor order contradicts the sort.**
- Where: `0064-production-agent.md:148` (`transfer_reservation`: "latest donor first"), `:150` (order and cap); `t25_production_agent.py` `candidates()` and P47b, P47c.
- Probe: 4 expedite lines and 3 source warehouses fill all 7 places, so `reschedule`, `transfer_reservation` and `split_order` are never offered. With three donors, the sort (start date, larger cover, document number) offers the donor that is earliest in the priority first, not the latest.
- Fix:
  - Cap per kind (for example the first 3 of each kind), or guarantee the first candidate of every enabled kind before filling the rest.
  - For `transfer_reservation`, make the donor's reservation priority, latest first, the sort key ahead of covered quantity, and say so in the order sentence.
  - Add both cases to t25. P47c compares the function with a ranking of its own output, so it proves the sort only; say that, or enumerate independently.

**S2. A stale transfer is not refused when a receipt has covered the target but nothing has reserved yet.**
- Where: `0064-production-agent.md:241` ("also when a goods receipt has meanwhile covered the target"), `:332` (EC-200); `apply_production.py` EC-200 row; `t25_production_agent.py` P41b (passes `target_unreserved=0` by hand).
- Problem: the cap is the target's unreserved open requirement, which a receipt alone does not change. It reaches 0 only after a sweep or a person reserves. In reservation mode `off`, or with the agent type `off`, the transfer executes while free stock would cover the target, and the source order loses its reservation for nothing.
- Fix: cap the quantity at the target line's short quantity at execution, max(0, unreserved open requirement − available to promise), under the lock; reword EC-200 and the DS-04 row; make P41b compute the cap from stock instead of receiving it.

## Nits

- **N1** `apply_production.py` (trigger `trg_stock_reservation_transfer_guard`): it fires only on insert and on a change of the link. Also refuse a change of `item_id`, `warehouse_id` or `lot_id` on a row that has, or is, a transfer source.
- **N2** `t25_production_agent.py` D20: add a lot case, so the trigger's lot branch runs.
- **N3** `0064-production-agent.md:149`: `split_order` divides by `required`; skip lines with required 0 and say how fixed-quantity components count.
- **N4** `t25_production_agent.py` `candidates()`: `partial_staging` is not modeled; add it or name it in "Not covered".
