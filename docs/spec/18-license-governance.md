# License and project governance

| Layer | License | Reason |
| --- | --- | --- |
| Core and business modules | AGPL-3.0, OCA-style | Every modification and every plugin running in the core's process must be open. LGPL is not chosen because it allows closed modules running with the core, part of why Odoo's ecosystem is half-open |
| SDK, command schemas, client libraries | Apache-2.0 | External integrations and agents are not constrained |
| Documentation | CC BY-SA 4.0 | Allows translation and redistribution |
| Synthetic dataset | CC0 | Free use for demos and training |

- Contributions: DCO instead of a CLA. A trademark policy for the project name.
- Governance: state clearly that in the early phase one person has final say (BDFL). Write down the conditions for inviting co-maintainers, e.g. a partner who has deployed successfully. Later, every repo has at least two people with merge rights.
- Transparency: public architecture decision records (ADRs), a public roadmap, a policy for reviewing AI-written code, a coverage threshold for the core.

**Fully open commitment:**

- One edition only: no Enterprise edition, no closed modules released by the project, no hosting-only features.
- No copyright-assigning CLA, so no party, the author included, can unilaterally relicense contributed code.
- The project treats plugins running in the core's process as derivative works under AGPL. External apps (level 5) that only call the public API may use any license.
- Partners may earn a living from services: deployment, data migration, hosting, support, customization. This is the most sustainable source of contributions to an open ERP.
- The trademark policy only prevents impersonation; it is never used to restrict distribution or services.
- Once several partners co-maintain, consider moving the project name and assets to a non-profit organization, so the project does not depend on one person.

**How the community forms after Phase 1:** the real contributors to an ERP are partners and businesses with real needs, rarely independent developers. So prepare during Phases 0 and 1:

- A reference customer in production, the synthetic dataset, a public demo and documentation good enough for outsiders to install and run it alone.
- Areas that are easy to contribute to and barely touch the core: e-invoice adapters, bank statement readers, print templates, readers for other software's data, updates for new circulars and decrees, localization packages for other countries.
- Invite Vietnamese Odoo partners who face exactly the problems listed in [01-vision.md](01-vision.md).
