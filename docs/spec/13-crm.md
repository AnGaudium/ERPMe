# Agentic CRM

CRM is where AI makes the clearest difference, because it holds the most unstructured data: email, chat, calls, notes. The advantage over a standalone CRM is that the agent sees the ERP side too: when drafting a quotation it knows stock, margin, credit limit and the customer's payment history.

Design principles:

1. **One partner, many roles**, like Business One's Business Partner. Lead, prospect, customer and supplier are the same record, with no conversion step that breaks history.
2. **The interaction timeline is central.** Email, chat messages, calls, meetings, quotations, orders, invoices and payments sit on one append-only timeline.
3. **Semantic search** over interactions with pgvector inside PostgreSQL (after Phase 1). The agent can answer questions such as "what has this customer complained about regarding delivery?".
4. **CRM work goes into the system-wide work queue.**
5. **A gate on everything sent outside.** Messages or emails an agent drafts for customers are drafts by default; only explicitly permitted types are sent automatically.

| Stage | What the agent does |
| --- | --- |
| Intake | Read incoming email and messages, attach them to the right partner, summarize the need, create a draft lead or quotation request |
| Enrichment | Look up the tax ID to fill name, address and business status. Detect duplicate records |
| Quotation | Draft a quotation from the request: check stock, price from price list and purchase history, warn on low margin or credit limit exceeded |
| Follow-up | Remind about unanswered quotations, draft follow-ups, prepare a summary before meetings |
| Repeat sales | Learn each customer's purchase cycle, detect customers due to order who have not, suggest contact |
| After sales | Combine payment reminders with delivery status and complaints, so customers with an open issue are not chased for money |
| Management | Weekly pipeline summary, flag cooling opportunities and churn risk |

Vietnam-specific notes:

- **Zalo** is integrated only through Zalo Official Account. Automating personal Zalo accounts is unstable and risks the account. B2B selling in Vietnam runs mostly over personal Zalo, so little data may flow through the OA. Email comes first.
- **Personal data:** Personal Data Protection Law 91/2025/QH15 is in force from 2026-01-01. Implementing decrees and penalties: unverified. The system needs:
  - A recorded lawful basis per purpose: contract, legal obligation or consent. Consent is per purpose and withdrawable; silence is not consent. Marketing and proactive messages require consent.
  - A process for access, correction and deletion requests. Deletion must propagate to pgvector embeddings, summaries and agent logs. Data that belongs to accounting documents is retained for the accounting-law retention period.
  - Sending data to a foreign LLM provider is a cross-border transfer: the system has a switch that lets the customer force personal-labeled data (contacts and similar fields) to be processed only by local models. Whether to turn it on is the customer's decision; it is off by default. See AI seatmap and data classification.
  - A processing log, a breach-notification process and a data-protection role.
  - Looking up the tax ID of household businesses and individuals is also personal-data processing.
- **Call recording and transcription** require notifying the person called, so they come after the MVP.
