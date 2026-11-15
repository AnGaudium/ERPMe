# Review of ADR-0056 "Multiple units of measure" — verdict: NOT YET

1 blocking, 9 should-fix, 9 nits. File:line refer to the review copy (`adr/0056-multiple-units-of-measure.md` = "0056").

What I ran:
- `t17_uom.py --load`: 89/89 pass on my throwaway database.
- `t14`: 83/83 pass on the draft.
- `t01`, `t05`, `t06`, `t16`: not verified. I could not reproduce their own load setups; under `load_all.py` they fail identically on base and draft.
- Cleanup done: `erpme_lab_ru` dropped, `/tmp/ru` deleted, repo untouched (`git status` clean).

## Blocking

**B1. The cumulative rule for returns and credits contradicts the per-part limits (0056:121-125, rule 10; 0056:138, rule 11; ADR-0047 rule 20, `0047:250-255`).**
- Rule 10 computes a return on the order line as `P − round((C − q) × f)`. But a return names one receipt, delivery or invoice line, and ADR-0047 rule 20 limits it to that line's inventory quantity.
- The ADR's own bag example breaks: receipts post 2.333 and 2.334 kg. Returning the bag of receipt 1 posts 4.667 − 2.333 = 2.334 kg, which is more than the 2.333 received on that line.
- Result: `correction_exceeds_original` on a full return, or the lot goes to −0.001. The same holds for a quantity credit against an invoice line and a customer return against a delivery line.
- Lab U22 (`t17_uom.py:320-323`) models returns only at order-line level and never checks the per-part limit, so it does not catch this.
- Fix: a return, credit or reversal that names a posted part in that part's unit takes the part as its source. A full return mirrors the part's stored inventory quantity; a partial one applies the cumulative rule on the part. The order line keeps C and P as actual net sums. Forward parts stay `round((C + q) × f) − P`, which self-corrects, so completion still sums to Q_S.
- Then replace the claim "P always equals round(C × f)" (0056:122), restate INV-601, and add a lab case and an edge case for returning one receipt of an inexact unit.
- Side effect to decide: with this fix the latest-only reversal for deliveries and sales documents may no longer be needed.

## Should-fix

**S1. The unit rounding tolerance is one-sided (0056:124).** It only relaxes "fulfilled ≥ Q_S − tolerance". Parts in another unit that round up overshoot and are hard-rejected.
- Order 8.000 kg, three deliveries of 1 bag of 8/3 kg: 3 × 2.667 = 8.001, so the last one gets `quantity_exceeds_open`.
- Same for three invoices in bags against a delivery in kg (`invoice_exceeds_delivered`), and for a bag receipt after a kg receipt with zero receipt tolerance.
- Fix: apply the same tolerance (one step per rounded other-unit part) to the upper limits `quantity_exceeds_open`, `receipt_exceeds_order`, `invoice_exceeds_delivered` and `correction_exceeds_original`. Or state that the last part must be entered in the source's unit, and add the edge case.

**S2. The clearing of a mixed-unit GR/IR residual does not fit (0056:124; `0047:175`).**
- A line "fulfilled" within tolerance is not "closed short". For I > R by 0.001, ADR-0047 rule 13's remedy is a supplier quantity credit, which cannot exist for a rounding step. For R > I it is the human-only write-off, which the Context says this ADR avoids.
- Fix: define a system posting at fulfilment that moves the lagging side to the other within the tolerance, valued at the positions, to price difference. Or state plainly that it is a human `gr_ir_write_off` in both directions and extend that document to I > R.

**S3. The rule does not say when C and P are read (0056:108, 122).**
- The snapshot is taken on the draft, and `inventory_quantity` is NOT NULL on drafts, but C and P are "earlier posted parts". Two open drafts of 1 bag each both compute 2.333; the second must become 2.334 at posting, after reservations and pick tasks were made for 2.333.
- Fix: state that a part's inventory quantity is provisional on a draft and recomputed at Post under the source document's lock (as `0047:173` does for GR/IR). State how a pick or reservation of the provisional quantity reconciles, and that INV-600/601 apply to posted parts.

**S4. Retire-and-replace: price entries (0056:63; `0045` rule 3 note at line 56).** "End-dates the open price entries to the day before the business date" fails in three cases:
- An entry starting on the business date cannot be end-dated to yesterday (`ck_price_list_entry_dates`, `DS-20:696`), and ADR-0045 rule 7's note forbids removing it.
- Future-dated entries, and entries with a later explicit end date, are not "open" and would price the new carton at the old carton's price.
- For a product-level replacement it is unclear whether entries of items that have their own active item-level row for the unit are spared, and whether product-keyed entries (`price_list_entry.product_id`) are included.
- Fix: cover every entry of the unit valid on or after the business date. Started earlier: end-date to the day before. Starting later: remove. Starting today: define it (for example, end-date to today and make the replacement effective the next business date, or refuse). Scope it by resolution level. Add a lab check.

**S5. Retire-and-replace: dependents are missed (0056:60-65).**
- Packaging rows that contain the replaced unit: a pallet of 40 cartons at 960 against a new carton of 20 immediately violates INV-605 and `uom_packaging_inconsistent`. The pallet row is itself "used" and immutable.
- Bill of materials components and outputs that snapshot the unit keep the old can size, while new issue lines in cans use the new one.
- `partner_item.uom_id` and the product's purchase and sales defaults are not mentioned.
- Fix: the command must retire and replace containing rows in the same command (or refuse until they are done). List active bill of materials lines and partner items in `product_uom_replaced`.

**S6. Adding an item-level row that shadows a used product-level unit is an unhandled factor change (0056:51, 72-73).**
- A carton of 12 added for a variant that already has price entries, a supplier minimum, barcodes or open lines in the product's carton of 24 changes that item's factor. Nothing is retired, no entries are end-dated, there is no `product_uom_replaced`, and INV-603 does not see it.
- Fix: treat `CreateProductUom` with `item_id` for a unit the item already resolves at product level as a replacement for that item (same end-dating and review list), or refuse it while the item has dependents in that unit.

**S7. Units that convert through the catalog can no longer be defaults, price units or order units (0056:57 against 0056:161; `0045` rule 3; `0018` rule 12).**
- `uom_conversion_exists` forbids a product unit for such a unit. But price entries (ADR-0045 rule 3), `purchase_uom_id`/`sales_uom_id` (ADR-0018 rule 12), `supplier_item.order_uom_id` (rule 14) and the counting and pick flags all require "inventory unit or product unit".
- So a product kept in kg cannot be bought by the tonne as its default or order unit, priced per tonne, or counted in grams. Before this ADR a product unit row made that possible.
- DS-04's new `uom_not_allowed` row ("no path … for any line, price entry, supplier order unit or product default") contradicts ADR-0045 rule 3 and rule 14's text.
- Fix: say "any allowed unit of the item (rule 6)" for price entries, defaults and the supplier order unit, with notes on ADR-0045 rule 3 and ADR-0018 rule 12. Decide where counting and pick flags live for catalog units, or state the limit.

**S8. The serial rule is the wrong condition (0056:58; INV-604; `0018` rule 9 note).**
- A whole factor does not stop rounding when the product unit has decimals: 0.1 of a 1-decimal `x-carton` × 24 = 2.4, which rounds to 2 serials.
- The stated reason ("serial counts then equal inventory quantities") holds anyway, because the inventory unit has 0 decimals.
- Fix: require `is_exact` for every unit of a serial-tracked product (with dI = 0 it implies a whole factor), and restate INV-604 and `serial_unit_not_whole`.

**S9. Amendments made without a note on the amended ADR, and one catalog row not updated (0056:278-293, rule 24).**
- Latest-only reversal is extended to deliveries, customer returns and sales documents (0056:125; `0047:177`). ADR-0047 rule 13 itself says that precondition amends ADR-0009 rules 18–19, but ADR-0009 gets no note. DS-04's `reversal_not_latest` row (`DS-04:257`) still says "GR/IR postings on an order line".
- Unit names: rule 2 says core names are "translated through the core i18n catalog" and "the core holds no Vietnamese unit name" (0056:37, 40). ADR-0016 rule 18 and ADR-0053 rules 1 and 16 put the Vietnamese UI language and plain translations of core catalog names in the core, with only statutory names in the package terminology catalog (i18next JSON). `i18n/vi/unit_names.csv` is a third mechanism, and a Vietnamese-language user of a non-`l10n_vn` company gets English unit names.
- Fix: state the lookup path (the CSV feeds the package terminology keys `uom.<code>.name`) and the deliberate exception, with notes on ADR-0016 rules 18–19 and ADR-0053 rule 16. Or keep plain Vietnamese names in the core catalog and only e-invoice names in the package. This one is the author's ruling to confirm.
- `partner_item.uom_id` as a unit proposal (rule 13) amends ADR-0019 rule 6 without a note.

## Nits

- **N1 (0056:206-208).** Resolution step 3 says the code "equals the normalized text". Codes are upper case and `x-carton` contains a hyphen, so it never matches literally. The lab normalizes the code and the partner text (`t17_uom.py:240-242`); say so in the rule.
- **N2 (0056:204).** `đ → d` is a single-language special case in a core function; ø, ł and ß do not fold. Make it a general fold table, or say why only this one.
- **N3 (0056:39; `units.csv`).** "So that the common conversions are exact" holds only toward the smaller unit. KGM→TNE, LTR→MTQ and MLT→MTQ are inexact, and MIN↔HUR is inexact both ways. `units.csv` says of MTQ "3 decimals hold one litre", but a 3-decimal litre does not fit. Decimals bind forever, so consider 6 for TNE and MTQ, or correct the claim.
- **N4 (audit coverage).** Four audit points are neither resolved nor explicitly deferred:
  - U-21: no rounding value for production and transfer proposals (only implied by "identity");
  - U-23: rounding of co-product and by-product quantities;
  - U-25: `item_barcode` still has a composite key (`DS-20`, `PRIMARY KEY (company_id, barcode)`);
  - U-27: the glossary line for `service_receipt_line.inventory_quantity`.
  - Also not restated: U-18's "sales history is in the inventory unit" (it is only a DDL comment).
- **N5 (0056:300-306 against `invariants.csv`).** The INV-603 and INV-605 statements in the catalog say more than rule 25 (one active row; price entries and supplier items; no catalog-convertible product unit). Align the two texts. INV-605's area `platform` should probably be the master data area.
- **N6 (`t17_uom.py` INV-603 query, about lines 668-685).** It ignores `uom_factor_source` and level, so an item whose own active row equals a retired product-level factor is a false positive. It covers only two line tables.
- **N7 (0056:118; the `ck_*_uom_quantity` checks).** The bound is one whole inventory unit, not one step. For kg at 3 decimals, 0.9 kg of error passes. That matches the text, but the comment "which every rounding … satisfies" oversells it. A tighter bound needs the decimals; say it is a gross-error check only.
- **N8 (0056:67, 108; INV-603 "recorded after").** It is not stated whether a draft line snapshotted before a retirement may still post at the retired factor, or whether a re-priced draft finds its end-dated entries.
- **N9 (small items).**
  - 0056:125 "with an inexact snapshot" should say S's snapshot; parts in other units need no ordering.
  - `operation_progress_component` has no check that its source is `identity`, although the rule says it always is.
  - `check_package.py` does not fail when a core unit lacks a package name (only lab U48 does).
  - Price example 0056:183 shows 5 cartons (216,000) cheaper per carton than the 10-carton break (220,000); worth one sentence saying this is intended.

## Confirmed sound

- **Amendment discipline:** all 15 amended ADRs are changed by appended notes only; no accepted ADR or spec line is removed or edited. The glossary gets rows only. In-place edits are limited to design files (DS-04 rows, DS-16/DS-17 numbering sentences, backlog, lab README).
- **Exactness formula:** correct, scale-invariant, and matched by brute force (U18). All five examples are right.
- **Worked arithmetic:**
  - bag receipts 2.333 / 2.334 / 2.333 with GR/IR 69,990 / 70,020 / 69,990, net zero;
  - carton example 958,333 + 1,341,667 = 2,300,000;
  - `ck_*_positions` equals the inventory quantity;
  - three-way match per inventory unit (41.67 per piece);
  - price breaks 230,000 / 216,000 / 240,000 / 22,166.6666666667 / 23,333.3333333333;
  - credit in kg 42,857.1428571429 × 7 = 300,000;
  - planning 100 pieces → 5 cartons, 120, excess 20, and the half-up back-conversion never falls below the need;
  - paint 2.5 cans → 15.000 l;
  - scrap rounded once.
- **DDL:**
  - the unit block is on all 19 quantity line tables, NOT NULL where the quantity is required;
  - all-or-none via `num_nulls` on the three optional tables, so the checks are null-safe;
  - identity only at 1/1;
  - partial unique indexes with `NULLS NOT DISTINCT` work (PostgreSQL 18);
  - `product_uom` holds not-the-inventory-unit, same-product item and company through composite keys;
  - `uom_conversion` holds direction and pair uniqueness;
  - bill of materials defaults are dropped;
  - `supplier_item.order_uom_id` is NOT NULL.
- **Retire and replace:** snapshots, one active row, follow-on lines at the old factor and no fall-through on retired rows all work as stated (U11–U12, D34–D40).
- **Catalogs:** `units.csv` has 15 unique codes; `unit-conversions.csv` has 12 unique pairs, larger unit first, no chains needed. INV-600..605 and EC-101..109 have no duplicates and the blocks were free. The DS-04 codes are added.
- **Core neutrality:** no Vietnamese unit name in core catalogs or DDL beyond labelled examples; package names are all `unverified` with an open question.
- **Agent rule:** unknown unit text stays unresolved (`unit_text_unresolved`) with an alias proposal. ADR-0051, ADR-0030 and ADR-0044 are noted.
- **Public repo rule:** no customer information in the changes.
- **Coverage:** simulator observations 1–9 are all addressed. Audit U-01..U-29 are addressed except the points in N4. Phase 1 scope and the later seams are stated (rules 22–23).
