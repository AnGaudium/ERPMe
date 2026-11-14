# Escalation and stop rules

Every agent session reads this file. When a rule here applies, the agent stops the affected work package, records why, and asks the author. Stopping early is always cheaper than building on a guess (Build principles, [11-build-order.md](../spec/11-build-order.md)).

## An agent stops and asks when

1. The documents are silent or contradict each other on something the work needs ([00-reading-guide.md](../spec/00-reading-guide.md), rule 5). Small technical decisions consistent with ADR-0002 are the exception: choose the simplest option and record it.
2. The work needs an accounting, tax or legal rule that is not written in the spec, a DS file or a localization package.
3. The work would change a decided item (D1–D17), an accepted ADR, scope, a gate, the build order or a glossary term.
4. The work would change the contract of a layer that has passed its gate (B2), or a commercial document would need a core change (B3).
5. A fix would change an invariant, a golden-scenario expected value or the naive recomputation, rather than the code under test.
6. The work touches posted-row protection, DB triggers, RLS, permission intersection, segregation of duties or the routing switch, beyond what its DS file specifies.
7. The work needs a dependency not listed in ADR-0002, or a framework before a concrete need (B7).
8. The work would build an "After Phase 1" feature or a hand-built screen or agent before its manual path passed its gate (B6).
9. The schema is frozen (4 weeks before go-live, B8) and the work changes it.
10. The work needs real company or personal data, or pilot data would enter the repository, CI or the test server.
11. A budget is reached, or CI or the nightly run stays red after two attempts at the same fix.
12. The work would weaken a hard floor: untrusted content, segregation of duties, "Human only" actions ([03-agent-safety.md](../spec/03-agent-safety.md)).

**How to stop:** commit the work in progress on its branch with a message starting `WIP (blocked):` and the reference IDs; add the question to [open-questions.md](../open-questions.md) with those IDs; tell the author in one paragraph what is blocked, what options exist, and which one the agent would pick and why. Do not merge, and do not start dependent work packages.

## Never decided by an agent

- Accounting, tax and legal rules, including their verification status.
- Decided items D1–D17 and accepted ADRs; ADRs and DS files are drafted by agents and accepted by the author.
- Golden-scenario expected values; which reference is right when core, recomputation and golden disagree.
- Whether a gate has passed.
- Merges to `main`; releases and their timing after go-live.
- Pilot selection, go-live, and anything said to the pilot customer.
- Closing periods and reversing posted documents (Human only, [14-agent-workflows.md](../spec/14-agent-workflows.md)).
- Relaxing a hard floor or a policy threshold.
- Changes to `seatmap.yaml` taking effect without passing the evaluation suite ([17-seatmap-data-classification.md](../spec/17-seatmap-data-classification.md)).

## Unverified legal rules

A rule marked "unverified" in the spec or the open questions follows [00-reading-guide.md](../spec/00-reading-guide.md), rule 4:

1. It is never hard-coded. It lives in the localization package as configuration with an `unverified` flag and a link to its open question.
2. Tests that depend on it name the flag; golden scenarios built on it are marked "pending verification".
3. The nightly report lists every flagged rule the run exercised, so the author sees which results depend on unverified rules.
4. Verification is done by one contracted verifier, a practising Vietnamese chief accountant or auditor independent of the author, against the original legal text, batched by the step that needs each rule ([ADR-0003](../adr/0003-build-operating-rules.md) R10 schedule). The open question is closed with the source (document, article, date) and the verifier's name; then the flag is removed in the same change.
5. The pilot never goes live using a flagged rule; rules it does not use stay flagged and disabled for its company (R11).

Open legal items today include the TT99 FX rules (413, 515, 635), TT133 status and B03, Decree 70/2025, the VAT deduction rule for invoices of VND 5 million or more, the implementing decree of the Personal Data Protection Law, landed cost from a closed period, and the GR/IR account ([open-questions.md](../open-questions.md)).
