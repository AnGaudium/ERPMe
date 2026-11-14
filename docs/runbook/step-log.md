# Step log

Dated record of gate decisions, the week list and one line per Friday review ([README.md](README.md#weekly-cadence)). Newest entry first. Gate entries link the gate report and state pass or fail; only the author writes a gate entry.

| Date | Step | Entry |
| --- | --- | --- |
| 2026-11-14 | 0 | DS-09 ADR part done: [ADR-0020](../adr/0020-inventory-and-costing-model.md) and [movement-types.csv](../catalogs/movement-types.csv) 0.1.0 accepted under ADR-0005 after three review rounds (Claude Fable 5.2). Two questions for the author (purchase return value, count difference valuation) |
| 2026-11-14 | 0 | DS-20 partner part and DS-35 foundation done (drafted ahead of steps 2 and 5 at the author's request): [ADR-0019](../adr/0019-partners-and-crm-foundation.md) accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Five questions for the author |
| 2026-11-14 | 0 | DS-20 item part done (drafted ahead of step 2 at the author's request): [ADR-0018](../adr/0018-product-and-item-model.md) accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Two questions for the author |
| 2026-11-14 | 0 | DS-15 envelope part done: [ADR-0017](../adr/0017-permission-envelope.md) accepted under ADR-0005 after two review rounds (Claude Fable 5.2); full model at step 5. Two questions for the author |
| 2026-11-14 | 0 | DS-14 done: [ADR-0016](../adr/0016-localization-package-structure.md) localization package structure accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Two questions for the author |
| 2026-11-14 | 0 | DS-08 done: [ADR-0015](../adr/0015-account-determination.md) and [transaction-keys.csv](../catalogs/transaction-keys.csv) 0.1.0 accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Four questions for the author |
| 2026-11-14 | 0 | DS-06 done: [ADR-0014](../adr/0014-universal-journal.md) universal journal and DDL draft accepted under ADR-0005 after two review rounds (Claude Fable 5.2). One question for the author (manual entries to control accounts) |
| 2026-11-14 | 0 | DS-13 done: [ADR-0013](../adr/0013-outbox-and-events.md) outbox and events accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Group 2 of step 0 complete |
| 2026-11-14 | 0 | Author delegated the three DS-12 questions; agent decided: close jobs may post in soft-locked periods; only current and next period accept postings by default; Vietnam closes P&L to 911/421 every period (TT99 text to verify) |
| 2026-11-14 | 0 | DS-12 done: [ADR-0012](../adr/0012-posting-periods-and-closing.md) posting periods and closing accepted under ADR-0005 after two review rounds (Claude Fable 5.2). Three questions for the author (TT99 closing, close jobs in soft-locked periods, future-dated postings) |
| 2026-11-14 | 0 | DS-10 ADR done: [ADR-0011](../adr/0011-multi-currency.md) multi-currency accepted under ADR-0005 after two review rounds (Claude Fable 5.2); logic in steps 6 and 8. Four TT99 FX questions for the author |
| 2026-11-14 | 0 | Author confirmed the system chart classification choices (ADR-0010 rule 8, catalog 0.1.0) |
| 2026-11-14 | 0 | DS-07 done: [ADR-0010](../adr/0010-system-chart-of-accounts.md) and [system-accounts.csv](../catalogs/system-accounts.csv) 0.1.0 accepted under ADR-0005 after two review rounds (Claude Fable 5.2); released as 1.0.0 at the step 0 gate. One question for the author on classification choices |
| 2026-11-14 | 0 | Author's decision on corrections recorded (ADR-0009 amended, Principle 5 reworded): posted documents are corrected by correction documents; internal documents can be reversed; reversal of unreferenced outside-party documents and who posts corrections are flagged interim rules with open questions |
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
