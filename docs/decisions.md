# Decided items

These decisions are not reopened without a new ADR. If another section says otherwise, this table wins (only ADRs rank above it).

| ID | Decision | Details in |
| --- | --- | --- |
| D1 | Rebuild; do not continue on Odoo | Vision and decisions |
| D2 | Deterministic core; AI only proposes; workflows are code-orchestrated | Principles 3, 12, 13 |
| D3 | Fully open source; core under AGPL-3.0; DCO instead of CLA; no closed edition | License and project governance |
| D4 | No event sourcing; state tables, append-only journal and transactional outbox | Data storage and synchronization |
| D5 | Accounting and inventory core modeled on SAP; not modeled on ERPClaw | Accounting and inventory core modeled on SAP |
| D6 | Default costing: periodic weighted average (period-end actual costing) | Costing |
| D7 | Two-tier chart of accounts, many-to-one | Multi-country and localization packages |
| D8 | Global market; English source, Vietnamese shipped; first pilot in Vietnam | Vision; Multi-country and localization packages |
| D9 | Vietnam package: TT99 first, TT133 in step 10; basic US package | Build order |
| D10 | Multi-currency and landed cost are in Phase 1 | Build order |
| D11 | No parallel run with old software; no customer commitment before the platform is complete (step 10) | Roadmap |
| D12 | Personal-data routing switch, off by default, turned on by the customer | Data classification and routing |
| D13 | Python and PostgreSQL, TypeScript for the UI; modular monolith | ADR-001 |
| D14 | Core tools; React, TypeScript and Vite UI; warehouse app as a PWA | ADR-002 |
| D15 | Timeframe 12–18 months; gates are conditions, months are estimates | Roadmap |
| D16 | Test data is our own synthetic dataset: fictional companies simulated day by day through the public commands, large enough and covering the edge-case catalog. No third-party data is copied; Odoo's demo data is only a checklist. A reader for MISA or another system is built only to migrate a pilot that uses it | Continuous testing; Build order |
| D17 | Project name ERPMe. This repository is the source of truth for the specification; the shared Claude doc is a discussion copy | `docs/README.md` |
