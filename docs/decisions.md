# Decided items

These decisions are not reopened without a new ADR. If another file says otherwise, this table wins (only ADRs rank above it).

| ID | Decision | Details in |
| --- | --- | --- |
| D1 | Rebuild; do not continue on Odoo | [01-vision.md](spec/01-vision.md) |
| D2 | Deterministic core; AI only proposes; workflows are code-orchestrated | [Principles 3, 12, 13](spec/02-principles.md) |
| D3 | Fully open source; core under AGPL-3.0; DCO instead of CLA; no closed edition | [License and project governance](spec/18-license-governance.md) |
| D4 | No event sourcing; state tables, append-only journal and transactional outbox | [Data storage and synchronization](spec/07-shared-foundation.md#data-storage-and-synchronization) |
| D5 | Accounting and inventory core modeled on SAP; not modeled on ERPClaw | [Accounting and inventory core modeled on SAP](spec/05-accounting-inventory-core.md) |
| D6 | Default costing: periodic weighted average (period-end actual costing) | [Costing](spec/08-l10n-vn.md#costing) |
| D7 | Two-tier chart of accounts, many-to-one | [Multi-country and localization packages](spec/06-localization.md) |
| D8 | Global market; English source, Vietnamese shipped; first pilot in Vietnam | [Vision](spec/01-vision.md); [Multi-country and localization packages](spec/06-localization.md) |
| D9 | Vietnam package: TT99 first, TT133 in step 10; basic US package | [Build order](spec/11-build-order.md) |
| D10 | Multi-currency and landed cost are in Phase 1 | [Build order](spec/11-build-order.md) |
| D11 | No parallel run with old software; no customer commitment before the platform is complete (step 10) | [Roadmap](spec/10-roadmap.md) |
| D12 | Personal-data routing switch, off by default, turned on by the customer | [Data classification and routing](spec/17-seatmap-data-classification.md#data-classification-and-routing) |
| D13 | Python and PostgreSQL, TypeScript for the UI; modular monolith | [ADR-0001](adr/0001-programming-language.md) |
| D14 | Core tools; React, TypeScript and Vite UI; warehouse app as a PWA | [ADR-0002](adr/0002-core-technology-tools.md) |
| D15 | Timeframe 12–18 months; gates are conditions, months are estimates | [Roadmap](spec/10-roadmap.md) |
| D16 | Test data is our own synthetic dataset: fictional companies simulated day by day through the public commands, large enough and covering the edge-case catalog. No third-party data is copied; Odoo's demo data is only a checklist. A reader for MISA or another system is built only to migrate a pilot that uses it | [Synthetic dataset](spec/12-testing.md#synthetic-dataset); [Build order](spec/11-build-order.md) |
| D17 | Project name NativeFlows. This repository is the source of truth for the specification; the shared Claude doc is a discussion copy | [docs/README.md](README.md) |
