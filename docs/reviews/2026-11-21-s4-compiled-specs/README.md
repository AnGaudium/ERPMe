# S4 compiled specs: independent reviews (2026-11-21)

Reviews of the per-module specs in [`../../compiled/`](../../compiled/) and of the lint that gates them (`tools/docs/doc_lint.py`).
Method: a reviewer on a different model draws a seeded sample of source units, reads each unit in the ADRs (with its notes and
any later rule they name), and judges the spec's statement against it; then checks the Conflicts entries, the DDL and the catalogs.
The lint proves completeness and trace; these reviews are the semantic gate.

| File | Subject | Spot check |
| --- | --- | --- |
| `ledger.md`, `tax.md`, `quality.md` | pilots (Fable-compiled, Opus-reviewed) | 30, 30, 20 units |
| `cash.md`, `policy.md`, `sales.md`, `automation.md`, `crm.md` | Fable-compiled, Opus-reviewed | 20 units each |
| `inventory.md`, `master_data.md`, `production.md`, `agents.md`, `registry.md`, `agent_runs.md`, `permissions.md` | Opus-compiled, Sonnet-reviewed | 15 to 25 units each |
| `review-lint-r3.md`, `review-lint-r4.md`, `review-lint-r5.md` | rounds 3 to 5 of the lint review | bypass probes |

Every report lists findings as BLOCKING, SHOULD-FIX and NOTE, and SOURCE findings (defects of ADRs, DDL or catalogs, which do not
count against a spec; they are collected in [`open-questions.md`](../../open-questions.md), "S4 compiled specs"). The findings
were fixed after each review; the fixes were verified by the lint, not by a second independent reading (see `STATE.md` of the lab).
The lint review rounds 3 and 4 and the lint's known blind spots (round 5, findings B1 to B3) are described in
[`tools/docs/README.md`](../../../tools/docs/README.md).
