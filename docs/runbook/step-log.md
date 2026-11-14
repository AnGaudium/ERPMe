# Step log

Dated record of gate decisions, the week list and one line per Friday review ([README.md](README.md#weekly-cadence)). Newest entry first. Gate entries link the gate report and state pass or fail; only the author writes a gate entry.

| Date | Step | Entry |
| --- | --- | --- |
| 2026-11-14 | 0 | Author's instruction recorded in AGENTS.md: the AI is the chief architect; agents cross-check and challenge the author's input; SAP is the reference when unsure (D5) |
| 2026-11-14 | 0 | DS-05 done: [ADR-0009](../adr/0009-document-lifecycle.md) document lifecycle accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Five questions for the author, each with a flagged interim rule |
| 2026-11-14 | 0 | Author confirmed the Vietnam default for rounding differences: `rounding_gain` → 515, `rounding_loss` → 635 (TT99), changeable per company (DS-19) |
| 2026-11-14 | 0 | Author's answer recorded: a late purchase invoice defaults to the last day of its month when that period is open (Vietnam package default). Open: the default when that month is closed; the VAT period date |
| 2026-11-14 | 0 | Author's answers recorded: rounding mode per currency (ADR-0006 rule 17); rounding gain and loss accounts declared per company (rule 20, default pending confirmation); calendar-year fiscal year by default (ADR-0007 rule 21). E-invoice date finding added for verification |
| 2026-11-14 | 0 | DS-04 done: [ADR-0008](../adr/0008-command-envelope-and-registry.md) and [DS-04-command-envelope.md](../design/DS-04-command-envelope.md) accepted under ADR-0005 after two review rounds (Claude Fable 5.2). One open question for the author (integrations and `human_only`) |
| 2026-11-14 | 0 | DS-03 done: [ADR-0007](../adr/0007-time-model.md) time model accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Three legal points raised as open questions |
| 2026-11-14 | 0 | DS-02 done: [ADR-0006](../adr/0006-id-and-numeric-model.md) ID and numeric model accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Two legal points raised as open questions |
| 2026-11-14 | 0 | [ADR-0005](../adr/0005-technical-decisions-delegated.md) accepted by the author: agents decide technical questions and accept technical ADRs and DS files after an independent review; the author keeps the reserved list (items 1–11) |
| 2026-11-14 | 0 | DS-01 done: [ADR-0004](../adr/0004-naming-conventions.md) naming conventions accepted. The author delegated technical decisions to the agents; overriding goal: easy for AI agents to use. Accounting, tax and legal rules, golden values, gates and merges stay with the author |
| 2026-11-14 | 0 | ADR-0003 amended: R3 uses the existing repository AnGaudium/ERPMe, made public; R10 the author verifies Vietnam rules, no contracted verifier |
| 2026-11-14 | 0 | ADR-0003 answers the 14 runbook questions (R1–R14). Next: author creates the GitHub organization and engages the legal verifier |
| 2026-11-14 | 0 | Runbook added. Step 0 in progress: DS-01 to DS-18 not started |
