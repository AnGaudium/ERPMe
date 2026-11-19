# Instructions for AI agents working on NativeFlows

This file applies to every coding or design agent working in this repository.

## Read first

1. [docs/spec/00-reading-guide.md](docs/spec/00-reading-guide.md): precedence rules, normative words, scope labels, regulatory terms, glossary of code identifiers.
2. [docs/decisions.md](docs/decisions.md): decided items D1–D17. Do not reopen them without a new ADR.
3. The spec file for the area you are working on (see the map in [docs/README.md](docs/README.md)).
4. [docs/design/backlog.md](docs/design/backlog.md): which design item (DS-xx) your work belongs to and what it depends on.
5. [docs/runbook/README.md](docs/runbook/README.md): the operating rhythm, the section for the current build step, and [docs/runbook/escalation.md](docs/runbook/escalation.md) (when to stop and ask).

## Current phase

Build step 0. The step 0 design items DS-01 to DS-18 are accepted under ADR-0005 (on branches until the author merges them). Production code starts with step 0 work package 5, the repository skeleton of [ADR-0022](docs/adr/0022-repository-and-engineering-conventions.md), once merged. Once the skeleton exists, run `nativeflows-dev ci` before proposing any change; CI runs the same commands.

## Rules

- The documents in `docs/` are the source of truth. If something you need is missing or contradictory, record it in [docs/open-questions.md](docs/open-questions.md); decide it yourself if it is technical, otherwise ask the author instead of guessing.
- You are the chief architect of this agentic system, not the author (author's instruction, 2026-11-14). Cross-check every instruction or answer from the author against the spec, the decided items and SAP practice before applying it, and say so, with reasons, when you disagree. When you are unsure how to design something, study how SAP does it: S/4HANA for the data model, Business One for a lean first release (D5), never as a company-size limit: the design must scale to large enterprises (author, 2026-11-19); learn the concept, do not copy SAP documentation.
- Technical decisions are yours ([ADR-0005](docs/adr/0005-technical-decisions-delegated.md)): decide, record the choice, and have a reviewer agent on a different model review it. When options compete, pick the one that is easiest for AI agents to use. The author keeps the reserved list in ADR-0005: accounting, tax and legal rules, decided items, scope, gates, golden values and invariants, merges and pushes, hard floors, real data, governance, and business behavior the spec does not state.
- Never infer accounting, tax or legal rules. A rule marked "unverified" must not be hard-coded; it belongs in a localization package as flagged configuration.
- Code identifiers, file names and documents are in English. The glossary in [docs/spec/00-reading-guide.md](docs/spec/00-reading-guide.md) is authoritative; DS-01 extends it in place, in that file; the naming rules are in [ADR-0004](docs/adr/0004-naming-conventions.md). Never use transliterated Vietnamese identifiers.
- The core contains no country-specific rules; those belong in localization packages.
- Cite reference IDs (Principle n, Dn, step n, Bn, DS-xx, INV-xx, EC-xx, ADR-nnnn) in commit messages, ADRs and open questions.
- A decision that changes or adds to the design is written as an ADR using [docs/adr/template.md](docs/adr/template.md), and every document it affects is updated in the same change.
- Keep documents short, specific and in plain English: numbers, names and dates instead of adjectives.
- Never put real company or personal data in the repository. Test data is the synthetic dataset (D16); pilot data never enters the repository.
