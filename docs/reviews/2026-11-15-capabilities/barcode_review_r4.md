# ADR-0061 Barcodes: independent review, round 4 (2026-11-15)

Reviewed: copies of `base-ds-uom` and `base-uom-sim` in `/tmp`, each with `drafts/ds-barcode/apply_barcode.py` applied (55 writes over 33 files on both). No git command was run in `~/Projects/ERPMe` and the bases were not changed.

## Verdict: ACCEPT

0 blocking, 0 should-fix, 1 nit. Round 3's S1, S2 and nits 1 to 3 are applied and verified.

## Lab results (a fresh database for each `--load`)

| Copy | Lab | Result |
| --- | --- | --- |
| base-ds-uom + barcode | t19 `--load` | 177 / 177 |
| | t11, t14, t15, t16, t17 `--load` | 163, 83, 146, 99, 114: all pass |
| | t12 | 187 / 187 |
| | t01 to t10 and t13 on the standard load | 16, 6, 4, 5, 62, 60, 38, 46, 60, 69, 24: all pass |
| base-uom-sim + barcode | t12, t17 `--load`, t19 `--load` | 189 / 189, 117 / 117, 177 / 177 |

t15 and t16 failed on the first try with the shared container's "out of shared memory" error and passed on the one retry.

## Round-3 items, verified

- **S1 (own SSCCs and deleted prefixes).** `gs1_company_prefix` has `is_active`; the cleanup job counts every prefix row as the company's own, active or not; `DeleteGs1CompanyPrefix` is refused with `gs1_prefix_in_use` while a registry GTIN or SSCC, live or retired, lies under the prefix (rule 11, DS-04, the ADR-0045 note, INV-624). t19 P119 and P120 cover a prefix that holds only a retired SSCC and a deactivated prefix; D46g holds "the generation prefix is active" in the database.
- **S2 (system job).** `RunRetiredSsccCleanup` is `is_internal_only` in rules 7 and 10, in the ADR-0054 rule 24 note beside `RunApprovalEscalation`, and in t12's internal set; no level grants it.
- **Nits 1 and 2 (overlap).** The trigger and the advisory lock are gone. `ex_gs1_company_prefix_overlap` holds the rule; t19 D46i inserts two overlapping prefixes from two connections at REPEATABLE READ and only one commits, which was the failing case in round 3. No advisory lock is left in the DDL.
- **Nit 3.** Rule 10 says the single-value form of Set replaces and never merges.

## The btree_gist claim

Correct. ADR-0022 rule 8 says the first migration creates the extensions `btree_gist` and `pg_trgm` (`adr/0022-repository-and-engineering-conventions.md:128`). DS-20's header already relies on it for the price list exclusion constraint of ADR-0045, no DDL file has a CREATE EXTENSION line, and the lab loader installs both. The new constraint loads on both bases.

## Nit

1. The refusal to delete a prefix that has registry codes under it is a command rule; the database would delete the row, and INV-624 catches it afterwards. That matches how the ADR states it. If the author wants the database to hold it, a BEFORE DELETE trigger on `gs1_company_prefix` is enough; not needed for acceptance.

## Not verified

- The GS1 facts the ADR carries as open questions (the Dictionary's predefined-length table and AI pairs, the Digital Link key search, the SSCC reuse period, company prefix lengths) and Zint's licences were not checked against their sources in any round.
- BarcodeDetector behaviour on devices is an open question for DS-31.
- Row-level security is by the generated-policy convention and is not enabled by the lab load.

Cleanup done: database `erpme_lab_rv61` dropped; `/tmp/rv61`, `/tmp/rv61sim` and `/tmp/rv61r2` deleted; the bases, the repository and the drafts were not changed.
