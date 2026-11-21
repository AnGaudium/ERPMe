Module: assets    Chunk: whole    Source ADRs: ADR-0025
Build step(s): 0    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: assets

## Purpose

`assets` is the Phase 3 module for fixed assets and loans, a layer-3 module (ADR-0022.R2). Today it holds one rule: the
seam that says what Phase 3 adds. It owns no table, command or setting yet; the Phase 3 design writes them. The seams it
builds on, the `fixed_asset` and `loan` control kinds (ADR-0025.R3) and the activation (ADR-0025.R4), are law of
`ledger` and are not restated here.

## Entities and tables

None: the module owns no table. The Phase 3 design defines the asset register.

Reads: the system accounts `borrowing` and `receivable_loan` (`system-accounts.csv`, control kind `loan`), named by R2
and R3.

## Commands and queries

None: the sources register no command or query of this module. `ActivateSubledger` (R1) is a command of the seam in
ADR-0025, not of `assets`.

## Rules

### Phase 3 seam

R1. Phase 3 adds the `assets` module, depreciation runs as close tasks (ADR-0012), and `ActivateSubledger` with the
asset register as opening detail.
Source: ADR-0025.R10

R2. Phase 3 adds loans as partner open items on `borrowing` and `receivable_loan`, activated with the contracts as
opening detail.
Source: ADR-0025.R10

R3. Not decided, and settled by the Phase 3 design as author questions: whether loans are managed per contract as open
items, and whether `borrowing` is then revalued per loan open item instead of at balance level (spec 05).
Source: ADR-0025.R10

## Invariants

None: the catalog holds no `INV` row of this module.

## Edge cases

None: the catalog holds no `EC` row of this module.

## Settings

None: the sources name no setting key of this module.

## UI annotations

None: the sources hold no ADR-0077 annotation for this module.

## Conflicts

None

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0025.R10 | R1-R3 |
