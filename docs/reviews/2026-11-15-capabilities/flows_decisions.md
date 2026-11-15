# Architect decisions on the six-flow walkthrough (report: flows_report.md)
Items also covered elsewhere: A9 -> ledger fix; A12 -> commercial fix (S12); A14 -> production fix (item 2); A4 -> DDL agents (commercial/inventory, planning/production, platform). The flows fix script handles the rest:

- A1 note on ADR-0051 r14 stating the designed configuring path: a person records a note interaction (their own words) and starts the quotation agent on it (untainted); an e-mail-triggered run only resolves partner items and hands over. Author question (open questions 36/40/41) stays; the simulation and video show this path and say so.
- A2 DS-24 intake seam named in core (add-on fills it): table e_invoice_record (columns the agent reads), import command ImportEInvoiceRecord, reader interface EInvoiceRecordReader (package/add-on), raise of supplier_invoice_received, ConfirmEInvoiceSupplier (person) — note on ADR-0051 r20 and a pointer in backlog DS-24.
- A3 regime setting documents.e_invoice_required per document type (DS-19 settings.yaml seeded true for sales_invoice and correction types, unverified); note on ADR-0053 r8; the simulation uses the stub adapter of ADR-0028 r12.
- A5 DS-17 setup events (policy_rule_created, approval_pool_updated, user_registered, role_assigned) and sample company policy rules (thresholds) in the vn_* profiles so pools pr, po, sales, mo are reachable; note on ADR-0055 r2 (seed stays minimal in core; the dataset adds company rules).
- A6 seed sales_manager, purchasing_manager and production_planner as members of the general pool's standard stage with approve on change_proposal (eligibility still needs target permissions); correct ADR-0051 r25 wording by note (ADR-0055 r5; role-template-levels).
- A7 make the seeded role templates conflict-free against the seeded segregation rules with minimal changes (e.g. accountant loses partner edit; resolve price_list_vs_sales_approval by giving sales list maintenance to a role without sales approval, or narrowing); report choices (ADR-0054 r11/r17 notes; catalogs).
- A8 note on ADR-0054 r19 with the minimum cast for flow 6 (three finance users) and DS-17 seeding it.
- A10 quotations have no credit condition; note on ADR-0047 r22 and a correcting note on ADR-0051 r15.
- A11 quotation requires the active customer role: error partner_role_missing (or existing code) — note ADR-0047 r3.
- A13 "the approving human" = the approver whose approval completed the plan (ADR-0055 r16 note; ADR-0029 r3 pointer; ADR-0047 r9 converter wording, A20).
- A15 an external print or link of a document requires it approved (or later); note on ADR-0049 r28 and ADR-0052 r28.
- A16 worked TT99 example of the goods-line price difference (33882 then landed_cost to 152) as a note on ADR-0047 r21, labelled TT99 example.
- A17 open question proposing spec 09 wording (configurator, MRP, planning in Phase 1); do not edit spec.
- A18-A20 accept (stale names covered by notes; production_receipt/operation_confirmation pool intent is decided in production fix item 12; converter wording).
