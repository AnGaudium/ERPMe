# Multi-UoM in major ERPs: research and design decisions

Date: 2026-11-15. Purpose: input for re-evaluating and completing the multi-UoM design of the target ERP (assembly-type manufacturers; deterministic core with exact rational quantities, one inventory unit per product for costing, versioned documents, GR/IR by unit positions, MRP, configurable products, Vietnamese overlay). Companion to `uom_audit.md` (audit of the current design), which this file does not repeat.

Scope: SAP S/4HANA, Microsoft Dynamics 365 Finance & SCM (plus Business Central, for one lesson), Odoo 17/18/19, Oracle NetSuite, SAP Business One, Oracle Fusion Cloud SCM. Statutory: Vietnam e-invoices. Standards: UN/ECE Rec 20/21, GS1.

Confidence markers: **[doc]** = vendor documentation; **[kba]** = vendor support note or official troubleshooting article; **[comm]** = community or third-party source; **[inf]** = my inference, not stated by a source. Several SAP help pages found are from older releases (4.6C/4.70/ERP 6.0); the concepts are unchanged in S/4HANA, but field-level details should be checked per release.

---

## 0. Executive summary

1. Every system studied keeps **stock and valuation in exactly one unit per product** (SAP base unit, D365 inventory unit, Odoo product/reference UoM, NetSuite base unit, B1 inventory UoM, Oracle primary UOM). The target ERP's rule "inventory and cost only in the inventory unit" matches the whole market. The only exception is catch weight, where SAP S/4HANA now values in the *parallel* unit (kg) while counting in the base unit (pieces) — a second, independent quantity, not a conversion.
2. Systems differ mainly in **where conversions live**: global per unit (NetSuite units types, Odoo categories before 19), per group shared by items (B1 UoM groups), per product (SAP MARM, D365 product-specific conversions, Oracle item-specific), per variant (D365 since 2019), per lot/batch (SAP batch-specific units, Oracle lot-specific conversions), per supplier (SAP info record conversion, Odoo 19 vendor unit). The trend of the last five years is toward **more specific scopes** (variant, lot, item-specific intraclass in Oracle 26A).
3. The recurring bug classes are: (a) **rounding drift** when converted quantities are rounded per transaction (Business Central's "5/6 box becomes 4.99998 pieces"; Odoo's 2101 instead of 2100; SAP MR11 proposing quantity differences on rounding); (b) **conversion changed while documents are open** (D365 "Released quantity cannot be negative" — official article names a changed conversion as the most common cause; Oracle now blocks such changes outright); (c) **price per wrong unit** inflating cost (SAP stock account off by the conversion factor after loading prices per carton as per each; Odoo valuation bugs when purchase UoM differs from stock UoM); (d) **floating-point factors** (Odoo floats; NetSuite 8-decimal rate). The target ERP's exact integer ratios already eliminate (d) and most of (c); (a) and (b) need two more explicit rules (below).
4. Decisions recommended for Phase 1 beyond what the current ADRs hold (details in §11):
   - **Snapshot the conversion on every document line** (numerator/denominator), never re-read it from master data after entry.
   - **Cumulative-difference rounding** for inexact conversions on lines that are received/issued/invoiced in parts, mirroring the GR/IR "rounded cumulative values" technique; and classify each product unit as *exact* or *inexact* at its decimal places.
   - **Follow-on documents may use a different unit** than their origin line (receive in pieces against a carton order, invoice per kg against an order in bars); linking, open quantities, tolerances and GR/IR are all in the inventory unit.
   - **Item-level (variant) override** of product units (D365 pattern), as an optional `item_id` on `product_uom`, resolved item → product → global.
   - **Supplier order unit** on `supplier_item` (one of the product's units; no supplier-specific factor — a different pack size is a different product unit).
   - **Immutable conversions with retire-and-replace**, not edits and not effective dates.
   - **Packaging hierarchy metadata** on product units (`contains` relation) and a **unit alias table** for agent intake of supplier documents; Vietnamese unit names via translations for e-invoices.
   - Keep **catch weight, batch-specific factors, cut-to-length remnants and separate order price units out of Phase 1**, with seams reserved.

---

## 1. SAP S/4HANA

### 1.1 Where conversions are defined
- **Global unit table** (T006, customizing "Units of measurement"): units by dimension with SI conversion, ISO code, decimal places and rounding decimals; units not convertible through T006 need a material-specific factor. **[doc]** [SAP Learning: Defining Units of Measurement](https://learning.sap.com/courses/cross-functional-customizing-in-sap-s-4hana-materials-management/defining-units-of-measurement); decimal/rounding fields DECAN/ANDEC discussed in SAP notes 442987 and 866505 **[comm]** ([SAP Community](https://groups.community.sap.com/t5/enterprise-resource-planning-q-a/re-what-is-the-standard-number-of-decimal-places-t006-decan-for-energy/qaq-p/427916/comment-id/28361)).
- **Per material**: table MARM holds each alternative unit with an integer ratio `UMREZ/UMREN` (numerator/denominator for conversion to base unit, 5 digits each), plus EAN, dimensions, gross weight and volume *per alternative unit*. **[doc/comm]** [MARM fields](https://leanx.eu/en/sap/table/marm.html); [SAP help ME60: units distinguished](https://help.sap.com/saphelp_me60/helpdata/en/a0/7cbd534f22b44ce10000000a174cb4/content.htm). "Only enter an alternative unit if it differs from the base unit" (error M3 332). **[kba]** [KBA 3559563](https://userapps.support.sap.com/sap/support/knowledge/en/3559563)
- **Per supplier**: the purchasing info record stores order unit, order price unit and the conversion between them; documents adopt them automatically. **[doc]** [SAP help: two units in a PO](https://help.sap.com/doc/saphelp_sfin100/1.9/en-US/af/7eb65334e6b54ce10000000a174cb4/content.htm). If info-record and material-master factors differ, the GR converts to base unit using the material master factor (message M7 235). **[comm]** [M7 235](https://michaelmanagement.com/sap-error-messages/en/m7/m7235)
- **Per batch**: batch-specific units of measure (proportion units, usage "A"; product units, usage "B") for materials whose ratio varies by batch; the material master holds a *planned* factor used until the batch is known, and the batch's characteristic holds the *actual* factor. Batches can be valued in the batch-specific unit (e.g. kg of active ingredient). **[doc]** [SAP help 4.70: valuation with BSUoM](https://help.sap.com/saphelp_470/helpdata/en/25/283db54f7811d18a150000e816ae6e/content.htm); [BSUoM in logistics](https://help.sap.com/saphelp_470/helpdata/EN/25/283d744f7811d18a150000e816ae6e/content.htm); steel example [SAP blog](https://blogs.sap.com/2010/02/22/batch-specific-units-of-measure-step-by-step-configuration-for-steel-industry/) **[comm]**.
- **Unit of measure groups** (customizing for quantity optimization) restrict which units rounding may switch to, per supplier or distribution chain. **[doc]** [SAP help: master data for quantity optimizing](https://help.sap.com/saphelp_46c/helpdata/en/4c/420d89470a11d1894a0000e8323352/content.htm)
- **EWM stock-specific units** add warehouse-only handling units of measure. **[doc]** [SAP Learning: stock-specific UoM](https://learning.sap.com/courses/advanced-customizing-in-sap-s-4hana-ewm/using-stock-specific-units-of-measure)

### 1.2 Units a line may use and defaults
- Base unit; **order unit** (Basic Data/Purchasing view), **sales unit** (sales org view), **unit of issue** (plant data) are proposed defaults; any alternative unit can replace them on the document. **[kba]** [KBA 3559563](https://userapps.support.sap.com/sap/support/knowledge/en/3559563); [SAP help ME60](https://help.sap.com/saphelp_me60/helpdata/en/a0/7cbd534f22b44ce10000000a174cb4/content.htm)
- **Variable order unit**: must be active on the material (or info record) to order in units other than the master's order unit; the info record's unit wins; when converting a requisition to a PO without it, the info record overwrites the requisition's unit; third-party orders adopt the sales unit. **[doc]** [SAP help 4.6C: units in POs](https://help.sap.com/saphelp_46C/helpdata/EN/75/ee0d5a55c811d189900000e8322d00/content.htm). SAP itself documents that the default chosen is not always obvious **[kba]** [KBA 3625025](https://userapps.support.sap.com/sap/support/knowledge/en/3625025); an S/4HANA Cloud info record can save an order unit not among the material's alternative units without warning **[kba]** [KBA 3734926](https://userapps.support.sap.com/sap/support/knowledge/en/3734926).
- Only units flagged as **commercial units** can be used in purchasing. **[doc]** (same help page).

### 1.3 Quantity and price on lines
- A PO item carries **order unit** (quantity) and **order price unit** (price basis, e.g. order boxes, price per kg) with a conversion factor; the order price unit is the **basis for invoice verification**. **[doc]** [SAP help: two units in a PO](https://help.sap.com/doc/saphelp_sfin100/1.9/en-US/af/7eb65334e6b54ce10000000a174cb4/content.htm)
- Prices also have a **price quantity** (PEINH on PO, KPEIN in conditions, integer, e.g. per 100 PC) and condition unit KMEIN with its own conversion KUMZA/KUMNE; scales have their own scale unit KONMS. **[comm]** [KONP/KOND fields](https://leanx.eu/en/sap/table/kond.html); decimals not allowed in PEINH/KPEIN **[kba]** [KBA 3443866](https://userapps.support.sap.com/sap/support/knowledge/en/3443866).
- Rounding of PO quantities follows T006 decimal rounding and rounding profiles; BAPI and dialog behave differently. **[kba]** [KBA 2413079](https://userapps.support.sap.com/sap/support/knowledge/en/2413079), [KBA 3550038](https://userapps.support.sap.com/sap/support/knowledge/en/3550038)

### 1.4 Inventory, valuation, costing
- Stock is managed in the base unit; all entered quantities convert to it. **[doc]** (ME60 page). Moving average/standard price per base unit (MBEW). **[comm]** [SAPinsider on MAP](https://sapinsider.org/moving-average-price-learn-how-it-functions-in-project-stock-and-figure-out-how-to-explain-the-unexplainable/)
- Exceptions: BSUoM valuation per proportion unit; catch weight valuation in the parallel unit (§1.6).

### 1.5 Receipts, issues, handling units
- GR may be entered in any alternative unit; when order price unit ≠ order unit, the GR is recorded **in both** and invoice verification uses the GR quantity in order price unit (field BPMNG); if only order unit is entered, the system derives the price-unit quantity from the PO factor and the user may override. **[doc/comm]** [SAP Learning: order price unit in IM](https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/applying-order-price-unit-in-inventory-management); [M7 027](https://michaelmanagement.com/sap-error-messages/en/m7/m7027)
- Packaging: alternative units per material + packing instructions + handling units (EWM). Changing base unit is blocked when the material is in packing instructions. **[kba]** [KBA 2788475](https://userapps.support.sap.com/sap/support/knowledge/en/2788475)

### 1.6 Variable / approximate conversions
- **Catch weight management (CWM)**: base unit plus one **parallel unit**, the valuation unit may be the parallel unit; both quantities are recorded per movement; tolerance groups check the actual ratio. In S/4HANA the category where the base unit is the valuation unit ("B") is not supported; materials typically have base unit CAR/PC/EA and KG as parallel and valuation unit; business function /CWM/CM_1 is required. Only one parallel unit; changing it is no longer possible in S/4HANA. **[comm/kba]** [SAP blog 2022: CWM change in S/4HANA](https://blogs.sap.com/2022/02/06/change-in-catch-weight-management-in-s-4hana-and-extended-warehouse-management-on-s-4hana/); [EWM help: parallel/valuation unit](https://help.sap.com/doc/saphelp_ewm92/9.2/en-US/e5/c9cb53ad377114e10000000a174cb4/content.htm); [tolerance groups](https://help.sap.com/doc/be9dcf535b804808e10000000a174cb4/1610%20002/en-US/fa9ccf535b804808e10000000a174cb4.html); [KBA 3424138](https://userapps.support.sap.com/sap/support/knowledge/en/3424138), [KBA 3448084](https://userapps.support.sap.com/sap/support/knowledge/en/3448084), [KBA 3586490](https://userapps.support.sap.com/sap/support/knowledge/en/3586490)
- **Batch-specific units** (planned vs actual factor), §1.1.
- **Cut-to-length in BOMs**: *variable-size items* (item category R) with sizes 1–3 and a formula (OS15); quantity returned in the component's base unit; number of variable-size pieces kept separately. **[doc/comm]** [SAP help: shape and size variants](https://help.sap.com/saphelp_470/helpdata/en/92/58c3e2417011d189ec0000e81ddfac/content.htm); [SAP Answers: item category R](https://answers.sap.com/questions/3647892/help-understanding-the-item-category-r-in-boms.html)

### 1.7 Purchasing, invoice, GR/IR
- Order unit vs order price unit vs base unit as above. A **price-quantity variance** arises when the invoice's ratio of price-unit quantity to order-unit quantity differs from the GR or order ratio. **[doc]** [SAP help 4.70: variance in order price quantity](https://help.sap.com/saphelp_470/helpdata/en/47/60f9d049f011d1894c0000e829fbbd/content.htm)
- **GR/IR**: the GR/IR journal stores quantities **in the order unit**; GR/IR account maintenance (MR11) adjusts invoice quantity to GR quantity. **[doc]** [SAP help: GR/IR clearing account maintenance](https://help.sap.com/saphelp_46C/helpdata/EN/47/6100f249f011d1894c0000e829fbbd/content.htm). Known issues: MR11 proposes a quantity difference although PO history totals match; MR11 processes unexpected quantities including rounding cases. **[kba]** [KBA 3065375](https://userapps.support.sap.com/sap/support/knowledge/en/3065375), [KBA 3638409](https://userapps.support.sap.com/sap/support/knowledge/en/3638409)

### 1.8 Sales
- Sales unit proposed and replaceable; **delivery unit** (only exact multiples can be delivered), **minimum order** and **minimum delivery quantity** (warnings, not blocks) on the sales-org view; rounding profiles for sales. **[doc]** [SAP help 4.6C: units and quantity specifications](https://help.sap.com/saphelp_46c/helpdata/en/dd/55f68b545a11d1a7020000e829fd11/content.htm); [SAP blog: rounding permitted](https://blogs.sap.com/2020/03/03/how-to-use-rounding-permitted/) **[comm]**; delivery unit not enforced on scheduling agreements **[kba]** [KBA 3394363](https://userapps.support.sap.com/sap/support/knowledge/en/3394363)
- Condition records priced per KMEIN/KPEIN; scales per scale unit (§1.3).

### 1.9 Manufacturing and MRP
- BOM item quantity in any unit of the component; MRP nets in base unit. **[inf, standard SAP behavior]**
- **Assembly scrap** (MRP 1, increases lot size), **component scrap** (BOM item overrides MRP 4), **operation scrap** (routing). **[doc]** [Component scrap](https://help.sap.com/doc/6297d7531a4d414de10000000a174cb4/1610%20002/en-US/d195d7531a4d414de10000000a174cb4.html); [Assembly scrap](https://help.sap.com/doc/6297d7531a4d414de10000000a174cb4/1610%20002/en-US/cb95d7531a4d414de10000000a174cb4.html)
- Lot-size **rounding value** and **rounding profiles** (static thresholds; dynamic profiles that round up to carton/layer/pallet with per-unit round-up percentages, needing the variable order unit to switch to a larger unit). **[doc]** [SAP help 3.6: dynamic rounding profile](https://help.sap.com/doc/9ea8c7536e8e2a4be10000000a174cb4/3.6/en-US/6951b9537cceb44ce10000000a174cb4.html); [Rounding profile](https://help.sap.com/SAPHelp_46c/helpdata/EN/f4/7d28c844af11d182b40000e829fbfe/content.htm)

### 1.10 Changing conversions after transactions
- Base unit **cannot be changed** once stock, open POs/SOs, BOMs, packing instructions etc. exist; MM02 "Display errors" lists blockers. **[comm/kba]** [SAP Answers](https://answers.sap.com/t5/enterprise-resource-planning-q-a/can-t-change-base-unit-of-measure/m-p/4495003), [KBA 2788475](https://userapps.support.sap.com/sap/support/knowledge/en/2788475), [KBA 3627935](https://userapps.support.sap.com/sap/support/knowledge/en/3627935). Alternative-unit factors are similarly guarded by use **[comm]**. No effective dating of MARM factors.

### 1.11 Precision
- Per-unit decimal places and rounding decimals in T006; integer ratio in MARM; integer price quantity. **[doc/comm]** above.

### 1.12 Reports, e-invoices, EDI
- ISO code per unit in T006 for EDI; internal vs external codes (EA stored as ST) cause load failures; ANSI vs ISO mapping needed. **[comm]** [SAPinsider: 11 UoM errors](https://sapinsider.org/avoid-these-11-common-unit-of-measure-errors/)

---

## 2. Microsoft Dynamics 365 Finance & SCM

### 2.1 Where conversions are defined
- **Units** with unit class, system of units, **base unit per class**, **system unit**, and **decimal precision** per unit. **Standard conversions** (all products), **intra-class** (per product, same class), **inter-class** (per product, across classes, e.g. kg↔ea). Each conversion has a **rounding** option (nearest/up/down) applied at the *target* unit's decimal precision; simple factor or advanced formula. **[doc]** [Manage units of measure](https://learn.microsoft.com/en-us/dynamics365/supply-chain/pim/tasks/manage-unit-measure)
- **Per variant** (feature *Unit of measure conversions for product variants*): conversion for a product variant, with the product-master conversion as fallback; not available for catch-weight products. Example: XL shirts 4 per box, other sizes 5. **[doc]** [UoM conversion per product variant](https://learn.microsoft.com/en-us/dynamics365/supply-chain/pim/uom-conversion-per-product-variant)
- **Per vendor and unit**: external item description per (item, vendor, unit) **[comm]** [External item description by unit](https://docs.staedean.com/life-sciences/docs/external-item-description-by-unit).
- Inter-class conversions must be set up for every needed pair, and rounding in chained conversions can cause unwanted results. **[comm]** [Price unit product documentation](https://innovation-product-documentation.azurewebsites.net/PRI-PriceUnit.html)

### 2.2 Units on lines and defaults
- Released product holds inventory, purchase and sales units; **default order settings** per purchase/inventory/sales give default site, standard quantity, **minimum, maximum and multiple**, with rules per site/variant/configuration by rank; *Multiple is mandatory* forces the multiple. **[doc]** [Unit sequence groups (default order settings section)](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/unit-measure-stocking-policies); [Default order settings](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/default-order-settings); [PRI-MultipleIsMandatory](https://innovation-product-documentation.azurewebsites.net/PRI-MultipleIsMandatory.html) **[comm]**
- **Unit translations** per language for external documents (unit texts, translated descriptions). **[doc]** [Manage units of measure](https://learn.microsoft.com/en-us/dynamics365/supply-chain/pim/tasks/manage-unit-measure)

### 2.3 Quantity and price on lines
- Order line holds quantity in purchase (or sales) unit; the inventory transaction holds the inventory-unit quantity. On the vendor invoice the purchase-unit quantity drives the liability and the inventory-unit quantity drives stock; synchronization is **one-way** and editing only the inventory quantity creates inconsistency. **[doc]** [Microsoft blog: quantities in PO and inventory transaction](https://www.microsoft.com/en-us/dynamics-365/blog/it-professional/2015/01/31/quantities-in-purchase-order-and-inventory-transaction/)
- **Price unit** (price quantity): net amount = quantity × price / price unit. **[comm]** [Encore: procurement pricing](https://www.encorebusiness.com/blog/pricing-options-dynamics-365-finance-operations/); [tier pricing](https://onlinehelpcrm.azurewebsites.net/HelpFiles/SB_D365FO_Help/Content/Topics/AX_ARCB/concept/conTierPricing.htm)
- Trade agreements hold price per unit with from/to quantity. **[doc]** [Create trade agreement](https://learn.microsoft.com/en-us/dynamics365/supply-chain/sales-marketing/tasks/create-new-trade-agreement)

### 2.4 Inventory and costing
- Inventory unit is the base for on-hand; costing per inventory unit. For catch weight the inventory unit is the weight (kg) and the CW unit (box) is the count. **[doc]** [Unit sequence groups](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/unit-measure-stocking-policies); [Catch weight processing](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/catch-weight-processing)

### 2.5 Warehouse handling and packaging
- **Unit sequence group**: units smallest → largest (e.g. Pcs, Box, PL); first unit must equal the inventory unit; per line: license plate grouping, cycle-counting units (max 4), default unit for purchase/transfer receiving, for production reporting, for material consumption, container type, wave label type. Work is created in the **largest unit that represents the quantity as a whole number**. Mixing unit classes in one group warns about unexpected rounding. Default order settings and sequence groups are independent and must be kept consistent. **[doc]** [Set up unit sequence groups](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/unit-measure-stocking-policies)

### 2.6 Variable conversions (catch weight)
- Nominal quantity (e.g. 5 kg per box) in the unit conversion; **min/max per CW unit**; item handling policy says when weight is captured (picking or packing), per CW unit or per picking unit, with or without **catch weight tags** (one tag per box with its weight); weight variance on storage posts automatic adjustments to **catch weight loss/profit accounts**; reservation uses the minimum weight; orders must be in the CW unit. A long list of unsupported scenarios (no BOM-based production — formulas only, no serials, no kanban, no ASN weights, no cluster picking...). **[doc]** [Catch weight processing](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/catch-weight-processing)
- BOM formulas with height/width/depth/density × constant for dimension-driven consumption. **[doc]** [Calculate material consumption](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/consumption)

### 2.7 Purchasing and matching
- Two/three-way matching compares invoice **net unit price** with the PO's, and receipt quantity with invoice quantity; tolerances by item, item group, vendor, combinations or legal entity; matching by unit price or optionally price total. **[doc]** [Three-way matching policies](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/three-way-matching-policies); [Invoice matching](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/accounts-payable-invoice-matching). Matching is on the PO line's quantity/price basis (purchase unit) **[inf]**.

### 2.8 Sales
- Sales unit default; trade agreements per unit with quantity brackets; default order settings minimum/multiple for sales. **[doc]** (above)

### 2.9 Manufacturing
- BOM line unit; **constant vs variable** consumption; formulas; **rounding-up** by *Quantity* (multiple), *Measurement* (e.g. 2 m pieces cut from 4.5 m tubes) or *Consumption* (round to whole 25-quart cans: 360 → 375); step consumption. Scrap: constant and variable scrap on BOM lines. **[doc]** [Calculate material consumption](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/consumption); [Scrap calculations](https://learn.microsoft.com/sk-sk/dynamics365/supply-chain/master-planning/scrap-calculations). Rounding can be inaccurate in multilevel explosion with line type "item" — by design **[kba]** [KA-23761](https://community.dynamics.com/article/KA-23761).

### 2.10 Changing conversions
- Not blocked by design: Microsoft's own troubleshooting article states the **most common cause** of "Released quantity cannot be negative" is a conversion changed while load lines are open (50 Ea = 1 PL → 100 Ea = 1 PL); the fix is to revert the conversion temporarily, or edit released quantities by hand, and to stop processing other loads meanwhile. **[kba]** [Released quantity cannot be negative](https://learn.microsoft.com/en-us/dynamics365/supply-chain/troubleshooting/warehousing/released-qty-cannot-be-negative)
- I found no official page on changing a released product's inventory unit after transactions; practitioners treat it as not possible without zeroing stock. **[comm/inf]**

### 2.11 Precision
- Decimal precision per unit; rounding mode per conversion. Changing a unit's decimals has side effects. **[doc/comm]** [Manage units of measure](https://learn.microsoft.com/en-us/dynamics365/supply-chain/pim/tasks/manage-unit-measure); [Logan: units, conversions and decimals](https://www.loganconsulting.com/blog/units-conversions-and-decimal-places-in-dynamics-365-for-operations/)

### 2.12 Business Central (same vendor, SMB product) — one lesson
- Item units with **Qty. per Unit of Measure** and, since 2021 wave 2, **Quantity Rounding Precision**, introduced because receiving 5/6 of a box of 6 "would lead to a receipt of 4.99998 pieces, rather than five". **[doc]** [BC: set up item units of measure](https://learn.microsoft.com/en-us/dynamics365/business-central/inventory-how-setup-units-of-measure); [Release plan: rounding for base unit](https://learn.microsoft.com/en-us/dynamics365-release-plan/2021wave2/smb/dynamics365-business-central/rounding-base-unit-measure). Also a **manufacturing batch unit** (produce in tons, stock in pieces). **[doc]**

---

## 3. Odoo 17 / 18 / 19

### 3.1 Where conversions are defined
- **17/18**: units belong to **categories**; conversion only within a category; one reference unit per category; ratio "bigger/smaller than reference"; rounding precision per unit. **[doc]** [Odoo 17: units of measure](https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/inventory/product_management/configure/uom.html). Per-product factors are not native: a "carton of 24" for one product and "of 12" for another require two global units **[inf]**.
- **Packagings** (17/18): `product.packaging` per product with quantity and barcode, separate from UoM. **[doc/comm]**
- **19**: categories **removed**; each unit may reference another unit (`relative_uom_id`) with a `relative_factor` (hierarchies such as pallet → case → unit); absolute factor computed; **packaging merged into UoM** — a packaging is a unit with a quantity and optional package type, attached to products by `uom_ids`, barcode per product and packaging; `uom_po_id` removed and the **vendor's unit** (on the vendor pricelist line) is used on POs; orderpoint `qty_multiple` replaced by `replenishment_uom_id`; per-unit `rounding` removed in favor of the global "Product Unit of Measure" decimal accuracy. Rationale stated in the PR: "no intrinsic difference between a packaging and a unit", and separate unit/packaging fields on lines confused users. **[doc]** [odoo/odoo PR 184131](https://mergebot.odoo.com/odoo/odoo/pull/184131). A consultant guide claims `rounding` is retained and warns of migration hazards (orphan units, valuation drift after migration) — conflicts with the PR on rounding; trust the PR. **[comm]** [Octura: death of uom.category](https://octurasolutions.com/resources/the-death-of-uom-category-odoo-19-migration-guide)

### 3.2 Units on lines and defaults
- Sales lines default to the product UoM; purchase lines to the purchase UoM (17/18) or the vendor pricelist unit (19); replenishment POs use the purchase unit; "Purchase units must be in the same category as the default unit" (17/18). **[doc]** [Odoo 19: units of measure](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/product_management/configure/uom.html)

### 3.3 Quantity and price
- Lines store quantity and unit; price per line unit; conversion to product UoM at stock move. Quantities and factors are **floats** (double precision with a configured decimal accuracy), not decimals **[inf from Odoo ORM]**. Pricelist rules are per product; native per-UoM pricelist rules are provided only by community modules (e.g. OCA *product_pricelist_item_uom*, which warns that prices must be proportional to the product UoM). **[comm]** [OCA product-pricelist-item-uom](https://pypi.org/project/odoo-addon-product-pricelist-item-uom/)

### 3.4 Inventory and costing
- Stock and valuation layers in the product UoM. **[doc]** (Odoo 19 page)

### 3.5 Receipts and packaging
- PO quantities convert to inventory UoM on receipt (e.g. 2 dozen → 24 units). **[doc]** (Odoo 17 page). Community reports packagings not converting on manual receipts in 18. **[comm]** [Odoo forum 285525](https://www.odoo.com/forum/help-1/packaging-quantities-not-converting-automatically-in-manual-receipts-odoo-18-285525). "Sell only by packaging" (block or auto-round quantities to packaging multiples) is an OCA module, not core. **[comm]** [sell_only_by_packaging](https://apps.odoo.com/apps/modules/18.0/sell_only_by_packaging)

### 3.6 Variable conversions
- None native (no catch weight); 19 allows buying in pieces and selling in kg without categories, but the factor is still fixed. **[doc]** (PR 184131)

### 3.7–3.9 Purchasing, sales, manufacturing
- Vendor pricelist lines carry min quantity and unit (19: the vendor unit). BoM lines take a unit; MO component quantities are converted and rounded by UoM rounding — many forum threads about MO rounding; an OCA module validates BoM quantities against UoM rounding. **[comm]** [mrp_bom_line_uom_rounding](https://pypi.org/project/odoo-addon-mrp-bom-line-uom-rounding/); [Odoo forum 281030](https://www.odoo.com/hi_IN/forum/help-1/rounding-issue-in-manufacturing-order-when-consuming-raw-materials-with-decimal-precision-odoo-18-281030)

### 3.10 Changing conversions
- Not blocked in general; changing done move UoMs once left quants inconsistent (fixed in 2021). **[comm]** [OCB commit](https://git.coopdevs.org/coopdevs/odoo/OCB/-/commit/d813873f6c841feea361a9e4f761a9324ff7c956)

### 3.11 Precision and known defects
- Historical defect list: inventory wrong when purchase UoM ≠ default UoM [LP 488736](https://bugs.launchpad.net/bugs/488736); valuation wrong for moves with purchase unit ≠ UoM [LP 889093](https://launchpad.net/bugs/889093); pack UoM with rounding 1 giving 2101 instead of 2100 [LP 842758](https://bugs.launchpad.net/bugs/842758); request for ceiling instead of half rounding in conversions [LP 1280463](https://bugs.launchpad.net/bugs/1280463); intermediate rounding removed from `_compute_qty` [commit](https://gitea.sysmocom.de/odoo/odoo/commits/commit/d37dd370599bdf2cf8b2be4656f1fe3d110770ce/addons/product/product.py); doubled unit cost on bill in 19 (forum, unconfirmed) [forum 288324](https://www.odoo.com/forum/help-1/odoo-uom-miscalculation-288324). **[comm]**

---

## 4. Oracle NetSuite

- **Units types** (Length, Weight, Each/Case...) with one **base unit** (rate locked at 1) and other units by **conversion rate** = base units per unit; conversions are **global to the units type**, not per item (so "case of 24" vs "case of 12" need separate types). Items get one units type and default **purchase, stock, sale and consumption** units. **[doc]** [Setting up units of measure](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2212143.html); [Assigning units to items](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2212390.html); per-type rates confirmed by community [forum](https://archive.netsuiteprofessionals.com/t/28063219/is-there-a-way-to-convert-between-two-different-unit-types-e) **[comm]**
- "Stock unit" is a display/default; quantities are stored in base units; a line cannot exceed 9,999,999,999 base units — likely with small base units and big rates. Rate precision about 8 decimals **[comm]**. **[doc]** (setting-up page)
- Restrictions: after a units type is assigned to any item it can only gain units; an item's units type cannot change; purchase and sale units fixed after save, stock unit changeable; changing the purchase unit converts standard cost. **[doc]** (same)
- Assemblies: builds, unbuilds and work orders in **base units only**; serialized assemblies need integer conversions and serial count = base quantity. **[doc]** [Assemblies and units of measure](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2320172.html); [Serial and lot with multiple UoM](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2214525.html)
- Transactions default: PO in purchase units, invoice in sale units, adjustments in stock units; receipts and fulfillments editable in the source order's units; reports show the units used in transactions. **[doc]** (assemblies page)
- No catch weight in core **[inf]**.

---

## 5. SAP Business One

- **Global UoM master**; **UoM groups** define conversions (Alt. Qty / Base Qty pairs, i.e. a rational) to a base UoM; one group serves many items; the embedded **Manual** group allows free entry. **[doc]** [B1 help: UoM groups](https://help.sap.com/saphelp_sbo900/helpdata/en/64/1a2505ffb142f6bc4de5a800b6b119/content.htm); [SAP Learning: UoM in B1](https://learning.sap.com/courses/managing-logistics-in-sap-business-one/working-with-units-of-measure-uom-in-sap-business-one)
- Item: one **inventory UoM** (all postings, cannot change once transactions exist), several purchasing and sales UoMs with defaults; documents may use any unit of the group; postings go to inventory UoM (1 carton of 24 posts 24). **[doc]** (SAP Learning)
- Per UoM: barcodes, **price per UoM in price lists** (UoM prices window, not for Manual), and **packaging types** with quantity per package (a level above sales unit: 10 cases per container). **[doc]** [B1 help: UoM prices](https://help.sap.com/saphelp_sbo900/helpdata/en/b6/c2d489a3f64bc5b15f103796b7e74c/content.htm); quantity per package ≥ 1 **[kba]** [KBA 3477493](https://userapps.support.sap.com/sap/support/knowledge/en/3477493)
- Changing rates: blocked while open documents contain the item; workaround: new group with the same units, reassign, change after open documents close; a group can be replaced only by one containing the original rules. **[doc/kba]** (SAP Learning); [KBA 3365952 title](https://userapps.support.sap.com/sap/support/knowledge/en/3365952)
- No catch weight in core (partner add-ons). **[inf]**

---

## 6. Oracle Fusion Cloud SCM (the additional system)

- **UOM classes** with a base unit; **standard conversions** (unit ↔ class base), **intraclass** item-specific conversions, **interclass** item-specific (or global) conversions between class bases; item-specific wins over standard. 25A merged intra/interclass into one item-specific task; 26A WMS added item-specific intraclass computing. **[doc]** [What's a UOM interclass conversion](https://docs.oracle.com/en/cloud/saas/procurement/24c/oapro/what-s-a-uom-interclass-conversion.html); [25A Redwood UOM](https://docs.oracle.com/en/cloud/saas/readiness/scm/25a/plm25a/25A-plm-wn-f35771.htm); [26A item-specific intraclass](https://docs.oracle.com/en/cloud/saas/readiness/logistics/26a/wms26a/26A-wms-wn-f42720.htm); packaging string auto-creates conversions [24C](https://docs.oracle.com/en/cloud/saas/readiness/scm/24c/plm24c/24C-plm-wn-f33227.htm)
- **Lot-specific conversions**: e.g. standard 1 gal = 15 lb, a particular lot 1 gal = 16 lb; allowed for on-hand or zero-balance lots. **[doc]** [26A lot-specific UOM conversions](https://docs.oracle.com/en/cloud/saas/readiness/scm/26a/inv26a/26A-inventory-wn-f41700.htm)
- **Dual UOM** (primary + secondary quantities tracked): defaulting control *Fixed* (secondary = primary × conversion; Oracle support notes secondary on-hand can drift out of sync through accumulated rounding), *Default* or *No Default* with **positive/negative deviation factors** (e.g. ±10% around 1 Ea = 10 lb); **residual quantity transactions** clean up the secondary balance when the primary hits zero. **[doc]** [Set up dual units of measure](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/faims/set-up-dual-units-of-measure.html); [Manage leftovers for dual measures](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/famml/residual-quantity-transactions-with-dual-uoms.html)
- **Changing a conversion is blocked** while the item has on-hand stock, pending or uncosted transactions, unreceived inbound lines, un-put-away receipts, unshipped outbound lines, pending counts or adjustments; for interclass changes, any transaction in any unit of the other class blocks. **[doc]** [Inventory transactions verified when a UOM conversion is updated](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/faicf/inventory-transactions-verified-when-a-uom-conversion-is-updated.html)
- Order in one unit, receive/transfer/ship in another; UOM conversions view on transaction pages. **[doc]** [UOM conversions for inventory, receiving and shipping](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/famml/uom-conversions-for-inventory-receiving-and-shipping.html)

(Epicor and Infor were checked briefly: Epicor uses UOM classes with a base unit and per-part conversions, and practitioners warn that changing a part's UOM class or primary inventory UOM after transactions causes problems **[comm]** [EpiUsers](https://www.epiusers.help/t/uom-conversion-how-to-use/35466.md); no authoritative Infor CloudSuite Industrial documentation was found, so neither is in the matrix.)

---

## 7. Statutory e-invoices (Vietnam), EDI and GS1

- **Vietnam**: Decree 123/2020/ND-CP, Article 10 clause 6 lists the name, **unit of measure (đơn vị tính)**, quantity and unit price of goods/services as invoice content. Commentary: the seller determines the unit "based on the nature and characteristics of the goods" (examples: tấn, kg, cái, chiếc, hộp, thùng, bao, gói, m², m³); the unit is mandatory for goods and not necessarily for services; fixed-face-value stamps/tickets/cards are exempt (clause 14). Goods names must be in Vietnamese. Clause 6 was amended by Decree 70/2025/ND-CP, in force 1 June 2025 — check the consolidated text. **[comm, legal portals]** [LuatVietnam](https://luatvietnam.vn/thue-phi-le-phi/cach-ghi-don-vi-tinh-tren-hoa-don-dien-tu-theo-nghi-dinh-123-565-95759-article.html); [Thư viện pháp luật](https://thuvienphapluat.vn/hoi-dap-phap-luat/quy-dinh-ten-hang-hoa-tren-hoa-don-dien-tu-nhu-the-nao-138008657.html); [Decree 70 note](https://thuvienphapluat.vn/hoi-dap-phap-luat/ghi-ten-hang-hoa-tren-hoa-don-bang-tieng-anh-duoc-khong-138067007.html); [Decree 123 clause 6](https://hethongphapluat.com/nghi-dinh-123-2020-nd-cp-quy-dinh-ve-hoa-don-chung-tu/khoan-6-dieu-10)
- The XML format (Decision 1450/QĐ-TCT, amended by 1510/QĐ-TCT) carries the unit as **text per line** (tag commonly `DVTinh`); its maximum length was not confirmed in this research. **[comm]** [Decision 1450 text](https://thuvienphapluat.vn/van-ban/thue-phi-le-phi/quyet-dinh-1450-qd-tct-2021-thanh-phan-chua-du-lieu-nghiep-vu-hoa-don-dien-tu-490526.aspx). Implication **[inf]**: the invoice shows the **line's own unit name in Vietnamese**, not a code; a later e-invoice line must show the unit the goods were sold in.
- **UN/ECE Recommendation 20** codes (e.g. C62 "one", H87 "piece", KGM, MTR) are the unit code list for EN 16931/Peppol and many national e-invoice schemes (Malaysia MyInvois). Revision numbering differs between lists. **[doc]** [Peppol Rec 20 code list](https://docs.peppol.eu/pracc/espd/codelist/UNECERec20); [MyInvois unit types](https://sdk.myinvois.hasil.gov.my/codes/unit-types/); [UN digital library](https://digitallibrary.un.org/record/635432/files/%5BE_%5DECE_TRADE_C_CEFACT_2008_6-EN.pdf). Package types (box, carton, pallet) are **Recommendation 21**, a different list **[inf: not confirmed in this research's sources]**.
- **GS1**: each packaging level of a trade item (each, inner, case, pallet) gets its own GTIN, and the hierarchy records the quantity of the next lower level; logistic units (pallets as shipped) use SSCC, not GTIN. **[doc/comm]** [GS1 Sweden: trade item hierarchies](https://gs1.se/en/support/what-are-trade-item-hierarchies-and-trade-item-levels-2/); [GS1 trade item unit descriptor codes](https://gs1.se/en/guides/documentation/code-lists/t4010-trade-item-unit-descriptor-code/); [Syndigo: packaging hierarchies](https://community.syndigo.com/t5/Syndication-GDSN/Packaging-Hierarchies-Explained/ta-p/23137) **[comm]**

---

## 8. Pitfalls and lessons (cross-system)

| # | Pitfall | Evidence | Lesson for the target ERP |
|---|---|---|---|
| P1 | **Per-transaction rounding drift** with inexact conversions (5/6 box → 4.99998 pcs; 2101 vs 2100; MR11 rounding differences; Oracle "Fixed" dual UOM secondary drifts) | BC docs; Odoo LP 842758; SAP KBA 3638409; Oracle dual UOM docs | Exact rationals alone are not enough once results are rounded to the inventory unit's decimals. Round **cumulative** quantities per line and post differences; let users enter the follow-on line in the inventory unit. |
| P2 | **Conversion changed while documents are open** | D365 troubleshooting (most common cause of negative released qty); Oracle blocks updates; B1 blocks while open docs exist | Snapshot factor on each line; make product units immutable once used; retire-and-replace for future documents. |
| P3 | **Price per wrong unit** (prices loaded per carton read as per each; info record factor ≠ master factor; purchase UoM ≠ stock UoM valuation bugs) | SAP Community 900-material case; M7 235; Odoo LP 889093 | Every price row names its unit (already); cost per inventory unit derived only from line amount ÷ inventory quantity; no second factor anywhere (no supplier-specific factor). |
| P4 | **Floating or limited-precision factors** | Odoo floats; NetSuite ~8 decimals and 10-digit base limit; D365 decimal factors | Keep integer numerator/denominator (already ADR-0006 rule 11). |
| P5 | **Two independent unit settings that must agree** (D365 default order settings vs unit sequence group; SAP order unit vs info record vs variable order unit; Odoo 17/18 unit vs packaging fields) | D365 docs; SAP KBAs 3625025, 3734926; Odoo PR 184131 rationale | One list of product units, used by purchasing, sales, warehouse and barcodes; packaging *is* a product unit (Odoo 19 conclusion). |
| P6 | **Default unit not obvious** | SAP KBA 3625025 | One documented precedence for the proposed unit, returned with its source in the response (agent-readable). |
| P7 | **Base/inventory unit chosen too large or too small** | SAPinsider (precision loss vs overflow); NetSuite 10-digit limit | Guidance and a check: inventory unit = smallest unit counted/sold; decimal places fit the smallest fraction issued. |
| P8 | **Internal vs external codes, ANSI vs ISO** | SAPinsider | `uom.code` = Rec 20 where it exists; company units `x-`; external mappings per partner/channel. |
| P9 | **Catch weight is a feature swamp** | D365's long unsupported-scenario list; SAP S/4 change of valuation category | Do not enter catch weight half-way in Phase 1; reserve the seam. |
| P10 | **Packaging rounding left to add-ons** | Odoo OCA sell-by-packaging; SAP delivery unit only warns; D365 "multiple is mandatory" | Make multiples/minimums explicit data with check results, not silent rounding. |
| P11 | **Serial items with fractional conversions** | NetSuite rule | Serial products: integer factors only. |

---

## 9. Answers to the 12 questions, condensed

| Question | SAP S/4HANA | D365 F&SCM | Odoo 17/18 → 19 | NetSuite | SAP B1 | Oracle Fusion |
|---|---|---|---|---|---|---|
| 1. Conversion scope | Global (T006) + per material (MARM, integer ratio) + per supplier (info record OUn↔OPUn) + per batch (BSUoM) | Standard (global) + per product intra/inter-class + per variant (fallback to master) | Category-global (17/18); unit hierarchy, packaging as unit, per product attachment (19) | Per units type (shared by items) | Per UoM group (shared by items), rational pair | Standard (class) + item-specific + lot-specific |
| 2. Line units / default | Any alternative unit; order/sales/issue unit; info record unit wins with variable OUn | Any convertible unit; purchase/sales/inventory unit; default order settings rules | Any unit of category (17/18), any related unit (19); purchase UoM / vendor unit | Units of the type; purchase/sale/stock defaults | Units of the group; default purchase/sales UoM | Any convertible UOM; item primary |
| 3. Qty and price storage | Qty in OUn + base; price per OPUn × price quantity (PEINH) | Qty in line unit + inventory qty; price per line unit / price unit | Qty + unit (float); price per line unit | Qty in line units, stored base | Qty in line UoM + inventory qty; price per UoM | Transaction qty + primary qty |
| 4. Valuation unit | Base unit (CWM: parallel unit; BSUoM optional) | Inventory unit (CW: weight) | Product UoM | Base unit | Inventory UoM | Primary UOM |
| 5. Other units on receipt/issue; packaging | Yes; both OUn and OPUn on GR; alt units + packing instructions + HUs | Yes; unit sequence groups, work in largest whole unit, license plates | Yes; packagings (17/18), packaging = unit (19) | Receipts in source order units | Yes; packaging types above sales unit | Yes; packaging strings |
| 6. Variable conversions | CWM (parallel unit, tolerance groups); BSUoM; variable-size BOM items | Catch weight (nominal, min/max, tags, variance accounts); BOM formulas | None | None | None | Dual UOM with deviation; lot-specific factors |
| 7. Purchasing / IV / GR/IR | IV in OPUn; tolerances DQ/PP; GR/IR journal in OUn; MR11 | Match unit price and qty per PO line; tolerances by item/vendor | Vendor unit on PO; 2/3-way billing control | PO in purchase units | PO in purchasing UoM | Order in one, receive in another |
| 8. Sales | Sales unit, delivery unit multiples, min order/delivery (warnings), scales per scale unit | Trade agreements per unit + brackets; min/multiple | Pricelists per product UoM; packaging rules via OCA | Sale unit; price levels | Price per UoM in price lists | — |
| 9. Manufacturing / MRP | BOM unit any; MRP base unit; assembly/component/operation scrap; rounding value/profiles | BOM unit; rounding-up quantity/measurement/consumption; multiples; scrap | BoM line unit; replenishment multiple/unit (19) | Builds in base units | BOM in inventory UoM | — |
| 10. Change after use | Base unit blocked; no effective dates | Not blocked → known failures | Not blocked | Type editable only to add units | Blocked while open docs | Blocked with open transactions |
| 11. Precision | T006 decimals + rounding decimals; integer ratio | Decimal precision per unit; rounding per conversion | Global decimal accuracy (19), floats | ~8-decimal rates | Decimal settings | Per UOM |
| 12. Reports/EDI | ISO codes per unit | Unit texts per language | Unit names | Abbreviations, plural names | UoM codes | Item packaging/GS1 |

---

## 10. (a) Feature matrix

Legend: Y = native; P = partial/limited; N = not native; A = add-on/community only.

| Feature | SAP S/4 | D365 F&SCM | Odoo 17/18 | Odoo 19 | NetSuite | SAP B1 | Oracle Fusion | Target ERP today | Target ERP proposed |
|---|---|---|---|---|---|---|---|---|---|
| Single valuation unit per product | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| Exact integer-ratio factors | Y (5+5 digits) | P (decimal) | N (float) | N (float) | P (decimal) | Y (pair) | P | Y | Y |
| Global within-kind conversions | Y | Y | Y | Y | Y (per type) | P | Y | Y | Y |
| Per-product factors | Y | Y | N | Y | N | P (group) | Y | Y | Y |
| Per-variant factors | N | Y | N | N | N | N | N | N | **Y (P1)** |
| Per-batch/lot factors | Y | N | N | N | N | N | Y | N | Later |
| Per-supplier unit | Y | P | P | Y | N | N | P | P (partner_item unit) | **Y (P1, unit only)** |
| Per-supplier factor | Y (info record) | N | N | N | N | N | N | N | No (by design) |
| Separate order price unit | Y | P (price unit) | N | N | N | N | N | N | Later (evaluate) |
| Price quantity (per 100) | Y | Y | N | N | N | N | N | N (10-dp prices) | No (use 10 dp or a "1000 pcs" unit) |
| Price list per unit + breaks per unit | Y (scale unit) | Y | A | A | P | Y | — | Y | Y |
| Packaging hierarchy as units | P | Y (sequence group) | P (packaging) | Y | N | P (packaging types) | Y | P | **Y (P1 metadata)** |
| Barcode per packaging unit | Y | Y | Y | Y | P | Y | Y | Y | Y |
| Dimensions/weight per packaging unit | Y | P | P | P | N | P | Y | N | Later |
| Follow-on doc in other unit than origin | Y | Y | Y | Y | Y (source units) | Y | Y | Unclear | **Y (P1, explicit)** |
| Line snapshot of factor | P (PO factor OUn/OPUn) | N (cause of KBA) | N | N | N | N | — | Implicit | **Y (P1, explicit)** |
| Change guard on used conversions | Y | N | N | N | P | Y | Y | Y | Y + retire/replace |
| Effective-dated conversions | N | N | N | N | N | N | N | N | No |
| Cumulative rounding against drift | N | N | N | N | N | N | Residual txns (dual) | N (GR/IR money only) | **Y (P1)** |
| Per-unit decimal places | Y | Y | P | N (global) | P | P | Y | Y | Y |
| Rounding mode per conversion | P | Y | N | N | N | N | — | Command-chosen | Command-chosen (documented per use) |
| Catch weight / dual quantity | Y | Y | N | N | N | N | Y | Reserved | Later |
| Cut-to-length BOM support | Y (variable-size) | Y (formula, measurement) | N | N | N | N | — | Linear config formula | P1: issue multiple; later: remnants |
| BOM consumption rounding to multiple | P (rounding value) | Y | A | A | N | N | — | Up to inventory dp | **Y (P1, small)** |
| Supplier min/multiple in order unit | Y | Y | P | Y (repl. unit) | N | N | Y | Y | Y |
| Sales delivery unit/multiple | Y | Y | A | A | N | P | — | N | Later (check result) |
| Unit translations for documents | Y | Y | Y | Y | P | P | Y | Y (core units) | Y + VN names |
| Rec 20 codes | Y (ISO) | P | P | P | N | N | P | Y | Y |
| Unit alias mapping for intake | N | N | N | N | N | N | N | partner_item unit | **Y (P1)** |

---

## 11. (b) Recommended design decisions for the target ERP

The current design (ADR-0006 rules 11, 14–19; ADR-0018 rules 8–14; ADR-0045 rules 3–4; ADR-0047 GR/IR; ADR-0024 rule 6; ADR-0033 rule 6; ADR-0023 handling units) already makes the strongest choices: integer-ratio factors, inventory unit as the only costing unit, per-product units, a change guard, prices per named unit, and a pure price lookup. The decisions below complete it. Each states phase, the rule, why (source), and the tradeoff.

### D1. Inventory unit stays the sole stock, cost, MRP and GR/IR unit — Phase 1 (confirm)
- Rule: unchanged. Every quantity the core aggregates (stock, valuation, reservations, planning, GR/IR positions, open quantities, tolerances) is in the inventory unit.
- Why: universal (§0.1); SAP's GR/IR-in-order-unit plus MR11 rounding issues show the cost of a second matching unit.
- Tradeoff: users see inventory units in some views; the client shows both (entered and inventory) everywhere.

### D2. Line conversion snapshot — Phase 1 (new, small)
- Rule: every document line (commercial and stock) stores `uom_id`, `uom_numerator`, `uom_denominator` (the factor used at entry), the entered `quantity`, and `inventory_quantity`. Derived quantities, follow-on conversions of that line, reversals and reprints use the snapshot, never current master data. A line's factor changes only when the user changes its unit or quantity in draft (re-snapshot).
- Why: D365's most common load-line failure is a changed conversion under open lines; Oracle and B1 respond by blocking. A snapshot makes the document self-contained and its version hash reproducible.
- Tradeoff: two integers per line; a deliberate "re-convert open lines" command is needed if a master correction must reach drafts.

### D3. Exact vs inexact product units, and cumulative rounding — Phase 1 (new)
- Rule (classification): a conversion from unit E (decimal places `dE`) to inventory unit I (`dI`) is **exact** when every quantity representable in E converts to a quantity representable in I, i.e. `numerator × 10^dI` is divisible by `denominator × 10^dE` (examples: carton = 24/1 pcs, both 0 dp: exact; 1 unit = 7/3 kg at 3 dp: inexact; carton at 3 dp = 1000/1 g at 0 dp: exact). The product-unit command returns `is_exact` and the check result `conversion_inexact` at creation; price lists and documents still accept inexact units.
- Rule (cumulative rounding): when a line with an inexact unit is fulfilled in parts by follow-on lines in the **same** unit as the origin, the inventory quantity of each part is `round(cum_after × f) − round(cum_before × f)` (cumulative entered quantity of that origin line, rounding as ADR-0018 rule 11). The parts then sum exactly to the origin line's inventory quantity, as the GR/IR technique does for money (ADR-0047 rule 13). Reversals use the same cumulative formula, so a reversal mirrors its original.
- Why: P1 (Business Central 4.99998, Odoo 2101, MR11 rounding, Oracle residuals). The target ERP already rounds converted quantities per line, so three receipts of one 7/3 unit each give 6.999999 against an ordered 7.
- Tradeoff: follow-on conversion becomes stateful (depends on prior parts); the lab must check it with random part sequences like the GR/IR test. Alternative rejected: forbid inexact units (too strict: 1 carton = 7/3 kg of a product is real), or store fractional inventory quantities (breaks decimal domains).

### D4. Follow-on documents may use another unit — Phase 1 (clarify)
- Rule: receipts, deliveries, invoices, returns and production confirmations may use any allowed unit of the item, independent of the origin line's unit. Link checks, open quantities, over-delivery and match tolerances, and GR/IR positions compare **inventory quantities**. A follow-on line in a different unit than its origin uses ordinary per-line rounding (D3's cumulative rule applies only within one unit). The response shows the remaining open quantity in the origin's unit and in the inventory unit.
- Why: SAP (GR in OUn and OPUn), Oracle ("order in one UOM, receive in another"), NetSuite (receipts in source units) all allow it; it is the practical escape from inexact conversions (receive 5 pieces against a box order instead of 0.83333 box).
- Tradeoff: the open quantity in the origin unit may show a non-terminating fraction; display rounds it, the core never uses it.

### D5. Variant-level product units — Phase 1 (new seam, small)
- Rule: `product_uom` gains nullable `item_id`. Resolution for (item, unit): row with that item → row with the product (item_id null) → `uom_conversion` (same kind) → `uom_not_allowed`. The change guard (ADR-0018 rule 13) applies per row. The `find_price` factor and all conversions call one contract function, `master_data.contract.convert_quantity(item, quantity, from_uom, to_uom, rounding_mode)`, returning the factor, its source row and `is_exact`.
- Why: D365 added per-variant conversions because pack quantities depend on size; assembly makers' variants (lengths, sizes) and configured items have the same problem. Adding the key later would change every conversion lookup and price lookup.
- Tradeoff: one more resolution level; the client must show where a factor comes from. Configured items created on order (ADR-0046) inherit product rows unless a configuration rule creates item rows (later).

### D6. Proposed unit precedence — Phase 1 (clarify)
- Rule: purchase line: `supplier_item.order_uom_id` → product `purchase_uom_id` → inventory unit. Sales line: customer `partner_item.uom_id` (when the customer's code is used) → product `sales_uom_id` → inventory unit. Production components: BOM line unit. Stock documents: origin line's unit, else inventory unit. Scanning a barcode sets the barcode's unit. The response carries `proposed_uom_source`.
- Why: P6 (SAP KBA 3625025 documents that SAP's default is unclear); D365 and Odoo 19 move the purchase unit to the vendor level.
- Tradeoff: none significant.

### D7. Supplier order unit without supplier factors — Phase 1 (new, small)
- Rule: `supplier_item` gets `order_uom_id` (inventory unit or a product unit of the item). Its `minimum_order_quantity` and `order_multiple` are in that unit (ADR-0024 rule 6 already says "purchase unit"). A supplier whose carton holds 20 instead of 24 is modeled as a separate product unit (company unit code such as `x-carton20`), never as a supplier-specific factor.
- Why: SAP's info record factor differing from the material factor causes wrong valuation (M7 235); B1, NetSuite, D365 have no supplier factors and work.
- Tradeoff: more product units for multi-supplier items; acceptable and explicit.

### D8. Immutable conversions; retire and replace — Phase 1 (refine ADR-0018 rule 13)
- Rule: a used product unit's factor never changes. To change a pack size for the future: deactivate the row (`is_active = false`, no new lines, price entries may be end-dated) and create a new product unit. Open documents keep their snapshot (D2). The inventory unit never changes; the migration path is a new product (SAP's documented workaround). No effective-dated factors.
- Why: Oracle blocks changes with open transactions; B1 proposes a new group; D365 shows what happens otherwise; no system offers effective dating, and snapshots make it unnecessary.
- Tradeoff: users must create a new unit code for a real pack change; the agent can propose it.

### D9. Decimal places, rounding modes, and where they apply — Phase 1 (document)
- Rule: per-unit `decimal_places` (≤6, immutable once used) validate entered quantities (reject, never round — ADR-0006 rule 14). Converted quantities round by the mode the use case names: receipts/deliveries/invoices half away from zero; component requirements and purchase proposals **up**; issues from stock never below zero by rounding (up for consumption, half for sales). Each command documents its mode; `round_quantity` is the only rounding call (ADR-0006 rule 15).
- Why: D365 rounding per conversion vs SAP rounding per unit; Odoo's request for ceiling (LP 1280463); BC rounding precision.
- Tradeoff: the mode belongs to the use, not to the unit or conversion (unlike D365) — simpler to reason about and test.

### D10. Serial-tracked products: integer factors only — Phase 1 (new check)
- Rule: every product unit of a serial-tracked product has `numerator % denominator = 0`; serial count equals inventory quantity.
- Why: NetSuite's rule; prevents fractional serial counts.

### D11. Packaging hierarchy as product-unit metadata — Phase 1 (small); dimensions later
- Rule: `product_uom` may name `contains_uom_id` and `contains_quantity` (e.g. pallet contains 40 cartons). The factor stays the source of truth; a check requires `factor(pallet) = 40 × factor(carton)`. The warehouse uses the hierarchy for pick breakdowns, receipt license-plate grouping and "largest whole unit" display (D365 work-unit rule); `handling_unit_type` stays the physical container (ADR-0023). Per-packaging dimensions and weights: after Phase 1 (ADR-0018 rule 4 already defers them).
- Why: Odoo 19 merged packaging into units; D365 unit sequence groups; GS1 hierarchy records next-lower-level quantities; B1 packaging types sit above the sales unit.
- Tradeoff: a second way to express a factor, guarded by a consistency check.

### D12. Purchasing: one unit per line, price per that unit — Phase 1 (confirm); order price unit later
- Rule: a purchase line has one unit; its price is per that unit at 10 decimals (no price quantity, ADR-0006 unit-price scale). Supplier invoices priced "per 1000 pcs" use a product unit `x-1000pcs` or the 10-decimal price. Invoice lines may use another unit than the order line (D4); price tolerance compares per inventory unit (ADR-0047 rule 13 note), quantity tolerance in inventory units.
- Later: SAP-style **order price unit** (order in bars, invoice per kg with a per-line agreed factor) only together with catch weight/dual quantity (D16), because without an actual second quantity it is just a supplier-specific factor (D7).
- Why: P3; SAP's OPUn mechanism is the source of price-quantity variances and MR11 work.
- Tradeoff: suppliers who invoice by actual weight against piece orders need the inventory unit to be the weight unit in Phase 1 (see D16).

### D13. Sales: price per unit, breaks per unit; multiples as check results — Phase 1 (confirm), multiples later
- Rule: keep ADR-0045 (entered unit first, then inventory unit). Minimum quantities and quantity breaks are in the entry's unit. Optional sales multiple/delivery unit per product or customer (SAP delivery unit, D365 multiple) is **after Phase 1** and, when added, yields a check result (`quantity_not_multiple`) with a proposal, never silent rounding.
- Why: SAP minimums are warnings; Odoo leaves it to add-ons; silent rounding surprises customers.

### D14. Manufacturing: BOM units, scrap, issue multiples — Phase 1 (small addition)
- Rule: BOM line quantity in any allowed unit of the component, snapshotted (D2) and converted exactly; scrap percentages apply before rounding; requirement rounds up once per order line (ADR-0033 rule 6). Add optional `issue_multiple` (in the component's inventory unit) to the BOM line: the order-line requirement rounds up to a multiple (D365 "Consumption" rounding: paint in 25-quart cans; tape in whole rolls). MRP nets in inventory units; planned production quantities round to the item-warehouse lot multiple; purchase proposals apply supplier minimum/multiple in the supplier's order unit, then convert exactly (ADR-0024 rule 6).
- Later: cut-to-length with remnant stock (pieces of a bar as a lot with a length attribute), cutting optimization, SAP variable-size items beyond the existing linear configuration formula.
- Why: D365 rounding-up options and SAP rounding values are standard; assembly makers consume wire, tubes, tape and sheet.
- Tradeoff: `issue_multiple` raises planned consumption above theoretical; the difference shows as planned scrap in costing (explicit, Principle 6).

### D15. Counting and scanning in several units — Phase 1 (confirm/small)
- Rule: a count may have several lines per item and bin in different units; they sum in the inventory unit. Barcode per item and unit (ADR-0018 rule 14) enters one unit.
- Why: D365 allows up to four counting units per sequence group.

### D16. Catch weight / dual quantity — after Phase 1 (seam kept)
- Rule now: `catch_weight_uom_id` stays reserved (ADR-0018 rule 3). Phase 1 workaround for weight-invoiced materials: make the **weight** the inventory unit and the piece a product unit with a nominal factor; receipts record the actual weight (D4), so stock, cost and GR/IR are right; piece counts are approximate.
- Later design, informed by SAP S/4 and D365: a second quantity per stock movement and per stock key, valuation in the unit the supplier invoices (SAP S/4 moves valuation to the parallel unit), nominal factor with min/max tolerance per product, explicit weight-variance postings (D365 loss/profit accounts) and residual clean-up (Oracle). Expect a long unsupported-scenarios list; schedule it only for a customer that needs it.
- Why: P9.

### D17. Batch-specific factors — after Phase 1
- Rule later: optional actual factor on a lot (Oracle lot-specific conversions; SAP BSUoM planned vs actual), used for conversions of that lot only; planning keeps the product factor.
- Why: rare in assembly; valuable for coils, rolls, and chemicals.

### D18. Units on documents, e-invoices and EDI — Phase 1 (l10n_vn overlay + core)
- Core: `uom.code` = Rec 20 code when one exists (already); unit names translatable (core units through catalogs, company units as user data with `data_translation`); external code mappings per partner or channel for EDI (later with EDI).
- l10n_vn: the e-invoice line's unit text (`DVTinh`) is the Vietnamese name of the **line's own unit**; goods lines require a unit (services optional); a check fails an e-invoice draft whose goods line lacks a Vietnamese unit name. Watch Decree 70/2025 amendments and the XML field length (not confirmed here). Lines are never re-expressed in the inventory unit on statutory output.
- Why: Decree 123/2020 art. 10.6; D365 unit texts per language.

### D19. Unit aliases for agent intake — Phase 1 (small, high value for AI)
- Rule: `uom_alias` (company, optional partner, text, `uom_id`), normalized (case, diacritics), e.g. "Thùng", "thung", "CTN", "cuộn", "PCE". Agents map supplier-invoice and e-invoice unit texts through it; unknown texts produce a proposal to add an alias (ADR-0029), never a guess. `partner_item` keeps the partner's unit for its code.
- Why: Vietnamese e-invoices carry unit names as free text; no studied system has this, and it is the first failure point of automated invoice intake.

### D20. Agent-facing contract — Phase 1
- Rule: one query `GetItemUnits(item)` returning every allowed unit with factor, source (item/product/global), `is_exact`, decimal places, barcodes, hierarchy, active flag; and the contract `convert_quantity` (D5). Error codes: `uom_not_allowed`, `quantity_rounds_to_zero`, `quantity_decimals_exceeded`, `conversion_in_use`; check results: `quantity_rounded`, `conversion_inexact`.
- Why: target goal "easy for AI to use": one function, explicit sources, no hidden defaults.

### Phase summary

| Phase 1 (complete the core) | After Phase 1 |
|---|---|
| D1 confirm; D2 line snapshot; D3 exact/inexact + cumulative rounding; D4 follow-on in other units; D5 item-level units; D6 precedence; D7 supplier order unit; D8 retire-and-replace; D9 rounding modes documented; D10 serial integer factors; D11 packaging metadata; D12 one unit per purchase line; D13 price breaks per unit; D14 BOM `issue_multiple`; D15 multi-unit counts; D18 VN unit names; D19 alias table; D20 agent contract | Catch weight/dual quantity with order price unit (D16, D12); lot-specific factors (D17); sales multiples/delivery units (D13); packaging dimensions/weights (D11); cut-to-length remnants and cutting optimization (D14); EDI unit mappings and GS1 hierarchy export (D18) |

### Main tradeoffs accepted
- **Strictness over convenience**: immutable conversions and rejected over-precise inputs cost some user effort, but remove the drift and reconfiguration bugs that dominate the other systems' support notes.
- **No supplier-specific factors**: more product units, but one factor per (item, unit) everywhere, so cost cannot be distorted by a second factor.
- **Stateful follow-on conversion (D3)**: more complex than per-line rounding, but the only way to keep part receipts summing to the order with inexact units; the same proof technique as GR/IR.
- **Catch weight deferred**: weight-invoiced materials must use weight as inventory unit in Phase 1; piece counts are then approximate.

---

## 12. Source list (primary first)

SAP: [ME60 units](https://help.sap.com/saphelp_me60/helpdata/en/a0/7cbd534f22b44ce10000000a174cb4/content.htm) · [Two units in a PO](https://help.sap.com/doc/saphelp_sfin100/1.9/en-US/af/7eb65334e6b54ce10000000a174cb4/content.htm) · [Units in POs 4.6C](https://help.sap.com/saphelp_46C/helpdata/EN/75/ee0d5a55c811d189900000e8322d00/content.htm) · [Order price unit in IM](https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/applying-order-price-unit-in-inventory-management) · [Variance in order price quantity](https://help.sap.com/saphelp_470/helpdata/en/47/60f9d049f011d1894c0000e829fbbd/content.htm) · [GR/IR maintenance](https://help.sap.com/saphelp_46C/helpdata/EN/47/6100f249f011d1894c0000e829fbbd/content.htm) · [BSUoM valuation](https://help.sap.com/saphelp_470/helpdata/en/25/283db54f7811d18a150000e816ae6e/content.htm) · [Dynamic rounding profile](https://help.sap.com/doc/9ea8c7536e8e2a4be10000000a174cb4/3.6/en-US/6951b9537cceb44ce10000000a174cb4.html) · [Quantity optimizing](https://help.sap.com/saphelp_46c/helpdata/en/4c/420d89470a11d1894a0000e8323352/content.htm) · [Units and quantity specifications (sales)](https://help.sap.com/saphelp_46c/helpdata/en/dd/55f68b545a11d1a7020000e829fd11/content.htm) · [Component scrap](https://help.sap.com/doc/6297d7531a4d414de10000000a174cb4/1610%20002/en-US/d195d7531a4d414de10000000a174cb4.html) · [Assembly scrap](https://help.sap.com/doc/6297d7531a4d414de10000000a174cb4/1610%20002/en-US/cb95d7531a4d414de10000000a174cb4.html) · [Variable-size items](https://help.sap.com/saphelp_470/helpdata/en/92/58c3e2417011d189ec0000e81ddfac/content.htm) · [CWM EWM help](https://help.sap.com/doc/saphelp_ewm92/9.2/en-US/e5/c9cb53ad377114e10000000a174cb4/content.htm) · [CWM tolerance groups](https://help.sap.com/doc/be9dcf535b804808e10000000a174cb4/1610%20002/en-US/fa9ccf535b804808e10000000a174cb4.html) · [Defining units](https://learning.sap.com/courses/cross-functional-customizing-in-sap-s-4hana-materials-management/defining-units-of-measurement) · [EWM stock-specific UoM](https://learning.sap.com/courses/advanced-customizing-in-sap-s-4hana-ewm/using-stock-specific-units-of-measure) · KBAs [3559563](https://userapps.support.sap.com/sap/support/knowledge/en/3559563), [3625025](https://userapps.support.sap.com/sap/support/knowledge/en/3625025), [3734926](https://userapps.support.sap.com/sap/support/knowledge/en/3734926), [3552102](https://userapps.support.sap.com/sap/support/knowledge/en/3552102), [2413079](https://userapps.support.sap.com/sap/support/knowledge/en/2413079), [3550038](https://userapps.support.sap.com/sap/support/knowledge/en/3550038), [3443866](https://userapps.support.sap.com/sap/support/knowledge/en/3443866), [3065375](https://userapps.support.sap.com/sap/support/knowledge/en/3065375), [3638409](https://userapps.support.sap.com/sap/support/knowledge/en/3638409), [3394363](https://userapps.support.sap.com/sap/support/knowledge/en/3394363), [2788475](https://userapps.support.sap.com/sap/support/knowledge/en/2788475), [3627935](https://userapps.support.sap.com/sap/support/knowledge/en/3627935), [3424138](https://userapps.support.sap.com/sap/support/knowledge/en/3424138), [3448084](https://userapps.support.sap.com/sap/support/knowledge/en/3448084), [3586490](https://userapps.support.sap.com/sap/support/knowledge/en/3586490) · Community/third-party: [SAP blog CWM S/4](https://blogs.sap.com/2022/02/06/change-in-catch-weight-management-in-s-4hana-and-extended-warehouse-management-on-s-4hana/), [SAPinsider 11 UoM errors](https://sapinsider.org/avoid-these-11-common-unit-of-measure-errors/), [MARM fields](https://leanx.eu/en/sap/table/marm.html), [KOND fields](https://leanx.eu/en/sap/table/kond.html), [M7 027](https://michaelmanagement.com/sap-error-messages/en/m7/m7027), [M7 235](https://michaelmanagement.com/sap-error-messages/en/m7/m7235), [SAP Answers base unit](https://answers.sap.com/t5/enterprise-resource-planning-q-a/can-t-change-base-unit-of-measure/m-p/4495003), [BSUoM steel blog](https://blogs.sap.com/2010/02/22/batch-specific-units-of-measure-step-by-step-configuration-for-steel-industry/).

Microsoft: [Manage units of measure](https://learn.microsoft.com/en-us/dynamics365/supply-chain/pim/tasks/manage-unit-measure) · [Per variant](https://learn.microsoft.com/en-us/dynamics365/supply-chain/pim/uom-conversion-per-product-variant) · [Unit sequence groups](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/unit-measure-stocking-policies) · [Catch weight processing](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/catch-weight-processing) · [Material consumption](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/consumption) · [Default order settings](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/default-order-settings) · [Three-way matching](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/three-way-matching-policies) · [Invoice matching](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/accounts-payable-invoice-matching) · [Released qty negative](https://learn.microsoft.com/en-us/dynamics365/supply-chain/troubleshooting/warehousing/released-qty-cannot-be-negative) · [Blog: PO vs inventory quantities](https://www.microsoft.com/en-us/dynamics-365/blog/it-professional/2015/01/31/quantities-in-purchase-order-and-inventory-transaction/) · [BC units](https://learn.microsoft.com/en-us/dynamics365/business-central/inventory-how-setup-units-of-measure) · [BC rounding precision](https://learn.microsoft.com/en-us/dynamics365-release-plan/2021wave2/smb/dynamics365-business-central/rounding-base-unit-measure) · [KA-23761](https://community.dynamics.com/article/KA-23761) · third-party: [Encore pricing](https://www.encorebusiness.com/blog/pricing-options-dynamics-365-finance-operations/), [Logan decimals](https://www.loganconsulting.com/blog/units-conversions-and-decimal-places-in-dynamics-365-for-operations/), [PRI price unit](https://innovation-product-documentation.azurewebsites.net/PRI-PriceUnit.html).

Odoo: [17 UoM](https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/inventory/product_management/configure/uom.html) · [19 UoM](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/product_management/configure/uom.html) · [PR 184131](https://mergebot.odoo.com/odoo/odoo/pull/184131) · [Octura guide](https://octurasolutions.com/resources/the-death-of-uom-category-odoo-19-migration-guide) · [LP 488736](https://bugs.launchpad.net/bugs/488736) · [LP 889093](https://launchpad.net/bugs/889093) · [LP 842758](https://bugs.launchpad.net/bugs/842758) · [LP 1280463](https://bugs.launchpad.net/bugs/1280463) · [OCA pricelist UoM](https://pypi.org/project/odoo-addon-product-pricelist-item-uom/) · [OCA BoM rounding](https://pypi.org/project/odoo-addon-mrp-bom-line-uom-rounding/) · [OCA sell by packaging](https://apps.odoo.com/apps/modules/18.0/sell_only_by_packaging).

NetSuite: [Setting up units](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2212143.html) · [Assigning units](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2212390.html) · [Assemblies and units](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2320172.html) · [Serial/lot with units](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2214525.html) · [Multiple UoM chapter](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_N2211898.html).

SAP Business One: [SAP Learning UoM](https://learning.sap.com/courses/managing-logistics-in-sap-business-one/working-with-units-of-measure-uom-in-sap-business-one) · [UoM groups help](https://help.sap.com/saphelp_sbo900/helpdata/en/64/1a2505ffb142f6bc4de5a800b6b119/content.htm) · [UoM prices](https://help.sap.com/saphelp_sbo900/helpdata/en/b6/c2d489a3f64bc5b15f103796b7e74c/content.htm) · [KBA 3477493](https://userapps.support.sap.com/sap/support/knowledge/en/3477493) · [KBA 3365952](https://userapps.support.sap.com/sap/support/knowledge/en/3365952).

Oracle Fusion: [Interclass conversion](https://docs.oracle.com/en/cloud/saas/procurement/24c/oapro/what-s-a-uom-interclass-conversion.html) · [Conversion update checks](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/faicf/inventory-transactions-verified-when-a-uom-conversion-is-updated.html) · [Dual UOM](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/faims/set-up-dual-units-of-measure.html) · [Residuals](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/famml/residual-quantity-transactions-with-dual-uoms.html) · [Lot-specific 26A](https://docs.oracle.com/en/cloud/saas/readiness/scm/26a/inv26a/26A-inventory-wn-f41700.htm) · [Item-specific intraclass 26A](https://docs.oracle.com/en/cloud/saas/readiness/logistics/26a/wms26a/26A-wms-wn-f42720.htm) · [Redwood UOM 25A](https://docs.oracle.com/en/cloud/saas/readiness/scm/25a/plm25a/25A-plm-wn-f35771.htm) · [Receiving/shipping conversions](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/famml/uom-conversions-for-inventory-receiving-and-shipping.html).

Vietnam / standards: [Decree 123 art 10.6](https://hethongphapluat.com/nghi-dinh-123-2020-nd-cp-quy-dinh-ve-hoa-don-chung-tu/khoan-6-dieu-10) · [LuatVietnam on units](https://luatvietnam.vn/thue-phi-le-phi/cach-ghi-don-vi-tinh-tren-hoa-don-dien-tu-theo-nghi-dinh-123-565-95759-article.html) · [TVPL goods names](https://thuvienphapluat.vn/hoi-dap-phap-luat/quy-dinh-ten-hang-hoa-tren-hoa-don-dien-tu-nhu-the-nao-138008657.html) · [TVPL Decree 70](https://thuvienphapluat.vn/hoi-dap-phap-luat/ghi-ten-hang-hoa-tren-hoa-don-bang-tieng-anh-duoc-khong-138067007.html) · [Decision 1450/QĐ-TCT](https://thuvienphapluat.vn/van-ban/thue-phi-le-phi/quyet-dinh-1450-qd-tct-2021-thanh-phan-chua-du-lieu-nghiep-vu-hoa-don-dien-tu-490526.aspx) · [Peppol Rec 20](https://docs.peppol.eu/pracc/espd/codelist/UNECERec20) · [MyInvois units](https://sdk.myinvois.hasil.gov.my/codes/unit-types/) · [UN/CEFACT Rec 20 document](https://digitallibrary.un.org/record/635432/files/%5BE_%5DECE_TRADE_C_CEFACT_2008_6-EN.pdf) · [GS1 Sweden hierarchies](https://gs1.se/en/support/what-are-trade-item-hierarchies-and-trade-item-levels-2/) · [GS1 unit descriptor codes](https://gs1.se/en/guides/documentation/code-lists/t4010-trade-item-unit-descriptor-code/).

## 13. Open points not resolved by this research
- Exact maximum length and encoding rules of the e-invoice unit text in the current XML format (1450/QĐ-TCT as amended) and any change by Decree 70/2025.
- Whether D365 F&SCM officially supports changing a released product's inventory unit after transactions (no Microsoft page found).
- SAP S/4HANA catch-weight pricing and invoice-variance details (SAP notes 2358928, 2668177 not read).
- UN/CEFACT Rec 21 package codes were not confirmed from a primary source here.
