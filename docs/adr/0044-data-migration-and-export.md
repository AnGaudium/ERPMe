# ADR-0044: Data migration and full data export

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-21. Related decisions: D16. Principles 1, 2, 5. ADR-0003, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0014, ADR-0015, ADR-0018, ADR-0019, ADR-0020, ADR-0023, ADR-0024, ADR-0025, ADR-0026, ADR-0027, ADR-0029, ADR-0030, ADR-0031, ADR-0034, ADR-0037, ADR-0038, ADR-0039, ADR-0041, ADR-0043; spec 14, 15, 17.

## Decision

**Running a migration.** A migration is a `migration` record per company that runs ordered import batches (ADR-0030 rule 9) through the dispatcher:
1. master data;
2. account opening balances;
3. open items per old invoice;
4. opening stock per bin;
5. a reconciliation against the old books at item level.

**The migration period.** Opening documents post in a one-day migration fiscal year on the day before the cut-over. Their offsets go, per currency, to the opening balance clearing account.

**Completing.** A migration completes when:
- the clearing account is zero in company currency;
- the group-currency translation difference has been moved to its own account;
- reconciliation shows no unexplained difference.

The migration period is then locked.

**Formats.** The old books come in as a post-closing trial balance; year-to-date income and expense at a mid-year cut-over are kept as non-posting turnover figures. Files follow one Excel template generated from the registry, and external codes resolve through a key map, so a corrected re-run updates what changed.

**Who does what.** Agents prepare drafts; only a person runs, completes or reverses.

**Export.** `ExportCompanyData` writes every company table and the reference data they point to, without secrets, as JSON Lines with a manifest.

### Rules

**The migration and its period**

1. `migration` (module `imports`, layer 5; at most one non-abandoned per company):
   - **Columns:**
     - `cut_over_date` (the first day of a regular period, preferably a quarter, enforced; spec 10);
     - `opening_date` (the day before);
     - `state`: `draft` → `loading` (`StartMigration`) → `reconciling` (`StartMigrationReconciliation`) → `completed` (`CompleteMigration`), or `abandoned` (`AbandonMigration`);
     - `old_system` (free text);
     - `opening_vat_carry_forward` (rule 13);
     - the import batches it owns, in phase order.
   - **Commands.** All state changes are `human_only`.
   - **Rehearsals.** They run on staging from an empty database, and real data stays there at most 7 days (ADR-0003 R12).
2. The migration period. `CreateMigration` creates a migration fiscal year (code `M` and the opening year, e.g. `M2026`) of one regular period from `opening_date` to `opening_date`, with no special period. It also creates the company's first operating fiscal year from `cut_over_date` if it does not exist; at a mid-year cut-over that year is short (flagged). This is a declared exception to ADR-0012 rule 1 and ADR-0007 rule 18, noted there.
   - **Where opening documents post.** Only into this period, and only once `clock.today` is on or after `opening_date`, so the period-ahead check of ADR-0012 rule 6 has its reference period.
   - **Locking.** `CompleteMigration` locks it in every area, subledger areas first, without the soft-lock step or close tasks. This is a declared exception to ADR-0012 rule 7.
   - **Unlocking.** `UnlockPostingPeriod` on it is refused with `migration_period_locked`. `ActivateSubledger` later finds it locked like any earlier period (ADR-0025 rule 4).
3. Phases. Each phase is one or more import batches, run in order; a later phase's batch cannot run before the earlier phases have posted.
   1. **Company setup:** the package chart copied with company splits where one old account maps to several system leaves (ADR-0010 rule 11). It must be right before the first opening line, because `has_posting` freezes it (rule 12).
   2. **Master data:** partners (duplicates as check results, ADR-0019 rule 4), products and items, warehouses and bins, price lists, and the old-account map (rule 6).
   3. **Account opening balances** (rule 7).
   4. **Open items** (rule 8).
   5. **Opening stock** (rule 9).
   6. **Sales history** for forecasting, through `ImportSalesHistory` in the same format (ADR-0024).
   7. **Reconciliation** (rule 11).

   **Corrections.** A corrected batch of an earlier phase may run after later phases have posted.

   **Batch state.** ADR-0030 rule 9.3 gets a note: a batch is `posted` when all its rows are; the clearing check belongs to `CompleteMigration` (rule 12). A migration that is not completed blocks locking any operating period (a close check, as ADR-0030 rule 9.5).

   Note: phase 2 (master data) also loads money accounts, partner bank accounts, payment terms and cost centers, which later phases name: opening cash and bank balances post to money accounts' operational accounts, and open items carry payment terms (holistic review, 2026-11-15).

**Formats and identities**

4. The template is one workbook, generated from the registry:
   - **Layout:** one sheet per command type, columns as payload field paths in `snake_case`, and an `external_code` column.
   - **Headers** carry field meanings (Principle 7).
   - **Values** use the API's canonical forms (ADR-0006 rule 13; ADR-0007 rule 3).
   - **Readers.** A reader for an old system (DS-40, D16) writes the same structure.
   - **Screens.** Import batches are operated through generated screens (ADR-0040): rows, errors, simulate and run.
5. Import batches are created with `CreateImportBatch` (file as attachment, target migration and phase) in state `draft`, checked with `ValidateImportBatch` (simulating every chunk, ADR-0030 rule 9) and run with `RunImport` (`human_only`).
   - **External codes.** They resolve through `import_key_map` (company, table, `external_code`, `id`), generating a UUIDv7 for a new code (ADR-0006 rule 3). The key map and the old-account map of a draft batch live in the batch until a person runs it, so an agent preparing a batch changes no company data.
   - **Re-runs.** A corrected file re-run on the same database follows each row's state and the key map:
     - a master data row mapped and identical is skipped;
     - mapped and different becomes an `Update`;
     - an opening document must first be reversed (rule 14).

     Abandoning keeps the key map.
6. Old accounts. `old_account_map` maps each old account to one operational account, or splits it by detail given in the file or by a fixed share (flagged). Every account of the old trial balance must be mapped before reconciliation can pass.

**Opening documents** (internal, reversible while the migration is open, `is_approval_hold_allowed: false`; import chunks are consequence postings, ADR-0043 rule 5)

7. `opening_balance_entry`, one document per transaction currency (ADR-0011 rule 1), carries balance-sheet accounts with control kind `none` or `gr_ir`.
   - **Lines:**
     - account, side, amount in the document's currency, company amount at book (applied rate origin `book`, ADR-0011 rule 3), optional dimensions;
     - for GR/IR, the old receipt reference with a null purchase order line (ADR-0030 rule 3). A later supplier invoice clears such a line through a manual GR/IR clearing (flagged).
   - **Offset.** One offset line through `opening_balance`.
   - **Excluded accounts.** Receivables, payables and inventory are rejected with `opening_control_account`; they come from rules 8 and 9.
   - **Work in process, fixed assets and loans.** They post as plain balances before their subledgers are activated. Open production orders at cut-over are created as orders, and their detail comes with the activation's reclassification (ADR-0025 rule 4; ADR-0034 rule 15; flagged).
   - **The source.** The old trial balance is taken after the old system's closing. Income and expense accounts are not loaded. For a regime that closes only at year end, the migration closes profit and loss into retained earnings in the trial balance before loading (flagged).
8. `opening_open_item_entry`, one document per currency: one line per old invoice, credit, advance or payment on account, each creating an open item at its open amount with a book carrying amount.
   - **Line content:** partner, account (the partner's reconciliation account unless given), kind, `natural_side`, `reference` (old number), `partner_reference`, `document_date`, `due_date`.
   - **Dates.** The item's `posting_date` is `opening_date`, as its origin line's (ADR-0026 rule 3). The old posting date is kept in `original_posting_date` (a note on ADR-0026 rule 1).
   - **Installments** still open become one item each.
   - **Checks.** INV-30 to INV-33 hold (EC-50).
   - **Employee advances** need the employee as a partner (ADR-0019 rule 3).

   Each opening item line carries the old system's posting date as `original_posting_date`; advance and payment-on-account lines carry no due date and do carry `evidence_method`, how the advance was paid ([ADR-0048](0048-cash-bank-receivables-payables.md) rule 18).
9. Opening stock uses the stock document type `opening_balance` (ADR-0020 rule 7). Each line carries item, warehouse, bin (the default bin where there are no bins, ADR-0031 rule 8), stock status, handling unit, lot or serial, and quantity.
   - **Value per area.** The file gives one total value per item and valuation area. The handler spreads it over that item's lines by quantity, by largest remainder, so the lines sum exactly to the old books' value. A line without its total is rejected with `opening_unit_value_differs`.
   - **Preliminary price.** The total divided by the quantity becomes the first preliminary price (a note on ADR-0020 rule 11), so no costing run is needed in the migration period.
   - **Lots and serials** carry no cost of their own (ADR-0018; open question against spec 15).
   - **Processor locations** are allowed (ADR-0037 rule 1).
   - **Checks.** INV-20 to INV-24 hold.
10. Year-to-date at a mid-year cut-over. Income and expense of the fiscal year before the cut-over are loaded as `opening_turnover` rows (account, debit and credit turnover in company currency). These are non-posting figures that statutory reports of that year read (DS-26); the year's profit to date is already in the post-closing balance of retained earnings. Flagged.

    Note: `opening_turnover` is owned by `ledger` and written by `CreateOpeningTurnover`. Its rows hold turnover before closing entries, and carry `start_date` and `end_date` instead of a fiscal year, because the first fiscal year after a mid-year cut-over is short. DDL in DS-06 ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 14).

**Currencies and the clearing account**

11. Reconciliation. `old_balance` rows bring the old books' figures:
    - **What they cover:**
      - the trial balance per old account;
      - open items per partner, account and currency, by count and sum;
      - GR/IR per receipt;
      - stock quantity per item, warehouse, bin, lot or serial, and stock value per item and valuation area, the level ERPMe holds (ADR-0020).
    - **Comparing.** `GetMigrationReconciliation` compares them with ERPMe's figures on `opening_date`, through the old-account map.
    - **Accepting a difference.** `AcceptMigrationDifference` (`human_only`, by a holder of the `chief_accountant` role, with a reason) accepts a difference where ERPMe's figure stands because the old one is wrong (go-live). Differences do not touch the clearing account, because ERPMe's documents balance by construction.

    Note: "a holder of the `chief_accountant` role" means the permission `AcceptMigrationDifference`, on the leaf `opening_balance_entry` at level `full`, held through Finance `full` by templates `owner` and `chief_accountant` ([ADR-0054](0054-users-roles-and-authorizations.md) rules 8, 24).
12. `CompleteMigration` runs these steps:
    1. It checks that every batch is `posted`, `opening_balance_clearing` is zero in company currency, no difference is unaccepted, and INV-20 to INV-24 and INV-30 to INV-33 pass.
    2. Where the installation has a group currency, it posts a `migration_completion_entry` in the migration period. The entry has group-only lines per transaction currency of the clearing account (ADR-0011 rule 2) and moves the clearing account's group balance.
    3. It locks the migration period (rule 2).
    - **Per currency.** Each currency's offsets leave a transaction-currency balance on the clearing account by construction (ADR-0011 rule 4). That residual is expected. The account is never revalued: the core excludes `opening_balance_clearing` from every revaluation scope (a note on ADR-0011 rule 18).
    - **Group currency.** Group amounts are translated from transaction amounts (ADR-0011 rule 3) while company amounts are at book, so the group balance of the clearing account is not zero. Step 2's lines (transaction and company amounts zero) go through the new key `opening_group_translation` to `fx_difference_equity` (flagged; the TT99 template maps it to 413).
13. Opening VAT:
    - **Balances.** VAT balances load as balances (control kind `none`). Opening open items have no `tax_line`, so the `tax_payment_evidence` consumer ignores their settlements (ADR-0041 rule 15).
    - **The first return.** It carries forward `opening_vat_carry_forward` where `carry:` finds no earlier filed return (ADR-0041 rule 19).
    - **Corrections of pre-cut-over invoices.** They carry the original tax date and rate as entered fields, since no original exists in ERPMe.
    - **All flagged.**

**Reversal, agents, data**

14. `ReverseImportBatch` (`human_only`) reverses every posted document of a batch, newest first, as staged chunks, on the documents' own posting date, and only while the migration is not completed.
    - **What stops it:** `open_item_settled` (an item it would reverse is settled or adjusted), or `negative_stock` (stock it would remove is consumed).
    - **Master data** rows are not reversed.
    - **Tests.** DS-16 gets fault-injection edge cases for resume (ADR-0030 rule 9) and for bulk reversal.
15. The data migration agent (spec 14):
    - **What it does:** works on migrations in `draft` or `loading`, maps columns and old accounts inside draft batches, proposes duplicate merges as work items, and validates batches.
    - **What it may not do:** run, resume, abandon, reverse or complete.
    - **Taint.** Import files are outside content (ADR-0029 rule 10), so its runs are tainted, which its draft-only rights already allow.
    - **Proposals.** Human-run import batches are outside the change proposal carrier (ADR-0029 rule 4).

    The workflow is [ADR-0051](0051-agent-workflows.md) rules 26–28; draft batches are edited with `UpdateImportBatch`.
16. Data:
    - **Location.** Pilot data never enters the repository or CI.
    - **Personal data.** Contacts in import files are personal and go to a local model when an agent reads them (spec 17).
    - **Audit.** Imports and exports write audit records, and exports also write a processing-log entry (ADR-0038 rule 9).
    - **Retention.** Import files linked to posted opening documents become accounting evidence kept with the vouchers (ADR-0038 rule 15), with their personal data (flagged).

    Spec 17 has no local models in Phase 1; until the author decides, personal samples are removed whenever the routing switch is on ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 5; [ADR-0051](0051-agent-workflows.md) rule 28).

**Full export**

17. `ExportCompanyData` is `human_only`, needs the permission `ExportCompanyData` (only in the `owner` role template), and needs every field class. It runs as a long job, with an audit record and a processing-log entry.
    - **Output:** a zip written as a stream of per-table JSON Lines files in primary-key order, plus the attachment files and `manifest.json` (core and package versions, schema versions, row counts, file SHA-256s).
    - **Tables:** every company-scoped table, and the global reference rows those tables point to (currencies, system chart, transaction keys, movement types, work item kinds, the package data in use, and the display names of users in audit rows), so the package is self-contained for re-entry (ADR-0003 R13).
    - **What is left out:**
      - secrets (integration token hashes, TOTP and OIDC secrets, webhook credentials);
      - earlier exports and import files;
      - erased values, which stay masked (ADR-0019 rule 10).
    - **Download.** The zip is an attachment that is not accounting evidence. Its bytes are deleted after 7 days, and a download needs the same permission and is audited.
18. Historical transactions before the cut-over are not migrated in Phase 1 (open question); the rehearsal month of go-live is replayed as ordinary documents on staging.

    Note: comparatives of statements for ranges before the cut-over come from `report_comparative_value`, entered at migration ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 14).

## Context

DS-21 comes first at step 4. ADR-0030 rule 9 fixed staged imports, human-only posting and the close check; the clearing account and the `opening_balance` key exist; the TT99 template maps them to 999.

The first review found four problems in the earlier text:
- clearing could not be zero per currency when entries balance per currency;
- the batch rule of ADR-0030 deadlocked with phases;
- a migration period inside an ordinary fiscal year left open periods;
- year-to-date income and expense double-counted retained earnings under TT99's monthly closing.

SAP migrates with the Migration Cockpit, staging tables and migration clearing accounts; Odoo imports CSV per model. ERPMe keeps SAP's staging and clearing discipline, with every row going through the commands of daily work, simulated before it posts.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| A one-day migration fiscal year (chosen) | No stray open periods; locked at completion | A technical fiscal year in reports |
| Opening documents in the last period of an ordinary fiscal year | Familiar | Leaves earlier periods open; locking needs the close path |
| Post-closing trial balance, turnover as figures (chosen) | No double count of retained earnings; reports still get year-to-date | Reports read one more source |
| Loading year-to-date income and expense as balances | One source | Double counts under monthly closing |
| Clearing zero in company currency, group difference moved (chosen) | Reachable; explicit | One group-only posting |

## Constraints that come with the decision

- **Catalogs:**
  - transaction key `opening_group_translation` (required `fx_difference_equity`), with its TT99 row to 413;
  - edge cases for resume and bulk reversal faults.
- **ADR notes:**
  - ADR-0007 rule 18 and ADR-0012 rules 1, 7: the migration fiscal year and its lock;
  - ADR-0014 rule 10: typed opening documents;
  - ADR-0026 rules 1, 17: `original_posting_date`; opening items at step 4;
  - ADR-0027 rules 7, 8: opening types; export;
  - ADR-0030 rules 3, 9: GR/IR opening lines; batch state and the clearing check;
  - ADR-0041 rules 8, 15, 19: corrections of old invoices with entered original tax data; the evidence consumer skips opening items; the first return's carry-forward;
  - ADR-0011 rule 18: the clearing account is never revalued;
  - ADR-0020 rule 11: the opening unit value as the first preliminary price.
- **DS-04:** errors `opening_control_account`, `migration_not_open`, `migration_incomplete`, `migration_period_locked`, `opening_unit_value_differs` (`open_item_settled` exists).
- **Other design items:**
  - DS-16: the fault-injection edge cases;
  - DS-17: the `opening_balances_recorded` payload follows rules 7–10;
  - DS-26: `opening_turnover`;
  - DS-40: readers write the template.
- **Open questions:**
  - year-to-date turnover;
  - historical transactions;
  - fixed-share splits;
  - group translation;
  - opening VAT;
  - GR/IR and work in process;
  - fixed assets and loans as plain balances;
  - lot and serial cost;
  - import files as evidence;
  - phased batches against "one batch";
  - the export holder.

## Revisit when

- A pilot needs historical transactions or a cut-over that is not at a period start.
- An export larger than one job's limit.

## Documents updated

- **ADRs:** [docs/adr/0007-time-model.md](0007-time-model.md), [docs/adr/0011-multi-currency.md](0011-multi-currency.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0041-tax-engine.md](0041-tax-engine.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0014-universal-journal.md](0014-universal-journal.md), [docs/adr/0026-open-item-core.md](0026-open-item-core.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0030-commercial-seams-and-imports.md](0030-commercial-seams-and-imports.md): notes.
- **Catalogs:** [docs/catalogs/transaction-keys.csv](../catalogs/transaction-keys.csv), [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv).
- **Package draft:** [docs/design/DS-19-vietnam-tt99/](../design/DS-19-vietnam-tt99/README.md) (determination row).
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t04_opening.py`, finding L-12.
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
