# First agentic workflows and guardrails

The first four workflows are numbered by pilot value: structured, low-risk data first, so the pilot customer sees value in the first weeks. The build order is in [11-build-order.md](11-build-order.md#steps-and-gates): data migration, quotation, bank matching, purchase invoices.

1. **Purchase invoices from e-invoices:** fetch incoming invoices through the e-invoice provider, T-VAN or the receiving mailbox, and three-way match against the PO and goods receipt. Structured data, low risk, immediate benefit for accountants.
2. **Data migration:** map master data from the Excel template or the pilot's current system, detect duplicates, look up tax IDs, build opening balances as a simulated command batch. This removes the biggest adoption barrier and never touches posted books. The run's read scope is the import batch.
3. **Request intake and quotation drafting:** email first, chat channels after Phase 1. Needs clean master data and price lists, so it follows data migration.
4. **Bank statement matching:** start with statement-file import for 2–3 common banks, because Vietnamese bank APIs require individual partnerships.

Next: repeat-sales suggestions (needs order history, so no value for a new install), replenishment suggestions (the planning agent of [ADR-0024](../adr/0024-planning.md) rule 23), payment reminders, period-close assistant (runs the checklist, reconciles, flags anomalies).

## Deterministic first, LLM last

Each workflow is a sequence of steps orchestrated by code, not a free agent (Principle 13). Each step follows the order: stored rules and mappings → lookup → fuzzy matching with a deterministic score → LLM only for what remains. LLM output always passes a deterministic check before it becomes a draft.

| Workflow | Deterministic functions do | LLM only does |
| --- | --- | --- |
| Purchase invoices from e-invoices | Parse e-invoice XML, check signature and invoice status, look up tax ID, map lines via stored supplier item mappings, three-way match with PO and goods receipt, check tax rates and totals | Suggest an item for lines with no mapping; an approved mapping is stored |
| Data migration | Read files in known formats; normalize tax IDs, phone numbers, addresses; detect duplicates by key and similarity score; build opening balances as a simulated command batch; reconcile totals with the old books | Guess column meaning in unfamiliar files, suggest merging ambiguous duplicates |
| Request intake and quotation | Attach email to a partner by address and domain; check stock; price from price list, discounts and FX rate; check credit limit and margin | Understand the request in the email, map item descriptions to item codes, write the quotation text |
| Bank statement matching | Read the statement file; match by amount, date, reference, invoice number in the description; score matches by rule; one-to-many matching by a combinatorial algorithm | Read free-text transfer descriptions when rules fail, propose new matching rules |

Metric: the share of steps handled by deterministic functions in each workflow. It must rise over time, and LLM cost per document must fall with it.

Default policy guardrails. Customers can adjust them per action type and threshold, except the hard floors in [03-agent-safety.md](03-agent-safety.md) (untrusted content, segregation of duties and the "Human only" rows), which cannot be relaxed:

| Agent action type | Default |
| --- | --- |
| Read, query, summarize | Automatic |
| Create document drafts (quotation, PO, purchase invoice) | Automatic; a human confirms before posting |
| High-confidence bank match below an amount threshold | Draft. After shadow mode passes, deterministic matching may auto-post high-confidence matches below the threshold with no LLM contribution; a human reviews afterwards |
| Post documents above the threshold, or post directly to expense | Requires approval |
| Send messages or emails to customers or suppliers | Draft; a human sends. Auto-send only for permitted types |
| Change master data (partner, item, price) | Requires approval |
| Close periods, reverse posted documents | Human only; agents may not |

## Measuring agent value

An agent gains permissions only with evidence, never by impression.

- **Metrics per workflow:** share of drafts accepted unedited and degree of editing; auto-match accuracy, defects found later and documents reversed or corrected because of the agent; handling time per document versus the baseline measured before enabling the agent; LLM cost per document.
- **Evaluation:** an agent starts drafting only after it passes its offline evaluation set. Its drafts may reach auto-post only through the deterministic gateway, after people have posted them unchanged at the required rate for at least two months, below the limit and within the rules of [03-agent-safety.md](03-agent-safety.md) ([ADR-0065](../adr/0065-deterministic-auto-post-gateway.md) rule 11; [ADR-0078](../adr/0078-agent-simplification-for-phase-1.md)). Live shadow comparison of agents comes after Phase 1.
- **The evaluation suite** draws on the synthetic dataset. Anonymized pilot data is used only outside the repository; pilot data never enters the repository. The suite runs as set in [Principle 11](02-principles.md).
