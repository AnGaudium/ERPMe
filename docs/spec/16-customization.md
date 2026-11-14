# AI-driven deployment and customization

This entire section comes after Phase 1. In Phases 0 and 1, only keep the boundary between the core and extensions, and print templates as configuration, so the design below never requires core changes.

Each customer has its own repo following GitHub → staging → production. The repo is seeded with core AI skills so the customer (or a partner) can use AI to build new features and adjust how the system works. The vital rule: **every customization is additive and never modifies core source code.** The core is a pinned dependency, so upgrades do not break customizations.

Customer repo structure:

- `core.lock`: the core version in use. The repo contains no core code.
- `extensions/`: the customer's configuration, templates, rules and plugins.
- `skills/`: seeded AI skills and the customer's own skills.
- `seatmap.yaml`: which model does what (see AI seatmap).
- `tests/`: tests for each customization, run against the sample company.

Seeded skills: build print templates, user-defined fields and tables, approval rules, reports, plugins, data migration, writing tests, and a website for e-commerce.

## Five customization levels

AI always picks the lowest level that solves the need. The higher the level, the tighter the control.

| Level | Examples | How | Control |
| --- | --- | --- | --- |
| 1. Configuration | User-defined fields, policy thresholds, approval procedures | Declared as metadata | Schema validation |
| 2. Templates | Print templates, email templates, reports | Templates over a versioned data contract per document type | Test render on the sample company, compare with the reference image |
| 3. Rules and automation | "When X then Y", alerts, bank matching rules | Declarative rule language, not code | Simulation on sample data |
| 4. Plugins | New commands, before/after-command hooks, new screens | Public SDK and plugin API | Import-linter, contract tests, security scan, compatibility test with the next core version |
| 5. External apps | Website, e-commerce, customer portal | Separate app calling only the public API with narrowly scoped tokens | No DB access, never in the core's process |

Print templates are where customers customize most. The customer provides the old template (PDF, Excel, photo) and AI builds a template over the data contract. When the core changes its data structure, the data contract stays stable, so templates do not break.

## Pipeline from request to production

1. The customer describes the need in their own language, with a sample if available.
2. The builder agent uses the seeded skills, creates a branch, writes the change and its tests. It runs in a sandbox with no production credentials.
3. CI runs schema validation, blocks any change outside `extensions/`, `skills/` and `tests/`, contract tests, a security scan, and a review agent independent of the builder.
4. Automatic deploy to staging with anonymized data. The customer runs UAT.
5. The approval engine approves promotion to production. Plugins (level 4) also need approval from someone with a technical role.
6. Merge and deploy to production. Rollback by revert. Every step is traced.

On core upgrades, staging first runs all of the customer's customization tests against the new core version (upgrade preview). If a need truly requires a core change, the only path is an issue or PR on the core repo, never a local patch.
