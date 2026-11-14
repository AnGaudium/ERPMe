# Data migration, user experience and documentation

Adoption is decided in three places: whether old data moves over easily, whether the daily UI is fast, and whether users can learn on their own. "The UI is just one client" is about architecture; it does not mean the UI matters less.

## Data migration and go-live

- **Data to import:** master data, opening account balances, AR/AP open items per invoice, inventory per warehouse, lot and serial with opening cost.
- **Sources:** a standard Excel template; a reader for the pilot's current system, built in step 11 (D16). Every import is a simulated command batch, never an SQL script.
- **Process:** fix the cut-over date, a go-live checklist, and full data export at any time, to answer "what if we want to leave".

## User experience for accountants and warehouse staff

- Keyboard data entry no slower than MISA (step 9 gate).
- English is the source language; Vietnamese ships translated and is the default for companies on the Vietnam package.
- Vietnamese print templates: cash receipt, cash payment, goods receipt, goods issue, invoice.
- Excel export on every list.
- Warehouse screens work well on cheap Android phones over weak networks.

## Documentation and community

- **The synthetic dataset,** shared by the public demo, invariant tests, agent evaluation and training.
- Documentation in English as the source, user guides with a Vietnamese version, a migration guide for each source system that has a reader, an FAQ page "why not Odoo or ERPNext".
- Discussion groups in English and Vietnamese, regular demos, good-first-issue labels. Invite Vietnamese Odoo partners who face exactly the problems listed in [01-vision.md](01-vision.md).
