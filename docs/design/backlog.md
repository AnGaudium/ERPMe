# Design backlog

Forty design items, in the order they are needed. Items DS-01 to DS-18 must be decided before the first line of code (Build step 0); every other item must be finished before the step listed in "Needed by". Each item produces a file in the repo: an ADR in `docs/adr/` for decisions, a specification in `docs/design/` for models and algorithms, or a catalog file for data such as account and movement-type lists. A design item is done when its file exists, it cites the decided items it depends on, and its open points are listed as open questions.

## Before the first line of code (step 0)

| ID | Design item | Output | Depends on | Needed by |
| --- | --- | --- | --- | --- |
| DS-01 | Glossary and naming conventions: tables, columns, commands (verb + noun), events, modules | ADR, glossary file | — | Step 0 |
| DS-02 | ID and numeric model: ID strategy; precision of quantity, unit price, company and foreign currency; rounding rules | ADR | DS-01 | Step 0 |
| DS-03 | Time model: document date, posting date, recording timestamp, time zones, fiscal calendar | ADR | DS-01 | Step 0 |
| DS-04 | Command envelope and registry: schema conventions, `actor`/`on_behalf_of`, idempotency key and retention, `plan_hash` via run-and-rollback, schema versioning, error model | ADR, spec | DS-01–03 | Step 0 |
| DS-05 | Document lifecycle: states, draft versioning, approval bound to version hash, reversal semantics, gapless numbering series | ADR | DS-04 | Step 0 |
| DS-06 | Universal journal data model: entry and line columns, dimensions, multi-currency amounts, link to material documents, DB triggers protecting posted rows | ADR, DDL draft | DS-02, 03, 07 | Step 0 |
| DS-07 | System chart of accounts: catalog of system accounts with type and meaning; mapping rules 1–7; validation | Catalog file, ADR | DS-01 | Step 0 |
| DS-08 | Account determination: transaction key catalog, valuation classes, valuation area, cross-check rule | Catalog file, spec | DS-07 | Step 0 |
| DS-09 | Inventory and costing model: material documents, movement type catalog, price control, preliminary price, negative-stock rule, backdating and recalculation; the period-end actual costing algorithm across warehouses and BOM levels | ADR now; algorithm spec | DS-06, 08 | ADR step 0; algorithm step 3 |
| DS-10 | Multi-currency: currency types per line, rate types, rate source, realized and unrealized FX, open-item revaluation, localization hooks | ADR | DS-06 | ADR step 0; logic steps 6 and 8 |
| DS-11 | Landed cost: customs declaration, allocation methods, split between stock and COGS, link to GR/IR | ADR, spec | DS-09, 10 | ADR step 0; logic step 3 |
| DS-12 | Posting periods and closing: states, per account type, special periods, close-checklist framework, closing entries | ADR | DS-03, 05 | Step 0 |
| DS-13 | Outbox and events: event schema and naming, delivery guarantees, technical queue usage | ADR | DS-04 | Step 0 |
| DS-14 | Localization package structure: manifest, components, loader, versioning, CI checks, terminology and i18n | ADR, spec | DS-07, 08 | Step 0 |
| DS-15 | Permission model: roles, record and field rules, RLS policies, agent permission intersection, segregation of duties | ADR | DS-04 | Envelope step 0; full step 5 |
| DS-16 | Invariant catalog and test harness: named invariants (INV-xx), Hypothesis state machine, golden scenario file format, naive recomputation, reference comparison report | Spec, harness | DS-06, 09 | Step 0 |
| DS-17 | Synthetic dataset: business simulator design (fictional companies, seeded, day-by-day calls to public commands, generated input files), edge-case catalog EC-xx with coverage report, three dataset sizes; Odoo demo data used only as a checklist. Version 1 at step 0, extended at every step | Spec | — | Step 0 |
| DS-18 | Repo and engineering conventions: monorepo layout, import-linter contracts, CLAUDE.md and coding-agent skills, ADR template, CI pipeline, test server | ADR, repo skeleton | DS-01 | Step 0 |

## Before the step that needs it

| ID | Design item | Output | Depends on | Needed by |
| --- | --- | --- | --- | --- |
| DS-19 | Vietnam package, TT99: operational chart template with mapping, default account determination, tax codes, FX rules (after legal verification) | Package spec, catalog files | DS-07, 08, 14 | Step 1 |
| DS-20 | Master data model: partner and roles, contacts, item (UoM group, valuation class, lot and serial flags), warehouses and bins, price lists | Spec, DDL draft | DS-06 | Step 2 |
| DS-21 | Import batch format for data migration: mapping external data to commands, opening balances in several currencies | Spec | DS-04, 20 | Step 4 |
| DS-22 | Commercial documents: sales and purchase flows, state machines, partial fulfillment, returns, discounts and promotions, credit limit, three-way match tolerances, GR/IR and price-difference postings | Spec | DS-05, 09, 11 | Step 5 |
| DS-23 | Tax engine: tax codes, date-effective rates, tax determination, line versus document rounding, VAT return mapping | Spec | DS-14 | Data model step 2; logic step 7 |
| DS-24 | E-invoice adapter interface, BKAV adapter, incoming invoice intake | Spec | DS-23 | Step 7 |
| DS-25 | Cash, bank and AR/AP: open items, matching and netting, payment allocation, advances, bank statement formats | Spec | DS-06, 10 | Step 6 |
| DS-26 | Statutory reporting framework: report definition format inside localization packages (B01, B02, B03, books), report engine | Spec | DS-14 | Step 8 |
| DS-27 | Print template data contracts and PDF worker | Spec | DS-22 | Step 8 |
| DS-28 | Policy table and one-level approval: action types, thresholds, binding to document version | Spec | DS-05, 15 | Step 5 |
| DS-29 | Work queue model: work items, ownership, locking, due dates | Spec | DS-13 | Step 5 |
| DS-30 | UI architecture: schema-driven renderer, UI metadata format, navigation, i18n, keyboard model; UX spec for the 6 hand-built entry screens | Spec, UX spec | DS-04 | Renderer step 1; screens step 9 |
| DS-31 | Warehouse PWA: receipt, issue, transfer and count flows; barcode per packaging unit | UX spec | DS-09, 30 | Step 9 |
| DS-32 | Agent runtime: LLM gateway interface, single-provider seat config, data labels and routing switch, run records, budgets, untrusted-content tainting, fixed tool lists, replay evaluation harness | ADR, spec | DS-15 | First agent (after step 4) |
| DS-33 | Read-only query layer: semantic views, read-only role, time limits, MCP resources | Spec | DS-06, 15 | First agent (after step 4) |
| DS-34 | Workflow designs, one per agent: deterministic cascade, inputs and outputs, policy thresholds, shadow-mode metrics. Data migration, quotation, bank matching, purchase invoices | Spec per workflow | DS-32, 33 | After steps 4, 5, 6, 7 respectively |
| DS-35 | Minimal CRM: interaction timeline, email intake | Spec | DS-20 | Step 5 |
| DS-36 | Audit log and observability: audit record model, OpenTelemetry, operations dashboard (dead tuples, queue lag) | Spec | DS-13 | Audit step 1; dashboard step 10 |
| DS-37 | Deployment and operations: Docker Compose, backup and restore, upgrade and migration policy, LTS | Spec | DS-18 | Step 10 |
| DS-38 | Localization skill for AI agents, and the basic US package built with it | Skill file, package | DS-14, 19 | Step 10 |
| DS-39 | TT133 package | Package | DS-19 | Step 10 |
| DS-40 | Go-live kit: cut-over checklist, rehearsal procedure, schema freeze; reader for the pilot's current system if missing (e.g. MISA) | Spec | DS-21 | Step 11 |
