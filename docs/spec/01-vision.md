# Vision

Build a completely new open-source ERP, designed from the ground up for agentic workflows. The target is trading and assembly businesses worldwide, with CRM from day one. English is the source language, with a Vietnamese translation shipped. The accounting and inventory core follows the SAP model: S/4HANA for the data model, Business One for the leanness of a first release. There is no company-size limit: the design must grow to large enterprises as the product matures (author, 2026-11-19). Every country-specific rule lives in a localization package; the first packages are Vietnam and the US, and the first pilot customer is in Vietnam. The architecture is simple and does not try to do everything, but whatever it does, it does in depth.

Why rebuild instead of continuing on Odoo:

- **No system is natively designed for agentic workflows.** Large systems are retrofitting old workflows. In Odoo, the foundation itself is what must be designed differently: documents can be edited freely, business logic is scattered through the UI, and there is no schema'd command layer for agents to call.
- **AI-assisted design and development** significantly lowers the cost of building the foundation.
- **Odoo would need heavy rework anyway** to reach the depth required for Vietnam: VAS costing, banking, loans, fixed assets, hardening, barcode, plus a port every year to follow Odoo's foundation changes.

Kept from the earlier direction: fully open source with an OCA-style license; partners or customers with technical teams can deploy on their own; paid services only when they want them.

Overarching principle: **the business core is fully deterministic; AI lives only in the proposal layer.** The books never depend on whether an LLM answered correctly.

**Motivation and open commitment.** The project is not for profit. The goal is a fully open, agentic-by-design ERP: no Enterprise edition, no closed modules, no split between open and paid features as in Odoo. Once Phase 1 is done and a customer runs on it, the expectation is that the community contributes to complete the solution, and every contribution stays in the same open codebase. Details in [License and project governance](18-license-governance.md).

**Resources and timeframe.** A team of one person who knows accounting and business processes, understands large systems and Odoo's problems, and uses AI for design and development. No dates; build order and gates only: the most logical build order takes priority over dates. No commitment to any customer until the platform is complete. The solution must be lean and include only practical features.
