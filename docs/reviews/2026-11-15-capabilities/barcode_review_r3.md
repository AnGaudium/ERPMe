# ADR-0061 Barcodes: independent review, round 3 (2026-11-15)

Reviewed: copies of `base-ds-uom` and `base-uom-sim` in `/tmp`, each with `drafts/ds-barcode/apply_barcode.py` applied (54 writes over 33 files on both). Paths are relative to `docs/` after the apply script. No git command was run in `~/Projects/NativeFlows` and the bases were not changed.

## Verdict: NOT YET

0 blocking, 2 should-fix, 3 nits. Round 2's S1 and nits 1 to 6 are applied. Both should-fix items are in the new cleanup job, and each is a one-sentence change.

## Lab results (a fresh database for each `--load`)

| Copy | Lab | Result |
| --- | --- | --- |
| base-ds-uom + barcode | t19 `--load` | 172 / 172 |
| | t17, t14, t15, t16 `--load` | 114, 83, 146, 99: all pass |
| | t11 `--load` | 163 / 163 |
| | t12 | 187 / 187 |
| | t01 to t10 and t13 on the standard load | 16, 6, 4, 5, 62, 60, 38, 46, 60, 69, 24: all pass |
| base-uom-sim + barcode | t12, t17 `--load`, t19 `--load` | 189 / 189, 117 / 117, 172 / 172 |

No "out of shared memory" occurred.

## Should-fix

**S1. The cleanup job can delete an SSCC under the company's own prefix once that prefix row is deleted.**
`adr/0061-barcodes.md:80` (the job), rule 11 (`:111`); `design/DS-04-command-envelope.md:209`; `lab/t19_barcode.py:424-428`.
- The job tells own from supplier SSCCs only by the rows of `gs1_company_prefix` at the time it runs.
- `DeleteGs1CompanyPrefix` is refused only for "a prefix that generated GTINs". A prefix with `next_item_reference` 0 can be deleted (probe: the database deletes `893987654`). That is every prefix used only for SSCCs, or whose GTINs were typed and not generated, which is the normal case in Phase 1, where NativeFlows generates no SSCC.
- There is no retired state for a prefix, so "a prefix that has since been retired" can only mean a deleted row. After the delete, the company's own retired SSCCs under it look like a supplier's and the next daily run deletes them. Rule 7 says such an SSCC "is deleted only by a person".
- The lab passes the own prefixes as a list and does not test a deleted one.

Fix: never delete a prefix row that any registry row lies under. Refuse `DeleteGs1CompanyPrefix` with `gs1_prefix_in_use` while a GTIN or SSCC of the registry, live or retired, starts with the prefix (after the indicator or extension digit), not only when it generated GTINs. Or drop the delete command and add `is_active`, so old prefixes always stay listed. Add a t19 check for the deleted-prefix case.

**S2. `RunRetiredSsccCleanup` is registered against ADR-0054's rule for system jobs.**
`adr/0061-barcodes.md:80`, `:106-107`; `lab/t12_access.py:281`; `adr/0054-users-roles-and-authorizations.md:117`, `:377`.
- ADR-0054: "commands that only a registered system job or consumer runs are registered `is_internal_only`": the level expansion skips them, no role holds them, `owner` included, and they have no REST endpoint or tool. `RunApprovalEscalation` is listed that way.
- The ADR gives the job a leaf (`product`) and a declared minimum level `full`, and t12 registers it as an ordinary command at `full`. A role with Products `full` would then hold a command the text says only the system runs.

Fix: register it `is_internal_only` with no level, add it to the ADR-0054 rule 24 note beside `RunApprovalEscalation`, and model it that way in t12.

## Nits

1. The overlap trigger holds only at READ COMMITTED and SERIALIZABLE. Probe with two connections: at READ COMMITTED the second insert waits and fails with `gs1_prefix_invalid`; at SERIALIZABLE it fails with a serialization error; at REPEATABLE READ it waits and then commits, and both `5013` and `501334` stay, because the snapshot predates the lock. No ADR states the isolation level of commands, so say that the trigger relies on READ COMMITTED. Better, replace trigger and lock by a constraint that holds at every level and needs no advisory lock (tested on the loaded database, `btree_gist` is already there): `EXCLUDE USING gist (company_id WITH =, int8range(rpad(prefix, 12, '0')::bigint, rpad(prefix, 12, '9')::bigint, '[]') WITH &&)`.
2. The lock key itself is sound: one transaction-level lock per company on a 64-bit hash of `'gs1_company_prefix:' || company_id`, released at commit or rollback, so a simulated command leaves nothing behind. It is the first advisory lock in the design. ADR-0022 rule 13 bans `pg_advisory_lock` on trigger paths under the heading "Session locks"; add a note there that transaction-level advisory locks are allowed, or take nit 1's constraint and need none.
3. The glossary now has "Set (single-value form)" in the terms table and the verb row for Set unchanged. That is acceptable. ADR-0004 rule 20 still reads "a verb never takes a second meaning", so one clause in rule 10 saying the meaning is the same (replace, never merge) would close it.

## Points asked for

- **Trigger concurrency and lock key:** nits 1 and 2. One INSERT with two overlapping rows is refused, and so is an UPDATE of `prefix` into an overlap (probes).
- **Cleanup and own prefixes:** S1. With the prefix row present, the job leaves own SSCCs alone (t19 P118).
- **Edge-case numbering:** EC-110 to EC-129 are contiguous and in order in `catalogs/edge-cases.csv`, with no duplicate code; EC-119 to EC-129 are this ADR's and fill ADR-0054's block (EC-110 to EC-129); EC-130 and EC-131 remain ADR-0056's. The ADR-0054 rule 25 note, DS-17 and rule 27 agree. INV-620 to INV-624 have no duplicates.

## Round-2 items, verified

- **S1:** `barcode.sscc_reuse_months` is a company setting in rules 7 and 29 and in the ADR-0023 note; no regime setting is left.
- **Nit 2:** empty lot and serial codes are refused (D46d, D46e).
- **Nit 3:** the overlap is held by the database at the default isolation level, and INV-624 is in the catalog.
- **Nit 4:** EC-120 is `must_reject:scan_unresolved` and EC-129 `must_succeed`.
- **Nit 5:** the Zint distribution sentence is in rule 21.
- **Nit 6:** the job exists; see S1 and S2.

## Not verified

- The GS1 facts the ADR flags as open (Dictionary tables, Digital Link key search, SSCC reuse period, prefix lengths) and Zint's licences were not checked against their sources.
- Row-level security is not enabled by the lab load.

Cleanup done: database `nativeflows_lab_rv61` dropped; `/tmp/rv61`, `/tmp/rv61sim` and `/tmp/rv61r1` deleted; the bases, the repository and the drafts were not changed.
