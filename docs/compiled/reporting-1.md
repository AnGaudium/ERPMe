Module: reporting    Chunk: 1 of 2    Source ADRs: ADR-0049
Build step(s): 8    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `reporting`, chunk 1

## Purpose

`reporting` is a layer-4 module (ADR-0022.R2). It produces statutory statements, books and printed documents from report
definitions, reads the books through the contracts of the layer-3 modules and never posts. This chunk states the report
definition format, the source grammar, counterpart attribution, books, ranges and comparatives, the cut-over rules, the
report queries, drill-down, permissions and filing. Render jobs, exports, print templates, printing and the hand-overs to
other modules are in chunk 2. Country forms, lines and account numbers are package data of a localization package, not
of this module.

## Entities and tables

No DDL file creates a table of `reporting`; the index credits the module with no owned table.

Defined by rule, without DDL:

- `report_definition`: a company-added statement or book (R32); company data, change-tracked.
- `report_comparative_value`: a comparative value of a range before the cut-over (R44); company data, change-tracked.
- `statutory_report_filing`: the immutable snapshot of a filed statement (R56).
- `render_job`, `print_template`, `print_template_version`: owned by `reporting` (R3); stated in chunk 2 (ADR-0049.R20, ADR-0049.R24, ADR-0049.R28).

Reads: `journal_entry`, `journal_line`, `open_item`, `account`, `account_period_balance`, `opening_turnover` (owned by `ledger`, R43), `material_document`, `material_document_line`, `production_order_period_cost`, `partner`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateReportDefinition` | Leaf `report_finance`; verb level not stated; effect class `other`, `is_draft_only` (R33) | Code, kind, `effective_from`, header and lines | Writes a draft version of a `report_definition` artifact (R33) | not stated | `report_definition_invalid`, `report_definition_protected` |
| `UpdateReportDefinition` | As `CreateReportDefinition` | The definition and its changed content | Writes a draft version of a `report_definition` artifact (R33) | not stated | `report_definition_invalid` |
| `CreateReportComparativeValue` | Leaf `report_finance`; verb level not stated; effect class `master_data_change` | Report code, definition `effective_from`, line, `from`, `to`, amount, attachment | Adds a `report_comparative_value` row (R44) | not stated | not stated |
| `UpdateReportComparativeValue` | As `CreateReportComparativeValue` | not stated | Changes a `report_comparative_value` row (R44) | not stated | not stated |
| `DeleteReportComparativeValue` | As `CreateReportComparativeValue` | not stated | Removes a `report_comparative_value` row (R44) | not stated | not stated |
| `FileStatutoryReport` | `human_only`; leaf `report_finance` at post; role templates `owner` and `chief_accountant` (R51, R54) | Code, `from`, `to`, render job, submission reference | Stores an immutable `statutory_report_filing` from the render job's stored lines (R54 to R57) | not stated | `report_render_job_mismatch`, `report_not_fileable`; check results `report_snapshot_stale`, `report_periods_open` |
| `GetStatutoryReport` | Leaf `report_finance`; full record scope (R50) | Code, `from`, `to`, comparative range, `special_periods`, `display_unit` | Query (R45) | none (query) | See the line under the table |
| `ListBookRow` | Leaf `report_finance`; full record scope (R50) | Code, `from`, `to`, group filter, cursor | Query (R45) | none (query) | See the line under the table |
| `ListReportLineContribution` | Leaf `report_finance` | Code, line, range, column | Query (R48) | none (query) | not stated |
| `ListReportDefinition`, `GetReportDefinition` | Leaf `report_finance` | A date | Query: package and company definitions in force on the date, with their basis (R46) | none (query) | not stated |
| `ListStatutoryReportFiling`, `GetStatutoryReportFiling` | Leaf `report_finance` | not stated | Query: the snapshot and the difference per line from a fresh computation (R57) | none (query) | not stated |
| `ListReportComparativeValue` | Leaf `report_finance` | not stated | Query (R46) | none (query) | not stated |

`GetRenderJob` and `ListRenderJob` are named with the queries (R46); their rule is ADR-0049.R20 in chunk 2, on the leaf `general_access` (R51).

Codes of the report queries, bound by the rules to no single query: errors `report_definition_missing` (R6), `regime_setting_unverified` (R7), `report_range_invalid` (R36), `report_range_before_opening` (R42), `report_scope_incomplete` and `permission_denied` (R50); check results `report_comparative_missing` (R11, R42), `report_check_failed` (R25), `report_account_not_covered` (R26), `report_turnover_incomplete` (R40, R41). The package loader error is `report_definition_in_use` (R6).

`CreateOpeningTurnover` is a command of `ledger` (R43).

## Rules

### Module, layer and package data

R1. Statutory reports, books and printed documents are produced by the layer-4 module `reporting`. The format and the engine are regime-neutral: the core knows no form, no line and no account number. The statements, books, voucher forms, amount-in-words rules, product cost sheet and close checklist content of a regime are package data of its localization package (for Vietnam `l10n_vn`, under the test of ADR-0053.R1), all `unverified` until the author verifies them. Every figure is an exact sum of journal lines in company currency.
Source: ADR-0049.D0

R2. `reporting` reads journal lines, open items, account balances and `opening_turnover` through `ledger.contract`, stock through `inventory.contract`, taxes and returns through `tax.contract`, production period cost through `production.contract`, master data through `master_data.contract`, and document versions, approvals and attachments through the layer-2 contracts. It imports no other layer-4 module.
Source: ADR-0049.R1

R3. `reporting` never writes postings: it calls no posting interface of `ledger` or `inventory`. It owns the tables `report_definition`, `report_comparative_value`, `statutory_report_filing`, `render_job`, `print_template` and `print_template_version`. Agents and screens reach its queries through the registry and the read-only query layer (`query`, layer 5, DS-33), which exposes them; `reporting` itself never imports `query`.
Source: ADR-0049.R1

### Report definitions

R4. A report definition has the kind `statement` (lines with values, such as a balance sheet) or `book` (a listing of rows, such as a cash book). A package ships each definition version as a pair of files under `regimes/<regime>/reports/<code>/`: `<effective_from>.yaml` (the header) and `<effective_from>.csv` (the lines or columns). Format details join DS-14. Definitions are package rules (ADR-0016.R5): read live from the installed package, never copied into the company.
Source: ADR-0049.R2

R5. A definition code is the official form label in lowercase with every non-alphanumeric character as `_`, as ADR-0041.R19 does for tax returns. The official form label stays in the header as data.
Source: ADR-0049.R2

R6. The version used is the latest whose `effective_from` is on or before the report's end date; with none, the query fails with `report_definition_missing`. A version that any company has filed never changes; a correction is a new version with a later date. The package loader rejects a change to a filed version with the loader error `report_definition_in_use`, as ADR-0016.R13 does for settings.
Source: ADR-0049.R2

R7. The header carries the definition's basis, and every line or column row carries the basis columns of DS-14. Reading an `unverified` definition in a `production` installation fails with `regime_setting_unverified` (ADR-0016.R12).
Source: ADR-0049.R2

R8. Statement header fields:
- `code`, `kind`, `form` (the official label), names in English and each package language, `effective_from`;
- `is_fileable`: whether `FileStatutoryReport` accepts it;
- `comparative`: `day_before_from`, `prior_year_range` or `none` (R39);
- `term_months`: the horizon of the short-term and long-term split (R16); required when any term of the version uses `term=`; no core default, the value is the regime's choice and package content;
- `display_rounding`: optional, a rounding mode of ADR-0006 for displayed values; without it, half away from zero;
- `coverage`: optional list of account types (ADR-0010.R3) whose accounts must all be reached (R26);
- `cash_flow`: for a cash flow statement, `method` (`direct` or `indirect`) and `cash_accounts`, an account selector (R34);
- `exports`: optional `xml` with a Jinja2 XML template file and an XML schema file (ADR-0049.R21);
- `field_classes`: field classes (ADR-0017.R10) the definition reads, normally empty for statements.
Source: ADR-0049.R3

R9. Statement line columns, one row per line, in display order:
- `line`: the line code, unique in the version;
- `kind`: `heading` (a label only), `line` (a value) or `check` (a formula that must be zero, never displayed);
- `level`: indentation, 0 for top level;
- `label_en` and `label_<language>`;
- `note`: the reference to the notes to the statements, optional;
- `source` (R10);
- the basis columns.
Source: ADR-0049.R4

### Sources, selectors and measures

R10. A `source` is a list of terms separated by `;` and summed. A term prefixed with `-` is subtracted. The minus sign is the ASCII hyphen-minus `-` everywhere: in terms, in formulas and in data files. A `line` row with an empty source has the value zero. Terms:
- `account:<selector>:<measure>[:<option>]...` (R12 to R19);
- `cash_in:<selector>` and `cash_out:<selector>` (R34);
- `report:<code>:<line>`: a line of another statement, over the same range and options;
- `carry:<line>` (R11);
- `formula:<expression>` (R23).
Source: ADR-0049.R5

R11. `carry:<line>` is the line's value over the prior range, which is the comparative range of the header's `comparative`. It comes from the latest filing of this report over exactly that range, else from the line's `report_comparative_value` for that range. With neither, the term is empty with the check result `report_comparative_missing`, and so are its line and every formula that depends on it. A version whose header has `comparative: none` may not use `carry:` (`report_definition_invalid`).
Source: ADR-0049.R5

R12. An account selector is an operational account code, or several joined by `|`, each meaning that account and all its descendants in the company's operational tree (`account.parent_id`, ADR-0010.R10). `!<code>` removes an account and its descendants. A company's own detail accounts under a package account are therefore reached without any change to the definition. A code that the company does not have contributes zero.
Source: ADR-0049.R6

R13. Measures, all in company currency:
- `opening`: balance at the end of the day before `from`, signed debit positive;
- `opening_debit`, `opening_credit`: the debit and credit parts of that balance, split by R18, both zero or positive;
- `debit_turnover`: sum of company amounts of lines with `side` debit in the range, storno lines included, so they lower it (ADR-0014.R6);
- `credit_turnover`: minus the sum of company amounts of lines with `side` credit in the range, storno included;
- `change`: `debit_turnover` minus `credit_turnover`;
- `closing`: balance at the end of `to`, signed debit positive;
- `closing_debit`, `closing_credit`: the debit and credit parts of that balance, split by R18.
Source: ADR-0049.R6

R14. A liability's `closing` is negative; a definition presents it as a positive figure with `closing_credit` or a `-` term. Lines of entries in a migration fiscal year (ADR-0044.R2) count in balances and never in turnover measures.
Source: ADR-0049.R6

R15. Options of an `account:` term are each `<key>=<value>` and are applied in this order: filter, group, split. `kind=<kinds joined by |>` keeps only lines whose open item has one of these kinds (ADR-0026.R2).
Source: ADR-0049.R7

R16. `term=short` or `term=long` keeps only lines whose open item is due on or before the day `term_months` after `to` (short) or later (long); that day is found by the month-end rule of R38. `undated=short` or `undated=long` places items without a due date (advances, payments on account). `undated` is required with `term`, and the package sets it: where such items belong is the regime's choice, flagged package content.
Source: ADR-0049.R7

R17. `kind`, `term`, `undated` and `by=partner_kind` are valid only on selectors whose accounts have the effective control kind `receivable`, `payable` or `loan` (ADR-0025.R4), where every line carries an open item (ADR-0014.R10).
Source: ADR-0049.R7

R18. `by=account`, `by=partner` or `by=partner_kind` says how a balance is grouped before it is split into its debit and credit parts: each group's net balance is a debit part when positive and a credit part when negative. `account` groups by postable operational account. `partner` groups by account and `partner_id`. `partner_kind` groups by account, partner and open-item kind, so a bilateral account presents customer or supplier advances apart from receivables or payables (ADR-0010.R6, ADR-0010.R15, ADR-0026.R2). `by` is required on every `opening_debit`, `opening_credit`, `closing_debit` and `closing_credit` term. There is no core default: the grouping is the regime's choice, written in its definitions and flagged.
Source: ADR-0049.R7

R19. `closing_entries=exclude` leaves out entries with `is_closing_entry` (ADR-0012.R18; ADR-0014.R1); income statement lines use it on turnover measures, so the closing to the income summary does not cancel them. `counterpart=<selector>` is valid on turnover measures only: it keeps only the part of each line attributed by R20 to lines on the selected accounts.
Source: ADR-0049.R7

### Counterpart attribution

R20. Counterpart attribution splits each journal entry into pairs of a positive and a negative line. It is a pure function of the entry, used by `counterpart=`, by the counterpart column of books (`counterpart_accounts`) and by the direct cash flow. Let P be the entry's lines with a positive company amount, N those with a negative one, and S the sum over P. The exact pair amount of positive line i and negative line j is |a_i| × |a_j| ÷ S. Lines with a zero company amount take no part.
Source: ADR-0049.R8

R21. Every pair is its exact amount rounded down or up to the currency's minor unit, and every line's pairs sum exactly to its own amount (`INV-400`). The computation uses only line numbers and absolute amounts. The side that holds the entry's lowest line number is the first side. The steps, in order:
- each pair starts at its exact amount rounded down;
- the missing units go one at a time to the pair with the largest remainder whose lines on each side still need a unit; ties go to the lower line number on the first side, then on the other side;
- a unit still missing after that is placed along the shortest alternating path, searched breadth-first in line-number order: it rounds up a pair with a remainder that is still rounded down, and rounds down a pair rounded up earlier, until it reaches a line that still needs a unit. Such a path always exists.
Source: ADR-0049.R8

R22. Line i is attributed +m_ij to line j, and line j is attributed -m_ij to line i, so pairs between lines of the same report scope (cash accounts, R34) cancel exactly. A reversal entry has the original's lines with negated amounts and the same line numbers (ADR-0014.R8), so its pairs are exactly the original's, negated. When the entry has one line on one side, the result equals a largest-remainder split of that line in proportion to the others.
Source: ADR-0049.R8

### Formulas, checks and coverage

R23. The formula grammar holds `[line]` references to lines of the same version, `+`, `-` (binary and unary), parentheses, `pos(x)` = max(x, 0) and `neg(x)` = max(-x, 0); `neg` returns a magnitude. Nothing else: no constants, no division, no other functions. Lines are evaluated in dependency order. A cycle through formulas or `report:` terms is rejected by package CI and by `CreateReportDefinition` (`report_definition_invalid`).
Source: ADR-0049.R9

R24. Values are sums of amounts at the minor unit, so every value and every check is exact. A display unit (for example thousands) is a query and render option. It rounds each displayed value on its own, half away from zero unless the header's `display_rounding` names another mode, and never what checks and formulas use. A displayed total is the rounded total, not the sum of the rounded lines.
Source: ADR-0049.R9

R25. A `check` line that is not zero gives the check result `report_check_failed` naming the line and its value (`INV-403`). A balance sheet uses it for total assets against total sources; a cash flow statement for the reconciliation with cash.
Source: ADR-0049.R9

R26. When the header lists `coverage`, every postable account of those types (through its system account) with a non-zero `closing`, or a non-zero turnover for income and expense types, must be named by at least one `account:` term of the version. Otherwise the check result `report_account_not_covered` lists the accounts.
Source: ADR-0049.R9

### Books

R27. A book definition lists rows of one row source. The row sources are a closed list, extended by ADR:
- `journal_line`: general journal, general ledger, detailed ledgers, cash book and bank book;
- `material_document_line`: inventory detail with quantities, and values from the linked journal lines;
- `stock`: per item, warehouse and owner, quantities from material document lines and values from inventory journal lines, as of a date or over a range;
- `open_item`: open items as of a date with their open amounts, kinds and due dates;
- `production_order_period_cost`: per order, period and cost component (ADR-0035).
Source: ADR-0049.R10

R28. A row source's fields are the fields of its query's generated result schema (ADR-0022.R17), plus the computed fields `debit`, `credit` (the line's company amount by side), `counterpart_accounts` (codes from R20), `running_balance`, `quantity_in`, `quantity_out` and `running_quantity`. A book header holds, beside the statement header's names, dates and basis:
- `row_source`;
- `scope`: an account selector, for `journal_line` and `stock`;
- `filters`: field and value pairs, for example `owner: non_owned`;
- `group_by`: fields;
- `rows`: `line`, or `counterpart` for one row per counterpart pair as a general ledger shows it;
- `period`: `range` or `as_of`.
The columns CSV holds `column`, `label_en`, `label_<language>`, `field`, `total` (`sum` or empty) and the basis columns. Each group shows an opening row (for `range` books), its rows, a totals row and a closing row (`INV-402`).
Source: ADR-0049.R10

R29. Row order for `journal_line` and `material_document_line`: posting date, then document number (ADR-0014.R4), then document type and `journal_entry.id` (`material_document.id` for rows from material documents) as the final tiebreaks between entries, then line number within the entry. With `rows: counterpart`, a line's pairs follow in the counterpart line's number. For `open_item`: the group fields, then the open item's ID.
Source: ADR-0049.R10

R30. `stock` and `production_order_period_cost` rows are aggregates without an ID of their own and end on their natural key. For `stock`: the group fields, then `item_id`, `warehouse_id`, `owner_partner_id` (null for own stock, ADR-0030.R8) and `lot_id` or `serial_number_id`, whichever the item tracks, where the row source exposes them (ADR-0020.R8). For `production_order_period_cost`: the group fields, then `production_order_id`, `posting_period_id` and the cost component (`material`, `labor`, `overhead`, `other`, in that order; ADR-0035). In every key, group fields included, null sorts before any value, and the cursor compares it that way: null equals null, and null is less than any value. The `ListBookRow` cursor carries the same keys, so a page never repeats or skips a row.
Source: ADR-0049.R10

R31. The books named: the general journal; the general ledger per account; detailed ledgers per account and partner, or per account and item; the cash book per money account (each money account has its own operational account, ADR-0048.R2, so grouping by account suffices); the bank book; inventory detail per item and warehouse; materials held for others (ADR-0049.R22). Which books a regime requires, and their forms, are flagged package data.
Source: ADR-0049.R10

### Company definitions

R32. A company may add its own statements and books as company data in `report_definition`: `company_id`, code, kind, `effective_from`, header and lines as JSON, basis `company_decision`, change-tracked. A code that a package definition of the company's regime uses is rejected with `report_definition_protected`; a company never changes or hides a package statutory definition. Package definitions are rules read live; company definitions are company data beside them. Company definitions cannot be filed (`report_not_fileable`).
Source: ADR-0049.R11

R33. `CreateReportDefinition` and `UpdateReportDefinition` write a draft version of a `report_definition` artifact (effect class `other`, `is_draft_only`) and validate the grammar of R9 to R31 (`report_definition_invalid`). The draft's evidence (`CreateArtifactEvidence`, ADR-0059.R11) is a render of the draft on a closed period compared with at least one cell a person checked by hand, given when the evidence is created. Activation raises the version with `SetArtifactVersionState` (ADR-0059.R11) through a change proposal, so agents reach an active definition only through change proposals (ADR-0029.R1, ADR-0029.R5).
Source: ADR-0049.R11, ADR-0049.R11.N1

### Cash flow

R34. The package declares the method in the cash flow statement's header; the engine supports `direct` and `indirect`. Direct: `cash_in:<selector>` sums, over lines on `cash_accounts` with `side` debit in the range, the parts that R20 attributes to lines on the selected counterpart accounts; `cash_out:<selector>` does the same for `side` credit, signed, so outflows are negative. Parts attributed to other cash accounts are internal transfers and are left out; they cancel exactly, so the parts on all non-cash counterparts sum exactly to the change in cash. A package covers every counterpart through its selectors, and a `check` line compares the flows with `account:<cash>:change`. An entry with several counterpart lines is split in proportion by R20 to R22.
Source: ADR-0049.R12

R35. Indirect: profit before tax by a `report:` term on the income statement, adjusted by `change` measures of working-capital accounts and turnover measures with `counterpart=`. Which method a regime's package ships, and whether it ships a second definition a company may choose to render, is a flagged package choice (DS-19 data); whether a regime requires one method is the author's to verify.
Source: ADR-0049.R12

### Ranges and comparatives

R36. Every report runs over a date range `from`–`to`, never a fiscal year code (ADR-0007.R23). Balances read `to` (and `from` minus one day for `opening`); turnover reads the range. `from` after `to` is rejected with `report_range_invalid`.
Source: ADR-0049.R13

R37. Special-period entries carry the fiscal year's last day as posting date (ADR-0012.R2), so a range ending on that day includes them. The parameter `special_periods` is `include` (the default) or `exclude`. `exclude` removes only the special-period entries of the fiscal year whose last day is `to`, and removes them from turnover measures, `change` and `closing` alike, so opening plus change still equals closing. `opening` always includes them, and special-period entries of earlier fiscal years stay in every measure. When `to` is not a fiscal year's last day, `exclude` changes nothing.
Source: ADR-0049.R13

R38. Closing entries are in balances; income lines exclude them with `closing_entries=exclude` (R19). A date moves one year back to the same day, except a month's last day, which moves to the last day of the same month: 28 February 2025 becomes 29 February 2024, and 29 February 2024 becomes 28 February 2023. Moving a date by months (the `term_months` horizon, R16) follows the same rule, so from 31 December it is 31 December.
Source: ADR-0049.R13, ADR-0049.R7

R39. Comparatives are the same definition version over an earlier range, with `from` and `to` moved one year earlier by R38. `day_before_from` uses the range from `from` moved one year earlier to the day before `from`, so its balances are those at the day before `from` (the balance sheet's opening column, also for an interim balance sheet whose `from` is the start of the year). `prior_year_range` moves both dates (the income statement's comparative). A caller may pass another comparative range.
Source: ADR-0049.R13

### Before the cut-over

R40. A balance at a date on or after the migration's `opening_date` (ADR-0044.R10, ADR-0044.R18) is computed from the opening documents and later lines; a balance before it cannot be computed. A range that starts on or before `opening_date` and ends after it adds the `opening_turnover` rows of each account whose `start_date` equals `from` and whose `end_date` is `opening_date`. ADR-0044 loads them for income and expense only, so other accounts' turnover in such a range is incomplete and gives the check result `report_turnover_incomplete`.
Source: ADR-0049.R14

R41. `opening_turnover` is turnover before closing entries. It is added only to turnover measures with `closing_entries=exclude`; a turnover term without that option on an account with an `opening_turnover` row, over such a range, gives `report_turnover_incomplete`. `opening_turnover` has no journal entries to pair: `counterpart=`, `cash_in` and `cash_out` terms over a range that straddles `opening_date` give `report_turnover_incomplete`, and their value covers only the lines after the cut-over.
Source: ADR-0049.R14

R42. Any other range reaching before `opening_date` cannot be computed and uses the `report_comparative_value` rows of exactly that range. Without them, a comparative cell stays empty with the check result `report_comparative_missing`, and a current range fails with `report_range_before_opening`.
Source: ADR-0049.R14

R43. `opening_turnover` is owned by `ledger` (layer 3), because `reporting` may not import `imports` (layer 5). Its rows are written by `CreateOpeningTurnover` in the migration's batches and never change after `CompleteMigration`. Its DDL draft is in DS-06: `company_id`, `account_id`, `start_date`, `end_date`, `company_debit_turnover`, `company_credit_turnover`, unique on (company, account, start date). It holds dates and no fiscal year, because at a mid-year cut-over the company's first fiscal year is short (ADR-0044.R2) while the legal year is not.
Source: ADR-0049.R14

R44. `report_comparative_value` is a company table: report code, definition `effective_from`, line, `from`, `to`, amount in company currency, the attachment of the old filed statement, basis `company_decision`, change-tracked. The commands `CreateReportComparativeValue`, `UpdateReportComparativeValue` and `DeleteReportComparativeValue` have effect class `master_data_change`. The migration loads the rows; a company may add them later.
Source: ADR-0049.R14

### Queries and drill-down

R45. `GetStatutoryReport` (code, `from`, `to`, comparative range, `special_periods`, `display_unit`) returns every line with its current and comparative value (exact, and rounded to the display unit when one is given, R24), the definition version with its content hash and basis, and the check results. `ListBookRow` (code, `from`, `to`, group filter) returns a book's rows by cursor, with opening, totals and closing rows per group.
Source: ADR-0049.R15

R46. The other queries are `ListReportLineContribution` (R48), `ListReportDefinition` and `GetReportDefinition` (package and company definitions in force on a date, with their basis), `ListStatutoryReportFiling` and `GetStatutoryReportFiling` (R57), `ListReportComparativeValue`, `GetRenderJob` and `ListRenderJob` (ADR-0049.R20).
Source: ADR-0049.R15

R47. Each query reads one snapshot. Balances of locked periods may come from `account_period_balance` (ADR-0014.R18), which an invariant ties to the lines (ADR-0014.R15); the result is the same either way. Results carry check results in the `checks` format of DS-04. Queries keep the 30-second limit (ADR-0022.R9), and 10 seconds for agent runs (ADR-0050.R43). Large books are read by cursor or rendered as a job (ADR-0049.R20).
Source: ADR-0049.R15

R48. `ListReportLineContribution` (code, line, range, column) lists every journal line that contributes to a figure: posting date, document number and type, account, partner, and the line's contribution (its amount, its attributed part under R20, or its share of a bilateral group). The order is the book row order of R29: posting date, document number, document type, `journal_entry.id`, line number. Formula lines list the lines they refer to, each drillable in turn. Values from migration data (`opening_turnover`, `report_comparative_value`) appear as such, with their source. The sum of contributions equals the figure (`INV-401`).
Source: ADR-0049.R16

R49. The analysis layer's drill-down to the rows behind a cell keeps the contract of R48 for its facts over journal lines; that query is owned by `query`, not by `reporting`. The rows behind a cell are journal lines with their contributions, and the cell equals their sum, or for a balance an opening row plus the lines, as the books of R28 (`INV-410`; ADR-0060.R16).
Source: ADR-0049.R16.N1

### Scope, field classes, permissions and agents

R50. Statements and books need the whole company. An actor whose record scope (ADR-0017.R9) is limited gets `report_scope_incomplete`, never totals with rows left out; scoped views of the same data are ordinary DS-33 lists with `is_scope_filtered`. A definition that reads fields with a field class (for example unit costs in an inventory book, the product cost sheet) lists them in `field_classes`; an actor without them gets `permission_denied`. Statements built from journal amounts list none.
Source: ADR-0049.R17

R51. Each query and command is its own permission (ADR-0017.R4). By ADR-0054.R24 the authorization leaves are:
- `report_finance`: the reporting queries, `RenderReport`, report definitions, comparative values and `FileStatutoryReport`;
- `report_tax`: `RenderTaxReturn` and `FileTaxReturn`;
- `general_access`: `RenderPrint`, `GetPrintData` and the render job queries, each checking the subject's own `Get<Type>` and read scope;
- `print_template`: only templates and print data contracts, so it gives no access to document content;
- `print_profile`: print profiles, which only the `owner` template holds.
The reporting queries go to the role templates `owner`, `chief_accountant`, `accountant` and, read-only, `auditor`; filing goes to `owner` and `chief_accountant`. The cashier gets no report leaf, because book queries cannot be narrowed to the cash book.
Source: ADR-0049.R17, ADR-0049.R17.N1

R52. Agents may read statements, books and drill-downs through the query layer, to answer questions and explain figures. Statements and books are operational-account views, while ADR-0010.R14 makes agents reason in system accounts: reading them is allowed; using an operational code to choose an account, a policy input or a posting is not. Agents never file.
Source: ADR-0049.R18

R53. Agents also answer questions through the analysis layer, whose ledger measures select system accounts and follow R14, R19 and R37: migration entries never in turnover, `closing_entries=exclude` on profit-and-loss measures, and the `special_periods` option. At full scope each such measure equals the turnover measure of R13 over the operational accounts mapped to the subtree (`INV-411`). Statement lines are not claimed, since a line may split a measure by side or partner (ADR-0060.R35).
Source: ADR-0049.R18.N1

### Filing

R54. `FileStatutoryReport` (code, `from`, `to`, render job, submission reference) records that a statement was submitted to an authority. It is `human_only`; the verb File is in the glossary. The render job must be a `done` job of kind `report` for the same code and range, whose definition content hash equals that of the version in force for the range now. Any other job is refused with `report_render_job_mismatch`, whose `details` give the reason. The command takes the snapshot from the job's stored lines (ADR-0049.R20) and recomputes nothing, so the filing records exactly the file the person submitted.
Source: ADR-0049.R19

R55. When the inputs seem to have changed since the render, filing still succeeds and stores the check result `report_snapshot_stale`, as it stores `report_periods_open`. The signal is best effort, stored and never enforced: the journal-entry count up to `to` differs from the count the job stored (journal entries are append-only, the test of ADR-0012.R12), or the `report_comparative_value` rows of its ranges differ from the hash it stored. It misses inputs that change figures without a journal entry, such as an account moved to another parent, an open item's due date read by `term=`, or `opening_turnover` rows changed before `CompleteMigration`; the difference view of R57 shows those, and a supplement handles the drift.
Source: ADR-0049.R19

R56. Filing stores an immutable `statutory_report_filing`: company, code, the definition version (package version, `effective_from`, content hash), range, comparative range, options, the render job, every line's current and comparative value and the lines' hash from that job, check results, `supplement_number` (0 for the first filing of that report and range), `filed_at`, `filed_by`, the submission reference, and the job's file as the submitted file. Triggers reject changes.
Source: ADR-0049.R19

R57. Filing is allowed only for package definitions with `is_fileable` (`report_not_fileable`). A range with a regular period not locked in `general` gives the check result `report_periods_open`; filing still succeeds (flagged). `GetStatutoryReportFiling` returns the snapshot and the difference per line from a fresh computation; a later adjustment, for example in a special period, shows there and is filed as a supplement. The submitted file's attachment is accounting evidence (ADR-0038.R15).
Source: ADR-0049.R19

## Invariants

This chunk carries the invariants whose catalog source names a rule of this chunk. `INV-404` and the invariants sourced
from ADR-0060 only have their rows in chunk 2.

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-400` | day | `counterpart_pairs_exact`: for every journal entry, the counterpart pairs sum exactly to each line's company amount, and each pair is its exact share rounded down or up to the minor unit. | R20, R21 |
| `INV-401` | run | `report_drill_down_equals_figure`: every statement figure computed from account terms equals the sum of the contributions its drill-down lists. | R48 |
| `INV-402` | run | `book_balances_tie_to_accounts`: each book group's opening and closing balance equals the balance of its accounts (by partner or item where grouped) on those dates, opening plus rows equals closing, and the stock valuation book's total equals the inventory accounts. | R28; ADR-0049.R22 |
| `INV-403` | run | `statement_checks_hold` (flagged: check lines and coverage are package data): for each regular period of the run locked in `general`, and for each fiscal year of the run whose regular periods are all locked in `general`, over the range from its first to its last day, every check line of every package statement in force on the last day is zero, and no account is reported as not covered. | R25, R26 |
| `INV-411` | run | `management_turnover_equals_report_turnover`: for full scope, every range and every system account subtree, each ledger analysis measure equals the turnover measure of R13 over the operational accounts mapped to that subtree for the same range and `special_periods` option (`change`, `debit_turnover` or `credit_turnover`), with `closing_entries=exclude` for the profit-and-loss measures and migration entries left out, in every regime. | R13, R19, R53 |

## Edge cases

This chunk carries the edge cases whose catalog source names a rule of this chunk.

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-92` | `special_period_adjustment_in_year_end_report` | An adjustment posts in the special period after the last regular period is locked; year-end statements include it, and a report of the last month with special periods excluded does not. | `must_succeed` | R37 |
| `EC-93` | `customer_advance_and_invoice_at_year_end` | A customer has an open invoice and an unapplied advance at year end; the balance sheet presents them by the package's bilateral split, and the parts sum to the account balance. | `must_succeed` | R18 |
| `EC-94` | `adjustment_after_filing` | A statement is filed, then an adjustment changes it; the filing shows its snapshot and the difference, which a supplement files. | `must_succeed` | R57 |
| `EC-95` | `mid_year_cut_over_comparatives` | A company migrated mid-year: the year's income statement adds the opening turnover, and prior-year comparatives come from stored comparative values. | `must_succeed` | R40, R42 |
| `EC-96` | `payment_with_several_counterparts_in_cash_flow` | A payment settles an invoice with a bank charge and a realized exchange difference; the direct cash flow splits it in proportion and its check line holds. | `must_succeed` | R34 |
| `EC-97` | `filing_after_late_posting` | A statement is rendered, then a document posts into its range; filing that render succeeds with the check result `report_snapshot_stale`, and the filing's difference view shows the posting. | `must_succeed` | R55 |
| `EC-170` | `analysis_year_closed_by_entries` | A regime closes profit and loss by closing entries and an adjustment posts in the special period: net revenue for the year excludes the closing entry and includes the adjustment, `special_periods` `exclude` leaves it out, the closing balance of the revenue subtree after closing is zero, and both agree with the turnover of R13. | `must_succeed` | R19, R37; ADR-0060.R4, ADR-0060.R7, ADR-0060.R35 |

## Settings

None: the rules of this chunk name no setting key; `special_periods` and `display_unit` are query parameters, and `term_months`, `undated` and `by` are fields of package definitions.

## UI annotations

None: the sources of this chunk hold no ADR-0077 annotation.

## Conflicts

CONFLICT ADR-0049.R11: the rule gives `CreateReportDefinition` and `UpdateReportDefinition` the effect class `master_data_change`; the later note ADR-0049.R11.N1 (ADR-0059, 2026-11-15) governs: they write a draft artifact version with effect class `other` and `is_draft_only`, and activation goes through a change proposal (R33).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0049.D0 | R1 |
| ADR-0049.R1 | R2, R3 |
| ADR-0049.R2 | R4, R5, R6, R7 |
| ADR-0049.R3 | R8 |
| ADR-0049.R4 | R9 |
| ADR-0049.R5 | R10, R11 |
| ADR-0049.R6 | R12, R13, R14 |
| ADR-0049.R7 | R15, R16, R17, R18, R19, R38 |
| ADR-0049.R8 | R20, R21, R22 |
| ADR-0049.R9 | R23, R24, R25, R26 |
| ADR-0049.R10 | R27, R28, R29, R30, R31 |
| ADR-0049.R11 | R32, R33 |
| ADR-0049.R11.N1 | R33 |
| ADR-0049.R12 | R34, R35 |
| ADR-0049.R13 | R36, R37, R38, R39 |
| ADR-0049.R14 | R40, R41, R42, R43, R44 |
| ADR-0049.R15 | R45, R46, R47 |
| ADR-0049.R16 | R48 |
| ADR-0049.R16.N1 | R49 |
| ADR-0049.R17 | R50, R51 |
| ADR-0049.R17.N1 | R51 |
| ADR-0049.R18 | R52 |
| ADR-0049.R18.N1 | R53 |
| ADR-0049.R19 | R54, R55, R56, R57 |
