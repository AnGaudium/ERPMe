# Vietnamese rules for production and production costing

Research note for DS-51 to DS-55 ([ADR-0032](../../adr/0032-phase-1-scope-with-production.md)), written by a research agent on 2026-11-14. It is design input, not a decision. Under ADR-0016, legal facts stay `unverified` until the author verifies them.

**Status tags**
- **[V]** read in the legal text, through a full-text mirror;
- **[S]** confirmed only by a reputable secondary source (Big-4 firm, MISA, trade journal);
- **[U]** not verified.

## Regulatory landscape (November 2026)

| Area | Current rule | Status |
| --- | --- | --- |
| Enterprise accounting regime | Circular 99/2025/TT-BTC (TT99), issued 27/10/2025, for fiscal years from 01/01/2026; replaces TT200 | [V] |
| Small and medium enterprises | Circular 133/2016 (TT133) still in force; a draft replacement was in consultation in September–October 2026 | [S] |
| Micro enterprises | Circular 58/2026/TT-BTC from 01/07/2026, replacing Circular 132/2018 | [S] |
| E-invoices | Decree 254/2026/NĐ-CP and Circular 91/2026/TT-BTC from 01/07/2026, replacing Decree 123/2020 (as amended) and Circular 32/2025 | [S] |
| Corporate income tax | Law 67/2025/QH15, Decree 320/2025/NĐ-CP, Circular 20/2026/TT-BTC (replaces Circulars 78/2014 and 96/2015), from the 2025 tax period | [S] |
| VAT | Law 48/2024/QH15, Decree 181/2025/NĐ-CP, Circular 69/2025/TT-BTC | [S] |
| Customs | Circular 38/2015 as amended by Circular 39/2018 and Circular 121/2025/TT-BTC (from 01/02/2026); Law 90/2025/QH15; Decree 167/2025/NĐ-CP | [V] for TT121, [S] otherwise |
| Accounting standards | VAS 02 in force; replacement standards (VFRS) in preparation, none yet for inventory | [S] |

Spec 08 and the e-invoice and tax design may cite rules that these texts replaced (open question).

## TT99

Sources: the full text through the [atax.vn mirror](https://atax.vn/thong-tu-99-2025-tt-btc-huong-dan-che-do-ke-toan-doanh-nghiep-biiwjjur39); [MISA comparison](https://amis.misa.vn/251599/diem-moi-he-thong-tai-khoan-ke-toan-theo-thong-tu-99-2025/).

**Freedoms**
- Enterprises may change account names, numbers and structure if:
  - classification by substance and the statement lines are kept;
  - the change is documented in an internal regulation (Art. 11.2) [V].
- Enterprises may design their own vouchers and ledgers (Arts. 9.2, 12.2) [V].
- Accounting software must warn about or block alteration of posted data, and be able to connect to e-invoices and digital signatures (Art. 28) [V].

**Production-cost accounts** [V unless noted]

| Account | Content | Change from TT200 |
| --- | --- | --- |
| 152 | Raw materials | Unchanged |
| 154 | Work in process | Unchanged |
| 155 | Products, now explicitly including semi-finished goods | Renamed, scope stated |
| 621, 622 | Direct materials, direct labor | Unchanged |
| 627 | 6271–6278, with the new 6275 for taxes, fees and charges | 6275 added |
| 632 | Cost of goods sold | Unchanged |
| 611, 631 | Purchases, production cost under the periodic method | Removed [V absent, S] |
| 001–007 off-balance accounts | Including 002, materials received for processing | Appear removed [U] |

**Periodic method**
- The general principles still describe the perpetual method (typical for manufacturers) and the periodic method, but give no periodic accounts [V].
- KPMG reads TT99 as having removed the two concepts ([KPMG](https://kpmg.com/vn/en/home/insights/2025/11/key-changes-in-vietnamese-accounting-system-for-enterprises.html)).
- The research recommends building the perpetual method only [U on interpretation].

**Valuation methods** [V]
- The allowed methods are specific identification, weighted average, FIFO, the retail method, and the new standard cost method, applicable to manufacturers. Standard cost is based on normal usage and is reviewed regularly.
- LIFO is excluded.
- The method is applied consistently.

**Collecting production cost** [V]
- **TK 154** collects opening WIP, costs incurred and closing WIP for main and auxiliary production and for outsourced processing. It may be detailed by workshop, product, group, order, service or stage.
- **Fixed overhead:**
  - it is allocated per unit at normal capacity;
  - below normal capacity, the unallocated part goes to 632 in the period;
  - at or above normal capacity, it is allocated at actual;
  - normal capacity is defined as average output under normal conditions (155).
- **Variable overhead** is allocated at actual.
- **Abnormal costs.** Materials, labor and machine costs above normal levels go to 632 even when the product is unsold (621 section 1e, 622 section 1đ, 632 section 1đ). Product cost excludes them (155 section c).
- **Shortages and losses** go to 632, net of compensation. Unrepairable defects charged to a responsible party credit 154.
- **Overhead across several products** is allocated on a suitable, consistent basis (627 section e). TT99 does not address by-products or joint products; VAS 02 does.
- **Provisional prices.** Daily receipts and issues may use a provisional price (planned, standard or uniform). At period end the actual is compared and a difference coefficient applied (155 section e). This is the legal basis for provisional pricing with a period-end true-up.
- **Outsourced products** are valued at actual processing cost (155 section đ).
- **Scrap sales** post revenue (511) and cost (632 / 152) (152 entry 3.13c).
- **Typical entries:**
  - 154/632 ← 621, 622, 627;
  - 155 ← 154;
  - 632 ← 154;
  - 241, 641, 642 ← 154;
  - 152 ← 154 (processed materials returned).
- **WIP.** The debit balance of 154 is WIP. TT99 prescribes no valuation method; the method is a policy choice.

## TT133 and its draft successor

- **TT133** has no 621, 622 or 627: production cost goes straight to 154, detailed by element if wanted. It keeps 611 and 631 for the periodic method. Unallocated fixed overhead posts Dr 632 / Cr 154. Source: [MISA](https://amis.misa.vn/26440/phuong-phap-ket-chuyen-chi-phi-san-xuat-kinh-doanh-do-dang-cuoi-ky-theo-tt-200-va-tt-133/) [S].
- **The draft replacement** (22 level-1 accounts, customisable) is not issued, and its production accounts are not reported ([MISA](https://amis.misa.vn/293267/du-thao-thong-tu-thay-the-thong-tu-133/)) [S].

## VAS 02 (Decision 149/2001/QĐ-BTC)

Source: [text](https://tapchicongthuong.vn/quyet-dinh-149-5891.htm) [V].

- **Para 05.** Cost is purchase cost plus conversion cost plus other directly attributable costs.
- **Para 07.** Conversion cost is direct costs (such as direct labor) plus systematically allocated fixed and variable production overhead.
- **Para 08.** Fixed overhead is allocated at normal capacity, and at actual when output is above normal. Below normal, the unallocated part is a period expense. Variable overhead is allocated at actual.
- **Para 09.** Joint products whose costs cannot be separated are allocated on a suitable, consistent basis. By-products are valued at net realisable value, which is deducted from the main product's cost.
- **Para 11.** Excluded from cost:
  - costs above normal levels;
  - storage, unless needed between production stages;
  - selling costs;
  - administrative costs.
- **Para 24.** Losses net of compensation are a period expense.
- **Paras 04 and 19.** Inventory is valued at the lower of cost and net realisable value, with provisions item by item.

## Costing methods used in Vietnam

The methods come from university curricula and accounting software; none is prescribed by law.

**Costing methods**
- **Direct (giản đơn):** unit cost = (opening WIP + costs − closing WIP) ÷ output. The most common method.
- **Coefficient (hệ số):** joint outputs are converted to standard units by coefficients.
- **Ratio (tỷ lệ):** product groups; the ratio of actual to planned cost is applied to each item's planned cost.
- **Step (phân bước):**
  - sequential, with semi-finished goods costed (needed when they are stocked or sold);
  - parallel, without semi-finished goods costed.
- **Job order (đơn đặt hàng):** per order; unfinished orders are WIP. Common in furniture and make-to-order work.
- **Standard (định mức):** actual = standard ± norm changes ± deviations.
- **Mixed methods** are common.

**WIP valuation methods**
- by direct or main material;
- equivalent units (percentage of completion);
- 50% completion;
- standard cost;
- none.

**Practice** [U, indirect evidence; [MISA](https://sme.misa.vn/tinh-nang/gia-thanh/)]
- Most common: the direct method, WIP at direct material, monthly, with overhead allocated by direct material or direct labor.
- Next: job order, coefficient or ratio, and step.
- True standard costing with variance analysis is rare outside larger and foreign-invested firms.
- Normal capacity is often ignored, which auditors flag.

## Processing (gia công)

**Accounting** [V]
- **Sending materials out.**
  - Materials sent: Dr 154 / Cr 152.
  - Fees and freight: Dr 154, 1331 / Cr 331.
  - Receipts: Dr 152, 155, 156, 632 or 157 / Cr 154.
  - Processed items are valued at materials + transport + fee (152 section 1b).
- **Processing for others.**
  - Customer materials are not inventory. They are tracked in a detail ledger and disclosed in the notes (152 section 1d).
  - The processor's own costs go through 621, 622 and 627 to 154; revenue goes to 511 and cost to 632.

**Invoicing and VAT** [S]
- Materials sent to a domestic processor need no invoice; they travel with a stock-issue and delivery document. Decree 254/2026 Art. 7 lists no-invoice cases ([EY](https://www.ey.com/vi_vn/technical/tax/tax-and-law-updates/nghi-dinh-254-2026-nd-cp-ve-hoa-don-dien-tu-va-chung-tu-dien-tu)).
- The processor invoices the fee with VAT. The VAT base is the contract price covering labor, fuel, auxiliary materials and other costs (Decree 181/2025 Art. 7.2).
- Processing for a foreign party with exported products: 0% VAT under conditions. Materials imported to process for export are outside VAT (Law 48/2024 Art. 5.20).

**Customs** (Circular 38/2015 as amended by 39/2018 and 121/2025) [V unless noted]
- The product and material codes declared must match those used in management and production (TT121 amendment to Art. 18.1a). The item master therefore needs a customs-code mapping.
- **Actual consumption norms**, including losses, are reported with the finalization report (Art. 55).
- **Annual finalization report**:
  - on quantities of imported, exported and closing materials and products, with actual norms;
  - due within 90 days of the fiscal year end (Art. 60);
  - corrections are allowed within 60 days.
- **Records to keep:** the reports, norms, and stock ledgers and vouchers (TT121, new Art. 16a).
- **Leftovers** are settled within 30 days after a processing contract ends (Art. 64).
- **Customs type codes** (E21, E52, E31, E62 and others) [U].

## Income tax and consumption norms

- **History.** Circular 96/2015 removed the duty to keep own consumption norms. Only consumption above norms issued by the State stayed non-deductible [S].
- **Current rule.** Decree 320/2025 Art. 10 lists the non-deductible items; the "above State norms" item appears to be dropped [U] ([RSM](https://www.rsm.global/vietnam/sites/default/files/media/spotlight/2026/RSM_VN_Tax_Spotlight_Decree_3202025_guiding_the_2025_Law_on_Corporate_Income_Tax_vn.pdf)).
- **Evidence.** Circular 20/2026 sets the evidence needed to destroy damaged inventory: a decision, a count record and committee minutes [S].
- **Consequence.** A charge to 632 does not by itself make a cost non-deductible. Norms and loss records still serve as evidence and for customs.

## E-invoices for internal transfers

- **Inside one entity:** goods used to continue production need no invoice (Decree 254/2026 Art. 7) [S; EY's reading of a VAT-exempt condition is [U]].
- **Between sites and dependent branches:** the internal stock-issue and transport note is an electronic document under invoice rules [S].
- **Processing:** materials go with a stock-issue document; the processor invoices the fee [S].

## Choices for the chief accountant

The research proposes these choices, with defaults:
1. **Regime.** TT99 by default, TT133 as a second template; the chart is data-driven.
2. **Cost-element accounts.** 621/622/627 under TT99; 154 with a cost-element dimension under TT133.
3. **Overhead sub-accounts.** TT99's 6271–6278, with a fixed or variable flag on overhead lines.
4. **Inventory system.** Perpetual only.
5. **Valuation.** Monthly weighted average per item and warehouse. Options: FIFO, specific identification, standard cost. Locked per fiscal year.
6. **Costing period.** Monthly; quarterly allowed.
7. **Collection object.** Workshop × product, or production order in job-order mode.
8. **Costing method.** Direct by default; coefficient, ratio, step, job order and standard as options, per product group.
9. **WIP valuation.** By direct material by default; the other methods as options.
10. **Overhead basis.** Direct material cost by default; labor, machine hours, output or coefficients as options.
11. **Normal capacity.**
    - Set per workshop and period, initialised from the trailing 12-month average.
    - Under-absorption is tested automatically, and unabsorbed fixed overhead posts to 632 with approval.
    - A warning shows when capacity is not set.
12. **Norms and tolerance.**
    - Versioned BOMs with an allowed loss.
    - Consumption above tolerance is flagged at close, and the charge to 632 is confirmed.
    - The same versions serve customs norms.
13. **By-products** at net realisable value or a price list, deducted from the main product.
14. **Joint products** by coefficients, with relative sales value as an option.
15. **Scrap and defects.**
    - Scrap is received at an estimated value and credited to 154; scrap sales go to 511/632.
    - Defects above norm go to 632, or to a responsible party.
16. **Semi-finished goods.** Parallel step costing by default; sequential with semi-finished goods in 155 when they are stocked or sold.
17. **Provisional receipt cost.** Actual at month end by default; a planned or standard provisional price with a true-up as an option.
18. **Outsourcing.** A 154 sub-ledger per processor and order; quantity tracking at the processor; no invoice when materials are sent.
19. **Processing for customers.** Customer-owned stock by quantity outside the ledger, a year-end disclosure, and an invoice for the fee only.
20. **Customs regime flag** (none, processing, export production, export processing zone). When it is on:
    - customs-code mapping;
    - versioned norms;
    - quantity ledgers;
    - the annual finalization report.
21. **Inter-site transfers.** By tax unit and branch, per Decree 254/2026.
22. **Accounting currency.** VND by default.
23. **Income tax evidence.** Keep count and destruction records automatically.

## Points to verify against official texts

1. Whether TT99 has no off-balance accounts, and how Art. 29 treats legacy 611/631 balances.
2. Whether Decree 320/2025 Art. 10 still excludes consumption above State norms.
3. The exact wording of Decree 254/2026 Art. 7 on internal circulation.
4. The customs type codes.
5. Article numbers in Law 107/2016 and Decree 69/2018.
6. Whether the temporary 8% VAT rate covers processing services.
7. The status of the TT133 replacement.
