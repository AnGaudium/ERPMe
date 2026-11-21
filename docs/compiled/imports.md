Module: imports    Chunk: whole    Source ADRs: ADR-0030, ADR-0044, ADR-0056, ADR-0062
Build step(s): 2, 3, 4    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: imports

## Purpose

`imports` owns the staged import (`import_batch`, `import_row`), the `migration` record per company with its phases, the
old-account map, the opening documents `opening_balance_entry` and `opening_open_item_entry`, the reconciliation against
the old books, and the full data export `ExportCompanyData`. It is a layer 5 module (ADR-0022.R2) that reaches domain
modules only through the dispatcher. A migration runs ordered import batches: master data, account opening balances, open
items per old invoice, opening stock per bin, and a reconciliation against the old books at item level. Opening documents
post in a one-day migration fiscal year on the day before the cut-over, and their offsets go, per currency, to the opening
balance clearing account. A migration completes when the clearing account is zero in company currency, the group-currency
translation difference has been moved to its own account and reconciliation shows no unexplained difference; the migration
period is then locked. The old books come in as a post-closing trial balance; year-to-date income and expense at a mid-year
cut-over are kept as non-posting turnover figures. Files follow one Excel template generated from the registry, and
external codes resolve through a key map, so a corrected re-run updates what changed. Agents prepare drafts; only a person
runs, completes or reverses. `ExportCompanyData` writes every company table and the reference data they point to, without
secrets, as JSON Lines with a manifest. The module does not own the key map `external_id_map` (`master_data`), the
turnover rows `opening_turnover` (`ledger`) or the stock document `opening_balance` (`inventory`).

## Entities and tables

None: no DDL file creates a table of `imports` (ADR-0074.R7: no import DDL exists yet).

Defined by rule, without DDL: `migration` (R10), `import_batch` (R2), `import_row` (R3), `old_account_map` (R32),
`old_balance` (R50), and the documents `opening_balance_entry` (R33), `opening_open_item_entry` (R39) and
`migration_completion_entry` (R54).

Reads: `external_id_map`, `uom_alias`, `company` (`master_data`); `opening_turnover`, `report_comparative_value`
(`ledger`, ADR-0049.R14); `opening_balance`, `opening_balance_line` (`inventory`, DDL
`docs/design/DS-22-09-42-commercial-inventory.sql`); `tax_line` (`tax`); `personal_data_read_log` (`audit`).

## Commands and queries

"Not stated" means the sources do not fill the cell.

| Name | Actor and authorization | Input | Effect | Events | Errors |
| --- | --- | --- | --- | --- | --- |
| `CreateMigration` | not stated | not stated | creates the `migration`, the migration fiscal year and, if missing, the first operating fiscal year (R13) | not stated | not stated |
| `StartMigration` | `human_only` | the migration | `draft` to `loading` (R10) | not stated | not stated |
| `StartMigrationReconciliation` | `human_only` | the migration | `loading` to `reconciling` (R10) | not stated | not stated |
| `CompleteMigration` | `human_only` | the migration | checks, posts the `migration_completion_entry`, locks the migration period, sets `completed` (R53-R55) | not stated | not stated |
| `AbandonMigration` | `human_only` | the migration | sets `abandoned` (R10) | not stated | not stated |
| `CreateImportBatch` | not stated | file as attachment, target migration and phase, source system | creates a batch in state `draft` (R28) | not stated | `external_id_source_reserved` |
| `UpdateImportBatch` | not stated | a draft batch | edits a draft batch (R60) | not stated | not stated |
| `ValidateImportBatch` | not stated | the batch | simulates every chunk and stores row-level errors (R4, R28) | not stated | not stated |
| `RunImport` | `human_only`, effect class `posting` | the batch | posts the chunks in row order and writes the key map rows (R5, R6, R29) | an unnamed event per chunk | not stated |
| `ResumeImport` | `human_only`, effect class `posting` | the batch | continues from the first `pending` row (R7) | not stated | not stated |
| `AbandonImportBatch` | `human_only`, effect class `posting` | the batch | stops the batch; posted documents stay (R9) | not stated | not stated |
| `ReverseImportBatch` | `human_only` | the batch | reverses every posted document of the batch (R56) | not stated | `open_item_settled`, `negative_stock` |
| `GetMigrationReconciliation` (query) | not stated | the migration | compares `old_balance` rows with the figures on `opening_date` (R51) | none | not stated |
| `AcceptMigrationDifference` | `human_only`; leaf `opening_balance_entry` at level `full` | the difference and a reason | accepts a difference (R52) | not stated | not stated |
| `ExportCompanyData` | `human_only`; permission `ExportCompanyData`, every field class | the company | writes the export zip as a long job (R64-R68) | not stated | not stated |

Commands of other modules the rules name: `ImportSalesHistory` (ADR-0024), `CreateOpeningTurnover` (`ledger`),
`ExportDataSubject` (ADR-0079), `LockPostingPeriod`, `UnlockPostingPeriod`, `ActivateSubledger`. Functions of
`master_data`: `external_id_resolve`, `external_key_of`.

Error codes bound to no named command of the module: `unit_text_unresolved`, `item_unresolved` (a batch row);
`opening_control_account` (an `opening_balance_entry` line); `opening_unit_value_differs`, `migration_not_open` (an opening
stock document); `migration_period_locked` (returned by `UnlockPostingPeriod`); `external_id_conflict` (`EC-313`,
ADR-0074.R7). `legacy_code_gtin_like` is a listing mark, not a rejection.

## Rules

### Staged imports

R1. An import is posted only through simulated command batches, never by an SQL script (spec 15). The glossary reads: every data import is posted through simulated command batches; large ones are staged in an `import_batch`.
Source: ADR-0030.R9

R2. An import of up to 1,000 rows (the batch limit, ADR-0022.R9) is one command batch; this covers the step 2 gate. A larger import is an `import_batch` of module `imports`, a module in layer 5 that reaches domain modules only through the dispatcher.
Source: ADR-0030.R9

R3. File and staging: the file is stored as an attachment (ADR-0027.R2). Its rows are parsed into `import_row` (owned by `imports`): row number, target command type, payload, `state` (`pending`, `posted`, `failed`), `error` and `result_document_id`.
Source: ADR-0030.R9

R4. Validation: every chunk of `import_chunk_rows` rows (an installation setting, default 1,000) is simulated as a command batch. A row may refer only to records that exist or to rows of its own chunk (ADR-0006.R3). Dependent data is imported as successive batches, for example partners before their open items. Row-level errors are stored with their row numbers. The batch can be posted only when no row is `failed`.
Source: ADR-0030.R9

R5. `RunImport`, `ResumeImport` and `AbandonImportBatch` are `human_only`, effect class `posting`. Being human commands, they reset the origin (ADR-0013.R2), so an agent can prepare a batch but never post it.
Source: ADR-0030.R9

R6. `RunImport` posts the chunks in row order. Each chunk is one command batch in its own long-job transaction (15 minutes, ADR-0022.R9), run as `system` on behalf of the human, with idempotency key `<batch id>:<chunk number>`, and it sets its rows `posted`. Each chunk is an internal command that emits an event; a consumer of that event on queue `jobs` runs the next chunk, so progress lives in the database. The batch stays `posting` until every row is `posted`; then it becomes `posted`. The check that the opening balance clearing account is zero belongs to `CompleteMigration` (R53), not to the batch.
Source: ADR-0030.R9, ADR-0044.R3

R7. Resume: a failed chunk rolls back alone. Its error is then recorded on its rows in a separate transaction, and the delivery is held (ADR-0013.R8). After a fix, `ResumeImport` continues from the first `pending` row, and posted chunks are never re-run.
Source: ADR-0030.R9

R8. While posting: a batch in `posting` blocks `LockPostingPeriod` for the periods its rows post into, through a required close check like ADR-0028.R11 (a note on ADR-0012.R13). It does not block other postings.
Source: ADR-0030.R9

R9. Abandon: `AbandonImportBatch` stops a batch. Documents already posted stay, and the close check keeps blocking until they are reversed, by ordinary commands or the bulk reversal `ReverseImportBatch` (R56).
Source: ADR-0030.R9

### Migration record and migration period

R10. `migration` (module `imports`, layer 5) has at most one non-abandoned record per company. Columns: `cut_over_date` (the first day of a regular period, preferably a quarter, enforced; spec 10); `opening_date` (the day before); `state`, which runs `draft` → `loading` (`StartMigration`) → `reconciling` (`StartMigrationReconciliation`) → `completed` (`CompleteMigration`), or `abandoned` (`AbandonMigration`); `old_system` (free text); `opening_vat_carry_forward` (R48); and the import batches it owns, in phase order.
Source: ADR-0044.R1

R11. All state changes of a `migration` are `human_only`.
Source: ADR-0044.R1

R12. Rehearsals run on staging from an empty database, and real data stays there at most 7 days (ADR-0003.R12).
Source: ADR-0044.R1

R13. `CreateMigration` creates a migration fiscal year (code `M` and the opening year, e.g. `M2026`) of one regular period from `opening_date` to `opening_date`, with no special period. It also creates the company's first operating fiscal year from `cut_over_date` if it does not exist; at a mid-year cut-over that year is short. This is a declared exception to ADR-0012.R1 and ADR-0007.R18, noted there.
Source: ADR-0044.R2, ADR-0044.R7.N1

R14. Opening documents post only into the migration period, and only once `clock.today` is on or after `opening_date`, so the period-ahead check of ADR-0012.R6 has its reference period.
Source: ADR-0044.R2

R15. `CompleteMigration` locks the migration period in every area, subledger areas first, without the soft-lock step or close tasks. This is a declared exception to ADR-0012.R7.
Source: ADR-0044.R2

R16. `UnlockPostingPeriod` on the migration period is refused with `migration_period_locked`. `ActivateSubledger` later finds it locked like any earlier period (ADR-0025.R4).
Source: ADR-0044.R2

R17. A company is in its setup phase until its first journal entry outside the migration fiscal year, which sets `company.first_operating_posting_at`; the opening documents of phases 3 to 5 do not end it. During the phase the implementer an owner acknowledged sets loosening settings without a second approver, and the setup flow fills the record defaults of an applied operating preset, such as `backflush_at_receipt` for bill-of-materials components loaded in phase 2 where the file states no consumption method (ADR-0067 rules 7–9, 18).
Source: ADR-0044.R3, .N6

### Phases

R18. Each phase is one or more import batches, run in order; a later phase's batch cannot run before the earlier phases have posted. A corrected batch of an earlier phase may run after later phases have posted.
Source: ADR-0044.R3

R19. The phases, in order:
- phase 1, company setup: the package chart copied with company splits where one old account maps to several system leaves (ADR-0010.R11); it must be right before the first opening line, because `has_posting` freezes it (ADR-0010.R12);
- phase 2, master data: partners (duplicates as check results, ADR-0019.R4), products and items, warehouses and bins, price lists, and the old-account map (R32);
- phase 3, account opening balances (R33-R38);
- phase 4, open items (R39-R42);
- phase 5, opening stock (R43-R46);
- phase 6, sales history for forecasting, through `ImportSalesHistory` in the same format (ADR-0024);
- phase 7, reconciliation (R50-R52).
Source: ADR-0044.R3

R20. A migration that is not completed blocks locking any operating period, through a close check like that of R8.
Source: ADR-0044.R3

R21. Phase 2 also loads money accounts, partner bank accounts, payment terms and cost centers, which later phases name: opening cash and bank balances post to money accounts' operational accounts, and open items carry payment terms.
Source: ADR-0044.R3, .N1

R22. Units are mapped first, in phase 2. Order of loading: company units, unit aliases for every unit text of the old system, product and item units, then barcodes, before products' documents. Product and item units are classified exact or inexact at load (ADR-0056.R7), never imported as exact or inexact.
Source: ADR-0044.R3, .N2, ADR-0056.R21

R23. Old unit text resolves through `uom_alias`: an imported row's unit text resolves through the partner item's text, `uom_alias`, then a unit code (ADR-0056.R19). An unresolved text fails the batch row with `unit_text_unresolved` and is never guessed. Proposing aliases for unresolved texts is a task of the data migration agent (R58).
Source: ADR-0030.R9.N1, ADR-0056.R21

R24. Opening stock lines and every open document line a migration creates carry the line unit block, with the snapshot resolved at load. Quantities with more decimals than their unit holds are rejected, and the validation lists them with the unit's decimals. Sales history (phase 6) is loaded in the inventory unit, like every planning quantity (ADR-0024.R10).
Source: ADR-0044.R3, .N2, ADR-0056.R21

R25. Phase 2 loads the old system's barcodes. A code that is a valid GTIN loads as one; any other old code of 1 to 48 characters of `A-Z 0-9 - . / _`, starting with a letter or a digit, numeric ones included, loads with `is_legacy_barcode` on item barcodes, bins and handling units, so existing labels stay readable. Codes with other characters (a space, `+`, `$`, `%`) are listed for relabelling. Legacy codes are unique in the barcode registry, numeric ones also on their digits padded to 14, never parsed as GS1, and a numeric one that passes a GTIN check digit is listed with `legacy_code_gtin_like`. Lot and serial codes load as they are (ADR-0061.R8).
Source: ADR-0044.R3, .N3

R26. The migration's template workbook (R27) has sheets for work centers and activity types, bills of materials (multi-level by a level column or an indent column, phantom flag, scrap, operation number), routings (operations, work center code, setup and run times, activities) and production versions; phase 2 loads them after products and items. Rows resolve components by exact code, barcode, supplier code with its supplier and manufacturer part number with its manufacturer only, each to exactly one item; a row that resolves none, or several, fails with `item_unresolved` and is never guessed. The same templates serve E2 outside a migration through the staged imports of R2.
Source: ADR-0044.R3, .N4, ADR-0062.R18

R69. Company setup (phase 1) also presents the settings registry grouped by area with each setting's core default, bounds and direction; the company starts on the core defaults, and values set during setup follow the change path (ADR-0063.R5).
Source: ADR-0044.R3, .N5

### Template, batches and key map

R27. The template is one workbook, generated from the registry: one sheet per command type, columns as payload field paths in `snake_case`, and an `external_code` column. Headers carry field meanings (Principle 7). Values use the API's canonical forms (ADR-0006.R13; ADR-0007.R3). A reader for an old system (DS-40, D16) writes the same structure. Import batches are operated through generated screens (ADR-0040): rows, errors, simulate and run.
Source: ADR-0044.R4

R28. Import batches are created with `CreateImportBatch` (file as attachment, target migration and phase) in state `draft`, checked with `ValidateImportBatch` (simulating every chunk, R4) and run with `RunImport` (`human_only`). A batch names its source system, a field of `CreateImportBatch` and of the workbook header, added when the DDL of DS-21 is written. A batch whose source system is `group` is refused with `external_id_source_reserved`, at `CreateImportBatch` and at the workbook header, because `group` is reserved for the group key (ADR-0074.R7).
Source: ADR-0044.R5, .N1, .N2, ADR-0074.R7

R29. External codes (the `external_code` column) resolve through `external_id_map` of `master_data` (company, source system, table, external key, entity ID), with the functions `external_id_resolve` and `external_key_of` (ADR-0074.R7); a new code gets a generated UUIDv7 (ADR-0006.R3). The provisional key map and the old-account map of a draft batch live in the batch until a person runs it, so an agent preparing a batch changes no company data; `RunImport` writes the map rows with the records.
Source: ADR-0044.R5, .N1, ADR-0074.R7

R30. A corrected file re-run on the same database follows each row's state and the key map: a master data row mapped and identical is skipped; mapped and different becomes an `Update`; an opening document must first be reversed (R56). Abandoning keeps the key map.
Source: ADR-0044.R5, ADR-0074.R7

R32. `old_account_map` maps each old account to one operational account, or splits it by detail given in the file or by a fixed share. Every account of the old trial balance must be mapped before reconciliation can pass.
Source: ADR-0044.R6, ADR-0044.R7.N1

### Account opening balances

R33. `opening_balance_entry` is one document per transaction currency (ADR-0011.R1) and carries balance-sheet accounts with control kind `none` or `gr_ir`. A line holds account, side, amount in the document's currency, company amount at book (applied rate origin `book`, ADR-0011.R3) and optional dimensions. The document has one offset line through `opening_balance`.
Source: ADR-0044.R7

R34. A GR/IR line of an `opening_balance_entry` carries the old receipt reference with a null purchase order line (ADR-0030.R3). A later supplier invoice clears such a line through a manual GR/IR clearing.
Source: ADR-0044.R7, .N1

R35. Receivables, payables and inventory accounts are rejected on an `opening_balance_entry` with `opening_control_account`; they come from the open item and opening stock documents (R39, R43).
Source: ADR-0044.R7

R36. Work in process, fixed assets and loans post as plain balances before their subledgers are activated. Open production orders at cut-over are created as orders, and their detail comes with the activation's reclassification (ADR-0025.R4; ADR-0034.R15).
Source: ADR-0044.R7, .N1

R37. The old trial balance is taken after the old system's closing, and income and expense accounts are not loaded. For a regime that closes only at year end, the migration closes profit and loss into retained earnings in the trial balance before loading.
Source: ADR-0044.R7, .N1

R38. No transaction history is migrated: historical transactions before the cut-over are not migrated in Phase 1, and the rehearsal month of go-live is replayed as ordinary documents on staging. Comparatives of statements for ranges before the cut-over come from `report_comparative_value`, entered at migration (ADR-0049.R14).
Source: ADR-0044.R18, .N1, ADR-0044.R7.N1

### Opening open items

R39. `opening_open_item_entry` is one document per currency: one line per old invoice, credit, advance or payment on account, each creating an open item at its open amount with a book carrying amount. A line holds partner, account (the partner's reconciliation account unless given), kind, `natural_side`, `reference` (old number), `partner_reference`, `document_date` and `due_date`.
Source: ADR-0044.R8

R40. The opening item's `posting_date` is `opening_date`, as its origin line's (ADR-0026.R3). Each opening item line carries the old system's posting date as `original_posting_date` (a note on ADR-0026.R1). Advance and payment-on-account lines carry no due date and do carry `evidence_method`, how the advance was paid (ADR-0048.R18).
Source: ADR-0044.R8

R41. Installments still open become one item each. Employee advances need the employee as a partner (ADR-0019.R3).
Source: ADR-0044.R8

R42. For opening open items `INV-30` to `INV-33` hold (`EC-50`).
Source: ADR-0044.R8

### Opening stock

R43. Opening stock uses the stock document type `opening_balance` (ADR-0020.R7); the DDL is `opening_balance` and `opening_balance_line` (item, warehouse, bin, status, handling unit, lot or serial, the unit block and the spread `company_amount`). Each line carries item, warehouse, bin (the default bin where there are no bins, ADR-0031.R8), stock status, handling unit, lot or serial, and quantity. It posts only in the migration period (`migration_not_open`, `INV-870`).
Source: ADR-0044.R9, .N2

R44. Value per area: the file gives one total value per item and valuation area. The handler spreads it over that item's lines by quantity, by largest remainder, so the lines sum exactly to the old books' value. A line without its total is rejected with `opening_unit_value_differs`. The area's total divided by the quantity becomes the first `preliminary_price`, with `price_source` `opening` (a note on ADR-0020.R11; ADR-0075.R13; `INV-872`), so no costing run is needed in the migration period.
Source: ADR-0044.R9, .N2

R45. Opening stock lines carry the line unit block, with the snapshot resolved at load; quantities with more decimals than their unit holds are rejected and listed with the unit's decimals (ADR-0056.R9, ADR-0056.R21).
Source: ADR-0044.R9, .N1

R46. Lots and serials carry no cost of their own in opening stock (ADR-0018; open question against spec 15). Processor locations are allowed (ADR-0037.R1). `INV-20` to `INV-24` hold.
Source: ADR-0044.R9

### Year-to-date turnover and opening VAT

R47. At a mid-year cut-over, income and expense of the fiscal year before the cut-over are loaded as `opening_turnover` rows: account, `start_date`, `end_date` and the debit and credit turnover in company currency, before closing entries. The rows carry dates and no fiscal year, because the first fiscal year after a mid-year cut-over is short. `opening_turnover` is owned by `ledger` and written by `CreateOpeningTurnover`; its DDL is in DS-06. The rows are non-posting figures that statutory reports of that year read (DS-26; ADR-0049.R14); the year's profit to date is already in the post-closing balance of retained earnings.
Source: ADR-0044.R10, .N1, ADR-0044.R7.N1

R48. Opening VAT balances load as balances (control kind `none`). Opening open items have no `tax_line`, so the `tax_payment_evidence` consumer ignores their settlements (ADR-0041.R15). The first return carries forward `opening_vat_carry_forward` where `carry:` finds no earlier filed return (ADR-0041.R19).
Source: ADR-0044.R13, ADR-0044.R7.N1

R49. Corrections of pre-cut-over invoices carry the original tax date and rate as entered fields, since no original exists in NativeFlows.
Source: ADR-0044.R13, ADR-0044.R7.N1

### Reconciliation and completion

R50. `old_balance` rows bring the old books' figures: the trial balance per old account; open items per partner, account and currency, by count and sum; GR/IR per receipt; stock quantity per item, warehouse, bin, lot or serial; and stock value per item and valuation area, the level NativeFlows holds (ADR-0020).
Source: ADR-0044.R11

R51. `GetMigrationReconciliation` compares the `old_balance` rows with NativeFlows's figures on `opening_date`, through the old-account map.
Source: ADR-0044.R11

R52. `AcceptMigrationDifference` (`human_only`, with a reason) accepts a difference where NativeFlows's figure stands because the old one is wrong (go-live). It needs the permission `AcceptMigrationDifference`, on the leaf `opening_balance_entry` at level `full`, held through Finance `full` by the templates `owner` and `chief_accountant` (ADR-0054 rules 8, 24). Differences do not touch the clearing account, because NativeFlows's documents balance by construction.
Source: ADR-0044.R11, .N1

R53. `CompleteMigration` first checks that every batch is `posted`, `opening_balance_clearing` is zero in company currency, no difference is unaccepted, and `INV-20` to `INV-24` and `INV-30` to `INV-33` pass.
Source: ADR-0044.R12

R54. Second, where the installation has a group currency, `CompleteMigration` posts a `migration_completion_entry` in the migration period. The entry has group-only lines per transaction currency of the clearing account (ADR-0011.R2), with transaction and company amounts zero, and moves the clearing account's group balance through the key `opening_group_translation` to `fx_difference_equity`. Group amounts are translated from transaction amounts (ADR-0011.R3) while company amounts are at book, so the group balance of the clearing account is not zero before this entry. Which account of a regime's chart the key reaches is flagged package content of the localization package and is not stated here.
Source: ADR-0044.R12, ADR-0044.R7.N1

R55. Third, `CompleteMigration` locks the migration period (R15). Each currency's offsets leave a transaction-currency balance on the clearing account by construction (ADR-0011.R4); that residual is expected. The account is never revalued: the core excludes `opening_balance_clearing` from every revaluation scope (a note on ADR-0011.R18).
Source: ADR-0044.R12

### Bulk reversal

R56. `ReverseImportBatch` (`human_only`) reverses every posted document of a batch, newest first, as staged chunks, on the documents' own posting date, and only while the migration is not completed. It stops with `open_item_settled` (an item it would reverse is settled or adjusted) or `negative_stock` (stock it would remove is consumed). Master data rows are not reversed.
Source: ADR-0044.R14

R57. DS-16 holds fault-injection edge cases for resume (R7; `EC-67`) and for bulk reversal (`EC-68`).
Source: ADR-0044.R14

### Agents

R58. The data migration agent (spec 14) belongs to Phase 2. It works on migrations in `draft` or `loading`, maps columns and old accounts inside draft batches, proposes duplicate merges as work items, and validates batches. It may not run, resume, abandon, reverse or complete. Its workflow is ADR-0051 rules 26–28.
Source: ADR-0044.R15, .N1

R59. In Phase 1 the staged import uses stored mappings and deterministic fuzzy matching, which do the bulk of the mapping. The assistant's help is bounded: an `act` run is tainted and reads its request, the batch row as context subject and at most 100 selected import rows, so it may draft mappings for the selected rows only and proposes no merges against existing records. Every batch is still simulated and checked (ADR-0078.R2).
Source: ADR-0044.R15, .N1

R60. Import files are outside content (ADR-0029.R10), so agent runs that read them are tainted, which draft-only rights already allow. Human-run import batches are outside the change proposal carrier (ADR-0029.R4). Draft batches are edited with `UpdateImportBatch`.
Source: ADR-0044.R15

### Data protection and retention

R61. Pilot data never enters the repository or CI.
Source: ADR-0044.R16

R62. Contacts in import files are personal data, which spec 17 routes to a local model when an agent reads them. Spec 17 has no local models in Phase 1; until the author decides, personal samples are removed whenever the routing switch is on (ADR-0050.R5; ADR-0051.R28).
Source: ADR-0044.R16

R63. Imports and exports write audit records, and exports also write a processing-log entry (ADR-0038.R9). Import files linked to posted opening documents become accounting evidence kept with the vouchers (ADR-0038.R15), with their personal data.
Source: ADR-0044.R16, ADR-0044.R7.N1

### Export

R64. `ExportCompanyData` is `human_only`, needs the permission `ExportCompanyData` (only in the `owner` role template), and needs every field class. It runs as a long job, with an audit record and a processing-log entry.
Source: ADR-0044.R17

R65. The output of `ExportCompanyData` is a zip written as a stream of per-table JSON Lines files in primary-key order, plus the attachment files and `manifest.json` (core and package versions, schema versions, row counts, file SHA-256s).
Source: ADR-0044.R17

R66. The export holds every company-scoped table, and the global reference rows those tables point to (currencies, system chart, transaction keys, movement types, work item kinds, the package data in use, and the display names of users in audit rows), so the package is self-contained for re-entry (ADR-0003.R13).
Source: ADR-0044.R17

R67. The export leaves out secrets (integration token hashes, TOTP and OIDC secrets, webhook credentials), earlier exports and import files, and erased values, which stay masked (ADR-0019.R10).
Source: ADR-0044.R17

R68. The export zip is an attachment that is not accounting evidence. Its bytes are deleted after 7 days, and a download needs the same permission and is audited. `ExportDataSubject` (ADR-0079.R3) deletes its file after 7 days in the same way, and both exports write a `personal_data_read_log` row (ADR-0079.R12).
Source: ADR-0044.R17, .N1

## Invariants

No invariant has the area `imports`; the rules name these, each with check point `day`.

- `INV-20` `inventory_accounts_equal_valuation` (area `inventory`): every account with control kind inventory equals the stock valuation report, per warehouse. Checked by R46, R53.
- `INV-24` `stock_tables_equal_movements` (area `inventory`): `stock_quantity` and `stock_value` equal the sums of their movements. Checked by R46, R53.
- `INV-30` `open_items_equal_control_accounts` (area `receivables_payables`): every receivable or payable control account equals the sum of its open items, per partner and currency. Checked by R42, R53.
- `INV-33` `open_item_cache_equals_lines` (area `receivables_payables`): each open item's cached amounts equal the sums of its journal lines. Checked by R42, R53.
- `INV-870` `opening_balance_in_migration_period` (area `inventory`): every posted `opening_balance` posts in the migration period of its company. Protects R14, R43.
- `INV-872` `opening_value_spread_exact` (area `inventory`): the opening balance lines of an item and valuation area sum exactly to the area's total, and the first preliminary price of the area is that total divided by the quantity. Protects R44.

## Edge cases

- `EC-50` `opening_open_items` (area `receivables_payables`): opening balances create one open item per old invoice, in several currencies. Outcome: `must_succeed`. Rule R42.
- `EC-67` `import_resume_after_fault`: a chunk of a staged opening import fails by injected fault; the chunk rolls back alone, `ResumeImport` continues from the first pending row, and no posted chunk runs twice. Outcome: `must_succeed`. Rule R7.
- `EC-68` `import_bulk_reversal`: an abandoned opening batch is reversed by `ReverseImportBatch`, newest first, with an injected fault mid-way; the reversal resumes, and it stops on a settled open item or consumed stock. Outcome: `must_succeed`. Rule R56.
- `EC-313` `external_id_reimport`: a web-shop customer imported twice with the same key updates the partner; a second key for the same partner in that source system is refused. Outcome: `must_succeed` and `must_reject:external_id_conflict`. Rule R29, R30 (ADR-0074.R7).
- `EC-333` `opening_balance_outside_migration`: an opening balance dated in an ordinary period is refused. Outcome: `must_reject:migration_not_open`. Rule R14, R43.
- `EC-334` `opening_value_spread_sets_price`: one item in several bins with one total: the lines take their shares by largest remainder, and the first preliminary price is the total divided by the quantity. Outcome: `must_succeed`. Rule R44.

## Settings

None: `docs/catalogs/settings.csv` holds no key of `imports`.

R4 names `import_chunk_rows` (an installation setting, default 1,000); it has no row in `settings.csv`.

## UI annotations

None: the sources hold no ADR-0077 annotation for this module. Import batches are operated through generated screens
(R27).

## Conflicts

CONFLICT ADR-0030.R9: the closing sentence of step 3, amended for migrations, governs: a batch is `posted` when all its rows are, and the clearing check belongs to `CompleteMigration` (ADR-0044.R3, ADR-0044.R12; stated in R6 and R53).
CONFLICT ADR-0044.R5: `import_key_map` is replaced by `external_id_map` of `master_data`, and a batch names its source system (ADR-0074.R7, ADR-0044.R5.N1; stated in R28 to R30).
CONFLICT ADR-0044.R15.N1: the note moves the data migration agent to Phase 2 and bounds the Phase 1 assistant; the agent's description in the rule holds for Phase 2 only (stated in R58 and R59).
CONFLICT ADR-0056.R21: "the migration agent proposes aliases" is read with ADR-0044.R15.N1, which moves that agent to Phase 2; R23 points to R58 for it.
CONFLICT ADR-0044.R16: the closing paragraph of the rule governs the local-model sentence: Phase 1 has no local models, so personal samples are removed while the routing switch is on (R62); the mark "flagged" on evidence retention of import files is dropped by ADR-0044.R7.N1 (R63).
CONFLICT ADR-0044.R2: the mark "flagged" on the short first operating fiscal year is dropped, because ADR-0044.R7.N1 confirms the one-day migration fiscal year and the other interims.
CONFLICT ADR-0044.R6: the mark "flagged" on splitting an old account by a fixed share is dropped as an interim choice that ADR-0044.R7.N1 confirms.
CONFLICT ADR-0044.R7: the marks "flagged" on manual GR/IR clearing, plain balances before subledger activation and closing profit and loss before loading are dropped; ADR-0044.R7.N1 confirms them.
CONFLICT ADR-0044.R10: the mark "Flagged" on year-to-date figures as non-posting turnover is dropped; ADR-0044.R7.N1 names this choice as confirmed.
CONFLICT ADR-0044.R12: the mark "flagged" on posting the group difference through `opening_group_translation` is dropped by ADR-0044.R7.N1; the regime account mapping stays flagged package content (R54).
CONFLICT ADR-0044.R13: "All flagged" on opening VAT is dropped, since ADR-0044.R7.N1 confirms the other interims of ADR-0044; stated in R48 and R49.
CONFLICT ADR-0044.R18: the mark "open question" on not migrating historical transactions is dropped; ADR-0044.R7.N1 confirms no transaction history (stated in R38).
FALSE-POSITIVE ADR-0044.R10.N1: "instead of" describes the columns `start_date` and `end_date` chosen over a fiscal year column; the rule named no column, so nothing in it is contradicted.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0030.R9 | R1-R9 |
| ADR-0030.R9.N1 | R23 |
| ADR-0044.D0 | Purpose |
| ADR-0044.R1 | R10-R12 |
| ADR-0044.R1.N1 | not applicable: says how "ADR-0044 rule N" citations are read; no law of the module |
| ADR-0044.R2 | R13-R16 |
| ADR-0044.R3 | R6, R17-R22, R24-R26, R69 |
| ADR-0044.R3.N1 | R21 |
| ADR-0044.R3.N2 | R22, R24 |
| ADR-0044.R3.N3 | R25 |
| ADR-0044.R3.N4 | R26 |
| ADR-0044.R3.N5 | R69 |
| ADR-0044.R3.N6 | R17 |
| ADR-0044.R4 | R27 |
| ADR-0044.R5 | R28-R30 |
| ADR-0044.R5.N1 | R28, R29 |
| ADR-0044.R5.N2 | R28 |
| ADR-0044.R6 | R32 |
| ADR-0044.R7 | R33-R37 |
| ADR-0044.R7.N1 | R13, R32, R34, R36-R38, R47-R49, R54, R63 |
| ADR-0044.R8 | R39-R42 |
| ADR-0044.R9 | R43-R46 |
| ADR-0044.R9.N1 | R45 |
| ADR-0044.R9.N2 | R43, R44 |
| ADR-0044.R10 | R47 |
| ADR-0044.R10.N1 | R47 |
| ADR-0044.R11 | R50-R52 |
| ADR-0044.R11.N1 | R52 |
| ADR-0044.R12 | R53-R55 |
| ADR-0044.R13 | R48, R49 |
| ADR-0044.R14 | R56, R57 |
| ADR-0044.R15 | R58-R60 |
| ADR-0044.R15.N1 | R58, R59 |
| ADR-0044.R16 | R61-R63 |
| ADR-0044.R17 | R64-R68 |
| ADR-0044.R17.N1 | R68 |
| ADR-0044.R18 | R38 |
| ADR-0044.R18.N1 | R38 |
| ADR-0056.R21 | R22-R24 |
| ADR-0062.R18 | R26 |
