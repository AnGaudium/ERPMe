# ADR-0064 Production agent (DS-57): review round 3

Reviewer: Claude Fable 5.2 (independent, ADR-0005), 2026-11-15. Target: `drafts/ds-production/` after round 2 (`ds-production.bak-r2` for comparison).

**Verdict: ACCEPT** (0 blocking, 0 should-fix, 2 nits).

## Test results

Copy of base-integrated in `/tmp`, `apply_production.py` applied (rc 0, 51 writes over 27 files), a fresh database per script.

| Check | Result |
| --- | --- |
| t25 `--load` | 103 / 103 |
| t12 `--load` | 190 / 190 |
| t15 `--load` | 146 / 146 |
| t16 `--load` | 99 / 99 |
| t20 `--load` | 184 / 184 |
| t21 `--load` | 93 / 93 |
| t22 `--load` | 140 / 140 |
| t13 on the standard load | 24 / 24 |
| check_package (tt99) | RESULT PASS |

Cleaned up: database dropped, `/tmp/rv64*` removed. base-integrated untouched; no git run.

## Round 2 items

- **S1 closed.** Rule 16 now returns the best candidate of each enabled kind first, then fills to 7 in the total order; within `transfer_reservation` the donor's priority, latest first, precedes cover. P47e reproduces the round 2 probe (4 expedite lines, 3 warehouses) and still offers `reschedule`, `transfer_reservation` and `split_order`; P47f gives the donors as MO-9, MO-8, MO-7. P47c now compares against an independent repeated-minimum selection and says what it proves.
- **S2 closed.** Rule 24, the DS-04 row, EC-200 and INV-734 cap a transfer at the target's short quantity at execution, max(0, unreserved − available to promise). P41b computes it from stock: a receipt that nothing reserved makes the transfer `reservation_transfer_invalid`.
- **N1 to N4 closed.** The trigger also refuses a change of item, warehouse or lot on a row that has or is a source (D23, D24), a lot case runs (D22), a quantity change still passes (D25), split skips required 0 and blocks on an uncovered fixed-quantity line, and `partial_staging` is modeled.

## Blocking

None.

## Should-fix

None.

## Nits

- **N1** `0064-production-agent.md`, rule 16, `transfer_reservation` bullet: say once that the candidate's cover uses the short quantity as of the query, and that execution recomputes it (rule 24), so a reader does not take the two as the same number.
- **N2** `t25_production_agent.py`, `covered_g`: when every line is fixed-quantity or has required 0 it returns G, which the caller's `0 < covered G < G` test turns into "no split"; a one-line comment would make that intended.

## Left for integration (out of scope here)

The 26 settings rows join `settings.csv`, and t24's closed-world checks run, after ADR-0063 is accepted.
