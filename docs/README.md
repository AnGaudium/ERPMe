# ERPMe documentation map

This folder is the source of truth for the ERPMe specification (D17). Everything is in English; the archived Vietnamese version is kept for reference only.

## Reading order

1. [spec/00-reading-guide.md](spec/00-reading-guide.md): how to read these documents, regulatory terms, glossary of code identifiers.
2. [decisions.md](decisions.md): decided items D1–D17.
3. [spec/01-vision.md](spec/01-vision.md) and [spec/02-principles.md](spec/02-principles.md).
4. [spec/10-roadmap.md](spec/10-roadmap.md) and [spec/11-build-order.md](spec/11-build-order.md): phases, lean scope, build steps and gates.
5. [design/backlog.md](design/backlog.md): the design work, DS-01 to DS-40.
6. The spec files for the area you work on.

## Layout

| Path | Holds | Changes by |
| --- | --- | --- |
| `spec/` | The specification, one file per area | Edit in place; record significant changes as an ADR |
| `decisions.md` | Decided items D1–Dn, ranked just below ADRs | A new ADR, then add or amend the row |
| `adr/` | Architecture decision records, numbered `NNNN-title.md` | New file per decision; never rewrite an accepted ADR, supersede it |
| `design/` | Design backlog and one specification per design item (`DS-xx-title.md`) | Written when the design item is worked on |
| `catalogs/` | Data the core relies on: system accounts, transaction keys, movement types, edge cases | Versioned with the design item that owns it |
| `open-questions.md` | Questions that need the author or legal verification | Add freely; close with a link to the answer |
| `risks.md` | Risks and mitigations | Review at each phase gate |
| `prompts/` | Briefs used to start AI sessions for larger tasks | Add one per task |
| `archive/` | Frozen historical documents | Never edited |

## Spec files

| File | Area |
| --- | --- |
| [spec/00-reading-guide.md](spec/00-reading-guide.md) | Reading rules and glossary |
| [spec/01-vision.md](spec/01-vision.md) | Vision, motivation, resources |
| [spec/02-principles.md](spec/02-principles.md) | Agentic-by-design principles 1–13 |
| [spec/03-agent-safety.md](spec/03-agent-safety.md) | Agent safety and permissions |
| [spec/04-architecture.md](spec/04-architecture.md) | Overall architecture |
| [spec/05-accounting-inventory-core.md](spec/05-accounting-inventory-core.md) | Accounting and inventory core modeled on SAP |
| [spec/06-localization.md](spec/06-localization.md) | Localization packages, two-tier chart of accounts |
| [spec/07-shared-foundation.md](spec/07-shared-foundation.md) | Multi-company, regimes, currency, UoM, approval, lifecycle, storage, extensibility |
| [spec/08-l10n-vn.md](spec/08-l10n-vn.md) | Vietnam localization: VAS rules |
| [spec/09-mvp-scope.md](spec/09-mvp-scope.md) | MVP scope and not-doing list |
| [spec/10-roadmap.md](spec/10-roadmap.md) | Phases, gates, lean scope |
| [spec/11-build-order.md](spec/11-build-order.md) | Build principles, ADR list, steps and gates |
| [spec/12-testing.md](spec/12-testing.md) | Continuous testing, synthetic dataset, edge cases |
| [spec/13-crm.md](spec/13-crm.md) | Agentic CRM |
| [spec/14-agent-workflows.md](spec/14-agent-workflows.md) | First agentic workflows and guardrails |
| [spec/15-migration-ux-docs.md](spec/15-migration-ux-docs.md) | Data migration, UX, documentation |
| [spec/16-customization.md](spec/16-customization.md) | AI-driven customization (after Phase 1) |
| [spec/17-seatmap-data-classification.md](spec/17-seatmap-data-classification.md) | Model seats and data classification |
| [spec/18-license-governance.md](spec/18-license-governance.md) | License and governance |
| [spec/19-legacy.md](spec/19-legacy.md) | Legacy and technology choices (background) |
