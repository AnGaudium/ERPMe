# ADR-0002: Core technology tools

Status: accepted (2026-11-14). Design item: —. Related decisions: D14. The sentence on choosing the primary key for partitioning by fiscal year, and the revisit line "partition by fiscal year", are replaced by [ADR-0006](0006-id-and-numeric-model.md) rules 22–23.

## Decision

Use popular, mature tools; let PostgreSQL do everything it can; write only what makes the product.

## Context

One developer, most code written by AI. Popular libraries help AI write correct code; every dependency is maintenance, so choose few.

**Backend:**

| Need | Choice | Why |
| --- | --- | --- |
| Environment, lint, types | uv, ruff, pyright strict | Fast, one tool per job |
| Command schemas | pydantic v2 | Single source for JSON Schema, REST, MCP, TypeScript types |
| REST | FastAPI | OpenAPI generated from pydantic |
| MCP | Official MCP Python SDK | Tools generated from the same command registry |
| DB access | SQLAlchemy 2 Core, psycopg 3, Alembic | Full control of transactions and row locks |
| Money | Decimal in Python, NUMERIC in PostgreSQL | No floats, no money stored as strings |
| Technical queue, outbox | Procrastinate (queue running on PostgreSQL) | No Redis or RabbitMQ |
| Ledger protection at the data layer | Triggers blocking edits and deletes of posted documents and posting into locked periods; RLS | Second line of defense |
| Deterministic fuzzy matching | pg\_trgm, rapidfuzz | Duplicates, item mapping, bank matching without an LLM |
| Document printing | Jinja2 → HTML → PDF with WeasyPrint | Print templates are configurable HTML/CSS |
| E-invoice and tax return XML | lxml, xmlschema | Validate against XSD before sending |
| Excel | XlsxWriter to write, openpyxl to read |  |
| Authentication | argon2, pyotp, Authlib (OIDC) | No separate identity server to operate |
| LLM | Anthropic SDK behind a thin self-written gateway interface | Workflows are code-orchestrated, so no agent framework is needed |
| Logging, observability | structlog, OpenTelemetry |  |

Note (author's delegation, 2026-11-19): Procrastinate is dropped (OPT-08, [ADR-0031](0031-design-simplifications.md) rule 15 note). System jobs, scheduled jobs and the PDF worker run on the outbox workers and queues of ADR-0013 and ADR-0022 rule 12. A spike at step 0 confirms it; if the spike needs more than one small module, Procrastinate stays.

Note ([ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), proposed 2026-11-19): AG Grid Community leaves the stack (the tool choice delegated by the author, 2026-11-19). Line entry uses `line_grid`, an editable grid component on TanStack Table written in the repository, keyboard first, with barcode-capable cells and within the 150 KB route budget. AG Grid comes back only through an ADR, if a measured need appears; performance rule 3's AG Grid lines no longer apply.

Note ([ADR-0061](0061-barcodes.md), proposed 2026-11-15): the PDF worker draws barcodes as SVG with Zint's command-line program (GS1 mode, SVG to standard output), run in the worker's sandbox, so no Python binding is needed; libzint is BSD-3-Clause and the command-line program GPL-3.0, both compatible with the core's AGPL-3.0 (spec 18), to verify at build. GS1 data is parsed and built by the core's own `nativeflows.gs1`, whose Application Identifier table is generated from the GS1 Barcode Syntax Dictionary (rules 1, 21).

**Testing:** pytest on real PostgreSQL via testcontainers, never SQLite; Hypothesis stateful testing generates random business sequences and checks invariants after each step; golden scenarios read from hand-built spreadsheets; concurrency tests for stock posting.

**Frontend:**

| Need | Choice |
| --- | --- |
| Base | React, TypeScript, Vite |
| API types and client | Generated from OpenAPI with openapi-typescript |
| Data, routing | TanStack Query, TanStack Router |
| Components | shadcn/ui |
| Fast keyboard data-entry grid | AG Grid Community (MIT) |
| Forms | A thin self-written form builder on react-hook-form, reading the command's JSON Schema plus UI metadata |
| i18n | i18next; community translations via Weblate |
| Warehouse app | Same app as a PWA; scanning with the browser BarcodeDetector API, fallback @zxing/browser |

Note ([ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), 2026-11-21): the data grid is the in-repo TanStack Table grid, not AG Grid (ADR-0077 rules 5, 20).

Note ([ADR-0061](0061-barcodes.md), proposed 2026-11-15): the fallback is a WebAssembly decoder based on ZXing-C++ (Apache-2.0), which reports the symbology identifier and FNC1; it reads Code 128, GS1-128, DataMatrix and QR, while BarcodeDetector reads only EAN/UPC and ITF until a device proves it passes GS through. The PWA also runs the GS1 Syntax Engine (Apache-2.0) in WebAssembly for instant feedback; both load on first use. Apache-2.0 code may be used in the AGPL-3.0 core (spec 18) (rules 1, 22).

**Infrastructure and docs:** Docker Compose, Caddy, pgBackRest, GitHub Actions; MkDocs Material; the repo has CLAUDE.md and coding-agent skills from the start.

**Performance and resources:**

1. **PDF generation always runs in its own queue**, never in the web process, because WeasyPrint is heavy on RAM and CPU. The PDF worker is a separate process with limited concurrency, restarted periodically to release memory. PDFs of posted documents are stored by hash of document version and template version: posted documents are immutable, so each is generated once. The UI receives PDFs asynchronously.

   Note: the key also covers the document's state and e-invoice state, the print data contract version, the language and the marker, and a file is reused only for documents in a final state ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 28).
2. **Dead tuples are handled per table type**, not with one strategy for all:
   - The journal and material documents are append-only and produce almost no dead tuples. Not partitioned in Phase 1, but the primary key is chosen so the tables can later be partitioned by fiscal year without restructuring.
   - Fast-cycling tables (outbox, technical queue, agent run logs) are partitioned by month; when retention expires, drop the whole partition instead of deleting rows. Accounting and audit data are never deleted this way.
   - Continuously updated rows (stock balance per item and warehouse, document number counters): fillfactor below default and no indexes on changing columns, so PostgreSQL updates in place.
   - Autovacuum tuned per hot table, with lower thresholds than default.
   - Block long-running transactions, which stop vacuum from cleaning: time limits on agents' read-only queries and on idle-in-transaction sessions.
   - Monitor dead tuples and autovacuum lag on the operations dashboard.
3. **The frontend is split by screen** with Vite dynamic imports. AG Grid loads only on desktop data-entry screens, and only the AG Grid modules in use are registered. The phone warehouse app never loads AG Grid. On desktop, AG Grid is prefetched when the browser is idle after login so the first open does not wait.

Note ([ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), 2026-11-21): the data grid is the in-repo TanStack Table grid, not AG Grid (ADR-0077 rules 5, 20).

**Deliberately not used:** heavy ORMs, event sourcing, microservices, GraphQL, Kafka, Redis, Elasticsearch, agent frameworks such as LangChain, a separate workflow engine.

**Self-written:** command registry and dispatcher (generating REST, MCP, forms, running simulation); universal journal and posting logic; cross-checked account determination; inventory and costing engine; policy table; localization package loader; form builder.

## Revisit when

- Procrastinate does not meet measured throughput: consider a dedicated queue.
- The journal grows to where reports are measurably slow: partition by fiscal year.
- WeasyPrint cannot render complex print templates: consider headless Chromium in the PDF worker.

## Documents updated

- [docs/decisions.md](../decisions.md): D14.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): rule 5 (small technical decisions).
- [docs/open-questions.md](../open-questions.md): command schema tooling.
