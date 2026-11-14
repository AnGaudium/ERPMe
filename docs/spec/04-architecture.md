# Overall architecture

UI, mobile app, agents and integrations are peer clients that all call one command layer. No client writes directly to the data.

The command layer asks the policy engine before posting. The business core only appends to the books and emits events. Events go to the work queue and wake the responsible agent or human. Everything runs on one PostgreSQL database, packaged as a modular monolith.
