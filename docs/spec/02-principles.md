# Agentic-by-design principles

The agent is a first-class user of the system, not a bolt-on feature. These thirteen principles govern the design of every module.

| # | Principle | Meaning |
| --- | --- | --- |
| 1 | Every business operation is a schema'd command | e.g. `CreatePurchaseOrder`, `PostGoodsReceipt`, `MatchBankLine`: explicit inputs, preconditions and results. Command names, data model and source strings are English; the UI is multilingual with Vietnamese shipped. UI, agents and integrations all call the same command layer. The UI is just one client |
| 2 | Simulate before execute | Every command can answer "what would happen": journal lines, stock movements, cost impact. Simulation returns a `plan_hash`. The execute call sends the expected `plan_hash` and is rejected if the actual result differs |
| 3 | Agents propose, policy decides | Agents create drafts. The policy engine is one deterministic function that returns allow, deny, which approval procedure is required, or human-only. Confidence is computed by deterministic rules (bank match score, three-way match), never taken from a number an LLM reports about itself |
| 4 | Agents are principals with their own permissions | See Agent safety and permissions |
| 5 | Append-only books | Only posted documents are immutable; cancelling means posting a reversal document, in the spirit of Business One. Open commercial documents can be edited, but every edit creates a new version. Point-in-time figures use the posting date; the audit log also stores the recording timestamp |
| 6 | Every number is explainable | Every derived value (cost, price, tax) stores a trace ID pointing to its source lines and the rules applied |
| 7 | Self-describing data | Every entity and field has a meaning description (English source, translated) and a data classification label used for model routing. The read-only query layer uses semantic views, a read-only role and a runtime limit. Agents never generate SQL against the write database |
| 8 | The work queue is central | Exceptions, pending approvals, unmatched bank lines and low stock are all work items. Each has an owner (human or agent), a due date and a status. An agent takes a work item by locking it and never works on it at the same time as a human |
| 9 | Commands are safe to retry | Idempotency key per (actor, command type) with a retention period; a retry returns the original result. Stock posting is serialized per (item, warehouse), because optimistic locking does not prevent negative stock |
| 10 | MCP from the start | Commands, queries and resources are exposed over MCP alongside REST, with the same permission filters |
| 11 | Agent behavior is tested with scenarios | CI runs scenarios against recorded LLM responses (replay). An evaluation suite runs real LLMs on a schedule for each provider–model pair, with pass thresholds. Changing a model or prompt requires passing it |
| 12 | Fully usable without an LLM | With agents off, every operation can still be done by hand. AI accelerates; it is not a precondition for operating |
| 13 | Maximum determinism in workflows | Anything a deterministic function can compute is never given to an LLM: reading e-invoice XML, tax-ID lookup, three-way matching, bank match scoring, pricing, tax, allocation, duplicate detection. A workflow is a sequence of steps orchestrated by code; the LLM handles only the remaining unstructured part, never computes numbers, and its output always passes a deterministic check. When an LLM resolves a case, the resolution is proposed as a stored rule or mapping so that next time a deterministic function handles it |
