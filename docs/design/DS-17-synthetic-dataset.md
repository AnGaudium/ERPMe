# DS-17: Synthetic dataset and edge-case catalog

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Kind: specification and catalog. Version 0.1.0 at step 0, extended at every step; the simulator code is step 0 work package 8. Related decisions: D14, D16. Build principles B4, B5. ADR-0002, ADR-0003 (R1, R6, R10), ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0012, ADR-0016, ADR-0020, ADR-0021, DS-16. Spec [12-testing.md](../spec/12-testing.md#synthetic-dataset); runbook [testing-operations.md](../runbook/testing-operations.md#running-the-simulator).

Note: a fictional Vietnamese manufacturing company profile (`vn_manufacturing_*`) is added with the production design, due at the production core step gate ([ADR-0032](../adr/0032-phase-1-scope-with-production.md) rule 6). Production edge cases reserved by [ADR-0033](../adr/0033-production-master-data.md) rule 16 are coded when the step is numbered.

The simulator runs fictional companies day by day. It writes what happened in business terms, as a versioned business-event log, together with the files agents read. Per-step adapters turn business events into the commands that exist at each step. The log never holds expected balances, and the simulator decides no accounting rule.

## 1. Packages

| Package | Holds | May import |
| --- | --- | --- |
| `erpme_events` | Business-event log schema (pydantic models, JSON Schema export), canonical writer and reader | standard library, pydantic |
| `erpme_simulator` | Profiles, generators, random helpers, edge-case injectors, input file writers, log coverage | `erpme_events` |
| `erpme_adapters` | One adapter module per build step (`step_1`, `step_3` …): business event → commands | `erpme_events`, `erpme_client` (DS-16 section 1) |

1. The simulator imports no core code and never touches the database (a contract DS-18 enforces). It cannot see what the core computed. The replay runner, not the simulator, sets `business_date_override` per company for each `sim_date` (ADR-0007 rule 15; DS-16 rule 19).
2. One schema serves the simulator, the adapters, DS-16's state machines and scenario files, and the test-scenario model's proposals (rule 21 below). It is published as `docs/catalogs/business-events.schema.json` (generated, CI diff). A small example log `docs/catalogs/business-events.example.jsonl` (generated from the small profile's first week, CI diff) gives the recomputation writer a fixture inside `docs/` (DS-16 rule 3).

## 2. Business events

3. A **business event** is a fact of the business written by the simulator: something that happened, such as `goods_received`. A core event is different: it is something the core posted, such as `GoodsReceiptPosted` (ADR-0004 rule 22; ADR-0013). Business event types are snake_case enumerated values (ADR-0004 rule 14), in the past tense, and are never outbox events.
4. Every business event has these fields:

   | Field | Content |
   | --- | --- |
   | `ref` | Unique within its log or scenario, e.g. `E000123`. Used by `refs`, `expected.csv`'s `document_ref` and idempotency keys (DS-16 rules 16, 24) |
   | `sequence` | Integer, gap-free in a log; it alone orders events |
   | `sim_date` | The date the event happens |
   | `local_time` | Display only |
   | `company` | Business code |
   | `type` | The business event type |
   | `actor` | A fictional user and role, or `agent:<workflow>` |
   | `on_behalf_of` | For agent actors, the accountable fictional human |
   | `payload` | Rule 6 |
   | `refs` | `ref`s of earlier events this one follows from |
   | `outcome` | `must_succeed`, `must_reject` with a code, or `may_reject` with codes, set from the simulator's own state (DS-16 rule 14) |
   | `retry` | True when the event is to be sent twice with the same idempotency key |
   | `edge_cases` | EC codes injected here |
   | `input_files` | Paths relative to the run directory |
   | `concurrency_group` | Optional. A hint used only by parallel test PAR-01; sequential replays ignore it |

   A log file starts with a header line (rule 13); `scenario.yaml` `events` have no header.
5. Business event types in log schema 0.3.0 (0.2.0 added the ADR-0028 events; 0.3.0 adds the ADR-0029 events), with the first step at which each is executable:

   | Area | Types | First step |
   | --- | --- | --- |
   | Setup | `company_founded`, `exchange_rate_published` | 1 |
   | Setup | `partner_registered`, `product_registered`, `warehouse_opened`, `price_list_published` (`SetPriceListEntries`, [ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 7) | 2 |
   | Setup | `partner_account_changed` (a partner's reconciliation account changes) | 5 |
   | Periods | `period_restricted`, `period_locked` (by a human, with area; ADR-0012 rule 7) | 1 |
   | Periods | `period_closed`, `year_closed` | 8 |
   | Journal | `journal_recorded`: balanced test entries for transactions without a document, and accountants' manual entries | 1 |
   | Journal | `document_reversed` | 1 |
   | Stock | `goods_received`, `goods_delivered`, `goods_returned_to_supplier`, `goods_returned_by_customer` (stock side), `stock_transferred`, `stock_dispatched`, `stock_arrived`, `stock_counted`, `goods_consumed`, `goods_scrapped` | 3 |
   | Landed cost | `landed_cost_allocated` (an accountant allocates a cost source to receipts) | 3 |
   | Planning | `replenishment_planned` (a planner runs planning and converts), `forecast_adjusted`, `sales_history_recorded` (history imported before the calendar) | 5 |
   | Landed cost | `purchase_cost_invoice_received`: as a cost-source journal (rule 10) from step 3; as the purchase cost invoice from step 5 | 3 |
   | Opening | `opening_balances_recorded` (DS-21) | 4 |
   | Purchasing | `purchase_requested`, `purchase_ordered`, `purchase_invoice_received`, `customs_declared` | 5 |
   | Sales | `quotation_requested` (e-mail), `sales_ordered`, `sales_order_changed`, `sales_invoice_issued` (with installments from the payment term), `credit_note_issued` | 5 |
   | Cash | `payment_received`, `payment_made`, `bank_statement_received`, `netting_agreed`, `advance_paid`, `auto_post_confirmed` (the rule owner confirms auto-posts) | 6 |
   | Safety | `bank_account_change_requested` (an e-mail asks to change a partner's bank account) | 5 |
   | Tax | `tax_rate_changed`, `invoice_replaced`, `invoice_adjusted` | 7 |
   | E-invoice (stub adapter from step 5, ADR-0028 rule 12) | `e_invoice_rejected`, `e_invoice_outage` | 5 |

   A new type or optional field raises the schema's minor version; a change of meaning raises its major version and needs a migration note. Readers accept older minor versions of the same major version.
6. Payloads carry every business fact a recomputation needs, so results can be computed from the log alone (DS-16 rule 29):
   - All codes are business codes, all amounts and quantities canonical decimal strings (ADR-0006 rule 13), and there are no UUIDs.
   - Required for every type:
     - posting types: `document_date` and `posting_date` (ADR-0007 rule 8);
     - lines with an amount: `currency`;
     - foreign currency: `rate` with its quote kind and rate type (ADR-0011).

   For the types executable at steps 1–4:

   | Type | Payload |
   | --- | --- |
   | `company_founded` | Company code, localization package and regime, company currency, costing policy (`valuation_area_level`), fiscal year start |
   | `exchange_rate_published` | Source, rate type, currency pair, quote kind, rate, date |
   | `period_restricted`, `period_locked` | Period, area |
   | `journal_recorded` | Lines: operational account code, side, transaction amount, currency, rate, dimensions (item, warehouse, partner); the accounts are the profile's test accounts (rule 11) |
   | `document_reversed` | `ref` of the reversed event, posting date |
   | `partner_registered` | Code, kind, roles, payment terms, credit limit, tax ID (rule 19) |
   | `product_registered` | Code, kind, tracking, inventory unit, purchase and sales units with factors, valuation class, gross weight |
   | `warehouse_opened` | Code, kind, `valuation_warehouse` for transit and goods-sent kinds |
   | Stock types | Item, warehouse(s), quantity in the inventory unit, lot or serial, unit price for receipts, the movement's business reason |
   | `landed_cost_allocated` | `ref` of the cost source, target receipt `ref`s, allocation method, manual amounts |
   | `opening_balances_recorded` | Account balances per currency at book company amounts; open items per old invoice; stock per item, warehouse, bin, lot or serial with one unit value per item and valuation area; year-to-date turnover at a mid-year cut-over ([ADR-0044](../adr/0044-data-migration-and-export.md) rules 7–10) |

   Later types get their table when their step's adapter is designed (B4).

## 3. Adapters and executable steps

7. The adapter of step N maps each business event type whose first step is at most N to commands, mechanically. Every other type is `not_executable_at_step`. Adapters of earlier steps are kept, so any log can be replayed at any step.
8. Steps 1–2: only journal-level, period, rate and master-data events are executable. `journal_recorded` maps line by line to the journal command, with no account choice. The mapping is documented in `docs/design/DS-17-step-1-projection.md` (written at step 1, inside `docs/` so the recomputation writer can read it). Commercial and stock events wait for their steps. This matches step 1 work package 8 and its verification, "journal-level events" ([steps-0-4.md](../runbook/steps-0-4.md)).
9. Steps 3–4: stock events map to material documents through their movement types (ADR-0020), and the core determines every account. Commercial events stay `not_executable_at_step` until step 5, except rule 10.
10. Cost sources for landed cost at steps 3–4:
    - The adapter maps `purchase_cost_invoice_received` to a general journal entry with two lines:
      - a debit to an account mapped to `purchase_cost_clearing`, which ADR-0021 rule 2 requires;
      - a credit to the profile's test offset account (rule 11).
    - That mapping is the only account-bearing part of an adapter. It is documented in the same projection document and replaced by the purchase cost invoice at step 5.
11. Accounts in `journal_recorded` and the test offset account are test data drawn from the profile: balanced, arbitrary, and not rules of the product. Two things stay with the author:
    - Any wider projection, such as projecting goods receipts or invoices into journal entries before their steps, is excluded. If one is ever proposed, it goes to the author (ADR-0005 items 1, 3).
    - The projection document is a `reserved-review` path (DS-16 rule 6): agents may write it, and the author reviews it line by line.
12. An adapter never decides accounting. The replay runner records each command's outcome and error code in `outcomes.jsonl`. Whether the outcome was right is judged by the business event's `outcome` class (INV-19), which generators and injectors set.

## 4. Run identity, determinism and the run directory

13. A run is identified by the triple (simulator version, seed, dataset version). The dataset version names a profile and its version, e.g. `vn_trading_small@1`. The log's header line holds exactly:
    - the schema version;
    - the triple;
    - the profile parameters;
    - the localization package code and version;
    - the catalog versions it reads;
    - the companies.

    Nothing outside the triple and these versions enters the log, so the same triple and versions yield byte-identical output. Any change of output requires a new simulator version: CI fails when a lock hash changes without a change of the triple or of a recorded version.
14. The run directory holds:

    | File | Written by |
    | --- | --- |
    | `events.jsonl` | Simulator |
    | `inputs/` | Simulator |
    | `regime_snapshot.json` | Harness (DS-16 rule 3) |
    | `outcomes.jsonl` | Replay runner (harness), per command, with the actual outcome of `may_reject` events that the recomputation reads (DS-16 rule 14) |
    | `run.json` | Harness: generator commit, timings, machine; excluded from every hash |

15. Randomness:
    - Each stream's generator is `random.Random(int.from_bytes(sha256(f"{seed}|{company}|{stream}".encode("utf-8")).digest()[:8], "big"))`, with streams such as `sales.orders` and `edge.EC-07`; company and stream codes never contain `|`.
    - Draws use only `getrandbits` through the simulator's own helpers (integer ranges by rejection sampling, Fisher-Yates shuffle, weighted choice with integer weights). The library's `choice`, `shuffle`, `sample`, `randrange`, `gauss` and floats are not used, because their results are not guaranteed across Python versions or platforms.
    - Rates, seasonal factors and prices are `Fraction` or `Decimal`, rounded by `erpme.numeric`'s published rules, re-implemented in `erpme_events`.

    Adding a stream leaves other streams' draws unchanged. Injectors that change shared state can still change what later generators see.
16. Output canonical form:
    - JSON with keys in schema field order, separators `,` and `:`, `ensure_ascii=False`, text in Unicode NFC, LF line endings, written by `erpme_events`' own writer, not by pydantic's dump.
    - `.eml` files with fixed MIME boundaries, `Message-ID` and `Date` derived from the event.
    - XML in canonical form (C14N 2.0).

    The input tree hash is the SHA-256 of a sorted manifest of `path<TAB>sha256` lines.
17. The CI determinism test generates the small dataset twice, in separate processes with different `PYTHONHASHSEED`, and compares the results with each other and with the lock. The same two runs feed the replay. The nightly run regenerates the small and medium datasets on the test server and compares them with their locks, which checks determinism across platforms. Python's minor version is recorded in the lock.

## 5. Profiles and sizes

18. A profile is a versioned YAML file in `erpme_simulator/profiles/`. It holds:
    - the calendar (start, end, pinned year);
    - the companies with package, regime, costing policy, and test accounts and test offset account (rule 11);
    - master data counts;
    - daily rates per flow, with weekday and seasonal factors as fractions;
    - payment term mix;
    - currency mix;
    - edge-case frequencies overriding the catalog's defaults.

    Edge cases are injected by frequency, then topped up deterministically, at the last feasible date of their stream's calendar, until `min_small` is reached; CI checks `min_small`.

    | Profile | Content | Used in |
    | --- | --- | --- |
    | `vn_trading_small@1` | One fictional Vietnamese trading company (TT99, VND, warehouse-level valuation, three physical warehouses and one transit warehouse, USD imports). Calendar 1 November 2027 to 15 February 2028: three months of operation, three month-end closes, a year-end close and a mid-month test tax-rate change inside. A few hundred documents. Every EC at least `min_small` times | CI |
    | `vn_trading_medium@1` | Same company, 12 months, about 10,000 documents | Nightly; step 4 gate |
    | `multi_company_large@1` | Defined at step 10 (adds the US company) | Load tests; step 10 gate |

19. All generated data is fictional:
    - Names, addresses, e-mails, phone numbers, bank account numbers, invoice and customs numbers, and third parties (banks, carriers, customs offices) are generated from word lists the project writes itself and licenses CC0. E-mail domains use `example.com`-style reserved domains.
    - Tax IDs use the official format with a valid check digit and a fixed prefix intended to be unassigned. A CI test checks that every generated ID carries the prefix. Whether the prefix is truly unassigned, and which phone ranges are safe, is a real-data fact the author confirms (open question).
    - Odoo demo data is used only as a checklist of record kinds (`erpme_simulator/checklist.md`), with nothing copied.

## 6. Input files

20. Under `inputs/` the simulator writes the files agents read:
    - e-invoice XML (DS-24 fixes the schema version; until then a placeholder with the same fields);
    - bank statements (DS-25 formats; a generic CSV in version 0.1.0);
    - `.eml` e-mails for quotation requests and supplier documents;
    - migration files for DS-21 at step 4.

    Each file is named by its business event's `input_files`.

## 7. Edge-case catalog

21. The test-scenario model (an LLM, test server only, budget ADR-0003 R6) proposes extra situations as DS-16 `proposed` scenarios: business events with the outcome classes it expects, and no expected values. These are judged like any other run. A proposal that finds a defect becomes a regression scenario (DS-16 rule 25). A recurring kind becomes a catalog row by an ordinary change.
22. The catalog is [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv), version 0.1.0, owned by DS-17. Its columns:

    | Column | Content |
    | --- | --- |
    | `code` | `EC-nn`, never reused |
    | `name` | |
    | `area` | |
    | `first_executable_step` | ADR-0003 R1 |
    | `business_event_types` | A `;` list validated against the schema; `*` for any |
    | `frequency_value`, `frequency_basis` | `per_month`, `per_quarter`, `per_year`, `per_dataset`, `per_period_close`, `percent_of_events`, `percent_of_postings`, `percent_of_lines`, `percent_of_orders`, `percent_of_tracked_item_movements` |
    | `min_small` | |
    | `expected_outcome` | `must_succeed`, `must_reject:<code>`, `may_reject:<codes>`, several joined by `\|` when they depend on the actor, or `undecided:<DS-xx>` |
    | `source` | |
    | `added_in` | |
    | `description` | |

    Version 0.1.0 has 71 edge cases (EC-46 to EC-52 for open items, ADR-0026; EC-65 and EC-66 for tax, ADR-0041; EC-67 and EC-68 for imports, ADR-0030 and ADR-0044; EC-69 to EC-71 for commercial documents, ADR-0047; EC-53 to EC-55, EC-59, EC-60 for the document lifecycle, ADR-0028; EC-56 to EC-58 for agent safety, ADR-0029; EC-61 to EC-64 for commercial seams, ADR-0030), EC-32 to EC-40 for warehouse management (ADR-0023) and EC-41 to EC-45 for planning (ADR-0024):
    - 23 from [12-testing.md](../spec/12-testing.md#synthetic-dataset), counting landed cost after partial sale and after period lock separately;
    - eight that ADRs require: foreign-currency journal, reversal of an internal document, transfer through transit, preliminary price missing, degenerate costing, one cost source over several receipts, cost before receipt, import VAT on customs.

    Outcomes of EC-20, EC-21, EC-22 and EC-63 are business behavior the spec does not state (ADR-0005 item 11). ADR-0047 gives them interim, flagged outcomes (rules 18, 20, 22); the author confirms them before their first executable step.
23. Each edge case has one injector in `erpme_simulator/edge_cases/`, registered by code. A CI test compares catalog and registry (as DS-16 rule 5 does for invariants) and validates `business_event_types` against the schema. Injectors add or modify events only through the generators, and never write anything a real business could not produce.
24. EC-26 changes a fictional, date-effective test tax code in a test setting. It is not a claim about any law; DS-23 provides such test codes.

## 8. Coverage report

25. For each EC, per run, the coverage report shows:
    - the target and the count in the log;
    - the count executed at or after `first_executable_step`;
    - whether every execution passed: its outcome class held and no check failed.

    "Covered in the log" is the step 0 gate view (ADR-0003 R1). "Exercised" is the step 4 view for steps 1–3 and the step 10 view for all steps ([testing-operations.md](../runbook/testing-operations.md#coverage-reports)). The runbook's step 0 fallback (ship only step 1 events) does not lift R1: the small log still covers every EC.

## 9. Storage, locks and budget

26. Logs and input files are not committed; they are reproducible from the triple and versions.
    - `datasets/<profile>.lock` commits the triple, package and catalog versions, Python minor version, the log's SHA-256 and the input tree hash.
    - When a lock changes, CI attaches a summary diff (counts per business event type and per EC) to the pull request, so the change can be reviewed.
    - Medium and large locks are verified by the nightly run.
    - The test server caches runs by triple and never edits one in place.
    - The dataset licence is CC0 ([18-license-governance.md](../spec/18-license-governance.md)).
27. Budget: generating the small dataset twice and comparing it with its lock takes 30 seconds or less, within the `dataset` CI job ([ADR-0022](../adr/0022-repository-and-engineering-conventions.md) rule 16).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| JSON Lines log (chosen) | Streamable, diffable, one event per line; agents read it directly | Larger than binary |
| Parquet or a database dump | Compact | Not reviewable; ties the log to tools |
| Lock file with hashes (chosen) | Small repository; regenerated and verified | Needs a determinism discipline |
| Committed logs | Visible | Megabytes per change; diffs are noise |
| Journal-only adapter at steps 1–2 (chosen) | No accounting logic in test code | Commercial events wait for their steps |
| Projecting all events to journal entries at step 1 | More coverage early | An agent would decide accounting rules (ADR-0005) |
| Scenario-local `ref` (chosen) | Works for logs, scenarios and proposals alike | A second identifier beside `sequence` |
| UUID event IDs from the triple | Globally unique | Hand-written scenarios have no triple |

## Open points

Questions for the author:
- Outcomes of EC-20 (return of partly invoiced goods), EC-21 (credit limit exceeded) and EC-22 (price below cost): interim, flagged outcomes in ADR-0047 rules 18, 20 and 22; the author confirms them before step 5.
- Is the tax ID prefix the simulator uses unassigned, and which phone number range is safe for fictional data?

Requirements this item places on others:
- DS-16 and the testkit: the replay runner sets `business_date_override` and writes `outcomes.jsonl`, `regime_snapshot.json` and `run.json`; parallel test PAR-01 uses `concurrency_group`.
- DS-18:
  - packages and import contracts;
  - `docs/design/DS-17-step-1-projection.md` among the `reserved-review` paths;
  - `datasets/`;
  - the CI determinism, lock and summary-diff checks;
  - the simulator-version-bump check;
  - the test server cache;
  - external lookups and gateways disabled when `environment` is `test` or `simulation`.
- DS-21: the opening balances payload. DS-23: date-effective test tax codes. DS-24: the e-invoice schema; disabled gateways in test environments. DS-25: bank statement formats.

## Documents updated

- [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv): new, version 0.1.0.
- [docs/catalogs/README.md](../catalogs/README.md): edge cases row.
- [docs/design/backlog.md](backlog.md): DS-17 row links here.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for edge case, business event and business event type, business-event log, simulator triple, adapter, profile.
- [docs/open-questions.md](../open-questions.md): the two questions above.
- [docs/runbook/testing-operations.md](../runbook/testing-operations.md): "where generated logs are stored" points here.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
