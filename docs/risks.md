# Risks

| Risk | Mitigation |
| --- | --- |
| The ERP pull toward doing everything | The not-doing list is written down. Every new feature must name the trading or assembly workflow that needs it |
| Accounting core correctness: double entry, tax, FX, rounding | Invariant tests and the synthetic dataset from the first commits |
| Non-deterministic AI in financial operations | Deterministic core, agents only propose, the policy engine decides, every change is traced |
| Vietnamese compliance: e-invoice law, TT99 templates | Track regulatory changes; templates are configurable data |
| Personal data and LLM cost | Data labels and a customer-controlled routing switch, several providers, control of data sent outside, cost limits per agent |
| Trust and ecosystem | A reference customer with audited statements, partners co-maintaining early, good documentation and tests |
| One-person dependency, and partners' concerns about AI-written code | Public ADRs and roadmap, a policy for reviewing AI code, a core coverage threshold, architecture docs good enough for someone else to take over, invite partners to co-maintain early |
| One person both developing and supporting the pilot | Only one pilot customer until the Phase 1 gate. Reserve 30–50% of time for support from go-live. No feature releases on closing days or near tax deadlines |
| Concurrency and data-layer defects in AI-written code that business tests do not catch | Parallel tests for stock posting, outbox and idempotency. Periodic independent review of these core parts |
| No community forms after Phase 1 | Target Vietnamese Odoo partners, who have customers paying for services. Prepare easy contribution areas. Documentation, the synthetic dataset and tests good enough for outsiders to run it alone |
| Going global inflates scope | A generic core with no country rules. The author builds only the full Vietnam package and the basic US package (no state tax returns). Other packages come from the community via the shipped skill; CI requires legal sources and tests |
