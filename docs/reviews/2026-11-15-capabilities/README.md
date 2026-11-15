# Holistic review and capability design records (2026-11-15)

Working records of the holistic design review and of ADR-0056 to ADR-0064, kept as evidence for ADR-0005 acceptance.

- **Holistic review** (before the first simulation): `ledger.md`, `commercial.md`, `production.md`, `platform_report.md`, `platform_decisions.md`, `catalogs_report.md`, `catalogs_decisions.md`, `flows_report.md`, `flows_decisions.md`.
- **Capability check:** `capability_check.md` (which of the six requested capabilities the design already had).
- **Architect decisions** given to each builder: `uom_decisions.md`, `uom_audit.md`, `analysis_barcode_decisions.md`, `intake_engineering_decisions.md`, `workflows_ai_decisions.md`, `config_decisions.md`, `production_decisions.md`.
- **Independent review rounds** (Claude Fable 5.2), one file per round: `uom_review_r1..r6`, `barcode_review_r1..r4`, `intake_review_r1..r5`, `workflows_review_r1..r6`, `analysis_review_r1..r6`, `settings_review_r1..r5`, `production_review_r1..r3`.
- **Simulation observations:** `sim_decisions.md` (the first six-flow run), `uom_sim_observations.md` (multiple-units purchase scenario) and `sim_final_observations.md` (the eleven-flow run); their fixes are in the commits "Simulation review: multiple-units purchase scenario gaps" and "Final simulation review: gaps found by the eleven-flow run".

File paths inside these records refer to the build server layout at the time; line numbers refer to the drafts each round reviewed.
