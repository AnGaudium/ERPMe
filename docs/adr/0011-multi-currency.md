# ADR-0011: Multi-currency

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Design item: DS-10 (ADR part; logic in steps 6 and 8). Related decisions: D5, D7, D10. Principles 2, 6, 13. ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010.

## Decision

Every journal line carries three currency types: transaction currency, company currency and, when the installation sets one, group currency. Each conversion a line uses is recorded as an applied rate that names its quotes, so every amount can be explained. Exchange rates are stored as their source publishes them (quotes per source, currency pair, kind and date) and resolved directly, inversely or through the source's reference currency. Rate types are uses: some are looked up (transaction, revaluation, group translation), the others are carried on documents (document, invoice, customs, settlement). The accounting regime declares, with no core default, which quote and which date each lookup uses, the book rate method, and the scope, frequency, method and accounts of revaluation; carrying amounts, realized FX and revaluation are computed separately in company and group currency. Every choice that is a country's FX rule is configuration of the regime, flagged until verified (spec [07](../spec/07-shared-foundation.md#multi-currency)). In SAP terms, ERPMe's quote kind is SAP's exchange rate type (M, B, G), and ERPMe's rate type is SAP's assignment of an exchange rate type to a use.

### Rules

**Currencies on documents and lines**

1. A foreign-currency document has one `transaction_currency` (as in SAP, one document currency; currency exchange documents are the exception, rule 4), and may carry a `document_exchange_rate` entered by the user (e.g. a rate agreed with the bank, or an approximate rate where the regime allows it, rule 12). Rates are resolved when the document is posted, not while it is a draft; a draft shows an indicative rate only.
2. Every journal line has `transaction_currency`, `transaction_amount`, `company_currency`, `company_amount` and, when the installation's `group_currency` is set, `group_currency` and `group_amount` (ADR-0004 rule 13; columns in DS-06). A line that adjusts only company or group amounts (realized FX, revaluation, rounding) has transaction amount 0 and the transaction currency of the item or account it adjusts, which keeps an account restricted to one currency consistent (ADR-0010 rule 10).
3. Each line refers to the applied rate of each conversion it used: `company_applied_rate_id` and `group_applied_rate_id`. An `applied_rate` row holds `from_currency`, `to_currency`, `rate` (ADR-0006 `ExchangeRate`), `origin` (`lookup`, `document`, `invoice`, `customs`, `settlement` or `book`), the selection date, and the quotes used (`first_exchange_rate_id`, and `second_exchange_rate_id` for a cross rate, rule 10). Many lines of one document share one applied rate. Group amounts are always converted from the transaction amount with the group translation rate. So every amount can be explained (Principle 6).
4. Every journal entry balances in each transaction currency, in company currency and in group currency (spec [05](../spec/05-accounting-inventory-core.md)). A document that exchanges one currency for another (buying USD with VND) therefore posts balancing lines in each currency through a clearing account; DS-25 defines it and adds its system account to the catalog.
5. Converting and rounding follow ADR-0006: only `convert_amount`, per line, with one rounding line per entry for differences in company or group currency.
6. `company_currency` is fixed when the company is created and never changes once it has postings. The installation's `group_currency` is set before the first posting in the installation and never changes afterwards. Inventory value is always in company currency (07); which rate values an import goods receipt is an open question (DS-09, DS-11, DS-19).

**Currencies, sources and quotes**

7. `currency` is a global table loaded from ISO 4217: `code`, `minor_unit`, `rounding_mode` (ADR-0006 rules 14, 17) and `is_active`. A company activates the currencies it uses.
8. `exchange_rate_source`: `code`, `reference_currency` (the currency the source quotes against, e.g. VND for a Vietnamese bank), `company_id` (null for a public source fetched by a job; set for a company's own manual source) and which publication of a day its fetch job stores. Each company chooses its default source; the installation sets `group_exchange_rate_source_id` and the quote kind for group translation, so every company translates to group currency with the same rates and intercompany items eliminate. Rate fetch jobs per public source are provided by localization packages. Manual rates are entered only into a company's own source (`CreateExchangeRate`, `ImportExchangeRate`), never into a public one; who may enter them is DS-15.
9. `exchange_rate` rows are quotes as published: `exchange_rate_source_id`, `from_currency`, `to_currency`, `unit` (positive integer, default 1: the rate is for `unit` units of `from_currency`, e.g. 100 JPY), `quote_kind`, `effective_date` (the publisher's business date in the source's country), `version` and `rate`, unique on (source, from, to, kind, date, version). Quote kinds are `buy_cash`, `buy_transfer`, `sell_cash`, `sell_transfer`, `average` and `central` (a central bank's reference rate); a source publishes the kinds it has. A correction is a new `version`; a quote that an applied rate refers to never changes.
10. A lookup takes, from the chosen source, the highest version of the quote with the latest `effective_date` on or before the selection date, for the required quote kind: first the pair in either direction (a reverse quote is divided by `convert_amount`, ADR-0006 rule 10), otherwise a cross rate through the source's reference currency from two quotes, both recorded on the applied rate. The applied rate's `rate` is computed once per unit of `from_currency` (dividing by `unit`, combining the two quotes of a cross rate) and rounded by `round_exchange_rate`; `convert_amount` then uses that single rate. A currency the source does not quote fails with `exchange_rate_missing`; there is no silent fallback to another source. A quote older than the rate type's `max_rate_age_days` (rule 11) also fails with `exchange_rate_missing`, which names the source, pair, kind and date and the commands that add a quote.

**Rate types**

11. Lookup rate types are `transaction` (recognizing a foreign-currency transaction), `revaluation` (period end) and `group_translation` (to group currency). For each, the configuration declares the quote kind, which may differ by the side of the foreign-currency item (debit or credit balance, as SAP's valuation does), the selection date, and `max_rate_age_days`. The regime declares them for company currency; the installation declares `group_translation`.
12. Document rate types are `document` (rule 1), `invoice` (the rate printed on a foreign-currency invoice, kept separately from the book rate), `customs` (from the customs declaration, separate from the accounting rate) and `settlement` (a payment's actual rate). They are stored on their documents (DS-11, DS-22, DS-25) and recorded as applied rates with that origin. The regime declares whether a document rate may replace the lookup rate and within what tolerance; outside it, posting fails with `document_rate_out_of_tolerance`.
13. The core has no default for any of these values: a posting that needs a value the regime has not declared fails with `regime_configuration_missing`. Interim TT99 values are flagged configuration in the Vietnam package (DS-19), e.g. selection by posting date as SAP defaults, until verified (open questions).
14. The query `GetExchangeRate` (rate type, currency pair, date, company) returns the unsaved applied rate the lookup would produce (a computed result, an exception to ADR-0004 rule 21's stored record), with its quotes and their age, so an agent can check a rate before simulating. The rate is part of the plan, so a quote added between simulation and execution gives `plan_hash_mismatch` (ADR-0008 rule 13).

**Realized FX**

15. Carrying amounts, book rates and realized FX are computed separately in company currency and in group currency. When a foreign-currency open item is settled or a foreign-currency cash or bank balance is paid out, the amount leaving the account in each currency is its carrying amount by the book rate method the regime declares per kind of item: `specific` (each open item keeps its own amounts) or `moving_average` (a running weighted average per account and currency). The settlement amount is the amount, in that currency, of the line that settles the item. The difference posts through account determination (DS-08) to the realized FX transaction keys. Backdating and negative balances under `moving_average` are DS-25. For open items: [ADR-0026](0026-open-item-core.md) rules 6–7 (specific method only, flagged).
16. Whether realized FX after a revaluation is measured from the original carrying amount or the revalued one is a separate regime setting, `realized_fx_basis` (`original` or `revalued`), flagged until verified. `revalued` is meaningful only with the `delta` method; configuration validation rejects it with `reverse_and_repost`. Logic: [ADR-0026](0026-open-item-core.md) rule 6; build step pending the author. Settlement mechanics: [ADR-0026](0026-open-item-core.md) rule 6.

**Revaluation**

17. Period-end revaluation is a system job (actor `system`, on behalf of the human who starts the close; ADR-0008 rule 2) that creates and posts revaluation documents, computed separately for company currency (regime settings) and group currency (installation settings). It can be simulated before closing (Principle 2).
18. The regime declares: per system account, whether it is revalued per open item, per balance (account and currency), or not at all (e.g. advances, which spec 07 says are non-monetary, are excluded by open item kind); how often (every period end or only at fiscal year end); the method, `reverse_and_repost` (reversed on the first day of the next period) or `delta` (only the change since the last revaluation; SAP's foreign currency valuation offers both); and the target, unrealized FX transaction keys or an equity account such as `fx_difference_equity` first.
19. A revaluation line posts to the revalued operational account itself and refers to the open item it revalues, so the open item's carrying amount and the control account stay equal (ADR-0010 rule 5); the offsetting line goes to the target. A backdated posting into a revalued open period makes that period's revaluation stale; the close reruns it (DS-12). It is an `adjusts` line ([ADR-0026](0026-open-item-core.md) rule 10).
20. Revaluation documents are internal documents (ADR-0009 rule 19); `reverse_and_repost` reverses them by system job; whether a human may reverse them is DS-12. Logic in step 8.

**Localization hooks**

21. The accounting regime supplies, as configuration with legal sources or `unverified` flags ([00-reading-guide.md](../spec/00-reading-guide.md) rule 4): rules 11–13 for company currency, 15–16 and 18. The TT99 values are verified before the step 1 gate for the FX rules and before steps 6 and 8 for realized FX and revaluation ([ADR-0003](0003-build-operating-rules.md) R10).

## Context

DS-10's ADR part is needed by DS-06 (journal columns) and DS-11 (landed cost); its logic is built in steps 6 (realized FX) and 8 (revaluation). Constraints:

- Every document and journal line stores transaction, company and optional group currency with the rate applied; FX rules are regime configuration, never hard-coded: transaction rate (approximate where allowed), book rate by moving weighted average or specific identification, revaluation rate and accounts, rate source the company's commercial bank fetched daily; balancing per currency; advances not revalued; rate types kept separate ([07](../spec/07-shared-foundation.md#multi-currency), [05](../spec/05-accounting-inventory-core.md)).
- TT99 FX rules (413, 515, 635, buy/sell versus average rate) are unverified (07, open questions). Multi-currency is in Phase 1 (D10).
- ADR-0006: rates stored as published, converted only by `convert_amount`; ADR-0007: business dates; ADR-0010: control accounts equal their open items.
- SAP practice (D5): exchange rate types as quote categories, translation date defaulting to the posting date, foreign currency valuation per debit or credit balance with reversal or delta ([SAP Learning: foreign currency valuation](https://learning.sap.com/courses/configuring-the-financial-closing-in-sap-s-4hana/managing-the-foreign-currency-valuation)).
- ADR-0005: FX rules are the author's; the mechanism is the agent's.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Quotes as published, resolved directly, inversely or through the reference currency (chosen) | Works with a bank that quotes everything against VND; keeps the published figures | Lookup logic in one place to test well |
| One rate per currency per day | Simple | Cannot serve buy/sell rules or cross rates |
| Applied rate rows (chosen) | One place per conversion names rate, origin and quotes; shared by a document's lines | One more table |
| Rate and quote id columns on each line | No join | Two conversions and cross rates need four to six columns per line |
| Group amount from company amount | Matches some practice | A second conversion path; rounding on rounding |
| Group rates chosen per company | Flexible | Intercompany items would not eliminate in group currency |
| Core defaults for selection date and revaluation scope | Fewer settings | Decides FX rules in the core, against ADR-0005 |
| Revaluation to a separate adjustment account (SAP) | Keeps the original amount on the account | Control account and open items would differ until reset; the Vietnamese practice adjusts the account itself |

## Constraints that come with the decision

- DS-04: errors `exchange_rate_missing`, `document_rate_out_of_tolerance`, `regime_configuration_missing`; query `GetExchangeRate`.
- DS-06: journal line columns (rules 2–3); balancing per transaction currency (rule 4).
- DS-08: transaction keys for realized and unrealized FX gains and losses and for rounding.
- DS-09, DS-11: rate used for import receipts and landed cost (open questions).
- DS-12: revaluation runs and reruns in the close; reversal of revaluation documents.
- DS-14, DS-19: the regime's FX configuration (rule 21); rate fetch jobs per public source.
- DS-15: permission to enter manual rates.
- DS-16: invariants for balancing per currency and for carrying amounts.
- DS-25: book rate per open item and moving average; realized FX at matching; currency exchange clearing.

## Revisit when

- A regime needs a rate that depends on the time of day, or more than one source for one company at once (e.g. to revalue items in a currency the company's bank does not quote).
- A group needs more than one group currency in one instance.

## Documents updated

- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for exchange rate source, quote kind, rate type, applied rate, rate origin, book rate method, realized FX basis, revaluation.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): three error codes.
- [docs/design/backlog.md](../design/backlog.md): DS-10 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): date that selects the transaction rate; quote kind per rate type and tolerance; book rate method; realized FX basis; revaluation frequency.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
