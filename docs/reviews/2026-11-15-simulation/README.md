# Test-database simulation (2026-11-15)

The simulator in `sim/` builds the whole design schema in a fresh PostgreSQL 18 database and runs business flows against it, recording every command, LLM step, check and invariant in a trace.

Final run on the design at commit bd459d4 (the five gaps it found were then fixed in 280a682): eleven flows (customer and contacts, price list, CPQ, order to cash, demand planning, procure to pay with a multiple-units purchase, document intake, barcodes, workflows and settings, analysis, production), run twice on fresh databases with recorded LLM steps (`SIM_LLM=off`): 83/83 checks, 27/27 invariants, 17 LLM calls per run, 0 trace differences. Results: `sim/runs/final_a.*`, `sim/runs/final_b.*`; the trace of run B is `sim/trace/`.

The simulator is design evidence, not product code, like the design-validation lab. See `sim/README.md` for how to run it; it needs `NATIVEFLOWS_DOCS` pointing at a docs directory and a lab database (see the design-validation lab README). Sample people in the seed data are fictional.
