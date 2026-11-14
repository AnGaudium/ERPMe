# Legacy and technology choices

This file is historical background, not requirements. The business content of the two earlier Odoo-based documents is reference only: *Preliminary survey: VAS costing on Odoo 19* and *Open platform direction for Vietnamese manufacturing on Odoo 20 CE*. Neither document is in this repository; where they live is an [open question](../open-questions.md). What is replaced is the platform (Odoo 20 CE, adapters, OCA).

| Carried over | Change in the rebuild |
| --- | --- |
| Periodic-average costing, WIP, clearing accounts | The costing engine is framework-independent and carries over as is. Costing method chosen per company; see [Costing](08-l10n-vn.md#costing) |
| Vietnamese-style banking | Becomes the bank statement matching workflow |
| Loans, fixed assets | Phase 3 |
| Hardening, cancel locks, period locks | Become core design: append-only journal and posting periods, not patches |
| Approvals, governance | Become the policy engine and approval engine shared by humans and agents |
| Barcode from the start, mobile app | Kept |
| Dual UoM, BKAV, MCP | Become native features |
| OCA-style license, partners deploy on their own | Kept |

Technology choices:

- Python (strict typing, see [ADR-0001](../adr/0001-programming-language.md)) and PostgreSQL, modular monolith; TypeScript for web and PWA; no microservices. Reuses the costing engine, has a strong AI ecosystem, and one person can run it.
- pgvector for semantic search (after Phase 1), no extra infrastructure.
- REST and MCP generated from the same command schemas.
- An LLM gateway routing by seatmap and data labels, supporting several providers and local models, so customers control data and cost.
