# Escalation and stop rules

Every agent session reads this file. When a stop rule below applies, the agent stops the affected work package, records why, and asks the author. Rules 1, 3, 4, 6 and 7 also say which part the agent decides itself under [ADR-0005](../adr/0005-technical-decisions-delegated.md). Stopping early is always cheaper than building on a guess (Build principles, [11-build-order.md](../spec/11-build-order.md)).

## An agent stops and asks when

1. The documents are silent or contradict each other on something the work needs ([00-reading-guide.md](../spec/00-reading-guide.md), rule 5), and the point is on the reserved list of [ADR-0005](../adr/0005-technical-decisions-delegated.md). A technical point is decided by the agent and recorded.
2. The work needs an accounting, tax or legal rule that is not written in the spec, a DS file or a localization package.
3. The work would change a decided item (D1–D17), scope, a gate, the build order, the governance (ADR-0003, ADR-0005, the review, merge, escalation and gate rules of this runbook), or an ADR that sets a reserved decision. An accepted technical ADR or a glossary term is changed by the agent with a new ADR.
4. A commercial document would need a core change (B3). A layer's contract after its gate (B2) may be changed by the agent for a measured reason that no commercial document triggered, by ADR, with the affected verification rerun; the author re-confirms the gate.
5. A fix would change an invariant, a golden-scenario expected value or the naive recomputation, rather than the code under test.
6. The work touches permission intersection, segregation of duties or the routing switch beyond what its DS file specifies. For posted-row protection, DB triggers and RLS beyond the DS file, the agent updates the DS file first and the author reviews the change line by line (stage 5).

   Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): "the author reviews the change line by line (stage 5)" now reads: the change passes ADR-0073's mechanical layers and two model reviews (the author's decision of 2026-11-18). Updating the DS file first still holds.
7. The work would replace a tool chosen in ADR-0002 (D14), add one on its "deliberately not used" list, or build a framework before a concrete need (B7). Any other library is added by the agent with a recorded reason; one that opens a category ADR-0002 does not cover needs an ADR.
8. The work would build an "After Phase 1" feature or a hand-built screen or agent before its manual path passed its gate (B6).
9. The schema is frozen (4 weeks before go-live, B8) and the work changes it.
10. The work needs real company or personal data, or pilot data would enter the repository, CI or the test server.
11. A budget is reached, or CI or the nightly run stays red after two attempts at the same fix.

    Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): this applies to the coder seat too. After two red attempts at the same fix (a failing check, test or review finding), it stops and reports. A stopped work package is never handed to a stronger model: it is re-specified for the same seat, or asked of the author. A stronger model is assigned only up front, in the package's manifest (ADR-0073 rule 10).
12. The work would weaken a hard floor: untrusted content, segregation of duties, "Human only" actions ([03-agent-safety.md](../spec/03-agent-safety.md)).

**How to stop:** commit the work in progress on its branch with a message starting `WIP (blocked):` and the reference IDs; add the question to [open-questions.md](../open-questions.md) with those IDs; tell the author in one paragraph what is blocked, what options exist, and which one the agent would pick and why. Do not merge, and do not start dependent work packages.

## Never decided by an agent

- Accounting, tax and legal rules, including their verification status.
- Decided items D1–D17, scope, gates, the build order and the governance (reserved list in [ADR-0005](../adr/0005-technical-decisions-delegated.md)). ADRs and DS files that contain a reserved decision are accepted by the author; technical ADRs and DS files are accepted by agents after an independent review.
- Golden-scenario expected values; which reference is right when core, recomputation and golden disagree; removing or weakening an invariant, or changing the naive recomputation to make a failure pass.
- Whether a gate has passed.
- Merges to `main`; pushing to the public repository and opening pull requests (on the author's request only); releases and their timing after go-live.
- Pilot selection, go-live, and anything said to the pilot customer.
- Closing periods and reversing posted documents (Human only, [14-agent-workflows.md](../spec/14-agent-workflows.md)).
- Relaxing a hard floor or a policy threshold.
- Changes to `seatmap.yaml` taking effect without passing the evaluation suite ([17-seatmap-data-classification.md](../spec/17-seatmap-data-classification.md)).

## Unverified legal rules

A rule marked "unverified" in the spec or the open questions follows [00-reading-guide.md](../spec/00-reading-guide.md), rule 4:

1. It is never hard-coded. It lives in the localization package as configuration with an `unverified` flag and a link to its open question.
2. Tests that depend on it name the flag; golden scenarios built on it are marked "pending verification".
3. The nightly report lists every flagged rule the run exercised, so the author sees which results depend on unverified rules.
4. The author verifies Vietnam package rules against the original legal text; US package rules come from public primary sources (DS-38). Each is done by the step in the [ADR-0003](../adr/0003-build-operating-rules.md) R10 schedule. An agent may find and quote the source, but never marks a rule verified. The open question is closed with the source (document, article, date) and the verifier's name; then the flag is removed in the same change. The pilot's chief accountant reviews the rules the pilot uses during the step 11 rehearsal.
5. The pilot never goes live using a flagged rule; rules it does not use stay flagged and disabled for its company (R11).

Open legal items today include the TT99 FX rules (413, 515, 635), TT133 status and B03, Decree 70/2025, the VAT deduction rule for invoices of VND 5 million or more, the implementing decree of the Personal Data Protection Law, landed cost from a closed period, and the GR/IR account ([open-questions.md](../open-questions.md)).
