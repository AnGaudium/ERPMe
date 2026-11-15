# Catalogs

Versioned data the core relies on. Each catalog is owned by one design item and changes only together with it.

| Catalog | Owner | Status |
| --- | --- | --- |
| System accounts | DS-07 | [system-accounts.csv](system-accounts.csv), version 0.1.0, released as 1.0.0 at the step 0 gate ([ADR-0010](../adr/0010-system-chart-of-accounts.md)) |
| Transaction keys | DS-08 | [transaction-keys.csv](transaction-keys.csv), version 0.1.0 ([ADR-0015](../adr/0015-account-determination.md)); valuation classes and item groups are company data seeded by the localization package |
| Movement types | DS-09 | [movement-types.csv](movement-types.csv), version 0.1.0 ([ADR-0020](../adr/0020-inventory-and-costing-model.md)) |
| Work item kinds | DS-29 | [work-item-kinds.csv](work-item-kinds.csv), version 0.1.0, seeded now and generated from the registry once `work` exists ([ADR-0042](../adr/0042-work-queue.md)) |
| Invariants (INV-xx) | DS-16 | [invariants.csv](invariants.csv), version 0.1.0 ([DS-16](../design/DS-16-invariants-and-harness.md)) |
| Edge cases (EC-xx) | DS-17 | [edge-cases.csv](edge-cases.csv), version 0.1.0, released as 1.0.0 (EC v1) at the step 0 gate ([DS-17](../design/DS-17-synthetic-dataset.md)) |
| Authorization areas | DS-15 | [authorization-areas.csv](authorization-areas.csv), version 0.1.0, seeded now and generated from the registry once it exists ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 7) |
| Authorization verb levels | DS-15 | [authorization-verb-levels.csv](authorization-verb-levels.csv), version 0.1.0, one row per glossary verb ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 8) |
| Role templates | DS-15 | [role-templates.csv](role-templates.csv) and [role-template-levels.csv](role-template-levels.csv), version 0.1.0, interim defaults ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 11) |
| Segregation rules | DS-15 | [segregation-rules.csv](segregation-rules.csv), version 0.1.0 ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 17) |
