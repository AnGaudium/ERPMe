# AI seatmap and data classification

The seatmap defines which model does what, at which effort level, and which data classes it may see. It is a configuration file (`seatmap.yaml`) changed through the pipeline, and it must pass the agent evaluation suite before taking effect.

## Multi-model, no lock-in to one provider (Phase 1: one provider behind a common interface)

The system works with many models and providers, including local models. No business module calls a provider SDK directly.

- **A seat declares capabilities, not a model name:** tool calling, structured output, image and PDF reading, long context, reasoning level. Any model that meets the capabilities and passes the seat's evaluation may take the seat.
- **The LLM gateway has one adapter per provider**, normalizing the differences: tool-call format, structured output, reasoning control, prompt caching, token counting, refusal handling, cost reporting. Local models go through servers exposing a common compatible API.
- **A common reasoning level** (low, medium, high, very high) is mapped by the gateway to each provider's own parameter: effort for Claude; reasoning parameters, thinking budget or temperature for other providers.
- **No lowest common denominator.** The gateway publishes capability flags per model; a seat uses advanced features when the model supports them, with a fallback when it does not.
- **Prompts and skills are provider-neutral**, with small per-provider overlays where needed. Skills are Markdown following common conventions so different coding agents can read them.
- **Agent tools go through MCP**, a provider-neutral protocol.
- **Fallback chains may cross providers**, but always respect data labels: when the routing switch is on, a seat with personal data only falls back to another local model.
- **Every (seat, model) pair must pass evaluation before use.** Changing a model is a configuration change through the pipeline, not a code change.

## Data classification and routing

The system provides the mechanism; whether to enforce it is the customer's decision. Data is always labeled. Enforcing routing by label is a per-company switch, off by default. Large companies that must comply with personal-data law turn it on. Small companies may leave it off and take responsibility for the lawful basis and cross-border transfer themselves. Whoever turns the switch on or off is recorded as accountable.

- **Labels on every entity and field**, part of the self-describing data layer (Principle 7): public, internal, personal, sensitive personal.
- **Default label personal** for contacts, users, employees, email and message content, and tax IDs and addresses of household businesses and individuals. A company's tax ID is public.
- **When the switch is on, routing is enforced in the LLM gateway, not by prompt:** any request whose context contains a personal-labeled field may go only to a seat with a local model. The gateway rejects it if the selected seat uses a cloud model.
- **Logging always on:** whether the switch is on or off, the gateway records which personal-labeled fields were sent to cloud models, for the legally required processing log.
- (After Phase 1) **Optional pseudonymization** (only where the customer's policy allows): replace personal fields with surrogate codes before sending to a cloud model and restore them locally. Strict mode uses local models only.
- **Embeddings and logs:** when the switch is on, embeddings of personal data are computed by a local embedding model. Agent run logs containing personal data are stored locally and follow the deletion process.
- **User-defined fields must declare a label.** CI rejects a new field without one.

## Reference seatmap

The table below is a reference configuration. The model column lists the model used to set the evaluation baseline, not a requirement. Claude does not accept temperature as a control (the API errors on non-default values), so the gateway maps the reasoning level to effort; temperature applies only to providers that still support it. Whatever the model, stable results come from structured output, strictly schema'd tools and the deterministic core.

| Seat | Work | Required capabilities | Reasoning | Temperature (providers that support it) | Reference model | Data visible |
| --- | --- | --- | --- | --- | --- | --- |
| Classification, extraction | Email intent, mapping e-invoice lines to items, tax-ID lookup | Structured output | Low | 0 | Claude Haiku 5.5 | Non-personal |
| Classification with personal data | Read email and messages, attach to partner, summarize interactions | Structured output, good Vietnamese | Low | 0 | Local model | Personal |
| Embedding | Semantic search over interactions | Vietnamese embedding | — | — | Local embedding model | Personal |
| Drafting | Quotations, follow-ups, approval files | Tool calling, natural Vietnamese writing | Medium | 0.3 | Claude Sonnet 5.5, or a local model with personal data | Per routing |
| Matching and reconciliation | Bank-matching exceptions, three-way match | Tool calling, structured output | Medium | 0 | Claude Sonnet 5.5 | Non-personal |
| Data migration | Master data mapping, duplicate detection | Structured output, batch processing | High | 0 | Claude Sonnet 5.5 via Batch API | Master data; contacts go to a local model |
| Data Q&A | Answer questions through the read-only query layer | Tool calling | Low | 0 | Claude Sonnet 5.5 | Per routing |
| Analysis | Period-close assistant, explaining differences, anomaly reports | Tool calling, long context | High | — | Claude Opus 5.5 | Non-personal |
| Builder | Customization pipeline: templates, rules, plugins, websites | Coding agent, image and PDF reading | Very high | — | Claude Opus 5.5 | Code, anonymized data |
| Reviewer | Independent review of the builder's changes | Coding agent; should be a different model, ideally a different provider from the builder | High | — | Claude Fable 5.2 for changes touching money and books | Code |
| Eval judge | Score the agent evaluation suite | Structured output | Medium | 0 | A model different from the one being scored | Anonymized data |

Each seat also declares: a fallback model chain, budget per run and per day, output token limit, and its mandatory evaluation suite. Customers change model or provider by editing the seatmap and running the seat's evaluation, never by changing code.

Seats listing a local model apply only when the customer turns on the personal-data routing switch. Otherwise those seats use a cloud model with the same capabilities, e.g. Claude Haiku 5.5 for classification and Claude Sonnet 5.5 for drafting.
