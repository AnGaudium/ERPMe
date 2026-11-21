Module: ledger    Chunk: 2 of 3    Source ADRs: ADR-0015, ADR-0025, ADR-0026, ADR-0027, ADR-0035, ADR-0037, ADR-0041, ADR-0044, ADR-0048
Build step(s): 0, 1, 2, 4, 4b, 5, 7    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `ledger` compiled spec, chunk 2: determination queries, later-phase seams, open items, payment evidence

## Purpose

This chunk states the part of `ledger` law on: the account determination template and queries, the catalog rows added for production, the later-phase seams with subledger activation, the open-item core, payment evidence, general journal entries, the derivation trace and opening turnover. `ledger` owns open items and is the only writer of `open_item`; the DS-25 processes of `cash` use these interfaces. `ledger` never imports `tax` and never reads a higher layer (ADR-0041.R15, ADR-0026.R15). The journal, the chart, currency and the other determination rules are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-06-universal-journal.sql`. Every company table of that file carries the `rls_v1` policies (ADR-0017.R19.N2).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `open_item` | One obligation with a partner on one operational account, with its cached open amounts (R221-R224) | `id`; `origin_journal_line_id` unique; (`company_id`, `id`) | `company` | `ledger` |
| `payment_term` | Payment term header (R231) | `id`; (`company_id`, `code`) unique | `company` | `ledger` |
| `payment_term_line` | Installment line of a term (R231) | `id`; (`payment_term_id`, `line_number`) unique | `payment_term` | `ledger` |
| `subledger_activation` | Activation of a gated control kind for a company (R211) | `id`; (`company_id`, `control_kind`) unique | `company` | `ledger` |
| `fixed_asset` | Stub for the fixed-asset dimension (R209) | `id`; (`company_id`, `code`) unique | `company` | `ledger`, until the `assets` module exists |
| `derivation_trace` | Generic record of how a value was derived (R262) | `id`; (`company_id`, `id`) | `company` | `ledger` |
| `opening_turnover` | Non-posting income and expense turnover before a mid-year cut-over (R266) | `id`; (`company_id`, `account_id`, `start_date`) unique | `company`, `account` | `ledger` |

Reads: `journal_line`, `journal_entry`, `account`, `system_account`, `transaction_key` (`ledger`, other chunks); `cost_object`, `production_structure` (`production`); `open_item_collection`, `money_account_balance` (`cash`); `material_document_line`, `stock_value`, `stock_quantity` (`inventory`); `partner`, `company` (`master_data`); `document`, `document_line_price_step`, `regime_setting`, `event_subject`, `configuration_state`, `purchase_order_line`.

## Commands and queries

Authorization areas of this chunk (catalog `authorization-areas.csv`, under `finance`): the function `chart_of_accounts` (account determination and subledger activation) and the document type `open_item_matching`, the area of the matching document of R239; the `balance_transfer` documents of R244 fall under the document type `balance_transfer`. The sources name no area for open item queries or `CreateOpeningTurnover`. The level of a verb is the catalog's (`List`: `read`; `Create`: `edit`; `Transfer`: `post`; `Activate`: `full`; computed queries need `read`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `GetAccountDetermination` | computed query; area `chart_of_accounts` | key, determinant values, company | Returns the account a posting would use, the matching row and the check result (R202) | none | none stated |
| `ListAccountDetermination` | query; area `chart_of_accounts` | company | Lists the company's determination rows (R202) | none | none stated |
| `ActivateSubledger` | `human_only`; area `chart_of_accounts` | company, control kind, `effective_from`, opening detail per asset, cost object or loan | Writes `subledger_activation` and posts the `subledger_reclassification` document (R211-R213) | none stated | rejected when the detail does not sum to the balance (no code stated) |
| `TransferPartnerOpenItems` | human-only; area not stated | not stated (a partner and its new reconciliation account) | Changes the partner's account and posts `balance_transfer` documents (R244) | none stated | none stated |
| `ListOpenItem` | query, within the origin document's read owner scope; area not stated | partner, account, kind, due date, currency, state, `as_of` | Lists open items (R248) | none | none stated |
| `GetPartnerExposure` | computed query, `is_owner_scoped: false`, owner scope `branch` or `company`; area not stated | not stated | Open receivable and payable amounts per partner and currency by kind and due bucket (R249) | none | none stated |
| `CreateOpeningTurnover` | not stated | account, `start_date`, `end_date`, debit and credit turnover | Writes `opening_turnover` rows (R266) | none stated | none stated |

Contract interfaces, not registry commands: `ledger.contract.write_journal_entry` takes the item effects of R226, emits `OpenItemSettled` (R257) and returns `open_item_mismatch`, `open_item_oversettled`, `subledger_activation_date_not_reached` and `control_dimension_missing`; `ledger.contract.write_derivation_trace` (R262). The reversal of a document whose items have unreversed settling lines is rejected with `open_item_settled` (R243). `UpdatePartner` (`master_data`) returns `partner_has_open_items` (R245). A payment term whose percents do not sum to 100 is rejected with `payment_term_invalid` (R231).

## Rules

### Account determination: template, queries and catalog rows

R201. The localization package supplies a default determination template per regime, written with its chart template's operational account codes and applied at company setup (DS-14, DS-19). The package's CI checks every row against ADR-0015.R4 and resolves every combination of key, valuation class, item group, partner group, tax code and currency that the template's documents can produce. The TT99 template, its format and its check are ADR-0039.R7, ADR-0039.R8 and ADR-0039.R11.
Source: ADR-0015.R13

R202. The query `GetAccountDetermination` (key, determinant values, company) returns the account a posting would use, the matching row and the check result, so an agent can explain a posting before simulating it (Principles 6, 13). It is a computed result, an exception to ADR-0004.R21 as in ADR-0011.R14. `ListAccountDetermination` lists a company's rows.
Source: ADR-0015.R14

R203. The column `has_regime_alternatives` of `transaction-keys.csv` is the one exception to ADR-0015.R2, kept as data; CI reads it. It marks every key whose listed accounts are alternatives that a regime or company chooses between under ADR-0015.R4: keys that share a system account's code (`price_difference`, `fx_gain_unrealized`, `fx_loss_unrealized`) and keys that do not (`cash_surplus`, `cash_shortage`, `bank_charge`, `production_abnormal_cost`, `production_unabsorbed_overhead`; ADR-0053.R6). The catalog is authoritative for how many keys exist.
Source: ADR-0027.R11, .N1

R204. Production movement types, catalog version 0.x, given as direction, value source, costing role, offset key. `production_issue`: out, `preliminary_price`, `production_input`, `production_consumption`. `production_return`: in, `preliminary_price`, `production_input`, `production_consumption`. `production_receipt`: in, `preliminary_price`, `production_output`, `production_output`. `co_product_receipt`: in, `preliminary_price`, `production_output`, `production_output`. `by_product_receipt`: in, `regime`, `production_output`, `production_output`. `disassembly_issue`: out, `preliminary_price`, `production_input`, `production_consumption`. `disassembly_receipt`: in, `preliminary_price`, `production_output`, `production_output`.
Source: ADR-0035.R19

R205. The costing roles of ADR-0020.R4 include `production_input` (into a cost-object node, revalued; a return counts negative) and `production_output` (from a cost-object node, revalued unless its value is final).
Source: ADR-0035.R19

R206. Production transaction keys, catalog version 0.x, given as accounts and determinants. `production_consumption`: `production_cost_material`, none. `production_output`: `inventory_work_in_process`, the valuation class of the order's main output. `production_wip_transfer`: `inventory_work_in_process`, the valuation class of the order's main output. `production_abnormal_cost`: `cost_of_goods_sold` or `expense_other` as regime alternatives, none. `production_unabsorbed_overhead`: `cost_of_goods_sold` or `expense_other` as regime alternatives, none (the TT99 determination row is flagged content of the localization package; ADR-0053.R6). `production_residual_cost`: `cost_of_goods_sold`, none. For a `disassembly` order the determinant of `production_output` and `production_wip_transfer` is the valuation class of the header item, the input being taken apart. The leaf side of the transfer, the abnormal cost and allocations copy the source line's account. Key `consumption` also lists `production_cost_overhead`, for internal consumption to a factory cost center.
Source: ADR-0035.R19, .N1, .N2

R207. Subcontracting transaction keys, catalog version 0.x. `production_external_service`: account `production_cost_other`, control kind `cost_object`, no determinant. `inventory_at_processor_posting`: the inventory leaves, control kind `inventory`, determinants valuation class and warehouse.
Source: ADR-0037.R9

### Later-phase seams

Fixed assets and loans (Phase 3) are designed in detail only when they are built (B7). What would be costly to change later is fixed now, at no cost to Phase 1: the dimensions on the journal line and the material document line, the gated control kinds, the system accounts (the system chart is frozen to additions at the step 0 gate, ADR-0010.R9) and a costing solver stated over typed nodes and the period's value flows. Everything else for these phases is additive: new tables, movement types, transaction keys, modules and enumeration values.

R208. `journal_line` has the nullable dimensions `cost_object_id` and `fixed_asset_id` (a new dimension is a nullable column added by ADR, ADR-0014.R9). `material_document_line` has a nullable `cost_object_id`, for consumption into a cost collector and output from it. These columns stay empty and out of command schemas until their phase.
Source: ADR-0025.R1

R209. `fixed_asset` is a stub table with `id`, `company_id`, `code`, `name` and `recorded_at`, unique on (`company_id`, `code`), with RLS. It is owned by `ledger` until the `assets` module (layer 3, Phase 3; ADR-0022.R2) exists, and is designed in Phase 3. `cost_object` exists from the first migration too, so the foreign keys to both tables exist from then. `cost_object` is a cost collector owned by `production`, which is in Phase 1 and designed in full on these seams (ADR-0032.R4). It has `id`, `company_id`, `code` and `name`, unique on (`company_id`, `code`), with RLS, and the columns of ADR-0035.R1: `kind`, which is `production_order` (one per production order, ADR-0034.R15) or `cost_pool` (one per cost center that collects production cost); `production_order_id` or `cost_center_id`, matching the kind; `state` (`open`, `closed`); and `recorded_at`. Collecting cost per production order answers part of the question on production cost collection (ADR-0035.R2); the rest stays an open question (R218).
Source: ADR-0025.R2, ADR-0025.H.N1

R210. The control kinds of ADR-0010 include the gated kinds `cost_object`, `fixed_asset` and `loan`; once a kind is active for a company, lines on its system accounts must carry its dimensions. `cost_object`: accounts `inventory_work_in_process` and the `production_cost` leaves; dimension `cost_object_id`. `fixed_asset`: accounts `fixed_asset_tangible`, `fixed_asset_intangible`, `fixed_asset_investment_property`, `fixed_asset_other`, `fixed_asset_accumulated_depreciation` and `construction_in_progress`; dimension `fixed_asset_id`. `loan`: accounts `borrowing` and `receivable_loan`; dimensions `partner_id` and `open_item_id`, with one `loan` item per drawdown (R246).
Source: ADR-0025.R3

R211. A gated kind is enforced for a company only after the command `ActivateSubledger` (`human_only`), which is unique per (company, kind) and irreversible. It writes a `subledger_activation` row: company, `control_kind`, `effective_from` and the reclassification document.
Source: ADR-0025.R4

R212. `effective_from` must be the first day of a posting period, and every earlier period must be `locked` in area `general` (ADR-0012), so no backdated line can change the reconciled balance. `ActivateSubledger` takes an exclusive lock on the area-state rows of the periods from `effective_from` on: area `inventory` for `cost_object`, area `general` for the other kinds (ADR-0035; DS-06).
Source: ADR-0025.R4

R213. Activation posts a document of type `subledger_reclassification`, dated `effective_from`, which only `ActivateSubledger` creates. For each account it credits the undimensioned balance and debits it per asset, cost object or loan, from the opening detail the command carries. The per-dimension lines must sum to the account's balance at `effective_from`, otherwise the command is rejected. Its undimensioned lines are the single exception to R214 and to `INV-70`. From then on the account equals the sum by dimension (DS-16).
Source: ADR-0025.R4

R214. After activation, a line on those accounts dated before `effective_from` is rejected with `subledger_activation_date_not_reached`, and a line dated on or after it without the kind's dimensions is rejected with `control_dimension_missing`.
Source: ADR-0025.R4

R215. Before activation the account's effective control kind is `none`. The effective kind (company, system account, posting date) is what ADR-0014.R10 and its trigger (required columns, the flagged manual-journal rule), ADR-0010.R12 (moving balances) and, for `fixed_asset` and `loan`, ADR-0012.R4 (posting area) read. The catalog value of the control kind is what account determination (ADR-0015.R4, R201) and `INV-16` read.
Source: ADR-0025.R4

R216. The kinds `inventory`, `receivable`, `payable` and `gr_ir` are active from company creation.
Source: ADR-0025.R4

R217. Lines of the gated kinds `fixed_asset` and `loan`, and depreciation close tasks, are in posting area `general` (ADR-0012.R4). `cost_object` lines are in area `inventory` before and after activation, and production is settled by the inventory costing job (ADR-0035.R3, ADR-0035.R5).
Source: ADR-0025.R4

R218. System account rows for the later phases: the node `production_cost` under `expense` with the postable leaves `production_cost_material`, `production_cost_labor`, `production_cost_overhead` and `production_cost_other`, control kind `cost_object` (overhead lines need a cost object once the kind is active); and `receivable_loan` under `receivable`, control kind `loan`, for loans the company grants. `expense_other` does not cover production costs. Which operational accounts map to the production cost leaves is DS-19's and the author's (spec 08: unverified; open question).
Source: ADR-0025.R5

R219. Control kinds on existing system accounts: `inventory_work_in_process` is `cost_object`; the fixed asset leaves and `construction_in_progress` are `fixed_asset` (assets under construction settle into fixed assets); `borrowing` is `loan`. Kept `none` by decision: `prepaid_expense` (allocation schedules can refer to journal lines without a control kind), `receivable_other` and `financial_investment_other` (loans granted go to `receivable_loan`; a later subledger on these accounts costs a new operational account and a balance transfer, ADR-0010.R12). After the step 0 gate these choices change only by a superseding ADR on a reserved rule (spec 06 rule 1).
Source: ADR-0025.R5

### Open items

An open item is one obligation with a partner on one operational account (an invoice installment, a credit, an advance, a payment on account, a loan drawdown), created by exactly one journal line. Every later line that settles or adjusts it refers to it, so its amounts are the sum of its lines, the subledger stays a view over the journal (ADR-0014.R17), and the cache on the row serves queries and locking. Settlement is explicit (the document names the items), partial or full, never above the open amount, and serialized per item. DS-25 keeps payments, bank statements, matching UX, netting, payment allocation rules, dunning and write-off processes, all on these interfaces.

R221. An `open_item` has an identity that a trigger keeps immutable: `company_id`, `partner_id`, `account_id` (an operational account mapped to a system account whose effective control kind is `receivable`, `payable` or `loan`, R215), `open_item_kind`, `natural_side` (`debit`: the partner owes; `credit`: the company owes), `transaction_currency`, `origin_document_id` and `origin_journal_line_id` (unique). Its `partner_id` is the payer (else the bill-to party, else the sold-to partner) of a sales document and the invoicing party of a purchase document, as the posting line carries it (ADR-0074.R4; `INV-863`).
Source: ADR-0026.R1, .N2

R222. Terms, references and link of an `open_item`: `installment_number` (information), `payment_term_id`, `document_date`, `posting_date`, `due_date`, `discount_due_date`, `discount_percent` (one tier; further tiers are out of scope); `reference` (the company's own number, for example an old invoice number at migration) and `partner_reference` (for example the supplier's invoice number); `predecessor_open_item_id` (R244). `original_posting_date` is the posting date for ordinary items and the old system's date for opening items, which the opening line carries (ADR-0044.R8). The check `ck_open_item_due_date` requires `due_date` for `invoice` and `credit`, requires it empty for `advance`, `payment_on_account` and `loan`, and allows either for `other`; opening advance and payment-on-account lines therefore carry no due date.
Source: ADR-0026.R1, ADR-0048.R18

R223. Amounts of an `open_item`: the original amounts `original_transaction_amount`, `original_company_amount` and `original_group_amount`; and the cache `open_transaction_amount`, `open_company_amount`, `open_group_amount`, `revaluation_company_amount` and `revaluation_group_amount` (sums of open revaluation lines), `is_settled`, `is_reversed` and `last_settlement_date` (the latest posting date of a settling line, recomputed on reversal). Amounts are signed like journal amounts, positive for debit and negative for credit in every currency, so a credit-side item has negative original and open amounts; comparisons such as "never above the open amount" use magnitudes. DS-06 checks that the sign of `original_transaction_amount` matches `natural_side` and that a settled item has all open amounts zero.
Source: ADR-0026.R1, .N1

R224. DS-25 attributes such as dunning level, payment block and dispute live in the side table `open_item_collection`, keyed by `open_item_id`, so the core table does not change (ADR-0048.R17).
Source: ADR-0026.R1

R225. `open_item_kind` is a core catalog with the values `invoice`, `credit` (credit notes, and debit notes that reduce an invoice), `advance` (non-monetary per spec 07, excluded from revaluation by kind, ADR-0011.R18), `payment_on_account` (money received or paid without an item to settle), `loan` (one per drawdown) and `other`. DS-25 may add kinds. Statutory presentation per kind and side is DS-26's (ADR-0010.R15), in the format of ADR-0049.R7; the meaning of each kind for presentation is the regime's.
Source: ADR-0026.R2, .N1, ADR-0026.R9.N1

R226. Every journal line on an account whose effective control kind is `receivable`, `payable` or `loan` declares its item effect to `ledger.contract.write_journal_entry` (ADR-0022.R4). `creates`: kind, due dates, terms and references; the line becomes the item's origin and its amounts the item's original amounts. `settles`: the item ID; the line has the opposite sign to the item's `natural_side`. `adjusts`: the item ID, for lines that change only company or group amounts (realized FX, revaluation; transaction amount 0). `reverses`: the item ID, for the mirrored lines of a reversal document (R243).
Source: ADR-0026.R3

R227. Only the ledger writes `open_item`. It creates the item with an ID from `context.new_id`, inserted before the line that refers to it (the `origin_journal_line_id` foreign key is `DEFERRABLE INITIALLY DEFERRED`), updates the cache under the item lock and writes the plan entries. `open_item` is a serialized table under ADR-0008.R10: lock helper only, no lock in simulation, CI check.
Source: ADR-0026.R3

R228. Created items, with kind, due dates and amounts, appear in the plan, so an approval binds to them. For an invoice the plan holds the installment schedule, which is part of the invoice's content, and not the `open_item` rows derived from it at posting (ADR-0047.R6; ADR-0031.R1).
Source: ADR-0026.R3

R229. A line that refers to an item must match the item's company, partner, account and transaction currency, else `open_item_mismatch`; the journal trigger checks the same. Settling in another currency goes through currency exchange clearing (ADR-0011.R4), so lines on an item are always in its currency.
Source: ADR-0026.R4

R230. A document posts one control-account line per installment, and each line creates one item. Transaction amounts are split by the largest-remainder method; company and group amounts are rounded per line with the rounding line (ADR-0006.R20). The document proposes installments from the partner's term (ADR-0019 profiles), editable before posting.
Source: ADR-0026.R5

R231. A `payment_term` has `code`, `name`, `is_active` and `payment_term_line` rows: `amount_percent`, `due_days`, `due_date_base` (`document_date` or `end_of_month`), and optional `discount_percent` and `discount_days`. The percents of a term sum to 100, else `payment_term_invalid`.
Source: ADR-0026.R5

R232. A settlement records its `evidence_method` (R254) and emits `OpenItemSettled` (R257). It locks the item and is rejected with `open_item_oversettled` when its transaction amount exceeds the open transaction amount, including on a settled item.
Source: ADR-0026.R6

R233. A settlement or an origin reversal dated before a revaluation line of the item is accepted. It takes the carrying amount as of its posting date, computed from the item's lines dated on or before it and not from the current cache, and it makes that revaluation's close task stale (ADR-0012.R12); the rerun posts the difference. Until the rerun, an item settled in full keeps the later revaluation amounts open, so it is not yet `is_settled` (DS-06's check). The code `open_item_revaluation_later` is unused; its DS-04 row stays, marked unused, so the code is not reused.
Source: ADR-0026.R6, .N1

R234. The carrying amount leaving at a settlement depends on `realized_fx_basis`. With `revalued` it is the share (amount settled ÷ open transaction amount) of the open company and group amounts including revaluation. With `original` it is the same share of the amounts excluding revaluation; only under `delta` is the matching share of revaluation then released to the revaluation target in the same entry. `original` is not limited to `delta`; ADR-0011.R16 limits `revalued` to `delta`.
Source: ADR-0026.R6, .N3, ADR-0026.R9.N1

R235. Under `reverse_and_repost` a settlement's carrying amount excludes revaluation lines, whatever `realized_fx_basis` says, because the revaluation job reverses the revaluation on the first day of the next period in the same run. The settlement takes the open amounts excluding revaluation, and the item's revaluation share leaves by the rerun or by the reversal, not by the settlement. A settlement dated in a period whose revaluation has posted makes that revaluation stale, and the rerun posts the difference.
Source: ADR-0026.R6, .N2

R236. The settlement that settles the item takes exactly what is left, so a settled item has all open amounts zero. Realized FX is the settlement's amount in each currency minus the carrying amount leaving, posted through the realized FX keys (ADR-0011.R15); FX is realized at clearing.
Source: ADR-0026.R6, ADR-0026.R9.N1

R237. Open-item accounts use the `specific` book rate method only; `moving_average` (ADR-0011.R15) applies to balance-level accounts such as cash and bank (interim, flagged; open question).
Source: ADR-0026.R7

R238. The excess of a payment over the items it names is posted by the document as a new `payment_on_account` item. Write-offs and early-payment discounts settle items through the same interface with their own lines; their accounting and approval are DS-25's and the regime's (flagged).
Source: ADR-0026.R8, ADR-0026.R9.N1

R239. Matching items of one partner and account in one currency is an `open_item_matching` document (internal, ADR-0009.R19): two lines netting to zero in transaction currency, each settling one item at that item's carrying amount, plus realized FX lines for the difference. Netting across accounts or partners, and across currencies, is DS-25's. Who may post a matching (agent draft, policy, human) is DS-28's; matchings pass the usual policy points (ADR-0043.R17).
Source: ADR-0026.R9, .N1

R240. A credit note always creates a `credit` item. Applying it to an invoice is always an `open_item_matching`, which the correction document may create in the same command.
Source: ADR-0026.R9

R241. Revaluation lines (ADR-0011.R19) are `adjusts` lines on items of accounts the regime revalues per open item. On accounts revalued per balance, revaluation lines carry no item reference.
Source: ADR-0026.R10

R242. `INV-32` covers the settled and the open part of an open item: its company-currency carrying amount equals the company-currency amounts of its settlements and matchings plus its cached open amount.
Source: ADR-0026.R9.N1

R243. Reversal of documents with open items. Reversing a document whose items have unreversed settling lines from other documents is rejected with `open_item_settled`; the settlements are reversed first. Reversing an untouched origin sets `is_reversed`: the item is neither open nor reported as paid; when the reversal is dated before a revaluation line of the item, R233 applies. A settlement's reversal mirrors its lines exactly, including realized FX, and restores the cache; shares are never recomputed. An item moved by R244 cannot have its origin reversed until the move is reversed.
Source: ADR-0026.R11, ADR-0026.R6.N1

R244. Moving items to another account, for example when a partner's reconciliation account changes (ADR-0015.R11), is the command `TransferPartnerOpenItems` (human-only; the verb Transfer is in the glossary). In one transaction it changes the partner's account and posts `balance_transfer` documents (ADR-0014.R3) with one line pair per item and at most 1,000 items per document (ADR-0022.R9). Each pair settles the old item and creates a new one with the same open and revaluation amounts in all three currencies, the same terms and `predecessor_open_item_id`, with no realized FX. For a revalued item the pair carries the open amounts excluding revaluation, and one `adjusts` line on each item moves the revaluation share out of the old item and into the new one; so the new item's original amounts exclude revaluation and its revaluation amounts equal the old item's (`INV-36`). A reversal is rejected once a new item has settlements.
Source: ADR-0026.R12, .N1

R245. `UpdatePartner` cannot change a reconciliation account while the partner has open items on it (`partner_has_open_items`).
Source: ADR-0026.R12

R246. No item exists on a `loan` account before the subledger is activated (R211). Afterwards each drawdown creates its own `loan` item, and the drawdowns of one contract share its `reference`. Whether loans are revalued per item or per balance follows the existing open question.
Source: ADR-0026.R13

R247. The lock order per command; within each class rows are locked in ascending ID unless stated. (1) Documents: the command's own and those it refers to (the order a delivery fulfills, the receipt a landed cost targets, the original of a reversal or correction, the production order of a shop-floor document; ADR-0034.R19). (2) Period area state rows, share lock. (3) The planning state row (planning runs only), or the company's `production_structure` row (releases of bills of materials and routings, production version and production setting saves, deactivations; ADR-0033.R8), or the company's `configuration_state` row (every activation, enable, rollback and demotion of a configuration artifact; ADR-0058). (4) Warehouse task rows. (5) Handling unit rows, parent first. (6) `stock_value` rows, ascending by item and warehouse ID. (7) `stock_quantity` rows. (8) Bin rows. (9) Partner rows (credit check, DS-22). Then `money_account_balance` rows, a class of their own (ADR-0048.R12). (10) Open item rows: the ledger locks all of an entry's items before inserting any line, and settlements of one item are serialized (PAR-10). (11) Numbering counters. (12) `event_subject` rows.
Source: ADR-0027.R10, .N1, .N2, ADR-0026.R14

R267. Locks outside the classes of R247. The idempotency record is taken first (ADR-0008.R16) and held to commit. Account rows locked by the first-posting trigger (ADR-0014.R12) are taken in line order after the open items and before numbering counters; they are outside the lock helper's assertion, because they are locked once per account in its life. Work item claims run in their own transactions. For a command of an agent run bound to a work item, that item row follows `FOR KEY SHARE` (claims, assignments and lease expiry take it `FOR UPDATE`); work item rows raised by a command are the last class, in (`kind`, `open_key`) order (ADR-0042.R5, ADR-0042.R9). Exception: credit hold updates on other orders' demand rows, made inside a `sales` command that holds the partner lock, take no class 1 lock of those orders (ADR-0047.R18).
Source: ADR-0027.R10

R248. The query `ListOpenItem` filters by partner, account, kind, due date, currency, state and `as_of`: an item is open on a date when `posting_date <= as_of` and it is not settled or reversed by lines dated on or before that date. It shows an item only within its origin document's read owner scope.
Source: ADR-0026.R15, .N1

R249. The query `GetPartnerExposure` (a computed result, like `GetExchangeRate`) returns open receivable and payable amounts per partner and currency by kind and due bucket; the partner is the payer, else the bill-to party, else the sold-to partner (ADR-0074.R4). It totals without listing, so it is registered `is_owner_scoped: false` and needs owner scope `branch` or `company` (ADR-0054.R15). Open order value is added by DS-22's own query; `ledger` never reads a higher layer.
Source: ADR-0026.R15, .N1, .N2

R250. Indexes of `open_item`: (`company_id`, `partner_id`), (`company_id`, `account_id`) and (`company_id`, `due_date`), each where the item is neither settled nor reversed; and (`origin_document_id`).
Source: ADR-0026.R15

R251. `general_journal` lines may declare `creates` or `settles` when the flagged rule on manual journals (ADR-0014.R10; R260) allows posting to control accounts. Step 1 tests run with that flag on in the test configuration, so the interfaces and invariants are exercised from step 1.
Source: ADR-0026.R16

R252. Build order of the open-item core: step 1 builds the tables, the catalog, payment terms, clearing (matching), the posting path and the queries; step 4 adds opening items per old invoice, as `opening_open_item_entry` (DS-21; ADR-0044.R8); step 5 adds invoices and credit notes; step 6 adds the DS-25 processes.
Source: ADR-0026.R17, .N1

### Payment evidence

R253. `journal_line.evidence_method` is nullable, with `CHECK (evidence_method IS NULL OR open_item_id IS NOT NULL)`. Its values are `cash`, `bank_transfer`, `card`, `offset`, `third_party` and `none`. It records how a settlement was paid, in any regime; a condition's `failing_methods` decides what fails that condition (ADR-0053.R3, ADR-0053.R11).
Source: ADR-0048.R18, ADR-0041.R15.N1

R254. Lines that carry `evidence_method`: every line with an `open_item_id` that is not the item's origin line and has a non-zero transaction amount (so not the `adjusts` lines of revaluation and realized differences), except the reversal of an origin line; and the origin lines of `advance` and `payment_on_account` items, which record how the advance was paid. Opening advance and payment-on-account lines carry it too, so a supplier advance paid by bank before cut-over still gives payment evidence when matched. No other line carries one (`INV-97`).
Source: ADR-0048.R18

R255. Values of `evidence_method` on settlements that are not payments. A matching against an advance or a payment on account copies that item's origin method onto its settling lines. A matching of a credit note uses `none`; it reduces the amount that needs evidence and counts as neither cash nor an offset. Write-offs and payment discounts use `none`. In a `balance_transfer` the settling line uses `none`, and the creating line of a successor advance or payment on account copies its predecessor's origin method. A reversal of a non-origin line copies the original's method.
Source: ADR-0048.R18, ADR-0041.R15

R256. Payment evidence travels by event, so `ledger` never imports `tax` (ADR-0022.R2). The method is recorded on the settlement, because offsets have no payment document.
Source: ADR-0041.R15

R257. `ledger` emits `OpenItemSettled` (item, amount, date, method, `reversal_of`) through the outbox for every settlement of an open item.
Source: ADR-0041.R15

R258. The transactional `tax` consumer `tax_payment_evidence` calls `tax.contract.record_payment_evidence` and, when a share becomes non-deductible, posts the `tax_adjustment` through the `ledger` contract (ADR-0013.R9); the adjustment follows the payment and is not in the payment's plan. `tax` may import the `ledger` contract. Settlements of opening open items, which have no tax rows, are skipped (ADR-0044.R13). Import VAT rows follow the customs declaration's link to its supplier invoice lines (ADR-0021) to find the open items whose settlements give evidence. A daily due-date job applies `condition_failed` with reason `lapsed` where the condition has a lapse (ADR-0053.R3, ADR-0053.R11).
Source: ADR-0041.R15, .N1

### General journal entries

R259. The core seeds a rule requiring `standard` approval for `submit` and `post` of `general_journal` (ADR-0014.R3), for every actor kind (flagged; small companies follow ADR-0043.R13). The seed is core segregation-of-duties practice, not a rule of one country (ADR-0053.R14).
Source: ADR-0048.R15, .N1

R260. General journal lines on accounts with a control kind are rejected with `manual_posting_to_control_account`, unless the regime setting `journal.manual_posting_to_control_accounts` is true; which kinds the setting can open is ADR-0014.R10. A localization package seeds the regime value as package content.
Source: ADR-0048.R15

R261. Expenses without an order may use a payment's `account` line or a purchase invoice's `expense` line (ADR-0047.R12); both apply the supplier-invoice key. General journal lines and payment `account` lines carry an explicit `business_unit_id`, and posted amounts move between business units only by a general journal on the same account (ADR-0069).
Source: ADR-0048.R15, .N2

### Derivation trace

R262. `derivation_trace` is owned by `ledger` and written through `ledger.contract.write_derivation_trace` in the caller's transaction. It holds `rule_code` and `rule_version`; `inputs` (typed references to lines, price rows, tax rate rows, a `regime_setting` key and `effective_from`, applied rates and open items); `steps` (ordered exact intermediate values); `result`, `recorded_at` and the `command_id` of the command that wrote it (ADR-0008). A line refers to it by `derivation_trace_id` (ADR-0014.R5). It is not OpenTelemetry's `trace_id`.
Source: ADR-0027.R3

R263. Trace writers follow spec 10's lean scope: costing (ADR-0020) and landed cost (ADR-0021) write traces. The business unit derivation writes one trace per journal entry, with `rule_code` `business_unit_derivation`, named by `journal_entry.business_unit_trace_id` (ADR-0069). Pricing writes no `derivation_trace` rows; prices are explained by the `document_line_price_step` rows of each line (interim; ADR-0047.R16).
Source: ADR-0027.R4, .N1

R264. Whether FX conversion, pricing (DS-22) and tax (DS-23) also write traces in Phase 1 is the author's decision, because it is a scope question (ADR-0005 item 2; open question). The generic schema lets them be added without change.
Source: ADR-0027.R4

### Period closing and opening turnover

R265. The open question on closing profit and loss to the regime's result and retained-earnings accounts every period (their account numbers are content of the localization package) keeps the agent's interim decision, and an unchecked item asks the author to verify the rule against the TT99 text; an unverified rule stays open (reading guide rule 4; ADR-0012.R18).
Source: ADR-0027.R19

R266. At a mid-year cut-over, income and expense of the fiscal year before the cut-over are loaded as `opening_turnover` rows: account, `start_date`, `end_date` and the debit and credit turnover in company currency, before closing entries. The rows carry dates and no fiscal year, because the first fiscal year after a mid-year cut-over is short. `opening_turnover` is owned by `ledger` and written by `CreateOpeningTurnover`. The rows are non-posting figures that statutory reports of that year read (DS-26; ADR-0049.R14); the year's profit to date is already in the post-closing balance of retained earnings. Flagged.
Source: ADR-0044.R10, .N1

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-32` | `carrying_amount_consistent` | day | An open item's company-currency carrying amount, its original amount plus its revaluations and realized differences, equals the sum of its settled part (the company-currency amounts of its settlements and matchings) and its open part (the cached open amount of `INV-33`). | R234, R236, R239, R242 |
| `INV-33` | `open_item_cache_equals_lines` | day | Each open item's cached open and revaluation amounts equal the sums of its journal lines in transaction, company and group currency; a settled item has all open amounts zero. | R223, R227, R236; ADR-0014.R17 |
| `INV-36` | `successor_equals_predecessor` | day | A moved item's original amounts equal its predecessor's open amounts excluding revaluation, and its revaluation amounts equal its predecessor's, at the move, in all three currencies. | R244 |
| `INV-70` | `active_subledger_dimensions_present` | day | Every line on an account whose control kind is active for the company on its posting date carries that kind's dimensions, except the undimensioned lines of the `subledger_reclassification` document; no line before an activation date is posted after activation; and no line refers to another company's cost object or fixed asset. | R210, R213, R214 |
| `INV-97` | `evidence_on_listed_lines` | day | Every journal line with an open item that is not the item's origin line, has a non-zero transaction amount and is not the reversal of an origin line, and every origin line of an advance or payment-on-account item, has an `evidence_method`; no other line has one. | R253, R254, R255 |

Named by rules of this chunk, with their rows in other chunks: `INV-16` (R215; chunk 1), `INV-863` (R221; chunk 3).

## Settings

None: the setting `journal.manual_posting_to_control_accounts`, used by R251 and R260, has its row in chunk 1.

Reads: `cash.small_difference_limit` and `cash.bank_account_cooling_days` (`cash`; ADR-0048.R11, ADR-0048.R3).

## Conflicts

CONFLICT ADR-0025.H.N1: ADR-0032.R4 governs; production is Phase 1 and designed in full, so R209 drops "designed in Phase 2" for `cost_object`.
CONFLICT ADR-0025.R2: the rule's own closing note and ADR-0034.R15 govern the owner: `cost_object` is owned by `production`, not by `ledger` until a phase module exists. ADR-0035.R1 with the DS-06 DDL governs its columns: `kind`, `production_order_id` or `cost_center_id` and `state` join the columns the rule lists, so only `fixed_asset` is stated as a stub; both tables also carry `recorded_at` (DDL). ADR-0035.R2 answers part of the rule's author question on cost collection (R209).
CONFLICT ADR-0025.R3: ADR-0026.R13 governs; a `loan` account has one open item per drawdown, not one per loan contract (R210, R246).
CONFLICT ADR-0025.R4: the rule's amendment citing ADR-0035.R3 governs; `cost_object` lines are in area `inventory`, and "WIP close tasks in area `general`" is not restated because production settles in the inventory costing job (R217).
CONFLICT ADR-0025.R5: the catalog total typed in the rule is historical; `system-accounts.csv` is authoritative (ADR-0010.R1), so R218 and R219 state no total.
CONFLICT ADR-0026.R2: ADR-0026.R9.N1 confirms the rule, so the mark "open question" on the meaning of each kind for presentation is not restated (R225).
CONFLICT ADR-0026.R3: the rule's closing paragraph citing ADR-0047.R6 governs for invoices; the plan holds the installment schedule and not the derived `open_item` rows (R228).
CONFLICT ADR-0026.R6: ADR-0026.R6.N1 drops the rejection `open_item_revaluation_later` (R233); ADR-0026.R6.N3 corrects the reading of `original` with `delta` (R234); ADR-0048.R18 adds the value `none` to the evidence values (R253); ADR-0026.R9.N1 confirms the release of revaluation at clearing, so its mark "interim" is not restated.
CONFLICT ADR-0026.R8: ADR-0026.R9.N1 confirms the overpayment as a payment on account, so the alternative "refund or hold" and the mark "interim" are not restated (R238).
CONFLICT ADR-0026.R9: ADR-0026.R9.N1 confirms that FX is realized at clearing, so the mark "flagged" on the realized FX lines of a matching is not restated (R239).
CONFLICT ADR-0026.R11: ADR-0026.R6.N1 governs; an origin reversal dated before a revaluation line is accepted, so "a revalued item's revaluation is reversed first" is not restated (R243).
CONFLICT ADR-0026.R14: ADR-0027.R10 holds the complete lock order (R247); only the serialization of settlements per item (PAR-10) is kept from this rule.
CONFLICT ADR-0026.R17: ADR-0026.R17.N1 decides the proposed build order; R252 states it as decided, without "proposed" and "the step change is the author's decision".
CONFLICT ADR-0027.R11: ADR-0027.R11.N1 governs; the key total typed in the rule is historical and the catalog is authoritative (R203).
CONFLICT ADR-0035.R19: the key totals typed in the rule are historical; `transaction-keys.csv` is authoritative (ADR-0015.R1.N1, ADR-0027.R11.N1), so R204 to R206 state no total.
CONFLICT ADR-0037.R9: the key total typed in the rule is historical; `transaction-keys.csv` is authoritative (ADR-0015.R1.N1), so R207 states no total.
CONFLICT ADR-0041.R15: the rule's closing paragraph citing ADR-0048.R18 adds `none` and replaces "inherits" by the copied origin method (R255); ADR-0041.R15.N1 replaces `due_date_lapse` by `condition_failed` with reason `lapsed` (R258).
FALSE-POSITIVE ADR-0026.R6.N2: "reversed" is the accounting term for the revaluation reversal posting, not a reversed decision; the note adds the `reverse_and_repost` case to the rule.
FALSE-POSITIVE ADR-0044.R10.N1: "instead of" describes the columns `start_date` and `end_date` chosen over a fiscal year column; the rule named no column, so nothing in it is contradicted.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0015.R13 | R201 |
| ADR-0015.R14 | R202 |
| ADR-0017.R19.N2 | ref: ADR-0017.R19.N2 |
| ADR-0020.R6 | ref: ADR-0020.R6 |
| ADR-0020.R11.N5 | ref: ADR-0020.R11.N5 |
| ADR-0025.H.N1 | R209 |
| ADR-0025.D0 | Later-phase seams |
| ADR-0025.R1 | R208 |
| ADR-0025.R2 | R209 |
| ADR-0025.R3 | R210 |
| ADR-0025.R4 | R211-R217 |
| ADR-0025.R5 | R218-R219 |
| ADR-0026.D0 | Open items |
| ADR-0026.R1 | R221-R224 |
| ADR-0026.R1.N1 | R223 |
| ADR-0026.R1.N2 | R221 |
| ADR-0026.R2 | R225 |
| ADR-0026.R2.N1 | R225 |
| ADR-0026.R3 | R226-R228 |
| ADR-0026.R4 | R229 |
| ADR-0026.R5 | R230-R231 |
| ADR-0026.R6 | R232-R236 |
| ADR-0026.R6.N1 | R233, R243 |
| ADR-0026.R6.N2 | R235 |
| ADR-0026.R6.N3 | R234 |
| ADR-0026.R7 | R237 |
| ADR-0026.R8 | R238 |
| ADR-0026.R9 | R239-R240 |
| ADR-0026.R9.N1 | R225, R234, R236, R238, R239, R242 |
| ADR-0026.R10 | R241 |
| ADR-0026.R11 | R243 |
| ADR-0026.R12 | R244-R245 |
| ADR-0026.R12.N1 | R244 |
| ADR-0026.R13 | R246 |
| ADR-0026.R14 | R247 |
| ADR-0026.R15 | R248-R250 |
| ADR-0026.R15.N1 | R248, R249 |
| ADR-0026.R15.N2 | R249 |
| ADR-0026.R16 | R251 |
| ADR-0026.R17 | R252 |
| ADR-0026.R17.N1 | R252 |
| ADR-0027.D0 | ref: ADR-0027.D0 |
| ADR-0027.R3 | R262 |
| ADR-0027.R4 | R263-R264 |
| ADR-0027.R4.N1 | R263 |
| ADR-0027.R5 | ref: ADR-0027.R5 |
| ADR-0027.R9 | ref: ADR-0027.R9 |
| ADR-0027.R10 | R247, R267 |
| ADR-0027.R10.N1 | R247 |
| ADR-0027.R10.N2 | R247 |
| ADR-0027.R11 | R203 |
| ADR-0027.R11.N1 | R203 |
| ADR-0027.R19 | R265 |
| ADR-0030.R3 | ref: ADR-0030.R3 |
| ADR-0035.R19 | R204-R206 |
| ADR-0035.R19.N1 | R206 |
| ADR-0035.R19.N2 | R206 |
| ADR-0037.R9 | R207 |
| ADR-0038.R4.N2 | ref: ADR-0038.R4.N2 |
| ADR-0039.R7 | ref: ADR-0039.R7 |
| ADR-0041.R1 | ref: ADR-0041.R1 |
| ADR-0041.R1.N1 | ref: ADR-0041.R1.N1 |
| ADR-0041.R1.N2 | ref: ADR-0041.R1.N2 |
| ADR-0041.R12 | ref: ADR-0041.R12 |
| ADR-0041.R12.N1 | ref: ADR-0041.R12.N1 |
| ADR-0041.R15 | R255-R258 |
| ADR-0041.R15.N1 | R253, R258 |
| ADR-0044.R10 | R266 |
| ADR-0044.R10.N1 | R266 |
| ADR-0047.R16 | ref: ADR-0047.R16 |
| ADR-0047.R16.N1 | ref: ADR-0047.R16.N1 |
| ADR-0048.R3 | ref: ADR-0048.R3 |
| ADR-0048.R3.N1 | ref: ADR-0048.R3.N1 |
| ADR-0048.R3.N2 | ref: ADR-0048.R3.N2 |
| ADR-0048.R11 | ref: ADR-0048.R11 |
| ADR-0048.R12.N1 | ref: ADR-0048.R12.N1 |
| ADR-0048.R15 | R259-R261 |
| ADR-0048.R15.N1 | R259 |
| ADR-0048.R15.N2 | R261 |
| ADR-0048.R18 | R222, R253-R255 |
| ADR-0049.R1 | ref: ADR-0049.R1 |
| ADR-0049.R5 | ref: ADR-0049.R5 |
