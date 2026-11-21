# Review of doc_lint.py round 4 — fresh bypass probes (r5)

Reviewer: independent, review-only. Subject: `tools/docs/doc_lint.py` (working tree of NativeFlows-s4), README "Lint checks",
`docs/design/compiled-spec-template.md`. Not run: the unit tests (the task was bypass probes). Nothing in the repository or in
`s4-out/specs/` was changed.

Probe folder: `~/Projects/NativeFlows-lab/fable/s4-out/review-lint-probes-r5/` (about 200 probe files `p*.md`; generators
`probes.py`, `probes2.py`, `probes3.py`; wrapper `lint.sh <module> <files> [flags]`). Bases: copies of `clock.md`, `numeric.md`,
`quality.md`, `reporting-1.md`, `reporting-2.md`. Command for every probe:
`cd ~/Projects/NativeFlows-s4 && PY tools/docs/doc_lint.py <probe>.md --module <m>` (via `./lint.sh <m> <probe>.md`).
Baselines all `LINT PASS findings=0`.

Result: BLOCKING 3, SHOULD-FIX 6, NOTE 6.

## BLOCKING

### B1. A whole rule can be deleted by citing its unit in a neighbour's `Source:` (L1/L11 measure nothing for it)
Probes (clock, one change each, all `LINT PASS findings=0`, retention 100%):
- `p02m-R20-dropped-folded-into-R19-source-only.md`: delete R20 (the whole of ADR-0007.R14, user time zone), trace row `ADR-0007.R14 | R19`, add `ADR-0007.R14` to R19's `Source:`.
- `p02n-R29-R30-dropped-folded-into-R28-source.md`: delete R29 and R30 (ADR-0007.R17, R23), fold both into R28's `Source:` and trace rows. Substance line: size ratio 1.51, retention 100%.
- `p02h-R5-deleted-merged-into-R4-source-only.md`: delete R5 (ADR-0007.R4, `AwareDatetime`, `zoneinfo`, 5 identifiers); R4 gets the unit in its Source. Pass, because R4 keeps one of the 5 identifiers (`Instant`) and the L11 retention test is "holds none of them" (p02g, which maps it to a statement with none, does fail).
- `p02l-R16-split-half-dropped.md`: the second half of ADR-0007.R10 (R16, ordering keys) deleted, trace row keeps R15; pass.
Expected: FAIL (a rule of the module has no statement). Actual: PASS. Source/trace agreement only checks that the Source line and the trace table agree, not that the cited unit has any text in the statement; L11 retention needs 3+ code-span identifiers (most rules have fewer) and then only 1 of them; the per-rule size floor (0.10) is the sum over all R-numbers the rule is traced to, so a big neighbour absorbs it.
Fix direction: per R-number, a floor on statement bytes (or distinctive words, numbers, negations) per cited unit, not per module; or an anchor phrase per cited unit: `Source: ADR-0007.R14 "dates are shown as stored"`, which must occur in the unit text and in the statement. I measured plain word coverage on clock: honest minimum 0.37 (ADR-0007.R15.N3), the folded units 0.21 and 0.29, so a coverage floor alone is marginal; the anchor is cheaper to calibrate.

### B2. A statement can be hollowed out and still pass (filler, truncation, shuffle)
All `LINT PASS findings=0`:
- `p01a-filler-same-length.md`: R6 replaced by same-length filler `Table time rule value zone.` x50 with `retention_days`, `timeout_seconds`, `interval`, `datetime` in a list at the front.
- `p01b-filler-R19.md` (same for R19), `p01c-salad-R20.md` (R20 = 12 repeated ADR words, no identifiers).
- `p01d-shuffled-words-R6-R9-R11.md`: the words of three rules shuffled.
- `p01f-truncate-30.md` (and `-50`): every rule cut to 30% of its length, first words kept. Fails only at 20% (retention 34% < 40%).
Expected: FAIL. Actual: PASS. The statement test is 12 characters + 2 distinct ADR words; the floors are 0.30 (module) and 0.10 (rule), so a spec may lose up to 70% of its text. The filler repeats one 5-word block 50 times; a distinct-word floor or a compression ratio would catch p01a/b/c (not p01d, p01f; those need B1's anchor).
Meaning blind by design, but p01a-c is not meaning, it is repetition, so I rate it BLOCKING with p01f.

### B3. The L2 ownership filter (round 4) demands nothing for 150 invariant/edge-case rows
The filter keeps an `invariants` / `edge-cases` row only if its `area` equals the compiled module. Rows whose area is `safety`, `platform`, `warehouse`, `receivables_payables`, `close` (no module has that name) are demanded by no spec. Computed with `owned_catalog_rows` over the 32 modules: 150 distinct rows (96 INV, 54 EC) are cited by a unit of a module, kept by nobody (354 module/row pairs in all, 217 INV + 137 EC, of which part is owned by another compiled module).
Probes:
- `p14f-drop-all-INV-rows.md`, `p14g-drop-all-EC-none.md` (quality): `## Invariants` / `## Edge cases` replaced by `None (the module owns none)`; PASS. The real spec states INV-834 and EC-280..287 (areas `warehouse`, `safety`).
- `p14d-drop-EC280.md`, `p14e-drop-INV834-row-area-warehouse.md`, `p14h-reporting-drop-INV413.md` (INV-413/414, area `safety`): PASS.
- `p14c-drop-both-settings-rows.md`: both owned setting rows of quality (type, scope, default, direction) deleted: PASS, because the key is also backticked in R65/R67 (a mention in the body is the whole L2 test for settings and for named rows).
Still working (good): `p14a` (owned table row removed: L2 FAIL), `p14j` (Entities = None: FAIL with 11 findings), `p06a/b/c` (a row in two chunks: L2 FAIL).
Expected: dropping a row the compiled spec states today is a finding. Actual: PASS. The round-4 filter fixed false positives and removed the demand. Suggested fix: demand a row for every INV/EC cited by a unit whose primary module is this module, whatever its area, unless another compiled module owns it by area (then `ref:`-style cite).
Also 18 INV and 17 EC rows of the catalog are cited by no unit and stated by no spec (e.g. INV-31, INV-53, INV-706, EC-46). Nothing can find those; this is a catalog/spec gap rather than a lint bug.

## SHOULD-FIX

### S1. Required-CONFLICT stops at `supersedes`/`superseded-by`; the entry's content is unchecked
- `p03a`-`p03d` (clock): drop each of the 4 CONFLICT entries, then all, with `None`; PASS. clock's 10 notes have relation `amends` (R9.N1, N2, N3, R15.N1..N4, R16.N1, N2). R9.N1 widens R9, R15.N3 narrows R15.N1; they are exactly the contradictions, yet none is required.
- `p03h` (conflict on the note id instead of the parent), `p03j` (numeric: "stated in R22" changed to "stated in R3"), `p03g` (clock: "stated in R11" -> "R30"), `p03f` (clock R15.N1: "narrowed" -> "widened to any date in the year"), `p03k` (numeric: reason says the opposite): all PASS.
- The real required one works: `p03i-numeric-conflict-dropped.md` FAIL (L5), `p03e` (FALSE-POSITIVE on it) FAIL.
Fix: `stated in R<n>` / `governed by <id>` should be checked: R<n> defined and traced to the entry's id or the governing id; consider requiring an entry (or an explicit `amends`-ack) for `amends` notes whose text differs from the parent's numbers.

### S2. Citations inside statements are not checked against the index
`p08f-wrong-id-in-statement.md`: `(ADR-0004.R13)` -> `(ADR-0004.R99)`, nonexistent: PASS. `p08g` (`ADR-0001.R1`, real but unrelated): PASS. L7 covers trace and `Source:` only; L8 only `<word> ADR-nnnn`. Cheap fix: every `ADR-nnnn.Rk` token in the body must exist in the index.

### S3. Front matter `Source ADRs` and `Build step(s)` are not compared with the units
`p09g-adr-wrong.md`: `Source ADRs: ADR-0042` on a clock spec (all units ADR-0007): PASS. `Chunk: 2 of 1`, wrong Module, wrong/short/uppercase/HEAD index commit, missing fields: all FAIL as designed (`p09a-f,h-k,m,n`). A duplicated `Module:` line after the heading is ignored (p09l, harmless).

### S4. Content-free section text passes
`p11-sec-only-hr` (Purpose = `---`), `p11-purpose-one-word` (Purpose = `Clock.`), `p11-sec-dash` (Settings = `-`), `p11-sec-nonereason-dot` (`None (n/a).`), `p11-sec-nonereason-because` (`None: none.`): PASS. Empty sections, comment-only and heading-only all FAIL (p11-empty-*). Fix: Purpose minimum words; a reason of `None` needs 3+ letters-words and not `n/a`/`none`; a section of only punctuation is empty.

### S5. L4 typed-count gaps (README says "closes the known shortcuts")
PASS where a count is stated in the Purpose (`p07y*`, clock, a lone sentence each; clock owns 0 tables, so every one is false):
- `It owns 12 (twelve) tables.` (`p07ya`); `Tables x12.` (`p07yb`); `Owned tables:` + blank line + `12` (`p07yc`); `12.0 tables` (`p07yd`), `1.2e1 tables`, `0x0C tables`; `12 entities`, `12 relations` (`p07yg/h`); `It defines 29 units.`, `11 sections` (`p07yi/j`: the lint has `count:` markers for sections, notes, columns, yet does not flag them typed); the list form `Owned tables` / `- 12` (`p07yk`); a table `| Owned | 12 |` under a `Tables` line (`p07yl`); `12\ tables` (`p07ym`).
- Unicode (L4 reads only some digit forms): `p13c` Cyrillic `а` in `tаbles`; `p13d` `Ⅻ`; `p13e` `¹²`; `p13h` `十二`; `p13i` `⑧`; and in `p13n/o` Cyrillic `Т` / fullwidth `ＴＢＤ` evade the placeholder list (filler already passes, B2).
- Caught: fullwidth digits (`p13a`), Arabic-Indic digits (`p13b`), zero-width inside number or noun (`p13f/g`), NBSP, tag characters, ligature (`p13p/q/w`), and about 40 forms with `tables/rules/commands/invariants/edge cases`.
Fix: NFKC + confusables folding before L4 (and before every identifier test; IDs are already safe: `p13j,k,l,x` en dash, Cyrillic А and З in IDs all FAIL), and the same noun list as the `count:` kinds.

### S6. `count:` marker kind and the word after it are not tied
`p13s5`: `It defines <!-- count:tables -->0<!-- /count --> rules.` PASS (0 is the true table count, the noun says rules); `p13s6` likewise. A marker is recomputed, the noun beside it is not read. Wrong values are caught (`p13s2/s3/s4`, `p15e`).

## NOTE

- **N1.** `not applicable` for a note: `p02c` (R10 note, ADR-0007.R8.N1) passes by design; printed under NOT APPLICABLE; `p02f` shows the n/a refusal for notes with new identifiers works (R15.N2, N3 refused). A note folded to a parent R by trace only, with the Source line citing it (`p02e`), passes: meaning.
- **N2.** Misattribution is invisible when the Source and trace rows are moved together: `p04b` (R2/R3 sources and trace swapped, statements stay), `p04c` (R29/R30), `p01h` (statements swapped, sources stay): all PASS. This is the "does it say what its source says" spot check; an anchor phrase (B1) would also catch it. A one-sided move fails as designed (`p04a`).
- **N3.** `p08a-e` (statement says the opposite: `is used`, `always used`, sets a default, any date in the year, 9 fractional digits) all PASS: meaning, only the spot check sees it.
- **N4.** Detected as designed: duplicate R-number (`p05a,b,c,e`), `R06` vs `R6` as one (`p05d` is a rename only, passes correctly); an INV row in two chunks (`p06a,b,c`); a moved row passes correctly (`p06d`); `cross`, `process`, nonexistent module, same file twice: exit 2 (`p10*`); wrong module and index (`p09*`); phantom chunk `1 of 3`: PARTIAL exit 3 without `--partial` it is a finding (`p12b/c`); a lone chunk relabelled `whole`: 36 findings (`p12f/g`); hollowed chunk 2: 26 findings (`p12h/i`); two chunks claiming `1 of 2` (`p12k/l`); `p12d/e`: `--partial` on a complete set gives PASS (correct).
- **N5.** L4 quote exemption (probe 15): a typed count of the spec's own tables as a quote is refused in every form I tried: `p15a` (section), `p15b` (in a rule), `p15d` (own-count context), `p15f/g/h` (quality, quote marks), `p15i/j`. A number+noun that really is in a cited source (`399 tables` of ADR-0007.R9.N3) passes, correctly. `p15c` (`the 2 types` in R4) passes; it is true. I found no bypass of the exemption itself. A count in the Trace table is not scanned (`p07j`).
- **N6.** The lint run is not a measure of the spec set: `docs/compiled/` and the index checks were run against the working tree (the whole tree is uncommitted: `docs/compiled/` untracked, doc_lint.py modified), so `Generated from index 30d5706` is checked against the committed index only.

## What the lint cannot see (meaning)
- That a statement says what its source says: opposite meaning, changed numbers (9 digits for 6), changed conditions, changed scope (p08a-e), a conflict reason that says the opposite (p03f/k).
- Whether the source units of an R-number are the ones its statement is about, once Source and trace move together (p04b/c, p01h).
- Whether a deleted rule was needed, when its unit is cited elsewhere (B1) or has fewer than 3 identifiers.
- Whether a `None (reason)` reason is true; whether a `ref:` target holds the unit (checked only when the beside spec exists).
- Anything in the catalog rows demanded by no module (B3, 150 rows); the content of a settings/INV/EC row that is merely mentioned (p14c).
- Whether the proposed/accepted status of a cited rule is described correctly in words (L3 reads IDs).

## What worked well (round 4)
Invisible characters and Unicode spaces; homoglyph and en-dash IDs in Source, trace and R-numbers; duplicate R-numbers; `not applicable` refusal for rules and for notes with new identifiers; required superseding CONFLICT (numeric); the lone-chunk and phantom-chunk handling (exit 3, never a pass); INV in two chunks; owned-table rows; `count:` recomputation; the module refusals (exit 2).
