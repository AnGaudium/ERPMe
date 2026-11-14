# Agent safety and permissions

External content (email, chat messages, invoices, bank statements) flows straight into agents that hold write tools. This is the biggest path for data leakage and price manipulation, so it must be blocked by design.

Rule 1 (untrusted content), rule 5 (segregation of duties) and the "Human only" rows of the guardrail table in [14-agent-workflows.md](14-agent-workflows.md) are hard floors. No policy, threshold or customer setting can relax them.

1. **Untrusted content:** all external content is labeled untrusted. An agent run that has read untrusted content keeps only read access scoped to the related partner (for the data-migration workflow: the import batch), plus the right to create drafts. That run must not send anything out, change master data or post. A draft for a customer may contain only that customer's data. Auto-posting is done only by deterministic code, never by an agent run that has read untrusted content; a match an LLM contributed to is never auto-posted.
2. **Fixed tools:** each agent type has a fixed tool list, never inferred from the prompt.
3. **Actors:** human, agent, integration and system. A system actor is a deterministic job (costing, FX revaluation, closing entries, scheduled matching). Every command carries `actor` and `on_behalf_of`; a system actor's `on_behalf_of` is always the accountable human: the policy owner, or the human who triggered the job. An agent's effective permission is the intersection of the agent's permissions and those of the human it acts for.
4. **Record- and field-level permissions:** by any analytical dimension in the canonical list in the universal journal row of [05-accounting-inventory-core.md](05-accounting-inventory-core.md); fields such as cost and margin can be hidden. The query layer and MCP apply the same filters; PostgreSQL RLS is the second line of defense.
5. **Segregation of duties:** the person who triggers an agent must not approve that agent's drafts.
6. **Legal accountability:** accounting law requires a preparer and an approver for each document. Every document an agent auto-posts must have one accountable human (the owner of the policy that allows auto-posting), who confirms in batches within the period. Unconfirmed agent auto-posts block the period close; this is an item in the close checklist.
7. **Run record:** trigger, model, prompt version, tool calls, tokens, cost, commands produced, link to audit.
8. **Budgets:** per agent, per company, per day, with a circuit breaker.
9. **No hidden memory:** anything an agent "learns" (e.g. a customer's purchase cycle) must be deterministically computed data stored in the system, viewable and editable.
