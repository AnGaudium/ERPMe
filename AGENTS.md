# Instructions for AI agents working on ERPMe

This file applies to every coding or design agent working in this repository.

## Read first

1. [docs/spec/00-reading-guide.md](docs/spec/00-reading-guide.md): precedence rules, normative words, scope labels, regulatory terms, glossary of code identifiers.
2. [docs/decisions.md](docs/decisions.md): decided items D1–D17. Do not reopen them without a new ADR.
3. The spec file for the area you are working on (see the map in [docs/README.md](docs/README.md)).
4. [docs/design/backlog.md](docs/design/backlog.md): which design item (DS-xx) your work belongs to and what it depends on.
5. [docs/runbook/README.md](docs/runbook/README.md): the operating rhythm, the section for the current build step, and [docs/runbook/escalation.md](docs/runbook/escalation.md) (when to stop and ask).

## Current phase

Design, Build step 0. Do not write production code until the step 0 design items (DS-01 to DS-18) are decided. Design work produces files under `docs/adr/`, `docs/design/` and `docs/catalogs/`.

## Rules

- The documents in `docs/` are the source of truth. If something you need is missing or contradictory, record it in [docs/open-questions.md](docs/open-questions.md) and ask the author instead of guessing.
- Never infer accounting, tax or legal rules. A rule marked "unverified" must not be hard-coded; it belongs in a localization package as flagged configuration.
- Code identifiers, file names and documents are in English. The glossary in [docs/spec/00-reading-guide.md](docs/spec/00-reading-guide.md) is authoritative; DS-01 extends it in place, in that file. Never use transliterated Vietnamese identifiers.
- The core contains no country-specific rules; those belong in localization packages.
- Cite reference IDs (Principle n, Dn, step n, Bn, DS-xx, INV-xx, EC-xx, ADR-nnnn) in commit messages, ADRs and open questions.
- A decision that changes or adds to the design is written as an ADR using [docs/adr/template.md](docs/adr/template.md), and every document it affects is updated in the same change.
- Keep documents short, specific and in plain English: numbers, names and dates instead of adjectives.
- Never put real company or personal data in the repository. Test data is the synthetic dataset (D16); pilot data never enters the repository.
