# ADR-001: Programming language

Status: accepted, 2026-11-12.

**Decision:** core, engines and extensions are written in strictly typed Python; the web UI and warehouse app (PWA) in TypeScript. Go or Rust only for standalone components when profiling shows the need. At most two languages, because one person operates the project.

**Context:** an ERP is heavy on business logic, not computation; the performance bottleneck is PostgreSQL. Customers and partners will use AI to write extensions through the customization pipeline, and partners come mostly from Odoo developers, who know Python. Most code is written by AI, so a safety net that catches errors before runtime is needed.

| Criterion | Python | Go | Rust |
| --- | --- | --- | --- |
| Partner skills (Odoo developers) | Existing skill | Must learn | Very few know it |
| Customers writing extensions with AI | Easiest | Good, but in-process plugins are very hard | Hard, long compile-fix loop |
| Static types to catch AI-written errors | Yes, with mandatory pyright strict and pydantic | Good | Best |
| Money (Decimal) | In the standard library | External library | External library |
| AI and data ecosystem | Strongest | Medium | Weaker |
| Performance for SMEs | Sufficient | More than needed | More than needed |
| Self-hosted deployment | Docker image | Single binary | Single binary |
| Iteration speed for one person | Fast | Fast | Slow |

**Constraints that come with the decision:**

- pyright strict is mandatory in CI for the core and for customer extensions.
- Command schemas are written in pydantic, the single source for JSON Schema, REST, MCP and the UI's TypeScript types.
- Money and quantities use `Decimal` only. Accounting invariant tests run together with type checking.

**Revisit when:**

- The LLM gateway or the offline warehouse sync service hits a measured throughput limit: consider Go for that component only.
- The periodic-average cost solver is too slow on large data, or a WASM plugin sandbox is needed: consider Rust for that component only.
- Python static typing does not stop AI-written errors at an acceptable rate, measured by defects reaching staging.
