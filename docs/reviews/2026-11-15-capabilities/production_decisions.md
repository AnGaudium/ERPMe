# Decisions: DS-57 production agent (ADR-0064), chief architect, 2026-11-15

Source: holistic/research_production_agent.md. Adopt its capabilities C1-C8, its six hard locks, its 18 edge cases, and close its listed design gaps. Settings follow ADR-0063's registry and asymmetric change path (if ADR-0063 is not yet in the base, write the settings as registry rows in the same shape and note the dependency). No Vietnam content.

Answers to the report's open questions (technical decisions delegated to the architect):
1. Three agent types: `production` (never tainted), `production_capture` (tainted, scoped to one order), `production_variance` (analysis layer). Reason: taint separation lets C2 run.
2. Boundary: planned orders stay with the planning agent; the production agent works from created production orders onward.
3. Reservation sweep (C2): deterministic, no LLM, runs without a person per run. Setting `production.reservation.mode` = off | on_release | scheduled, default on_release; company scope. Hard: never takes stock reserved for another order or demand.
4. Default reservation timing: at release (setting above).
5. Alternative production versions are the Phase 1 substitution path; substitute components stay after Phase 1 (record as decided, not open).
6. Split = change order on the original plus a new draft order: accepted.
7. Operator chat messages and photos are outside content: the capture agent is tainted; quantities are copied only as stated; a person posts.
8. Deterministic MES import (an integration, not an agent) may post confirmations only if the company enables `production.mes_import.auto_post` (default false), with the new confirmation checks (yield, activity, duplicate) passing; failures become drafts for a person.
9. Any remaining question the report raises: decide it in the configurable direction with a safe default, and list it in the ADR as decided by the architect; add an open question only if it truly needs the author.

Gaps to close in ADR-0064 (with DDL/queries as needed, names per ADR-0004, queries Get/List/Evaluate/Render):
- cross-order shortage list query and one release readiness evaluation;
- exceptions on real production orders (start overdue, overdue, move, cancel, reduce) with tolerance settings;
- a command to move a reservation between orders (always via change proposal);
- upward pegging from a production order to the demand it serves (query);
- in-period quantity variance, and drill-down lines per variance category;
- ADR-0057 extraction purpose `shop_floor_report`;
- confirmation checks: yield, activity, duplicate, with settings and bounds;
- the production query views the agent needs.

Numbering: INV-730..759, EC-200..219 (check collisions with ADR-0063, which uses INV-700..729 and EC-180..199).
Lab: t25_production_agent.py covering the edge cases, the hard locks, settings defaults and bounds, and the new DDL with --load.
