# ADR-0049: Statutory reporting and printing

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design items: DS-26, DS-27. Related decisions: D7, D8, D9, D14. Principles 2, 5, 6, 7, 10, 12. ADR-0002, ADR-0004, ADR-0007, ADR-0009, ADR-0010, ADR-0012, ADR-0013, ADR-0014, ADR-0016, ADR-0017, ADR-0018, ADR-0019, ADR-0021, ADR-0022, ADR-0023, ADR-0026, ADR-0027, ADR-0028, ADR-0029, ADR-0035, ADR-0037, ADR-0038, ADR-0039, ADR-0040, ADR-0041, ADR-0044, ADR-0047, ADR-0048, ADR-0050, ADR-0052, ADR-0053; spec 06, 07, 08, 15, 16.

## Decision

Statutory reports, books and printed documents are produced by one new layer-4 module, `reporting`. It reads the books through the contracts of the layer-3 modules and never posts.

**Reports are package data.** A statement (B01, B02, B03 in TT99) or a book is a report definition: a small dated header and one CSV of lines or columns, shipped in the localization package as a package rule and read live (ADR-0016 rule 5). The line grammar is the tax-return grammar of ADR-0041 rule 19, extended with account sources: an account selector, a measure (opening, turnover by side, closing, or the debit and credit parts of a bilateral balance) and a few options. The core knows no form, no line and no account number. A company may add its own definitions but never changes the package's.

**One deterministic engine.** Every figure is an exact sum of journal lines in company currency. Every figure can be drilled down to the journal lines behind it. Where a report needs to know what a line was posted against (the counterpart column of a ledger, the direct-method cash flow), each entry is split into pairs by one proportional rule whose rounding sums exactly. Comparatives come from the same definition over an earlier range; years before the cut-over come from migration data, because history is not migrated.

**Filing and files.** Filing stores an immutable snapshot taken from a finished render job, as for tax returns; a later recomputation shows the difference. A file (PDF, XLSX or XML) is produced by a render job on the `pdf` queue and stored as an attachment. The new verb Render requests it.

**Printing.** A print template is Jinja2 HTML and CSS rendered to PDF by WeasyPrint (ADR-0002). It is a package template copied into the company, which may change its copy. A template sees only a versioned print data contract: the document's version content plus derived print fields. So core changes do not break company templates (spec 16). Untrusted fields are always escaped. Cost and margin never reach a customer-facing print. Printing is not sending.

**Core and overlay.** The author's rule (2026-11-15) applies, with ADR-0053 rule 1's test: Vietnamese accounting and tax are an overlay in `l10n_vn`. TT99's B01, B02 and B03, the Vietnamese books, voucher forms, amount-in-words rules, the product cost sheet and the close checklist content are package data, all `unverified` until the author verifies them. The format and the engine are regime-neutral; Vietnamese names appear here only as labelled examples.

### Rules

**Module**

1. `reporting` is a new layer-4 module (ADR-0022 rule 2 gets a note).
   - **Reads.** It reads journal lines, open items, account balances and `opening_turnover` through `ledger.contract`, stock through `inventory.contract`, taxes and returns through `tax.contract`, production period cost through `production.contract`, master data through `master_data.contract`, and document versions, approvals and attachments through the layer-2 contracts. It imports no other layer-4 module.
   - **Never writes postings.** It calls no posting interface of `ledger` or `inventory`.
   - **Owns** the tables `report_definition` (company-added definitions, rule 11), `report_comparative_value` (rule 14), `statutory_report_filing` (rule 19), `render_job` (rule 20), `print_template` and `print_template_version` (rule 24).
   - **Agents and screens** reach its queries through the registry and the read-only query layer (`query`, layer 5, DS-33), which exposes them. `reporting` itself never imports `query`.

**Report definitions**

2. A report definition is one of two kinds: `statement` (lines with values, such as a balance sheet) or `book` (a listing of rows, such as a cash book; rule 10).
   - **Files.** A package ships each definition version as a pair of files under `regimes/<regime>/reports/<code>/`: `<effective_from>.yaml` (the header, rule 3) and `<effective_from>.csv` (the lines or columns, rules 4 and 10). Format details join DS-14.
   - **Kind of component.** Definitions are package rules (ADR-0016 rule 5): read live from the installed package, never copied into the company.
   - **Codes.** A code is lowercase with every non-alphanumeric character as `_`: the TT99 form `B01-DN` has code `b01_dn`, as ADR-0041 rule 19 does for `01/GTGT` (ADR-0004 rule 5 gets a note). The official form label stays in the header as data.
   - **Dating.** The version used is the latest whose `effective_from` is on or before the report's end date; with none, the query fails with `report_definition_missing`. A version that any company has filed (rule 19) never changes; a correction is a new version with a later date. The package loader rejects a change to a filed version with the loader error `report_definition_in_use`, as ADR-0016 rule 13 does for settings.
   - **Basis.** The header carries the definition's basis, and every line or column row carries the basis columns of DS-14. Reading an `unverified` definition in a `production` installation fails with `regime_setting_unverified` (ADR-0016 rule 12).
3. Statement header fields:
   - `code`, `kind`, `form` (the official label), names in English and each package language, `effective_from`;
   - `is_fileable`: whether `FileStatutoryReport` accepts it (rule 19);
   - `comparative`: `day_before_from`, `prior_year_range` or `none` (rule 13);
   - `term_months`: the horizon of the short-term and long-term split (rule 7). It is required when any term of the version uses `term=`, and has no core default, because the horizon is the regime's choice (12 months in TT99);
   - `display_rounding`: optional, a rounding mode of ADR-0006 for displayed values (rule 9); without it, half away from zero;
   - `coverage`: optional list of account types (ADR-0010 rule 3) whose accounts must all be reached (rule 9);
   - `cash_flow`: for a cash flow statement, `method` (`direct` or `indirect`) and `cash_accounts`, an account selector (rule 12);
   - `exports`: optional `xml` with a Jinja2 XML template file and an XML schema file (rule 21);
   - `field_classes`: field classes (ADR-0017 rule 10) the definition reads, normally empty for statements.
4. Statement line columns, one row per line, in display order:
   - `line`: the line code, unique in the version (e.g. `110`);
   - `kind`: `heading` (a label only), `line` (a value) or `check` (a formula that must be zero, never displayed);
   - `level`: indentation, 0 for top level;
   - `label_en` and `label_<language>`;
   - `note`: the reference to the notes to the statements, optional;
   - `source` (rule 5);
   - the basis columns.
5. A `source` is a list of terms separated by `;` and summed. A term prefixed with `-` is subtracted. The minus sign is the ASCII hyphen-minus `-` everywhere: in terms, in formulas and in data files. ADR-0041 rule 19 wrote `−` (U+2212); a note there aligns it with DS-14 and the shipped `01_gtgt.csv`, which already use `-`. Terms:
   - `account:<selector>:<measure>[:<option>]...` (rules 6, 7);
   - `cash_in:<selector>` and `cash_out:<selector>` (rule 12);
   - `report:<code>:<line>`: a line of another statement, over the same range and options;
   - `carry:<line>`: the line's value over the prior range, which is the comparative range of the header's `comparative` (rule 13). It comes from the latest filing of this report over exactly that range (rule 19), else from the line's `report_comparative_value` for that range (rule 14). With neither, the term is empty with the check result `report_comparative_missing`, and so are its line and every formula that depends on it. A version whose header has `comparative: none` may not use `carry:` (`report_definition_invalid`);
   - `formula:<expression>` (rule 9).

   A `line` row with an empty source has the value zero.
6. Account selectors and measures:
   - **Selector.** An operational account code, or several joined by `|`, each meaning that account and all its descendants in the company's operational tree (`account.parent_id`, ADR-0010 rule 10). `!<code>` removes an account and its descendants: in TT99, `338!33881!33882` is 338 without 33881 and 33882. A company's own detail accounts under a package account are therefore reached without any change to the definition (the DS-26 obligation of ADR-0016 on company-changed charts). A code that the company does not have contributes zero.
   - **Measures**, all in company currency:

     | Measure | Value |
     | --- | --- |
     | `opening` | Balance at the end of the day before `from`, signed debit positive |
     | `opening_debit`, `opening_credit` | The debit and credit parts of that balance, split by rule 7, both zero or positive |
     | `debit_turnover` | Sum of company amounts of lines with `side` debit in the range, storno lines included, so they lower it (ADR-0014 rule 6) |
     | `credit_turnover` | Minus the sum of company amounts of lines with `side` credit in the range, storno included |
     | `change` | `debit_turnover` minus `credit_turnover` |
     | `closing` | Balance at the end of `to`, signed debit positive |
     | `closing_debit`, `closing_credit` | The debit and credit parts of that balance, split by rule 7 |

   - **Signs.** A liability's `closing` is negative. A definition presents it as a positive figure with `closing_credit` or a `-` term.
   - **Migration entries.** Lines of entries in a migration fiscal year (ADR-0044 rule 2) count in balances and never in turnover measures, because they are opening balances, not movements.
7. Options of an `account:` term, each `<key>=<value>`, applied in this order: filter, group, split.
   - **`kind=<kinds joined by |>`.** Only lines whose open item has one of these kinds (ADR-0026 rule 2).
   - **`term=short` or `term=long`, with `undated=short` or `undated=long`.** Only lines whose open item is due on or before the day `term_months` after `to` (short) or later (long); that day is found by rule 13's month-end rule, so from 31 December it is 31 December. `undated` places items without a due date (advances, payments on account). It is required with `term`, and the package sets it, because where such items belong is the regime's choice (`undated=short` in TT99, flagged). This is how a definition splits short-term from long-term receivables, payables and loans.
   - **Where open-item options apply.** `kind`, `term`, `undated` and `by=partner_kind` are valid only on selectors whose accounts have the effective control kind `receivable`, `payable` or `loan` (ADR-0025 rule 4), where every line carries an open item (ADR-0014 rule 10).
   - **`by=account`, `by=partner` or `by=partner_kind`.** How a balance is grouped before it is split into its debit and credit parts: each group's net balance is a debit part when positive and a credit part when negative. `account` groups by postable operational account. `partner` groups by account and `partner_id`. `partner_kind` groups by account, partner and open-item kind. `by` is required on every `opening_debit`, `opening_credit`, `closing_debit` and `closing_credit` term, and there is no core default: whether a regime nets per account, per partner, or per partner and kind is its choice, written in its definitions (flagged for TT99). This serves ADR-0010 rules 6 and 15 and ADR-0026 rule 2: with `by=partner_kind` a bilateral account presents customer or supplier advances apart from receivables or payables.
   - **`closing_entries=exclude`.** Leaves out entries with `is_closing_entry` (ADR-0012 rule 18; ADR-0014 rule 1). Income statement lines use it on turnover measures, so the closing to the income summary does not cancel them.
   - **`counterpart=<selector>`.** Turnover measures only: only the part of each line attributed by rule 8 to lines on the selected accounts, e.g. the credit turnover of cost of goods sold against the income summary (632 against 911 in TT99).
8. Counterpart attribution splits each journal entry into pairs of a positive and a negative line. It is a pure function of the entry, used by `counterpart=`, by the counterpart column of books (rule 10) and by the direct cash flow (rule 12).
   - **The pairs.** Let P be the entry's lines with a positive company amount, N those with a negative one, and S the sum over P. The exact pair amount of positive line i and negative line j is |a_i| × |a_j| ÷ S. Lines with a zero company amount take no part.
   - **Rounding.** Every pair is its exact amount rounded down or up to the currency's minor unit, and every line's pairs sum exactly to its own amount. The computation uses only line numbers and absolute amounts. The side that holds the entry's lowest line number is the first side.
     1. Each pair starts at its exact amount rounded down.
     2. The missing units go one at a time to the pair with the largest remainder whose two lines both still need a unit. Ties go to the lower line number on the first side, then on the other side.
     3. A unit still missing after that is placed along the shortest alternating path, searched breadth-first in line-number order: it rounds up a pair with a remainder that is still rounded down, and rounds down a pair rounded up earlier, until it reaches a line that still needs a unit. Such a path always exists, because the exact amounts are a fractional solution. The lab needed this step for 264 units in 5,000 random entries.
   - **Use.** Line i is attributed +m_ij to line j, and line j is attributed -m_ij to line i. Pairs between two lines of the same report scope (two cash accounts, rule 12) therefore cancel exactly.
   - **Reversals.** A reversal entry has the original's lines with negated amounts and the same line numbers (ADR-0014 rule 8). Because the rounding reads only line numbers and absolute amounts, its pairs are exactly the original's, negated.
   - **When the entry has one line on one side** (the common case: one cash line against several lines), this equals a largest-remainder split of that line in proportion to the others.
9. Formulas, checks and coverage:
   - **Formula grammar.** `[line]` references to lines of the same version, `+`, `-` (binary and unary), parentheses, `pos(x)` = max(x, 0) and `neg(x)` = max(-x, 0). `neg` returns a magnitude, as in box [41] of the Vietnamese VAT return 01/GTGT. Nothing else: no constants, no division, no other functions.
   - **Order.** Lines are evaluated in dependency order. A cycle through formulas or `report:` terms is rejected by package CI and by `CreateReportDefinition` (`report_definition_invalid`).
   - **Exactness.** Values are sums of amounts at the minor unit, so every value and every check is exact. A display unit (e.g. thousands) is a query and render option. It rounds each displayed value on its own, half away from zero unless the header's `display_rounding` names another mode, and never what checks and formulas use. A displayed total is therefore the rounded total, not the sum of the rounded lines.
   - **Checks.** A `check` line that is not zero gives the check result `report_check_failed` naming the line and its value. A balance sheet uses it for total assets against total sources; a cash flow statement for the reconciliation with cash.
   - **Coverage.** When the header lists `coverage`, every postable account of those types (through its system account) with a non-zero `closing`, or a non-zero turnover for income and expense types, must be named by at least one `account:` term of the version. Otherwise the check result `report_account_not_covered` lists the accounts. This catches a company account added outside every package line.

**Books and listings**

10. A book definition lists rows of one row source:
    - **Row sources** (closed list, extended by ADR):
      - `journal_line`: general journal, general ledger, detailed ledgers, cash book and bank book;
      - `material_document_line`: inventory detail with quantities, and values from the linked journal lines;
      - `stock`: per item, warehouse and owner, quantities from material document lines and values from inventory journal lines, as of a date or over a range;
      - `open_item`: open items as of a date with their open amounts, kinds and due dates;
      - `production_order_period_cost`: per order, period and cost component (ADR-0035).
    - **Fields.** A row source's fields are the fields of its query's generated result schema (ADR-0022 rule 17), plus computed fields: `debit`, `credit` (the line's company amount by side), `counterpart_accounts` (codes from rule 8), `running_balance`, `quantity_in`, `quantity_out` and `running_quantity`.
    - **Header.** Beside the statement header's names, dates and basis: `row_source`; `scope` (an account selector, for `journal_line` and `stock`); `filters` (field and value pairs, e.g. `owner: non_owned`); `group_by` (fields); `rows`: `line`, or `counterpart` for one row per counterpart pair as a general ledger shows it; `period`: `range` or `as_of`.
    - **Columns CSV:** `column`, `label_en`, `label_<language>`, `field`, `total` (`sum` or empty), and the basis columns.
    - **Groups.** Each group shows an opening row (for `range` books), its rows, a totals row and a closing row.
    - **Row order.** For `journal_line` and `material_document_line`: posting date, then document number (ADR-0014 rule 4), then document type and `journal_entry.id` (`material_document.id` for rows from material documents), the final tiebreaks between entries, because numbers are unique only per type and entries of different types can share a date and number; then line number within the entry. With `rows: counterpart`, a line's pairs follow in the counterpart line's number. For `open_item`: the group fields, then the open item's ID. `stock` and `production_order_period_cost` rows are aggregates without an ID of their own, so they end on their natural key: for `stock`, the group fields, then `item_id`, `warehouse_id`, `owner_partner_id` (null for own stock, ADR-0030 rule 8) and `lot_id` or `serial_number_id`, whichever the item tracks, where the row source exposes them (ADR-0020 rule 8); for `production_order_period_cost`, the group fields, then `production_order_id`, `posting_period_id` and the cost component (`material`, `labor`, `overhead`, `other`, in that order; ADR-0035). In every key, group fields included, null sorts before any value, and the cursor compares it that way: null equals null, and null is less than any value. The `ListBookRow` cursor carries the same keys, so a page never repeats or skips a row.
    - **The books named so far:** the general journal; the general ledger per account; detailed ledgers per account and partner, or per account and item; the cash book per money account (each money account has its own operational account, ADR-0048 rule 2, so grouping by account suffices); the bank book; inventory detail per item and warehouse; materials held for others (rule 22). Which books a regime requires, and their forms, are package data (flagged).

**Company definitions**

11. A company may add its own statements and books as company data (`report_definition`, `company_id`, code, kind, `effective_from`, header and lines as JSON, basis `company_decision`, change-tracked):
    - **Never a package definition.** A code that a package definition of the company's regime uses is rejected with `report_definition_protected`. A company never changes or hides a package statutory definition.
    - **Why.** A regime may let a company design its own books under its accounting policy; TT99, for example, does (spec 07; ADR-0016 rule 7). Statutory statements stay package rules read live. This settles the template-or-rule question for reports: package definitions are rules, company definitions are company data beside them.
    - **Not fileable.** Company definitions cannot be filed (`report_not_fileable`).
    - **Commands.** `CreateReportDefinition` and `UpdateReportDefinition`, effect class `master_data_change`, so agents reach them only through change proposals (ADR-0029 rules 1, 5). They validate the grammar of rules 4 to 10 (`report_definition_invalid`).

**Cash flow**

12. The package declares the method in the cash flow statement's header. The engine supports both:
    - **Direct.** `cash_in:<selector>` sums, over lines on `cash_accounts` with `side` debit in the range, the parts that rule 8 attributes to lines on the selected counterpart accounts. `cash_out:<selector>` does the same for `side` credit, signed, so outflows are negative. Parts attributed to other cash accounts are internal transfers and are left out; they cancel exactly. So the parts on all non-cash counterparts sum exactly to the change in cash. A package covers every counterpart through its selectors, and a `check` line compares the flows with `account:<cash>:change`.
    - **Several counterparts.** An entry with several counterpart lines (a receipt settling an invoice with a bank charge and a realized exchange difference) is split in proportion by rule 8.
    - **Indirect.** Profit before tax by a `report:` term on the income statement, adjusted by `change` measures of working-capital accounts and turnover measures with `counterpart=`.
    - **TT99 seed** (package choice, flagged, DS-19 data): the direct method, with the indirect method shipped as a second definition a company may choose to render. Whether TT99 requires one method or allows either is the author's to verify.

**Periods and comparatives**

13. Ranges:
    - **By date.** Every report runs over a date range `from`–`to`, never a fiscal year code (ADR-0007 rule 23). Balances read `to` (and `from` minus one day for `opening`); turnover reads the range. `from` after `to` is rejected with `report_range_invalid`.
    - **Special periods.** Their entries carry the fiscal year's last day as posting date (ADR-0012 rule 2), so a range ending on that day includes them. The parameter `special_periods` (`include`, the default, or `exclude`) lets a monthly report of the last month show regular periods only. `exclude` removes only the special-period entries of the fiscal year whose last day is `to`, and removes them from turnover measures, `change` and `closing` alike, so opening plus change still equals closing. `opening` always includes them, and special-period entries of earlier fiscal years stay in every measure. When `to` is not a fiscal year's last day, `exclude` changes nothing.
    - **Closing entries** are in balances, and income lines exclude them with `closing_entries=exclude` (rule 7).
    - **One year earlier.** A date moves one year back to the same day, except a month's last day, which moves to the last day of the same month: 28 February 2025 becomes 29 February 2024, and 29 February 2024 becomes 28 February 2023. Moving a date by months (the `term_months` horizon, rule 7) follows the same rule.
    - **Comparatives** are the same definition version over an earlier range, with `from` and `to` moved one year earlier as above. `day_before_from` uses the range from `from` moved one year earlier to the day before `from`, so its balances are those at the day before `from` (the balance sheet's opening column, also for an interim balance sheet whose `from` is the start of the year). `prior_year_range` moves both dates (the income statement's comparative): February 2025 compares with 1 to 29 February 2024. A caller may pass another comparative range.
14. Before the cut-over (ADR-0044 rules 10, 18):
    - **Balances.** A balance at a date on or after the migration's `opening_date` is computed from the opening documents and later lines. A balance before it cannot be computed.
    - **Turnover.** A range that starts on or before `opening_date` and ends after it adds the `opening_turnover` rows of each account whose `start_date` equals `from` and whose `end_date` is `opening_date`. ADR-0044 loads them for income and expense only, so other accounts' turnover in such a range is incomplete and gives the check result `report_turnover_incomplete`.
    - **Before closing entries.** `opening_turnover` is turnover before closing entries. It is added only to turnover measures with `closing_entries=exclude`; a turnover term without that option on an account with an `opening_turnover` row, over such a range, gives `report_turnover_incomplete`.
    - **No pairs.** `opening_turnover` has no journal entries to pair. `counterpart=`, `cash_in` and `cash_out` terms over a range that straddles `opening_date` give `report_turnover_incomplete`, and their value covers only the lines after the cut-over.
    - **Ranges that cannot be computed** (any other range reaching before `opening_date`) use the `report_comparative_value` rows of exactly that range. Without them, a comparative cell stays empty with the check result `report_comparative_missing`, and a current range fails with `report_range_before_opening`.
    - **`opening_turnover`** is owned by `ledger` (layer 3), because `reporting` may not import `imports` (layer 5). Its rows are written by `CreateOpeningTurnover` in the migration's batches, and never change after `CompleteMigration`. DDL draft in DS-06: `company_id`, `account_id`, `start_date`, `end_date`, `company_debit_turnover`, `company_credit_turnover`, unique on (company, account, start date). Dates instead of a fiscal year, because at a mid-year cut-over the company's first fiscal year in ERPMe is short (ADR-0044 rule 2) while the legal year is not.
    - **`report_comparative_value`.** Comparatives of ranges before the cut-over come from this company table: report code, definition `effective_from`, line, `from`, `to`, amount in company currency, the attachment of the old filed statement, basis `company_decision`, change-tracked. Commands `CreateReportComparativeValue`, `UpdateReportComparativeValue` and `DeleteReportComparativeValue` have effect class `master_data_change`. The migration loads them; a company may add them later.

**Computing and reading**

15. Queries:
    - `GetStatutoryReport` (code, `from`, `to`, comparative range, `special_periods`, `display_unit`): every line with its current and comparative value (exact, and rounded to the display unit when one is given, rule 9), the definition version with its content hash and basis, and the check results.
    - `ListBookRow` (code, `from`, `to`, group filter): a book's rows by cursor, with opening, totals and closing rows per group.
    - `ListReportLineContribution` (rule 16), `ListReportDefinition` and `GetReportDefinition` (package and company definitions in force on a date, with their basis), `ListStatutoryReportFiling` and `GetStatutoryReportFiling` (rule 19), `ListReportComparativeValue`, `GetRenderJob` and `ListRenderJob` (rule 20).
    - **Computing.** Each query reads one snapshot. Balances of locked periods may come from `account_period_balance` (ADR-0014 rule 18), which an invariant ties to the lines (ADR-0014 rule 15); the result is the same either way. Results carry check results in the `checks` format of DS-04.
    - **Time.** Queries keep the 30-second limit (ADR-0022 rule 9), and 10 seconds for agent runs (ADR-0050 rule 43; a note on ADR-0050 rule 52 lists these queries). Large books are read by cursor or rendered as a job (rule 20).
16. Drill-down. `ListReportLineContribution` (code, line, range, column) lists every journal line that contributes to a figure: posting date, document number and type, account, partner, and the line's contribution (its amount, its attributed part under rule 8, or its share of a bilateral group).
    - **Order.** The book row order of rule 10: posting date, document number, document type, `journal_entry.id`, line number.
    - **Formula lines** list the lines they refer to, each drillable in turn.
    - **Values from migration data** (`opening_turnover`, `report_comparative_value`) appear as such, with their source.
    - **The sum** of contributions equals the figure (INV-401).
17. Scope, field classes and permissions:
    - **Full scope.** Statements and books need the whole company. An actor whose record scope (ADR-0017 rule 9) is limited gets `report_scope_incomplete`, never totals with rows left out. Scoped views of the same data are ordinary DS-33 lists with `is_scope_filtered`.
    - **Field classes.** A definition that reads fields with a field class (e.g. unit costs in an inventory book, the product cost sheet) lists them in `field_classes`. An actor without them gets `permission_denied`. Statements built from journal amounts list none.
    - **Permissions.** Each query and command is its own permission (ADR-0017 rule 4). DS-15's role templates give the reporting queries to `owner`, `chief_accountant` and `accountant`; `FileStatutoryReport` to `owner` and `chief_accountant`.
18. Agents may read statements, books and drill-downs through the query layer, to answer questions and explain figures.
    - **The tension with ADR-0010 rule 14.** That rule makes agents reason in system accounts. Statements and books are operational-account views. Reading them is allowed; using an operational code to choose an account, a policy input or a posting is not. A note on ADR-0010 rule 14 says so.
    - **No filing.** Agents never file (rule 19).

**Filing**

19. `FileStatutoryReport` (code, `from`, `to`, render job, submission reference) records that a statement was submitted to an authority.
    - **Who.** It is `human_only`; the verb File is added to the glossary. `FileTaxReturn` (ADR-0041 rule 18) already used this verb without a row in the verb table.
    - **From a render job, never recomputed.** The render job must be a `done` job of kind `report` for the same code and range, whose definition content hash equals that of the version in force for the range now. Any other job is refused with `report_render_job_mismatch`, whose `details` give the reason. The command takes the snapshot from the job's stored lines (rule 20) and recomputes nothing, so the filing records exactly the file the person submitted.
    - **Stale data is a check result.** When the inputs seem to have changed since the render, filing still succeeds and stores the check result `report_snapshot_stale`, as it stores `report_periods_open`. The difference view (below) and a supplement handle the drift. The signal is best effort, stored and never enforced: the journal-entry count up to `to` differs from the count the job stored (journal entries are append-only, the test of ADR-0012 rule 12), or the `report_comparative_value` rows of its ranges differ from the hash it stored. It misses inputs that change figures without a journal entry, such as an account moved to another parent, an open item's due date read by `term=`, or `opening_turnover` rows changed before `CompleteMigration`; the difference view shows those.
    - **Snapshot.** It stores an immutable `statutory_report_filing`: company, code, the definition version (package version, `effective_from`, content hash), range, comparative range, options, the render job, every line's current and comparative value and the lines' hash from that job, check results, `supplement_number` (0 for the first filing of that report and range), `filed_at`, `filed_by`, the submission reference, and the job's file as the submitted file. Triggers reject changes.
    - **Allowed only** for package definitions with `is_fileable` (`report_not_fileable`).
    - **Open periods.** A range with a regular period not locked in `general` gives the check result `report_periods_open`; filing still succeeds (flagged).
    - **After filing.** `GetStatutoryReportFiling` returns the snapshot and the difference per line from a fresh computation. A later adjustment, for example in a special period, shows there and is filed as a supplement.
    - **Evidence.** The submitted file's attachment is accounting evidence (ADR-0038 rule 15 gets a note).

**Rendering and exports**

20. Rendering a file is a job:
    - **The verb.** Render: produce a file from a print template or a report definition, as a job. Its event form is `RenderRequested`, because the file does not exist yet when the command commits; Issue and `IssueRequested` are the precedent (ADR-0004 rule 22). Export stays the verb for a company's full data (ADR-0044 rule 17).
    - **Commands:** `RenderPrint` (rule 25's subjects), `RenderReport` (a statement or book: code, range, options, format) and `RenderTaxReturn` (rule 21). Each checks permissions, scope and the template or definition, writes a `render_job`, and emits `PrintRenderRequested`, `ReportRenderRequested` or `TaxReturnRenderRequested`. Effect class `other`; none is `human_only`.
    - **`render_job`:** kind (`print`, `report`, `tax_return`), subject and parameters, template version, contract version, language, the subject's lifecycle and e-invoice state, marker, format, `render_key` (rule 28), `is_subject_final` (the subject is a document in a final state at request, rule 28), `state` (`pending`, `done`, `failed`), the attachment, `contains_untrusted` (rule 28), the error code, and the actor context of the request (ADR-0017 rule 16).
    - **Report jobs** also store, from the worker's snapshot: the definition content hash, every computed line with its current and comparative value and check results, the SHA-256 of those lines in canonical JSON (ADR-0008 rule 12), the count of the company's journal entries with a posting date on or before `to`, and the hash of the `report_comparative_value` rows of its ranges. Filing reads these (rule 19).
    - **The worker.** The consumer `render_worker` runs on queue `pdf` (ADR-0013 rule 6 gets a note) in the shape of ADR-0013 rule 10. It reads the data in one read-only snapshot transaction under the long-job timeout (ADR-0022 rule 9), renders with no transaction open, and records the outcome with the internal command `RecordRenderOutcome` (verb Record, which always succeeds, like `RecordEInvoiceOutcome`). It emits `RenderOutcomeRecorded`. Lease 30 minutes and 3 attempts, instead of ADR-0013's defaults of 5 minutes and 10, because the read alone may take the 15-minute long-job timeout and a render that failed twice rarely succeeds; a held delivery follows ADR-0013 rule 8.
    - **Failures** recorded on the job: `render_failed` (a template or definition error at run time), `render_too_large` (above the installation setting `render_max_bytes`, default 100 MiB; the caller narrows the range) and `render_output_invalid` (XML that fails the package's schema).
    - **Formats.** PDF through a print template: the package's template for that report, or the core's neutral report layout. XLSX, written with XlsxWriter (ADR-0002): one generic layout per kind (statement lines with labels, notes and values; book columns). XML only where the definition declares an export (rule 21).
    - **Books leave only through `RenderReport`.** `CreateListExport` (ADR-0050 rule 54) refuses every query of module `reporting` with `list_export_query_not_allowed`, because a list export has no opening, totals or closing rows, no full-scope check and no file a filing can name (a note on ADR-0050 rule 54).
21. Exports with an XML schema, and tax return files:
    - **XML.** A definition's `exports.xml` names a Jinja2 XML template (autoescaped for XML) and an XML schema file in the package. The output is validated against the schema with xmlschema (ADR-0002) before it is stored.
    - **Tax returns.** ADR-0041 rule 18's return export is `RenderTaxReturn` (form, period, declaring unit, supplement number, format). It renders the filed `tax_return` snapshot when one exists, otherwise a fresh `GetTaxReturn`, through the return form's export. A return form file gains the same optional header (`effective_from`, `exports`) at its next version; until then the undated `01_gtgt.csv` counts as effective from the package's first date (a note on ADR-0041 rule 19). The 01/GTGT XML layout for the tax authority's software is package data (flagged).

**Presentation items handed to DS-26**

22. Mechanisms for items that other ADRs handed over:
    - **33881 and 33882** (GR/IR clearing and purchase cost clearing, as TT99 maps them). ADR-0021 rule 14 said their presentation is DS-19's; ADR-0039 rules 8 and 10 said DS-26's. Both hold: DS-26 defines the format (rules 6, 7), and DS-19's definitions place the lines, e.g. `account:33882:closing_debit:by=account` under other receivables and `closing_credit` under other payables. Notes on both rules.
    - **4212 into 4211 at the new year (in TT99)** is a close task (rule 23) running the generic job `RunBalanceCarryForward` of module `ledger`, which owns account balances and posting (ADR-0022 rule 2). The job moves an account's balance at the previous fiscal year's last day to another account by a `balance_transfer` dated the first day of the new year, with the task's `close_task_id` on the journal entry (DS-06). The accounts are task parameters in the regime's checklist.
      - **Idempotent.** Each run transfers that year-end balance minus what earlier runs for the same fiscal year already moved, found by the `close_task_id` of their entries. A reversal of such an entry carries negated amounts (ADR-0014 rule 8) and is netted out of that sum, so a reversed transfer counts as not moved. A second run with nothing new posts nothing; after a special-period adjustment it moves only the difference.
      - **Flagged:** its timing, and whether a regime wants a special-period adjustment carried this way.
    - **Advances by open-item kind:** `kind=` and `by=partner_kind` (rule 7).
    - **Short-term and long-term:** `term=` (rule 7).
    - **Materials held for others** (ADR-0037 rule 8): a book over `stock` with `filters: {owner: non_owned}`, showing quantities and no values (ADR-0030 rule 8).
    - **The product cost sheet** (ADR-0035 rule 16): `l10n_vn`'s book definition over `production_order_period_cost`, with `field_classes: [cost]`; the core provides the row source (ADR-0053 rule 13).
    - **The stock valuation report:** a book over `stock` as of a date, by item and warehouse. Its total ties to the inventory accounts (INV-402; spec 12).

**Close checklist template**

23. Format of tasks in a regime's `close_checklist.yaml` (ADR-0012 rule 17):
    - **Fields per task:** `code`; `area`; `kind` (`job`, `check`, `manual`); `runs` (the registered job or check, empty for manual tasks); `is_required`; `is_sequential`; `depends_on`; `applies_to` (`every_period`, `fiscal_year_end` for the last regular period and the special periods, `special_period`, or `fiscal_year_first_period`); `parameters` (JSON validated by the job's schema, e.g. accounts); labels; and the basis.
    - **Copying.** Tasks are copied into the company's checklist template at setup (ADR-0016 rule 7). `applies_to` decides which periods get each task when ADR-0012 rule 11 copies them; `close_task` gains `parameters` (a note on ADR-0012 rule 11).
    - **Core tasks** that no template lists and no company removes: agent auto-posts confirmed (ADR-0012 rule 13; ADR-0029 rule 13); no document in `issuing` or accepted and unposted (ADR-0028 rule 11); no import batch posting into the period (ADR-0030 rule 9); the migration completed (ADR-0044 rule 3).
    - **Tasks other ADRs name,** whose area and order the regime sets:

      | Task | Kind | Owner |
      | --- | --- | --- |
      | `period_end_costing` (sequential; also settles production) | job | DS-09 (ADR-0020 rule 12; ADR-0035 rule 5) |
      | `inventory_write_down` | job | DS-09 (ADR-0027 rule 8) |
      | `landed_cost_unallocated` (lists open cost sources) | check | DS-11 (ADR-0021 rule 14) |
      | `gr_ir_closed_lines` (balances on closed order lines) | check | DS-22 (ADR-0047 rule 13) |
      | `bad_debt_provision`, `prepaid_amortization` | job | DS-25 (ADR-0048 rule 14) |
      | `bank_reconciliation` (reads `GetBankReconciliation`) | manual | DS-25 (ADR-0048 rule 8) |
      | `fx_revaluation` | job | DS-10 (ADR-0011 rule 17) |
      | `vat_apportionment` (yearly true-up at fiscal year end) | job | DS-23 (ADR-0041 rule 16) |
      | `closing_entries` (after costing) | job | DS-12 (ADR-0012 rule 18) |
      | `balance_carry_forward` (4212 into 4211 in TT99) | job | `ledger`'s `RunBalanceCarryForward`, specified in this ADR (rule 22) |
      | `statutory_report_checks` (check lines and coverage of the regime's statements) | check | this ADR (rule 9) |

    - **TT99 content** (which tasks, their areas, order and whether required) stays package data for step 8, `unverified` (DS-19).

**Print templates (DS-27)**

24. Print templates:
    - **Kind.** Package templates (ADR-0016 rules 5, 7) under `print_templates/<code>/` (package level) or `regimes/<regime>/print_templates/<code>/` (a regime's form, which wins over a package-level template of the same code). Each has `template.yaml` (subject, audience, contract version, languages, field classes, basis), `template.html` and optionally `style.css`. The core ships neutral English templates for subjects that no package covers (quotations, orders, labels, lists), so the basic US package needs none.
    - **Company copies.** Setup copies them into `print_template` (company, code, subject, `audience`, languages, `is_default` per subject and language) with immutable `print_template_version` rows (version, HTML, CSS, contract version, field classes, content hash, basis). `UpdatePrintTemplate` writes a new version with basis `company_decision`; `CreatePrintTemplate` adds one. Effect class `master_data_change`, so an agent that builds a template from a customer's old form (spec 16) drafts a change proposal (ADR-0029 rules 1, 5).
    - **Audience.** `external` (sent to partners) or `internal`. An external template may declare no field class (`print_template_audience_invalid`).
    - **Sandbox.** Templates run in Jinja2's sandboxed environment with autoescaping always on. `safe`, `Markup` and raw HTML output are unavailable, so data is always escaped. The core provides formatting filters (amounts, quantities and dates in the print language and the company's time zone) and `t()` for catalog strings. `{% include %}` reaches only the company's own templates of subject `partial`.
    - **No network.** WeasyPrint's URL fetcher serves only `asset:` references to the company's print assets (print profile images, rule 26) whose attachment is in scan state `clean` (ADR-0038 rule 14), and package static files. Everything else is refused. The worker image ships fonts for every package language (DS-37).
    - **Validation.** `CreatePrintTemplate` and `UpdatePrintTemplate` compile the template and render its HTML (not the PDF) against the contract's example instance with strict undefined values. An unknown field, filter or tag is rejected with `print_template_invalid`. A contract version the core does not serve is rejected with `print_contract_version_unsupported`.
25. Print subjects and data contracts:
    - **Subjects.** A document type registered `is_printable` (a registry flag; a note on ADR-0009 rule 2), or a registered query (warehouse labels and lists, ADR-0023 rule 22: `ListBin`, handling units, the pick and putaway task lists).
    - **The contract** of a subject is a JSON Schema generated by `erpme-dev generate` into `backend/generated/print_contracts/<subject>.<major>.json` (ADR-0022 rule 17), with each field's field class, data label and `is_untrusted` annotation.
    - **For a document**, the contract is its version content (ADR-0009 rule 9) plus derived print fields:
      - `company`: legal name and tax ID, with the print profile of the company and of the document's branch (rule 26);
      - `branch`: code, name, tax ID and address;
      - `document`: type, `number`, state, the `marker` (rule 28), dates, currency and references;
      - `e_invoice`, for e-invoice-capable types: what `RecordEInvoiceOutcome` stores on the e-invoice record (ADR-0028 rule 7): state, number and issue date, or the rejection reason; and `extension`, an object whose schema the installed e-invoice add-on defines and generates into the contract (DS-24). The core contract names no country's e-invoice fields;
      - `partner`: the snapshot in the content (ADR-0028 rule 16) and the partner's code;
      - `lines`: content lines with their taxes and, optionally used, price steps (ADR-0047 rule 16);
      - every `<relation>_id` in the content gains a sibling `<relation>` object with the referenced record's code and name, the name in the print language where a data translation exists (ADR-0018 rule 17). Documents resolve through `documents.contract` (type and number) and master data through `master_data.contract`. A record owned by another layer-4 module (e.g. a money account of `cash`) resolves through the hook `print_relation_resolver`, which `reporting` declares and the owning module registers, wired by `app` (ADR-0022 rule 2's hooks), so `reporting` imports no layer-4 module. `erpme-dev generate` fails when a printable type's content has a relation that nothing resolves;
      - `taxes`: totals per tax code (base, rate or label, tax) from `GetDocumentTaxes` (ADR-0041 rule 6);
      - `installments`: the schedule in the content (ADR-0047 rule 6);
      - `totals`: net, discount, tax and gross in document currency, and in company currency with the rate when they differ;
      - `amount_in_words`: the gross amount in the print language, from the package interface `AmountInWords` (package code, ADR-0016 rules 5 and 17 get a note; the core ships English). When no installed implementation covers the print language, it holds the amount in numerals only, formatted for that language, so a print never fails or shows words in another language;
      - `people`: the preparer (the actor of the version, ADR-0017 rule 16: a person's name, or the agent type and the person it acted for), the approver (from the `approval` row bound to the version, ADR-0009 rule 11), and the chief accountant and legal representative from the print profile. These come from document records, not from audit queries, which agents may not read (ADR-0038 rule 7);
      - `printed`: the instant of rendering in the company's time zone, and the language.
    - **For a query subject**, the contract is the query's result schema plus `company`, `branch` and `printed`.
    - **Versions.** Contract versions are semver per subject. A new optional field is a minor version. Removing, renaming or retyping a field is a major version. A CI check compares the generated schemas with the last release and fails on a breaking change without a new major. The core serves the current major and the previous one until the next LTS release (DS-37). A template declares `contract_version` (`major.minor`); the core accepts it when it serves that major with at least that minor. So a core change does not break a company's template (spec 16).
    - **Reading.** `GetPrintDataContract` (subject, version) returns the schema; `GetPrintData` (subject, template) returns the instance a template would receive, filtered as rule 29 says.
26. Print profile and signatures:
    - **`print_profile`** (module `master_data`, DS-20; change-tracked; `CreatePrintProfile` and `UpdatePrintProfile`, effect class `master_data_change`): one row for the company and optionally one per branch, a branch row's non-empty fields winning over the company's. Columns: address (the keys of `partner_address`, ADR-0045 rule 8), phone, email, website, legal representative's name and title, chief accountant's name (both labeled `personal`, spec 17), bank details printed as text, and the attachment IDs of a logo, a seal image and a signature image. `company` already holds legal name, tax ID and language; `branch` holds name, tax ID and address.
    - **Images** are PNG or JPEG attachments labeled `internal`. Only the `owner` role template holds `UpdatePrintProfile` (DS-15). The contract leaves the seal and signature images empty when the subject has a marker (rule 28), so a draft never carries them.
    - **Names.** Prints show the printed names of the preparer and approver (rule 25), as accounting law asks for a preparer and an approver (spec 03 rule 6).
    - **Digital signatures** on PDFs come later (open question).
    - **E-invoices.** The print of an e-invoiced document is not the legal e-invoice, which the provider issues (DS-24). The print shows the e-invoice data from rule 25 once accepted.
27. Print language: the render request's `language`, then the document's `print_language`, then the partner's `preferred_language`, then the company's `default_language` (ADR-0016 rule 19; ADR-0018 rule 17).
    - **The new field.** `print_language` (BCP 47, optional) is a header field of every printable document type and part of its content (notes on ADR-0047 rule 1 and ADR-0048 rule 1).
    - **The template** for a subject is the one the request names, else the default template of that language, else the subject's default template; with none, `print_template_missing`.
    - **Strings** come from the catalogs and the package terminology in that language. Entered data is never translated (ADR-0016 rule 19).
28. PDF worker and stored files:
    - **The render key** is the SHA-256 of the canonical JSON (ADR-0008 rule 12) of: the subject (document version ID, or query and parameters, or report parameters), the subject's `state`, the template version, the contract version, the language, the marker and the format. The element `state` tracks the lifecycle: for a document it holds `document.state` and, when the document has an e-invoice record, that record's state; for other subjects it is empty. A reversal changes `document.state` without a new version (ADR-0009 rule 14), and an e-invoice outcome changes no version either, so without `state` a reversed or newly accepted document would reuse its old file. ADR-0002 named document version and template version; state, contract version, language and marker are added because each changes the bytes (a note on ADR-0002 performance rule 1).
    - **Reuse.** For a document in a final state (`posted`, `reversed`, `canceled`, `closed`, ADR-0009 rule 14), `RenderPrint` returns the existing `pending` or `done` job with the same key and renders nothing. A partial unique key on `render_job` (`company_id`, `render_key`) over rows with `is_subject_final` and state `pending` or `done` enforces this: of two concurrent requests, the second's insert conflicts and it returns the first's pending job. A `failed` job leaves the key free. So a final document is rendered once per state, template version, contract version, language and format, and the first file stays even when master data used by derived fields changes later.
    - **The version printed** is the document's current version (ADR-0009 rule 9). While a change order is pending (ADR-0028 rule 4), prints use the current approved version, never the pending change.
    - **The marker.** The renderer stamps every page, in the print language, with `REVERSED` when the document is reversed, `CANCELED` when it is canceled, and otherwise `DRAFT` when it has no number. Templates cannot remove it.
    - **No copy marker or print counter.** Printing the same key again returns the same file. A form printed in several labelled copies is a template concern: the template renders the copies in one file.
    - **Attachments.** The file is stored through `attachments.contract` with source kind `generated` and scan state `clean`. "Clean" is a statement about the malware scan only: the file is not scanned, because our own worker produces the bytes from company templates in a sandbox without network access. It says nothing about the content.
    - **Generated-file columns.** The attachment row (layer 2) records, at creation and never changed: `generated_kind` (the job's kind), `generated_audience` (the template's audience; `internal` for report and tax return files), `generated_subject_document_id` (the printed document; empty for query and report subjects) and `contains_untrusted`. Notes on ADR-0027 rule 2 and ADR-0038 rule 14.
    - **Untrusted content.** The render job records whether the rendered instance held any non-null field annotated `is_untrusted`: a print contract field (rule 25), or a field of a report or book row, whose row source's result schema carries the same annotation (rule 10). The attachment takes it as `contains_untrusted`, the same way it takes the strictest data label of the fields the instance contains (a partner snapshot of an individual is `personal`). As with the label, a second creation of the same bytes keeps the stricter value. A run that reads a file with `contains_untrusted` is tainted (a note on ADR-0050 rule 25).
    - **Accounting evidence.** A file of a posted document (state `posted`, or `reversed` after it was posted) is linked to the document and is accounting evidence (ADR-0038 rule 15 gets a note: linking a generated file to a posted document sets `is_accounting_evidence`). A file of an approved or closed non-posting document is linked to it and is not evidence. A file of a document that is neither posted nor in a final state is linked only to its render job; a daily job removes that link after 30 days, so the bytes go unless another record (such as an outbound message draft) links them (ADR-0027 rule 2).
29. Escaping, audiences and sending:
    - **Untrusted fields** (ADR-0029 rule 10) are escaped like every field and never rendered as HTML, as ADR-0040 rule 17 asks of screens (a note there).
    - **Field classes.** An external template's contract omits every field with a field class, so `cost` and `margin` cannot reach a customer-facing print (ADR-0029 rule 14). An internal template's contract keeps only the field classes it declares; the requester must hold them (`permission_denied`). Record scope applies at request (`record_not_found`). So a stored file never depends on who asked for it.
    - **Printing is not sending.** Emailing a PDF is an outbound message draft with the file attached, which a person sends after the consent check (ADR-0019 rules 9, 17).
    - **The outbound gate** (module `crm`) accepts a generated file in a partner draft only when the attachment's `generated_kind` is `print`, its `generated_audience` is `external`, and the partner of its `generated_subject_document_id` (`document.partner_id`) is the message's partner; otherwise `outbound_content_out_of_scope`. `crm` reads these columns through `attachments.contract` and the partner through `documents.contract`, never from `reporting`, which is a layer-4 module like `crm` (notes on ADR-0019 rule 17, ADR-0029 rule 14 and ADR-0052 rule 28, check 3).

**Timing, catalogs and checks**

30. Timing, interim until the author answers open question (DS-26, DS-27) item 15, because build order is his (ADR-0005 item 2). The engine is needed before step 8:
    - **Step 5:** the print contract, the worker and the templates for warehouse labels and lists (ADR-0023 rule 22), quotations, orders and delivery notes.
    - **Step 6:** the statement and book engine, drill-down and listings, with the cash book and bank book definitions the step 6 gate reads; voucher prints of cash and bank documents (ADR-0048).
    - **Step 7:** the return export (ADR-0041 rule 18).
    - **Step 8:** the regime's statements (B01, B02 and B03 in TT99), comparatives, filing and the close checklist content.
    - **Flag.** Spec 11 and the runbook (steps-5-9, step 8 design items) place DS-26 and DS-27 at step 8. Both are the author's documents; this ADR asks him to move them (open question). Every place that applies the move is marked interim: the backlog's "Needed by" column, the ADR-0022 rule 2 text, and the notes on ADR-0023 rule 22 and ADR-0039 rule 10.
31. Catalog rows:
    - **Errors:** `report_definition_missing`, `report_definition_protected`, `report_definition_invalid`, `report_scope_incomplete`, `report_range_invalid`, `report_range_before_opening`, `report_not_fileable`, `print_template_missing`, `print_template_invalid`, `print_template_audience_invalid`, `print_contract_version_unsupported`, `report_render_job_mismatch`, `list_export_query_not_allowed`; job outcome codes `render_failed`, `render_too_large`, `render_output_invalid`; loader error `report_definition_in_use`.
    - **Check results:** `report_check_failed`, `report_account_not_covered`, `report_comparative_missing`, `report_turnover_incomplete`, `report_periods_open`, `report_snapshot_stale`.
    - **Work item kinds:** none. A held render delivery shows on the operations dashboard (ADR-0013 rule 8).
    - **Invariants**, a new group INV-400 to INV-499, area `reporting` (DS-16 gets a note):
      - **INV-400:** for every journal entry, the counterpart pairs of rule 8 sum exactly to each line's company amount, and each pair is its exact share rounded down or up;
      - **INV-401:** every statement figure computed from account terms equals the sum of the contributions its drill-down lists;
      - **INV-402:** each book group's opening and closing balance equals its accounts' balance (by partner or item where grouped) on those dates, and opening plus rows equals closing; the stock valuation book's total equals the inventory accounts;
      - **INV-403:** for each regular period of the run locked in `general`, the range from its first to its last day, and for each fiscal year of the run whose regular periods are all locked in `general`, the range from its first to its last day: every `check` line of every package statement in force on the range's last day is zero, and no account is reported as not covered (flagged: it tests package data);
      - **INV-404:** for subjects in a final state, no two render jobs in state `pending` or `done` share a render key, and every generated file linked to a posted document was rendered from its posted version.
    - **Edge cases:**
      - EC-92: an adjustment in the special period after the last regular period is locked;
      - EC-93: a customer with an open invoice and an unapplied advance at year end;
      - EC-94: an adjustment after a statement was filed, then a supplement;
      - EC-95: a mid-year cut-over, with year-to-date turnover and prior-year comparatives from migration data;
      - EC-96: a payment with several counterparts in the direct cash flow;
      - EC-97: a posting into the range after the statement was rendered; filing that render succeeds with the check result `report_snapshot_stale`, and the difference view shows the posting;
      - EC-98: a printed goods receipt is reversed, so a new print carries `REVERSED` and the first file stays.
    - **Glossary:** report definition, report line, measure, counterpart attribution, statutory report filing, report comparative value, print template, print data contract, print profile, render job, generated file (with `contains_untrusted`); the verbs Render and File; Record's intent covers the render worker's outcome.
32. CI and golden figures:
    - **Golden kind.** DS-16 gains the kind `report_line` (keys `report`, `line`, `from`, `to`; company amounts), compared through `GetStatutoryReport`. The naive recomputation of step 8 adds report lines from the definitions in the regime snapshot.
    - **Package CI** (ADR-0016 rule 15). Every definition parses; its selectors name accounts of the regime's chart template; formulas and `report:` terms refer to existing lines and have no cycle; book fields exist in the row source. Every statement with `is_fileable` has at least one golden scenario with `report_line` rows for it, as "statutory reports matching their sample figures".
    - **Packages without statements.** The basic US package ships none (spec 06), so the per-statement requirement is empty for it. CI still requires its core invariants and golden scenarios, and requires every book it ships to pass the definition checks.
    - **The test package.** `l10n_xx` (ADR-0053 rule 9) ships one fictional statement with a check line and coverage, one book per row source in use at the current step, and one print template, so the core's property tests and INV-400 to INV-404 exercise the engine without the overlay.
33. Lab check `t09_reporting.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)), pure functions:
    - formula grammar: `pos`, `neg`, unary minus, cycles, the ASCII minus, `carry` over the header's comparative range and an empty `carry` without filing or stored value;
    - definition checks: `by` required on the split measures, `undated` with `term`, `term_months` when `term` is used, no `carry` with `comparative: none`;
    - measures: turnover by side with storno, migration entries out of turnover, closing entries excluded, special periods of the year ending on `to` excluded from turnover, change and closing but not from opening or earlier years;
    - the bilateral split by account, partner, and partner and kind, with kind and term filters and `undated`;
    - counterpart attribution on random entries: exact sums, every pair rounded down or up, mirrored reversals, cancellation between cash accounts, equality with a largest-remainder split when one side has one line;
    - the direct cash flow summing exactly to the change in cash;
    - comparatives from `opening_turnover` and `report_comparative_value`; `opening_turnover` only with `closing_entries=exclude`; counterpart terms incomplete across the cut-over;
    - one year earlier with month ends, across leap years, for both comparative kinds;
    - book row order with the document type and entry tiebreaks, and a cursor that neither repeats nor skips, also over `stock` rows ending on their natural key with null owner and lot sorting first;
    - idempotent balance carry-forward after a special-period adjustment and after a reversed transfer;
    - filing from a render job: a mismatched or unfinished job refused, a stale one filed with `report_snapshot_stale`;
    - render keys, which change with the document's state and e-invoice state, and the `REVERSED` marker.

    Not covered: tables, templates, WeasyPrint, XML schemas.

## Context

DS-26 and DS-27 were planned for step 8. Earlier ADRs handed them work:
- ADR-0010 rules 8, 14, 15 and ADR-0026 rule 2: presentation on operational accounts and the bilateral split.
- ADR-0012 rule 17: close task content.
- ADR-0014: turnover by side and closing entries.
- ADR-0016: report and print formats, reports on company-changed charts, and CI on sample figures.
- ADR-0021 and ADR-0039: 33881, 33882 and the 4212 carry.
- ADR-0035 and ADR-0037: the cost sheet and materials held for others.
- ADR-0041 rule 18: the return export.
- ADR-0044: `opening_turnover`.
- ADR-0048: the cash book and advances.
- ADR-0023 and ADR-0047: labels, lists and document prints.

Steps 5 to 7 need parts of this work earlier.

Spec 06 rule 6 puts statutory reports on operational accounts, because some lines need more detail than a system account. Spec 07 lets a TT99 company design its own books. Spec 16 says companies customize print templates most and that the data contract must stay stable.

The reference systems:
- **SAP:** financial statement versions map G/L accounts to report items, with debit and credit balance assignment; Adobe Forms print over a data interface.
- **Odoo:** account reports with expression engines and tax grids; QWeb templates.
- **Vietnamese software (MISA):** books from journal pairs with a counterpart account per line.

ERPMe keeps definitions as package data in the tax-return grammar agents already know. It derives counterpart pairs deterministically instead of storing them. It versions the print data contract.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Definitions as dated package rules in the tax-return grammar (chosen) | One grammar for returns and statements; diffable data; no country logic in the core | Not every layout fits; notes to the statements stay text |
| Statements in package code | Any logic | Logic per country in code; harder to verify and review |
| Statements as company templates | Companies change everything | A company could change a statutory form; law changes would need a command per company |
| Account selectors on the operational tree (chosen) | Company detail accounts reached without changes | A tree change moves history in recomputation (filed snapshots keep what was filed) |
| Proportional counterpart pairs with exact rounding (chosen) | Deterministic; mirrored reversals; cash transfers cancel exactly | Not the pairs a person would choose in a multi-line entry |
| Stored counterpart pairs on journal lines | What the user entered | A new journal column and entry burden on every posting path |
| Render as a job on queue `pdf` with an outcome command (chosen) | Heavy work outside transactions; one path for PDF, XLSX and XML | Callers wait for the job |
| Rendering inside the query | Immediate | WeasyPrint in the web process, which ADR-0002 forbids |
| Generated files not scanned for malware (chosen) | No scanner delay for our own output | Trusts the sandbox; content from outside is still tracked by `contains_untrusted` |
| Versioned print data contract (chosen) | Templates survive core changes | A schema and a compatibility check to maintain |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0002 performance rule 1: the render key;
  - ADR-0004 rule 5: report codes;
  - ADR-0009 rule 2: `is_printable` and `print_language`;
  - ADR-0010 rules 14, 15: agents reading statements; the split options;
  - ADR-0012 rules 11, 17: task `parameters` and `applies_to`; the template format;
  - ADR-0013 rule 6: consumer queue `pdf`, with its lease and attempts;
  - ADR-0016 rules 5, 7, 15, 17, 19: format owners and `AmountInWords`; company definitions; CI; `AmountInWords` and its fallback; the document's print language;
  - ADR-0017 rule 9: `report_scope_incomplete`;
  - ADR-0018 rule 17: the print language order;
  - ADR-0019 rule 17, ADR-0029 rule 14 and ADR-0052 rule 28: generated files in outbound drafts, decided from the attachment's columns;
  - ADR-0021 rule 14 and ADR-0039 rules 4, 8, 10: presentation owners and the carry task;
  - ADR-0022 rule 2: module `reporting` (its step interim);
  - ADR-0023 rule 22: print subjects for labels and lists (their step interim);
  - ADR-0026 rule 2: the split per kind;
  - ADR-0027 rule 2 and ADR-0038 rules 14, 15: generated attachments and evidence;
  - ADR-0035 rule 16 and ADR-0037 rule 8: the cost sheet and the disclosure;
  - ADR-0040 rule 17: untrusted fields in prints;
  - ADR-0041 rules 18, 19: `RenderTaxReturn`; the minus sign and the form header;
  - ADR-0044 rules 10, 18: `opening_turnover` and comparatives;
  - ADR-0047 rule 1 and ADR-0048 rule 1: `print_language`; the cash book;
  - ADR-0050 rules 25, 52, 54: taint from generated files with `contains_untrusted`; the reporting queries among computed queries; list exports refusing reporting queries.
- **DDL:** [DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql): `opening_turnover`. [DS-20-master-data.sql](../design/DS-20-master-data.sql): `print_profile`.
- **DS-04:** the errors and check results of rule 31.
- **DS-14:** report, print template and close task formats.
- **DS-16:** the INV-400 group, the `report_line` kind and the step 8 recomputation.
- **Catalogs:** INV-400 to INV-404; EC-92 to EC-98.
- **Other design items:**
  - DS-15: permissions of rule 17 and `UpdatePrintProfile`;
  - DS-19: TT99 definitions, voucher templates, amount in words and the checklist content, all `unverified`;
  - DS-22, DS-25: `print_language` on printable types;
  - DS-24: the schema of `e_invoice.extension` in prints;
  - DS-33: exposing the reporting queries;
  - DS-36: the generated-file columns of `attachment`;
  - DS-37: fonts in the worker image, the LTS that ends a contract major.
- **Open questions:** listed in [open-questions.md](../open-questions.md) under DS-26 and DS-27.

## Revisit when

- A regime needs a statement layout the grammar cannot express (e.g. a matrix of equity changes), or notes to the statements as data.
- WeasyPrint cannot render a required form (ADR-0002's revisit condition).
- Digital signatures on PDFs, or filing directly to an authority, enter scope.
- Counterpart pairs chosen by users become a legal requirement.

## Documents updated

- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t09_reporting.py`, finding L-17.
- **ADRs:** notes in ADR-0002, ADR-0004, ADR-0009, ADR-0010, ADR-0012, ADR-0013, ADR-0016, ADR-0017, ADR-0018, ADR-0019, ADR-0021, ADR-0023, ADR-0026, ADR-0027, ADR-0029, ADR-0035, ADR-0037, ADR-0038, ADR-0039, ADR-0040, ADR-0041, ADR-0044, ADR-0047, ADR-0048, ADR-0050 and ADR-0052; module `reporting` in ADR-0022 rule 2's layer table, with a note.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql), [docs/design/DS-14-localization-package.md](../design/DS-14-localization-package.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/DS-20-master-data.sql](../design/DS-20-master-data.sql), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
