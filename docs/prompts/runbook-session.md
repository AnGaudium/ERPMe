# Session prompt: high-level implementation runbook

Use this prompt to start a session that writes the ERPMe implementation runbook.

---

You are working in the ERPMe repository. ERPMe is a fully open-source, agentic-by-design ERP built by one author who directs AI coding agents. The specification in `docs/` is the source of truth and is finished for now; the project is in Build step 0 (design). Your task is to write a **high-level implementation runbook**: the operating manual the author and the AI agents follow to execute the build plan from today until the Phase 1 gate.

## Read first

1. `AGENTS.md`, `docs/README.md`, `docs/spec/00-reading-guide.md` (precedence, scope labels, glossary).
2. `docs/decisions.md` (D1–D17), `docs/spec/10-roadmap.md`, `docs/spec/11-build-order.md` (build principles B1–B8, ADR list, steps 0–11 and gates).
3. `docs/spec/12-testing.md` (continuous testing, synthetic dataset, edge cases), `docs/design/backlog.md` (DS-01 to DS-55), `docs/adr/0002-core-technology-tools.md`, `docs/risks.md`, `docs/open-questions.md`.
4. Other spec files only as needed.

## What the runbook must cover

1. **Operating rhythm:** how a unit of work flows from design item to merged change (DS-xx → ADR or spec → implementation → tests and invariants → independent review → merge), branch and pull-request conventions, how the author and the AI agents split the work, which agent roles are used (builder, reviewer, test-scenario model) and when the author must decide. Weekly cadence, how open questions are raised and closed, how documents stay in sync with code.
2. **Per build step 0–11:** entry criteria, the design items that must be finished first, the work packages in order, how AI agents are used in that step, verification (which invariants, which synthetic dataset size, which golden scenarios), the exit gate copied exactly from `11-build-order.md`, the artifacts produced, the main risks and the fallback if the gate fails.
3. **Continuous testing operations:** running the test server, the simulator and its business-event log, nightly runs, budgets, how defects become regression scenarios, coverage reports for EC-xx.
4. **Go-live (steps 10–11 and the Phase 1 gate) at high level:** platform-complete review, pilot selection, rehearsal, schema freeze, cut-over checklist outline, the first three monthly closes, support mode (30–50% of time, no releases on closing days).
5. **Escalation and stop rules:** when an agent must stop and ask the author, what never gets decided by an agent (accounting, tax and legal rules; decided items), how unverified legal rules are handled.

## Constraints

- High level: no code, no detailed designs (those are DS items). Target 10–15 pages in total.
- Do not change decided items, gates, scope or the build order. If you find a gap or contradiction, add it to `docs/open-questions.md` and mention it in your report instead of resolving it.
- Do not invent accounting, tax or legal rules.
- Use the reference IDs (Principle n, Dn, step n, Bn, DS-xx, INV-xx, EC-xx, ADR-nnnn) and the glossary terms. Plain, specific English.

## Output

- `docs/runbook/README.md` (overview, how to use the runbook, operating rhythm) plus a small number of further files under `docs/runbook/`, e.g. one for steps 0–4, one for steps 5–11, one for testing operations and one for go-live. Choose the split that keeps each file readable on its own.
- Add `runbook/` to the layout table in `docs/README.md` and to the reading list in `AGENTS.md`.

## Done when

- Every step 0–11 has its section with entry criteria, design items, work packages, verification, gate and fallback.
- Gates match `11-build-order.md` word for word.
- New open questions, if any, are in `docs/open-questions.md`.
- The work is committed on a branch named `runbook` with a message that cites the files, ending with the co-author line used in this repository. Do not push and do not merge.

Report at the end: the files created, the open questions you added, and anything in the specification that made the runbook hard to write.
