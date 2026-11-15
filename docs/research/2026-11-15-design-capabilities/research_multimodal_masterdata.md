# Research: multimodal document intake and agent-assisted master data creation

Date: 2026-11-15. Written for the architect of an agentic ERP: deterministic core, LLM only drafts, people submit and approve, a taint model, and model seats that gate personal data.

Each claim carries one tag:
- **[doc]**: official product, standards or legal documentation. "[doc, vendor claim]" marks vendor marketing that has no published method.
- **[blog]**: practitioner, consultancy or vendor-adjacent writing, and trade press.
- **[paper]**: peer-reviewed or arXiv preprint.
- **[inference]**: my synthesis or design judgment. Treat it as a proposal.

Names of the ERP's own design objects come from `holistic/capability_check.md` and the ADRs it cites, for example `document_extraction`, `ImportEInvoiceRecord`, change proposals, `GetBillOfMaterialsRevisionCheck`, `CreateCostEstimate`, `rank_candidates`, the `import_batch` scope and the spec 17 seats. Where this report maps a finding onto them, the mapping is [inference].

---

## 0. Headline findings

1. **Vietnam's e-invoice law changed on 1 July 2026.** Decree 254/2026/ND-CP and Circular 91/2026/TT-BTC replaced Decree 123/2020, Decree 70/2025 and Circular 32/2025 [doc/blog, multiple secondary sources: https://www.crowe.com/vn/news/e-invoices-and-electronic-documents-from-1-july-2026 , https://www.fiscal-requirements.com/news/5767-vietnams-new-e-invoice-regulations-decree-2542026nd-cp , https://luatvietnam.vn/tin-van-ban-moi/nghi-dinh-123-2020-nd-cp-va-nghi-dinh-70-2025-nd-cp-ve-hoa-don-chinh-thuc-het-hieu-luc-tu-01-7-2026-186-110076-article.html]. Article 3 of Circular 91 now defines the e-invoice format, and replacement invoices must carry a coded reason from its Appendix XVII [blog: https://ihoadon.vn/hddt/hoa-don-dien-tu-tai-thong-tu-91-2026-tt-btc.html]. I found no confirmation that the XML technical standard of Decision 1450/QD-TCT (amended by 1510/QD-TCT) was replaced. Build the reader so it picks its parser by schema version, and check the official annex [inference]. Any design text that still says "Decree 123 and its amendments" is stale.
2. **The legal original of a Vietnamese e-invoice is the signed XML, not the PDF.** The XML has a business-data part (`HDon/DLHDon` with `TTChung` and `NDHDon`), a signature part (`DSCKS`) and, on coded invoices, the tax authority code `MCCQT` [doc: Decision 1450/QD-TCT via https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Quyet-dinh-1450-QD-TCT-2021-thanh-phan-chua-du-lieu-nghiep-vu-hoa-don-dien-tu-490526.aspx ; blog: https://vinatas.com.vn/hoa-don-dien-tu-can-phai-luu-file-xml/]. A deterministic XML reader with signature verification beats any model on this path.
3. **The mature IDP products share one human-in-the-loop design.** It has five parts: per-field confidence, per-field thresholds, validation rules that override confidence, a side-by-side verification screen, and learning from corrections. This holds for Rossum, ABBYY Vantage, UiPath, SAP and Azure [doc, section 1.1]. Google withdrew its managed human review (Document AI HITL was deprecated on 2024-01-16) and points customers to partners [doc: https://docs.cloud.google.com/document-ai/docs/deprecation]. That suggests the human verification screen belongs in the application, not in the extraction vendor [inference].
4. **LLM vision extraction is strong but not error-free, and its errors are quiet.** In the best peer-reviewed comparison, native image input reached 87–93% field exact-match on invoices and receipts, against 47% for a text-parsed pipeline on receipts [paper: https://arxiv.org/abs/2509.04469]. Line items are the weakest part for every engine [blog, section 1.3]. Self-reported LLM confidence is poorly calibrated [paper: https://arxiv.org/abs/2511.19806 ; blog, vendor: https://www.uipath.com/blog/product-and-updates/technical-tuesday-process-enterprise-docs-with-llms].
5. **Grounding has to be verified by code, not trusted.** In SafePassage, even the best model mistranscribed about 5% of its own "copied" evidence, and one open model did so for 42% of entities. A cheap verifier caught about 86% of hallucinations [paper: https://arxiv.org/html/2510.00276v1]. LMDX grounds values only to OCR lines, and its authors say finer localization is unreliable [paper: https://arxiv.org/abs/2309.10952]. Claude citations give page-level locations for text PDFs, but cannot cite scanned images [doc: https://platform.claude.com/docs/en/build-with-claude/citations].
6. **Prompt injection through documents is real and measured.** Hidden PDF text survives common parsers such as PyMuPDF [paper: https://arxiv.org/pdf/2509.10248]. Visual injection in images reaches up to 64% success [paper: https://arxiv.org/pdf/2603.03637]. Spotlighting cut attack success from over 50% to under 2% on its own test set [paper: https://arxiv.org/abs/2403.14720]. The structural defense is a tool-less reader that returns only typed, schema-bound output, as in CaMeL [paper: https://arxiv.org/abs/2503.18813]. Detection is not a boundary: "95% is very much a failing grade" [blog: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/].
7. **Vietnam's Personal Data Protection Law (91/2025/QH15) and Decree 356/2025 took effect on 1 January 2026.** Cross-border transfer explicitly covers cloud processing and needs a filed transfer impact assessment [blog: https://fpf.org/blog/fpf-releases-updated-issue-brief-on-vietnams-law-on-protection-of-personal-data-and-the-law-on-data/ , https://www.tilleke.com/insights/new-decree-provides-guidance-for-vietnams-personal-data-protection-law]. Photos of business cards and delivery notes are personal data as a whole, because an image cannot be field-stripped [inference].
8. **Major vendors use AI in master data to summarize, search, describe and deduplicate, not to release.** SAP MDG uses Joule for change summaries. SAP's BOM app has an AI summary [doc]. Oracle generates item descriptions from stored attributes [doc]. Siemens' AI BOM agent "executes changes within governed workflows" [doc, vendor claim]. PTC shipped AI parts rationalization in 2026 [blog]. Release still runs through change requests, ECOs or MCNs with human approval in every system surveyed [doc].
9. **Cost estimation in serious tools is a deterministic rollup of BOM × routing × rates.** In SAP only "release for costing" structures and costing-relevant items count, and lot size drives setup apportioning [doc: https://help.sap.com/doc/6297d7531a4d414de10000000a174cb4/3.6/en-US/fb96d7531a4d414de10000000a174cb4.html]. Quoting tools use AI to read RFQs and geometry, then price with the shop's own rates, and an estimator reviews every quote [doc, vendor claim: https://www.paperlessparts.com/pricing-costing-automation/]. Should-cost tools admit about ±30% spread [blog, vendor: https://www.apriori.com/blog/your-should-cost-estimate-is-not-accurate-but-thats-okay/]. I found no credible evidence that an LLM should produce cost numbers [inference].
10. **The ERP already has the right primitives.** Draft revisions, change proposals, a BOM check, a server cost estimate and a candidate ranker exist. What is missing is two things: one `document_extraction` record with field-level evidence, and one `product_engineering` workflow that chains them [inference, building on capability_check.md].

---

# Part 1. Multimodal document intake

## 1.1 What systems do

| System | What it extracts | Confidence and evidence | Human in the loop | Source |
|---|---|---|---|---|
| **Azure AI Document Intelligence v4.0** (prebuilt-invoice) | Header fields and line items from invoices, utility bills, sales orders and purchase orders; 27 languages; up to 2,000 pages and 500 MB (S0) | `pageResults` holds tables and cells with bounding boxes and confidence; `documentResults` holds typed fields; per-field confidence | Customer-built; guidance is to auto-accept above a threshold and flag below it | [doc] https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/invoice ; https://learn.microsoft.com/azure/ai-services/document-intelligence/concept-accuracy-confidence |
| Azure, bounding-region limits | No bounding regions for unrendered files (DOCX, XLSX, PPTX, HTML) | - | - | [doc] https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/analyze-document-response |
| Azure, business card model | **Deprecated from v4.0** | - | - | [doc] https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-business-card |
| **Azure AI Content Understanding** (generative fields) | Schema-defined fields, including generated ones | Opt-in `estimateFieldSourceAndConfidence` returns page plus bounding box plus confidence. Guidance: set thresholds per field and recalibrate when the model changes | Customer-built | [doc] https://learn.microsoft.com/azure/ai-services/content-understanding/overview ; [blog, vendor] https://devblogs.microsoft.com/foundry/azure-content-understanding-gpt-5-series-guide-model-selection-grounding-improvements-and-confidence-enhancements/ |
| **Google Document AI** | Invoice Parser (pre-trained) and Custom Extractor. A generative fine-tuned foundation model is recommended first for variable layouts and needs 0–50+ documents | Entity confidence from 0 to 1, "to set triggers for manual review" | **HITL deprecated** on 2024-01-16; partners recommended | [doc] https://docs.cloud.google.com/document-ai/docs/custom-extractor-overview ; https://docs.cloud.google.com/document-ai/docs/deprecation |
| **AWS Textract** AnalyzeDocument and AnalyzeExpense | Forms, tables, expense summary fields and line items | Per-block confidence; best practice is to discard or escalate below the threshold | Amazon A2I is documented for AnalyzeDocument (key confidence, missing keys, random sampling). I found no A2I documentation for AnalyzeExpense | [doc] https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html ; https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-textract-task-type.md ; [blog] https://idp-software.com/guides/aws-textract-guide/ |
| **SAP Document Information Extraction / SAP Document AI** | Prebuilt document types plus premium "schema-based extraction of unstructured data" using LLMs (GA 2023-12-06) | Field confidence from 0 to 100%. Documents with all fields above a configured threshold (typically 90%) proceed; the basic UI colours fields red (0–50), orange (51–79) and green (80–100). "Instant learning" applies corrections to later documents | Built-in validation UI | [blog, vendor] https://blogs.sap.com/2023/09/04/introducing-document-information-extraction-premium-edition-unleashing-the-power-of-large-language-models-and-generative-ai/ ; [doc] https://architecture.learning.sap.com/docs/ref-arch/LcR6Senh/2 ; https://developers.sap.com/tutorials/cp-aibus-dox-ui |
| **ABBYY Vantage** | Skills (classification and extraction) | A `NeedVerification` flag comes from thresholds (the example uses 70) **or** failed rules; rules rerun after an operator edits; rules can compute values (sums) and look up catalogs | Manual Review activity must follow Extract; Manual Review Client; online learning | [doc] https://docs.abbyy.com/vantage/getting-started/results.md ; https://docs.abbyy.com/vantage/documentation/skill-designer/process/manual-review |
| **Rossum** (Aurora, a "transactional LLM") | Transactional documents | Default "confident" threshold 0.975, described as calibrated so the score equals the probability of being correct. Thresholds are per field. **A validation error always blocks automation.** Grey tick = AI-validated, green tick = human-confirmed | Validation screen: Enter confirms and moves on, the user can type or click a region, automation blockers are shown; exact-duplicate detection | [doc] https://knowledge-base.rossum.ai/docs/using-ai-confidence-thresholds-for-automation-in-rossum ; https://knowledge-base.rossum.ai/docs/duplicate-detection-in-rossum ; [blog, vendor] https://rossum.ai/blog/rossum-aurora/ |
| **UiPath Document Understanding / IXP** | Taxonomy-driven classic and generative extractors | Two thresholds per field, OCR confidence (default 90%) and extraction confidence, and both must pass. A minimum-confidence filter drops predictions entirely. Optional generative "auto-validation" cross-check. IXP claims attribution to source plus calibrated confidence | Validation Station (classic and compact) | [doc] https://docs.uipath.com/document-understanding/automation-suite/2.2510/classic-user-guide/taxonomy-manager ; https://dplt.cms.uipath.com/docs/activities/other/latest/document-understanding/data-extraction-scope ; [doc, vendor claim] https://www.uipath.com/product/ixp |
| **Open-source OCR and layout** | PaddleOCR PP-OCRv5 (106 languages; Vietnamese is in the Latin model, with no Vietnamese-specific accuracy published); docTR; Donut (OCR-free, MIT code, CORD accuracy 91.1–93.9); LayoutLM family | Word or line boxes with scores; key-value extraction needs fine-tuning | Build your own | [doc] https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html ; [paper] https://arxiv.org/pdf/2111.15664 |
| **LLM vision** (Claude, GPT-5, Gemini) | Anything in a prompt schema | Claude: page-level `page_location` citations for text PDFs only. Gemini: boxes normalized to 0–1000 `[ymin,xmin,ymax,xmax]`. Confidence is not native or not calibrated | Build your own | [doc] https://platform.claude.com/docs/en/build-with-claude/citations ; https://ai.google.dev/gemini-api/docs/image-understanding |

Observations:
- Every product treats **validation rules as stronger than confidence**. Rossum blocks automation on any validation error. ABBYY flags on rule failure whatever the confidence [doc].
- **Thresholds are per field, and they need recalibration after a model change.** UiPath and Azure say so explicitly [doc].
- The "AI confirmed" and "human confirmed" states are kept apart in the UI and the data (Rossum's grey and green ticks, ABBYY's `verified` flag) [doc]. The ERP's audit model should copy this [inference].

## 1.2 Deterministic-first readers

Rule: if the document carries structure, parse it. A model is the fallback for pixels only [inference, consistent with the existing ADR-0051 reader].

### Vietnamese e-invoice (core contract; reader in the l10n_vn overlay)
- **Current law.** Decree 254/2026/ND-CP has applied since 2026-07-01, issued 2026-06-30. It replaces Decree 123/2020, Decree 70/2025 and Circular 32/2025. Circular 91/2026/TT-BTC gives the operational detail, including the XML data structure [doc/blog: https://www.fiscal-requirements.com/news/5767-vietnams-new-e-invoice-regulations-decree-2542026nd-cp ; https://thuvienphapluat.vn/phap-luat-doanh-nghiep/bai-viet/chinh-thuc-da-co-nghi-dinh-thay-the-nghi-dinh-123-va-nghi-dinh-70-ve-hoa-don-dien-tu-nghi-dinh-254-2026-nd-cp-22136.html]. The tax department introduced the changes in Official Letter 4831/CT-CS of 2026-07-15 [blog: https://luatvietnam.vn/thue/cong-van-4831-ct-cs-2026-cua-cuc-thue-ve-noi-dung-moi-tai-nghi-dinh-254-2026-nd-cp-va-thong-tu-91-2026-tt-btc-440460-d6.html].
- **Changes that touch inbound invoices** (secondary sources; verify against the text):
  - replacement invoices need a coded reason from Appendix XVII of Circular 91 [blog];
  - "time of creation" and "time of digital signature" are kept distinct [blog: https://bizzi.vn/en/decree-254-and-circular-91-on-electronic-invoices-new-points-and-what-businesses-need-to-update/];
  - buyer and seller identification must match the National Business Registration database [blog, same];
  - high-risk sellers can be forced onto per-transaction coded invoices, and invoices of sellers not operating at their registered address can be frozen [blog, same].
  For the ERP this means the supplier master should carry a tax-status flag, and the reader should record both timestamps [inference].
- **XML structure** (Decision 1450/QD-TCT 2021, amended by 1510/QD-TCT 2022):
  - `HDon` contains `DLHDon`, the seller's data, made of `TTChung` (general information) and `NDHDon` (content: seller, buyer, lines, totals);
  - `DSCKS` holds the signatures of the seller, the buyer if any, the tax authority, and others;
  - `MCCQT` is the tax authority code, at most 34 characters, 23 for cash-register invoices;
  - a message is at most 2 MB;
  - 1510 adds QR-code data inside `HDon` and a taxpayer signature on `TDiep\DLieu`
  [doc via https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Quyet-dinh-1450-QD-TCT-2021-thanh-phan-chua-du-lieu-nghiep-vu-hoa-don-dien-tu-490526.aspx ; https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Quyet-dinh-1510-QD-TCT-2022-sua-doi-Quyet-dinh-1450-QD-TCT-hoa-don-dien-tu-530232.aspx].
- **Legal weight.** The XML is the legal file and the PDF is a rendering. Practitioners cite Official Letter 1152/TCT-CS [blog: https://vinatas.com.vn/hoa-don-dien-tu-can-phai-luu-file-xml/]. Keep the original signed XML for 10 years [blog: https://www.fiscal-requirements.com/news/4803]. Do not save "only PDF files instead of the original XML" [blog: bizzi, above].
- **Verification.** The tax portal supports manual lookup by seller tax ID, series, number and code. Bulk lookup needs a login. **I found no official public verification API** [blog: https://www.meinvoice.vn/tin-tuc/771/tra-cuu-hoa-don-dien-tu/]. Practitioners check, in order: XML structure, digital signature, portal record, then the real transaction [blog: https://sme.misa.vn/351189/file-xml-hoa-don-dien-tu/]. Editing the XML breaks verification [blog].
- **Design consequence** [inference]:
  - The reader verifies the XML-DSig signature over `DLHDon` against the embedded certificate and a configured list of trusted certificate authorities. It checks that `MCCQT` is present for coded invoice types and that the arithmetic in section 1.5 holds.
  - The outcome is stored as `signature_status` (valid / invalid / unverifiable / expired certificate) and `portal_status` (unchecked / found / not_found), never inferred.
  - A PDF that arrives with the XML is attached as the rendering. It is never extracted when the XML is present.
  - Keep this reader in `l10n_vn`. The core owns only the generic `e_invoice_record` contract and the reader interface.

### Other structured formats (country-neutral core readers or later overlays)
- **Factur-X / ZUGFeRD** is a PDF/A-3 file carrying an embedded CII XML. The XML is registered in `/AF` and in the EmbeddedFiles tree, and XMP metadata names the profile [blog: https://ax.docentric.com/?p=34107 ; https://econnect.eu/en/docs/knowledge/document-formats/basics/hybrid-invoices]. Validation has three layers: XSD; EN 16931 Schematron business rules, which "are what actually reject invoices"; and PDF/A-3 conformance. ZUV and Mustangproject combine veraPDF with the official Schematron [blog: https://dev.to/facturata/your-factur-x-passes-xsd-and-still-gets-rejected-here-is-why-341g ; doc: https://github.com/ZUGFeRD/ZUV]. The Schematron is XSLT 2.0 and needs Saxon or similar [blog].
- **PEPPOL BIS Billing 3.0 (UBL)** has two rule sets, CEN-EN16931-UBL.sch and PEPPOL-EN16931-UBL.sch, and an XSD alone misses the Peppol rules. Releases change regularly (3.0.20-hotfix at the time of writing) [doc: https://docs.peppol.eu/poacc/billing/3.0/release-notes/ ; https://docs.peppol.eu/poacc/billing/3.0/upcoming/files/PEPPOL-EN16931-UBL.sch].
- **Detecting a hybrid PDF** is cheap: check the PDF's embedded files before anything else, and parse the XML if present [inference]. This matters for exporters and for foreign suppliers that send ZUGFeRD or UBL [inference].
- **Business-card QR codes** carrying vCard or MeCard decode deterministically [doc: https://developers.google.com/ml-kit/reference/swift/mlkitbarcodescanning/api/reference/Classes/BarcodeContactInfo]. Decode any QR or barcode first and use the LLM only for what is left [inference].
- **XLSX and CSV** are already a grid. Read cell values, not formulas, and keep a cell address as evidence (section 2.3) [inference].
- **Text-layer PDFs.** When a PDF has a real text layer, take words and coordinates from it, but compare it with OCR of the rendered page to catch hidden text (section 1.6) [inference].

## 1.3 Accuracy and limits: measured error rates

| Measurement | Number | Conditions | Tag and source |
|---|---|---|---|
| Native image vs text-parsed LLM, scanned receipts | 87.46% vs 47.00% field exact-match (best: Gemini 2.5 Pro) | 8 models (GPT-5, Gemini 2.5, Gemma 3), 3 public datasets, zero-shot | [paper] https://arxiv.org/abs/2509.04469 (figures via https://pith.science/paper/2509.04469) |
| Same paper, scanned invoices | 92.71% (Gemini 2.5 Pro) | same | [paper] |
| Line items, Jan 2025 third-party comparison | Azure 87%, Textract 82%, GPT-4o 63% image-only and 57% with OCR layer, Google Document AI 40% | scanned invoices; which Google processor was used is unclear | [blog] https://invoicedataextraction.com/blog/aws-textract-vs-google-document-ai-vs-azure-document-intelligence |
| Five-engine invoice test | Textract 91.3/91.1%, Azure 85.8/85.7%, Google 83.8 → 68.1% with tables, Gemini 1.5 Pro 90.0/90.2% | small set, not peer-reviewed; the ranking contradicts the row above | [blog] https://hackernoon.com/can-your-llm-handle-an-invoice-i-tested-5heres-the-truth |
| SAP generative extraction | "85–95% accuracy" | no method given | [doc, vendor claim] https://architecture.learning.sap.com/docs/ref-arch/b2b40e |
| LLM evidence fidelity (SafePassage) | best model about 95% of entities grounded; about 5% of copied contexts mistranscribed; Llama 4 Scout 42%; NLI verifier recall 0.857 and precision 0.928 | legal dataset, fixed schema | [paper] https://arxiv.org/html/2510.00276v1 |
| Donut on CORD receipts | 91.1–93.9 accuracy, depending on checkpoint | fine-tuned | [paper] https://arxiv.org/pdf/2111.15664 |
| Rossum default confidence threshold | 0.975, described as calibrated to expected accuracy | vendor | [doc] knowledge-base.rossum.ai |
| Visual prompt injection on a multimodal LLM | up to 64% attack success under stealth constraints | GPT-4-turbo, COCO images | [paper] https://arxiv.org/pdf/2603.03637 |
| Spotlighting (datamarking or encoding) | attack success from >50% to <2% | GPT-family, authors' corpus | [paper] https://arxiv.org/abs/2403.14720 |
| CaMeL | 77% of tasks solved with provable security vs 84% undefended (another version says 67%) | AgentDojo | [paper] https://arxiv.org/abs/2503.18813 |
| Whisper hallucination | about 1–1.4% of transcripts contained fabricated text; 38% of those were harmful; worse with long pauses | English, 2024 | [paper/blog] https://www.news.cornell.edu/stories/2024/06/ai-speech-text-can-hallucinate-violent-language |
| Vietnamese ASR (PhoWhisper-large) | WER 4.67 (VIVOS), 8.14 (Common Voice), 13.75 (VLSP T1), 26.68 (VLSP T2) | authors' evaluation | [paper] https://arxiv.org/pdf/2406.02555 |
| Title-block field extraction (detector + GPT-4o) | 86% key retrieval, 95% value matching | AEC drawings, cited in a 2026 benchmark | [paper] https://arxiv.org/pdf/2607.18997 |

Limits worth stating plainly:
- **Vendor accuracy figures cannot be compared with each other.** They differ in metric (field exact-match, character error rate, document-level straight-through rate), dataset and layout mix [blog, inference]. The only number that counts is measured on the company's own golden set [inference; matches ADR-0050 rule 39 golden sets].
- **Line items and tables are the weakest area** in every comparison [blog].
- **Vietnamese-specific accuracy is unpublished** for most engines. Azure's invoice model lists 27 languages, and I did not confirm Vietnamese among them [doc]. PaddleOCR lists Vietnamese with no Vietnamese benchmark [doc]. Expect to measure this yourself [inference].
- **Scanned PDFs cannot be cited** by Claude citations; only text-layer content can [doc]. LMDX grounding is reliable only at line level [paper]. Gemini boxes are model outputs, not measured coordinates [doc; inference].
- **Benchmark saturation.** OmniDocBench is over 94% for top models and mostly born-digital; the Real5 follow-up exists because real degradation is under-represented [paper: https://arxiv.org/html/2412.07626v2 ; blog: https://www.llamaindex.ai/blog/llm-ocr]. Phone photos of delivery notes are the hard case [inference].

## 1.4 Grounding, confidence and abstention

- **Field-level evidence** is standard in classic IDP: Azure gives bounding regions and spans [doc], Textract gives blocks [doc], and ABBYY and Rossum highlight the region on the page [doc]. Content Understanding and UiPath IXP now add it to generative fields [doc].
- **LLM-native evidence is self-reported and must be checked.**
  - LMDX: the model cites OCR line IDs, and code localizes from them [paper].
  - SafePassage: the model copies an evidence passage; code aligns it with Smith–Waterman (threshold 0.6) and then an NLI model checks that the passage supports the value [paper].
  - Practical rule: **a value counts as grounded only if code can find it on the page** [inference].
- **Confidence calibration.**
  - Raw VLM token probabilities are poorly calibrated. Hidden-state probes or geometric risk controllers can drive abstention [paper: https://arxiv.org/abs/2511.19806 ; https://arxiv.org/abs/2603.19790].
  - Practical proxies [inference]:
    - agreement between two independent readers (an OCR-layout engine and a VLM);
    - exact string match of the value to OCR tokens;
    - arithmetic consistency;
    - a match to master data (known supplier tax ID, known item code).
- **Abstention.** Each field must allow "not found" and "illegible" as first-class outputs. A VLM "made up names and dates that sort of fit the vibe" on unreadable handwriting [blog, anecdote: https://hn.svelte.dev/item/43187209]. Schema design should never force a value [inference].

## 1.5 Validation rules and duplicate detection

Deterministic checks to run on every extraction [inference, built on ABBYY and Rossum rule engines and EN 16931 / Peppol rule patterns]:
- **Arithmetic.**
  - Line: quantity × unit price − discount = line amount, within a rounding tolerance per currency.
  - Lines summed = pre-tax total.
  - Per tax rate: base × rate = tax amount.
  - Pre-tax total + tax − allowances + charges = grand total.
  - Amount in words equals amount in figures (a common field on Vietnamese invoices) [inference].
- **Formats and check digits.** Tax ID format: Vietnamese MSTs are 10 digits plus an optional 3-digit branch suffix, with a check digit (confirm in l10n_vn). GTIN mod-10. IBAN mod-97 for foreign suppliers. Date sanity: issue ≤ receipt, within the open period.
- **Master-data consistency.** Seller tax ID belongs to a known supplier, or else creates a supplier proposal. Buyer tax ID equals our own company's ID, which catches misdirected invoices. Currency is allowed for the supplier. PO number exists and is open for that supplier.
- **Bank details never update the master from a document.** A changed bank account on an invoice is a classic fraud pattern [inference]. Route it as a change proposal that needs out-of-band confirmation.
- **Duplicates** [blog: https://us.fitgap.com/stack-guides/flag-duplicate-invoices-before-payment-runs ; https://www.corpay.com/en-IE/resources/blog/duplicate-payment-detection]:
  - (a) exact byte hash of the attachment;
  - (b) deterministic key: seller tax ID + template/series + invoice number, normalized (strip separators and leading zeros);
  - (c) near-duplicate: same seller, amount within tolerance, date within a window, or the same PO. Practitioners suggest 85–90% similarity on the number string, but no standard exists; tune it on your own history;
  - (d) compare against full history, not only open items, because a paid invoice no longer collides in many ERPs [blog].
  Rossum's own duplicate detection covers exact duplicates only [doc]. For Vietnamese e-invoices, the key in (b) is legally unique, so (b) is decisive and (c) only advises [inference].

## 1.6 Prompt injection in documents and images

Attack channels:
- **Hidden text in PDFs** (white text, tiny fonts, off-page text) passes through text-layer parsers such as PyMuPDF and Mistral OCR on PDF input. Pipelines that rasterize and OCR drop it [paper: https://arxiv.org/pdf/2509.10248 ; blog: https://oneofftech.xyz/blog/ultraviolet.md].
- **Malicious fonts and glyph remapping**: the text the model reads differs from what a human sees [paper: https://arxiv.org/pdf/2505.16957].
- **Visible or stealthy instructions in images** [paper: https://arxiv.org/pdf/2603.03637]. Real hidden injections have been found in résumé PDFs, mostly white-on-white text [paper: https://arxiv.org/pdf/2605.28999].
- **Detection alone falls short.** The CrackedPDFs benchmark (29,322 PDFs) finds document-aware hybrid detection useful under controlled evaluation, but shows no "broad real-world robustness" [paper: https://arxiv.org/pdf/2607.19396].

Defenses, strongest first:
1. **Capability containment.** The reader that sees raw pixels or text has no tools, no memory and no outbound channel. It returns a typed schema (CaMeL / dual-LLM: untrusted data cannot change control flow) [paper: https://arxiv.org/abs/2503.18813]. Remove one leg of the "lethal trifecta" (private data, untrusted content, external communication) [blog: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/]. The ERP already enforces this: tainted runs only draft and cannot send or post [doc, internal: spec/03].
2. **Typed output and code checks.** Every extracted value is a typed field that must align to page tokens (section 1.4). An injected "instruction" has nowhere to go except a free-text field marked untrusted [inference].
3. **Render, then read.** Send the VLM a raster of the page, not the PDF's text layer. Dangerzone's method (render to pixels in a sandbox without network, then rebuild) also removes active content [doc: https://github.com/freedomofpress/dangerzone]. **Diff the text layer against OCR of the render.** Text that exists only in the layer means hidden-text suspicion. Set a flag and show it to the reviewer [inference].
4. **Spotlighting.** Datamark or encode the untrusted text and say so in the system prompt [paper: https://arxiv.org/abs/2403.14720]. It is cheap and a useful layer, not a boundary [inference].
5. **Classifiers** (Prompt Shields and others) only add a signal and a flag, never a gate [doc: Prompt Shields within Azure AI Content Safety, via the spotlighting search; blog: "95% is a failing grade"].

## 1.7 Privacy of images and redaction

- **Legal baseline in Vietnam.** The PDP Law (91/2025/QH15) and Decree 356/2025 have applied since 2026-01-01; Decree 356 replaced Decree 13/2023. Cross-border transfer explicitly includes "offshore storage, cloud-based processing and onward processing" of data collected in Vietnam and needs a filed transfer impact assessment. Fines can reach 5% of the prior year's revenue for serious violations [blog: https://www.tilleke.com/insights/new-decree-provides-guidance-for-vietnams-personal-data-protection-law ; https://vn.rajahtannasia.com/?p=63882 ; https://fpf.org/wp-content/uploads/2026/01/January-2026-FPF-Issue-Brief-Making-Sense-of-Vietnams-Latest-Data-Protection-and-Governance-Regime-1.pdf]. Sending a business-card photo to a foreign model API is a cross-border transfer of personal data [inference]. Keep the legal detail in l10n_vn, as decided on 2026-11-15.
- **What is personal in these cases** [inference]:
  - business cards: name, phone, e-mail, photo;
  - delivery notes: driver name, phone, ID or licence-plate number, signature;
  - supplier invoices from household businesses: the seller is a natural person;
  - inquiry e-mails: the sender;
  - voice notes: voice is biometric-adjacent, so check the sensitive category under Decree 356.
- **Whole-attachment labelling.** A field-level gateway cannot strip values from an image. The label therefore belongs to the whole attachment: `personal` by default for photos, business cards and delivery notes, and `non-personal` only for document kinds whose deterministic reader proves it [inference; aligns with capability_check direction].
- **Redaction tooling.** Presidio's image redactor uses OCR plus NER to find boxes and fills them. It is "still in beta and not production ready" [doc: https://microsoft.github.io/presidio/image-redactor]. Redaction depends on OCR recall: what the OCR misses, the redactor misses [doc: same, verify-engine note]. Use redaction to produce a derived copy for a non-personal seat. Never treat a redacted copy as proof that no personal data remains [inference].
- **Image metadata.** Phone photos carry EXIF GPS, device and time. Strip it from every derived copy sent to any model, and keep the original under the attachment's access rules [inference].

## 1.8 Storing extraction results with provenance

The products surveyed keep: raw document, OCR layer, field values with confidence and regions, rule results, and the human verification state. Rossum and ABBYY keep AI-validated and human-validated apart [doc]. SAP and Rossum feed corrections back into learning [doc]. Proposed record [inference]:

```
document_extraction            (one per reader run; immutable)
  id, attachment_id, attachment_sha256, page_count
  document_kind_detected       (vn_einvoice_xml | cii | ubl | pdf_text | image | xlsx | ...)
  reader_kind                  (deterministic_xml | pdf_text | ocr_layout | vlm | qr | xlsx)
  reader_name, reader_version  (parser version; for vlm: model id, seat id, prompt/template version)
  agent_run_id                 (null for deterministic system jobs)
  data_label                   (personal | non_personal), inherited from the attachment
  hidden_text_suspected        bool
  signature_status, portal_status   (e-invoice only)
  status                       (extracted | validated | needs_review | verified | rejected)
  created_at

document_extraction_field      (one per field occurrence; immutable; corrections are new rows)
  extraction_id, field_path    (e.g. lines[3].unit_price)
  value_raw (as seen), value_normalized, value_type, unit
  evidence_kind                (xpath | char_span | cell_ref | page_region | qr_payload | audio_span)
  evidence                     ({page, polygon in 0..1 page coords, token_ids} | {xpath} | {sheet, cell} | {t_start, t_end})
  method                       (parsed | ocr_token | vlm_aligned | vlm_unaligned | computed)
  confidence_raw, confidence_calibrated, agreement (second reader equal? y/n)
  rule_results                 ([{rule_id, pass, detail}])
  is_untrusted                 (true for free text from outside content)
  verified_by_user_id, verified_at, superseded_by_field_id
```

- Rendered page images (derived, hashed) are stored as attachments so the evidence region can be redrawn later. Store polygon coordinates normalized 0..1, not pixels, so they survive re-rendering [inference].
- `method = computed` marks values code derives, such as totals and tax. They are never model values [inference; Principle 13].
- An optional mapping to W3C PROV (entity = attachment and field, activity = reader run, agent = reader or person) is cheap when auditors want it [inference].

## 1.9 Pitfalls

1. Extracting the PDF when the signed XML is present. Only the XML has legal weight [blog].
2. Trusting text-layer extraction: it is the injection channel [paper].
3. Trusting LLM-reported confidence or LLM-reported citations without alignment [paper].
4. One global threshold instead of per-field thresholds, and not recalibrating after a model change [doc].
5. Forcing every schema field to a value, which manufactures hallucinations [blog/paper].
6. Comparing vendor accuracy claims across different metrics [inference].
7. Building review UI around the vendor's tool. Google's HITL was withdrawn [doc].
8. Duplicate checks only against open items [blog].
9. Letting a document update bank details or payment terms [inference].
10. Sending personal-data images abroad without a transfer impact assessment [blog, legal].
11. Treating a redacted image as non-personal [inference; Presidio beta caveat].
12. Using the business-card model of Azure, which is deprecated [doc].
13. Voice transcripts trusted as text. Whisper fabricates text during silences [paper].

## 1.10 Transferable patterns

- **Reader ladder**: structure → barcode/QR → text layer (cross-checked) → OCR layout → VLM. Stop at the first rung that yields a valid record [inference].
- **Quarantined reader**: a tool-less model that returns typed output and whose output is data [paper: CaMeL].
- **Evidence or abstain**: a value without code-verified evidence is shown as "suggested, unverified" or left empty [paper: SafePassage, LMDX].
- **Rules over confidence**: validation failures always block, whatever the confidence [doc: Rossum, ABBYY].
- **Two reviewer states**: machine-checked vs human-confirmed, per field [doc: Rossum].
- **Corrections become deterministic rules**: supplier-specific field mappings, unit mappings and item cross-references, stored as proposal-bound company data so the next case needs no model [doc: SAP instant learning, Rossum learning; inference: matches ADR-0051's "deterministic share must rise"].
- **Golden-set gating**: no reader, model or prompt change ships without a replay on the company's labelled set, with thresholds recalibrated per field [doc: UiPath and Azure recalibration notes; inference].

## 1.11 Recommendations for the ERP (intake)

### A. How an image or PDF becomes structured data with evidence (the pipeline)

[inference throughout, building on ADR-0038, 0050, 0051 and 0052 as summarized in capability_check.md]

1. **Intake (exists).** The IMAP job (no LLM) runs `CreateAttachment` for the raw message and each allowed part. Scan state must be `clean` before any reading (ADR-0038 r14).
2. **Sniff (deterministic system consumer).** Use magic bytes, not the extension. Then check, in order: XML root namespace, embedded files in the PDF, barcodes and QR codes on images and pages, and whether the PDF has a text layer. Record `document_kind_detected`. Strip EXIF on every derived image.
3. **Deterministic readers.** Readers for VN XML (overlay), CII/Factur-X, UBL, QR vCard and XLSX write a `document_extraction` with `method = parsed` and xpath, cell or payload evidence. For e-invoices this path is `ImportEInvoiceRecord`, run as `system` (close the mailbox-to-e-invoice route in core, as capability_check proposes).
4. **OCR layout reader** (for images and image PDFs): a word and line layer with boxes. Use a local engine (PaddleOCR-class) or a cloud layout API behind the same adapter. Output: tokens with ids and boxes, stored as a derived artifact.
5. **VLM reader** (only when 3 yields nothing):
   - Input: the rendered page image plus the token list (ids, text, boxes), datamarked.
   - Output schema: every field is `{value, token_ids[], page, status ∈ {found, not_found, illegible}}`.
   - The seat is "extraction with image and PDF reading", data class `personal` (section C). There are no tools.
6. **Alignment and checks (code).** For each VLM field, normalize and match the value against the concatenated text of the cited tokens.
   - Exact match after normalization → `vlm_aligned`.
   - Fuzzy match (Smith–Waterman ≥ threshold) → `vlm_aligned` with lower calibrated confidence.
   - No match → `vlm_unaligned`, shown as a suggestion only and never pre-filled into a draft.
   - Numbers must match exactly, digits included.
   - Computed fields (totals, tax) are recomputed by code and compared.
7. **Validation and duplicates** as in section 1.5. Status becomes `validated` or `needs_review`.
8. **Draft creation.** The workflow, not the reader, maps the record to a draft: a contact or partner change proposal, a draft purchase invoice, extra quotation lines, or a draft goods receipt. Only aligned or parsed fields pre-fill, and each pre-filled field links to its evidence.
9. **Verification screen** (build it into the ERP):
   - page on one side with evidence boxes, fields on the other;
   - order fields by risk (amounts, tax ID, bank and dates first);
   - keyboard-first, with Enter to confirm and move on (Rossum pattern);
   - unaligned suggestions are greyed out;
   - the hidden-text flag and rule failures appear at the top;
   - each human confirmation writes `verified_by`.
10. **Learning.** Corrections produce proposals for supplier-specific mappings, such as "supplier X's 'Mã hàng' column means supplier_item_code" or "unit 'cái' = PCE", reviewed like any rule. The deterministic share is measured per supplier.

### B. Where taint applies

[inference; consistent with spec/03 and ADR-0050 as summarized]
- **The reader run** (VLM step) is always tainted and needs no extra narrowing: it has no tools and produces data only.
- **Two kinds of trust, two different controls.**
  - *Instruction taint*: can this content steer an agent? Any free text from outside content (descriptions, notes, names, addresses, e-mail bodies) is `is_untrusted`. An agent run that reads it becomes tainted, which narrows it to one partner scope and drafts only. This already exists.
  - *Value trust*: is this number right? A typed field (amount, tax ID, date, item code) can still be attacker-chosen even though it cannot carry instructions. Taint does not control this; evidence alignment, validation rules and human verification do.
- **Typed fields that taint nothing.** Fields that are typed **and** passed deterministic validation (format, check digit, arithmetic, master-data lookup) do not taint a downstream run that reads only them. This matches the existing rule that structured e-invoice fields are trusted and free text is not (adr/0051:171). VLM-extracted typed fields stay "value-untrusted" until a person verifies them. They may pre-fill a draft but cannot auto-post or auto-match in Phase 1.
- **Signature failure.** A Vietnamese XML whose signature fails verification has all its fields downgraded to the image-derived trust level.
- **Hidden text.** When `hidden_text_suspected` is set, the whole extraction requires full human verification, and the hidden text itself is stored as untrusted evidence for the reviewer.

### C. How personal data is handled

[inference; legal facts tagged in section 1.7]
- Photos, business cards, delivery notes, voice and inquiry attachments are labelled `personal` as a whole on intake, unless a deterministic reader proves otherwise. Structured invoice XML from a company seller is `non_personal`, with household-business sellers as the exception.
- A `personal` attachment may go only to a seat approved for personal data with image input. The gateway sends or blocks the whole attachment and never partially strips it. Phase 1 preference: an in-country or self-hosted model for that seat, such as an open VLM on local hardware, which avoids a cross-border transfer dossier. A foreign API is allowed only once the l10n_vn overlay records a transfer impact assessment for it.
- A derived, redacted copy (OCR plus NER boxes filled) may go to a non-personal seat. It is labelled `redacted_derivative`, never `non_personal`.
- EXIF is stripped from every derived image. Retention follows the source document type: 10 years for invoice XML, and the contact-data policy for business cards, with deletion on request where the law requires it.

### D. Phase plan per case

| Case | Phase 1 | Later | Tradeoff |
|---|---|---|---|
| **Supplier e-invoice XML by mail** | Mail → XML part → `ImportEInvoiceRecord` (system) → signature and MCCQT checks → arithmetic → duplicate key → draft purchase invoice (existing workflow). PDF kept as rendering only | Portal lookup automation, if an official API appears; Factur-X/UBL readers for exporters | Deterministic and legally decisive. The reader must follow the Circular 91 format; schema-version dispatch costs little |
| **Supplier invoice, PDF only** (foreign, scanned) | Embedded-XML check (Factur-X); else text layer cross-checked with OCR, then VLM; full human verification, no auto-post, no auto-match | Calibrated thresholds per supplier after a golden set exists; straight-through for high-agreement suppliers | Extra reviewer time in exchange for no silent errors |
| **Business card photo** | QR vCard first; else OCR plus VLM on the personal seat → `CreateContact` change proposal with evidence; duplicate check on e-mail and phone | Batch scanning from a phone app | Low financial risk and high value, so a good first vision case. Personal data makes the seat choice decisive |
| **Customer inquiry with attachments** | XLSX and CSV lines read deterministically into draft quotation lines (tainted, partner scope); PDF and drawing stored and shown side by side, a person keys lines | VLM line extraction from PDF RFQs; title-block reading (Part 2) | RFQ PDFs vary widely, so the value of extraction is lower than for invoices |
| **Delivery note photo** | Stored and linked to the receipt; a person confirms quantities against the PO with the image beside it | VLM extraction to pre-fill a draft goods receipt, matched to PO lines by code | Phone photos are the hardest input (skew, glare, handwriting); the error cost is inventory accuracy |
| **Voice note** | Not in Phase 1 | Local Vietnamese ASR (PhoWhisper-class); transcript stored with audio-span evidence, untrusted and personal; drafts only | Hallucination during silences; voice is personal data |

Engine choice [inference]: keep one `reader` adapter interface with engines behind it (local OCR, cloud layout, VLM). Do not adopt a cloud IDP schema as the core model. Vendor schemas differ, and Google's HITL withdrawal shows how fast managed review features can disappear.

---

# Part 2. Agent-assisted master data creation

## 2.1 What systems do

### ERP master-data governance
- **SAP MDG.**
  - A change request writes to a **staging area**. Rule-based workflow steps (create, check, approve, process, revise, final check, activation) are configured per change-request type [doc: https://help.sap.com/saphelp_mdg80/helpdata/en/df/79cc5284084a4ee10000000a423f68/content.htm].
  - Validations and derivations are BRF+ rules bound to the change-request type. A failed validity or required-field check blocks activation. Duplicate check runs from the staging area, has no ranking, and can run on demand since S/4HANA 2022 [doc, same family of help pages; blog: https://blogs.sap.com/2022/10/12/benefit-from-sap-master-data-governance-on-sap-s-4hana-2022/].
  - Generative AI: Joule produces change summaries and assisted changes for approvers ("initial steps") [blog, SAP community: https://community.sap.com/t5/technology-blogs-by-sap/benefit-from-sap-master-data-governance-on-sap-s-4hana-2023-feature-pack/ba-p/13808294].
  - Data quality analytics cover product master segments [doc].
- **SAP Joule in PLM (S/4HANA Cloud Public).** Joule explains how to create a material BOM and which app to use, retrieves BOMs and change records in natural language, and the Maintain BOM app has an **AI summary** of the component structure [doc: https://learning.sap.com/courses/implementing-product-lifecycle-management-in-sap-s-4hana-cloud-public-edition/discovering-sap-ai-features_aa527e2d-a8af-4cd7-b215-0ae196e25fdd]. I found no Joule feature that creates BOMs from a description [gap].
- **Dynamics 365 Supply Chain Management, engineering change management (ECM).**
  - ECM has been mandatory since 10.0.36 [doc: https://learn.microsoft.com/dynamics365/supply-chain/engineering-change-management/product-engineering-overview].
  - Product master data lives in one **engineering company** and is released to operating companies. Engineering products can be released only from there [doc: https://learn.microsoft.com/en-us/dynamics365/supply-chain/engineering-change-management/release-product-structure].
  - Engineering product categories define version numbering, **release policies** (which data goes to which company) and **readiness policies** (checks that required data exists before use) [doc/blog: https://technologyblog.rsmus.com/microsoft/dynamics-365-for-finance-and-supply-chain/setup-and-configuration-for-engineering-change-management-functionality-part-1].
  - Microsoft's own Copilot in SCM covers purchase-order change summaries, demand planning and help. I found **no native Copilot for ECM**. A third-party add-on ships an "impact agent" for engineering change orders [doc/blog: https://docs.staedean.com/manufacturing/docs/analyze-the-impact-of-an-engineering-change-order].
- **Oracle Fusion Product Hub / PIM.**
  - Generative AI writes item descriptions "based on product-attribute data stored in" PIM. The user reviews and saves [doc: https://blogs.oracle.com/fusioninsider/post/new-genai-helps-launch-products-faster-demo].
  - Duplicate matching rules are defined per **item class**. Trade identifiers are matched in a fixed order: GTIN → supplier part number → manufacturer part number → ... [doc: https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25d/fapim/how-items-are-matched.html].
  - A profile option decides whether a duplicate may still be saved [doc].
  - There is a **New Item Request** workflow with entry and exit criteria and an approval phase [doc: 25c faipr TOC].
  - Known gap: the duplicate check did not run for items loaded through import maps [doc, support note: https://support.oracle.com/knowledge/Oracle%20Cloud/2854470_1.html].

### PLM and the CAD-to-BOM path
- **Siemens Teamcenter.**
  - Easy Plan builds the MBOM in the context of the EBOM. It offers side-by-side reconciliation, a change summary panel for EBOM updates, and **accountability checks** to find inconsistencies. MBOM changes are tracked in a manufacturing change notice (MCN) [doc, vendor: https://blogs.sw.siemens.com/teamcenter-manufacturing/2026/08/24/mbom-management-keeping-manufacturing-aligned-with-product-changes/ ; https://resources.sw.siemens.com/it-IT/fact-sheet-turn-engineering-boms-into-production-ready-manufacturing-boms/].
  - Teamcenter Copilot and the **AI BOM agent** "understand BOM structures, analyze impact, and execute changes within governed workflows" [doc, vendor claim: https://www.siemens.com/en-us/products/teamcenter/teamcenter-ai/]. A third-party blog dates the agent to release 2606, with proposals under human review [blog: https://www.getleo.ai/blog/teamcenter-built-in-ai].
- **PTC Windchill.**
  - BOM Transformer keeps **equivalence links** between upstream (EBOM) and downstream (MBOM) parts, including alternate and occurrence links.
  - Out-of-date links appear when the upstream part has a newer iteration.
  - A preference controls whether attributes copy downstream.
  [doc: https://support.ptc.com/help/windchill/r13.0.1.0/en/Windchill_Help_Center/mpmlink/ExpMPM_EbomMbom.html ; https://support.ptc.com/help/wnc/r12.0.0.0/en/Windchill_Help_Center/ExpMPM_EquivLinkCreate.html]
  - Windchill AI Parts Rationalization (2026) targets duplicate parts [blog: https://briefglance.com/companies/ptc-inc/pulses/135 ; https://monoist.itmedia.co.jp/mn/articles/2603/02/news043_2.html].
- **Arena.** Excel, CSV and PDX import and export; ECO approval routing by change type, priority and product line; no release without approval [doc, vendor: https://arenasolutions.com/products/plm/features/change-management]. Arena recommends non-intelligent part numbers [doc, vendor: https://www.arenasolutions.com/resources/articles/part-numbering/].
- **Propel.** "Propel One" agentic skills cover item, BOM and change work, including bulk item creation from a description. Propel offers an MCP connector so outside AI clients can query live PLM data [blog/doc, vendor: https://www.sdcexec.com/software-technology/software-solutions/news/22969739/propel-software-propel-software-launches-production-model-context-protocol-for-plm-agents]. No published validation method [gap].
- **CAD-native structure.** STEP AP242 has recommended practices for product and assembly structure (MBx-IF, v3.1, 2022) [doc: https://www.mbx-if.org/documents/rec_prac_ap242xml_assy_struct_v3.1.pdf]. I found no mature open-source AP242-to-BOM tool. OpenCascade-based parsing or PLM CSV exports are the practical routes [blog/inference].

### AI that reads drawings
- **Research.**
  - Detect-then-read pipelines: YOLOv11 detects views, title blocks and notes (title-block detection about 0.99), then a Donut-class VLM reads each region into one JSON [paper: https://arxiv.org/pdf/2510.21862].
  - An oriented-box detector plus Donut, trained on 1,367 drawings, reports GD&T precision of 94.77% [paper: https://arxiv.org/pdf/2505.01530].
  - Faster R-CNN plus GPT-4o on AEC title blocks: 86% key retrieval, 95% value matching [paper, cited in https://arxiv.org/pdf/2607.18997].
  - I found **no paper focused on parts-list (BOM table) extraction from drawings** [gap].
- **Products.**
  - Werk24 reads title blocks, dimensions, GD&T and revision tables into typed JSON at €1.25 per page. Its 98% figure is a customer case study [doc, vendor claim: https://werk24.io/use-cases/pmi-extraction ; https://werk24.io/llms.txt].
  - CADDi Drawer finds structurally similar drawings, even from a sketch, and shows **past prices, suppliers and purchase records** for them [doc, vendor claim: https://us.caddi.com/faq ; https://us.caddi.com/product/procurement].
  - Paperless Parts' Wingman reads RFQ e-mails and prints for GD&T, materials and finishes, and estimators review [doc, vendor claim: https://mtdcnc.com/news/mtdcnc/paperless-parts-wingman-ai-revolutionizes-quoting-accuracy-and-collaboration-for-job-shops].

## 2.2 Spreadsheet import practice

- **Stage before commit.** Load into a holding area that changes no live records. Map columns flexibly, validate each row on upload, preview with a summary, and commit only after confirmation [blog: https://appmaster.io/blog/staging-tables-vs-direct-imports-csv-excel-uploads ; https://dromo.io/blog/5-best-practices-to-streamline-your-csv-import-process ; doc: https://developer.salesforce.com/docs/platform/dataloader/guide/data-import-best-practices.html ; https://www.ibm.com/docs/SSANHD_7.6.1.x/com.ibm.sccd.doc/import/c_best_practices_for_data_import.html].
- **Formula injection.** Cells starting with `=`, `+`, `-`, `@` (also tab and carriage return) run as formulas when re-opened. Escaping is unreliable in Excel. Neutralize on export and flag on import [doc: https://owasp.org/www-community/attacks/CSV_Injection].
- **Specific to the ERP** [inference]:
  - read cached values, not formulas, and record a formula's presence as a warning;
  - XLSX only, no macro formats (already the ADR-0038 allowed-type list);
  - merged cells and multi-row headers are the usual failure: the column mapper (LLM-assisted) proposes a mapping, and the **mapping** is saved and reused as a company rule, not the data;
  - every imported row keeps `{sheet, row, column}` evidence;
  - a duplicate check must run on the import path too. Oracle's import-map gap shows why [doc].
- **Who owns the file decides taint** [inference]. A person's own spreadsheet imported as a batch is the `import_batch` scope (existing). A customer's or supplier's spreadsheet is outside content and tainted, even when a person uploads it.

## 2.3 Costing from BOM and routing, and quoting tools

- **Deterministic rollup (SAP CK11N as reference)** [doc: https://help.sap.com/doc/6297d7531a4d414de10000000a174cb4/1610%20002/en-US/c4a4b9537cceb44ce10000000a174cb4.html ; https://learning.sap.com/courses/outlining-cost-estimate-options-in-product-cost-planning/explaining-the-valuation-of-quantity-structure]:
  - estimate key: material, plant, costing variant, costing version;
  - quantity structure: only BOMs and routings with status "release for costing", and only BOM items flagged costing-relevant;
  - operations: work center → cost center → activity type with a **planned activity price**;
  - lot size sets setup apportioning, since setup does not depend on lot size and machine time does;
  - multilevel cost rollup; mark, then release, to move the price into the material master;
  - known traps: rounding and low routing quantities giving wrong activity prices (SAP KBA 3696269), and lot size overrides (KBA 2445963) [doc].
- **Quoting tools.**
  - Paperless Parts: CAD geometry analysis (setups, features, volume removal, manufacturability warnings) feeds **the shop's own** costing templates; the estimator reviews and can adjust every quote [doc, vendor: https://www.paperlessparts.com/processes/cnc-machining].
  - Xometry: deep learning on marketplace job data plus geometry. Pricing also uses customer history and conversion models, so it is market price, not cost [doc/blog: https://xometry.com/machine-learning-for-manufacturing ; https://www.digitalcommerce360.com/2026/03/03/xometry-tightens-grip-on-ai-sourcing/].
  - aPriori: physics and process simulation from CAD, with about ±30% spread admitted [blog, vendor].
  - Competitors include DigiFabster, Machine Research and Costimator [blog].
- **LLM estimation.** No credible manufacturing study found. A construction-costing preprint tested GPT-4o, Claude 3.5 and Gemini with chain-of-thought and reports only a confidence score [paper/preprint: https://www.preprints.org/manuscript/202510.1060]. Practitioners say AI "only goes as far as the first draft" [blog: https://timewell.jp/en/columns/manufacturing-cost-estimation-ai].
- **Transferable** [inference]:
  - Cost is a pure function of (released or draft BOM, routing, rates, lot size, valuation date).
  - The LLM's role is to **get the quantity structure drafted**: which components, which operations and their standard times from a source span. Code costs it.
  - Missing rates or times are explicit gaps, never filled by the model.
  - "Similar past items with their actual costs" (CADDi pattern) is useful *evidence* next to the computed estimate.

## 2.4 Data quality and duplicate detection for items

- **Entity resolution.** Pairwise comparison is quadratic, so use **blocking** (category, UoM, key tokens) before scoring [paper: https://journals.ysu.am/bulletin-ysu-economics/article/download/14584/11393/36915].
- **Normalization** of units, abbreviations, spec strings and manufacturer names comes before matching. Classification schemes such as UNSPSC and eCl@ss give the taxonomy backbone [blog: https://www.creactives.com/wp-content/uploads/2026/08/How-to-find-duplicate-materials-with-AI-in-global-inventory.pdf ; https://verusen.com/mro-data-master-data/how-ai-identifies-duplicate-mro-materials-across-complex-enterprises/].
- **Semantic matching** catches "M8x20 hex bolt zinc" against "Bulong lục giác M8 dài 20 mạ kẽm", where lexical matching fails [blog; inference for the Vietnamese example]. A vendor reports a 45% cut in duplicate material records [blog, vendor claim: https://www.credencys.com/work/parts-materials-master-data-management/].
- **Identifier precedence**, following Oracle: GTIN → supplier part number → manufacturer part number → customer part number [doc].
- **Part numbers.** PLM practice favours **non-intelligent (sequential) numbers** with meaning carried in attributes and category, and at most a short, governed category prefix [doc/blog: https://www.arenasolutions.com/resources/articles/part-numbering/ ; https://openbom.com/blog/part-numbers-best-practices-and-future-improvements ; https://www.durolabs.co/blog/part-numbering-systems-best-practices]. This matters for agents: a model should never *compose* a code, only a sequence should issue it [inference].

## 2.5 Governance: draft → review → release, engineering change

- **Common shape across SAP MDG, D365 ECM, Oracle NIR, Arena, Teamcenter and Windchill** [doc, sections above]:
  - a change object (CR / ECO / NIR / MCN) holds proposed changes in **staging** or a **draft revision**;
  - **rules** (validation, required fields, readiness) gate progress;
  - **duplicate check** at creation;
  - **approval routing** by type, value and product line;
  - **activation or release** with effectivity;
  - **release policies** say which data moves to which plant or company.
- **EBOM → MBOM practice** [blog: https://www.getleo.ai/blog/ebom-to-mbom-transformation-handoff ; https://book.st-hakky.com/en/industry/ebom-mbom-conversion-pitfalls ; https://virtualdutchman.com/2015/09/27/the-importance-of-a-plm-data-model-ebom-mbom/]:
  - remove or flag phantom groupings and link their children up, without double counting;
  - regroup by station or kit;
  - add consumables (adhesive, solder, labels, packaging) at as-consumed quantities;
  - keep make/buy, approved manufacturer list and approved vendor list explicit;
  - trace every MBOM line to the released EBOM and audit divergence periodically;
  - renumbering operations breaks component-to-operation assignments.
- **ECO evidence** [inference from ECM add-on impact agents, Teamcenter impact analysis and Windchill out-of-date links]: where-used, open production and purchase orders, on-hand stock of superseded components and their disposition, cost delta, effectivity date.

## 2.6 Accuracy and limits

- No vendor publishes accuracy for AI-drafted BOMs or routings [gap]. The LLM-for-BOM literature is thin. A generic LLM "lacks the specialized expertise to produce detailed Bills of Process" without domain input [paper: https://link.springer.com/article/10.1007/s10845-025-02732-z]. LLM plans "may still include infeasible steps under strict manufacturing constraints" [paper: https://arxiv.org/pdf/2606.29627].
- Drawing title blocks: about 86–95% field-level in research [paper]. GD&T about 95% precision in one framework [paper]. Parts lists are unmeasured [gap].
- Should-cost: about ±30% even for simulation tools [blog, vendor].
- Duplicate detection thresholds are company-specific, and no standard cutoff exists [blog].
- The AI master-data features shipped by the major vendors summarize, search, describe from existing attributes, and flag duplicates. **None auto-releases** [doc].

## 2.7 Pitfalls

1. Letting the model invent item codes, standard times, rates or prices. These must come from a source span, master data or a sequence [inference; Principle 13].
2. Creating a new item when an equivalent exists, caused by a tainted run that cannot see the catalog. This is the open read-scope question [inference, internal].
3. Duplicate check skipped on bulk import [doc: Oracle note].
4. Flat import of a multi-level BOM, losing levels or phantoms [blog].
5. Costing a draft BOM with missing rates silently as zero. Show the gaps [inference; SAP traps].
6. A single BOM serving both engineering and manufacturing without traceability. When CAD-derived EBOMs arrive later, the two diverge [blog].
7. Intelligent part numbers chosen by agents [blog].
8. The approver being the same person whose request triggered the agent run (already forbidden by spec/03 r5) [internal].
9. Customer drawings: a tainted source whose text may contain instructions such as "use supplier X" or "price at Y" [inference].

## 2.8 Transferable patterns

- **Staging and change object**: everything an agent makes is a draft revision or a change proposal. Release and activation are separate, approved steps (MDG CR, ECO, MCN) [doc].
- **Readiness checks as code**: per-category required attributes and structures before release (D365 readiness policies) [doc].
- **Candidate-first resolution**: the deterministic ranker proposes existing items, and the model only chooses or declares "new" with a reason (Oracle matching order plus entity-resolution blocking) [doc/paper; inference].
- **Equivalence links**: every derived line points to its source line or evidence (Windchill), giving traceability from a drawing cell or spreadsheet row to a BOM line [doc; inference].
- **Similar-item evidence**: show similar released items with their structures and actual costs as reference (CADDi) [doc, vendor; inference].
- **Descriptions from attributes, not attributes from descriptions**: generate display text from structured attributes (Oracle), and extract attributes only with evidence [doc; inference].

## 2.9 Recommendations for the ERP (master data)

### A. One workflow: `product_engineering` (DS-57 master-data part)

[inference; extends capability_check's direction]

**Entry points and taint:**

| Entry | Example | Taint and scope |
|---|---|---|
| E1 a person's own note or form | "New bracket assembly: 2 plates, 4 M8 bolts, weld, paint" | Untainted; full catalog read |
| E2 a person's own spreadsheet | Engineering BOM export | `import_batch` scope; untainted |
| E3 outside content | A customer's drawing, RFQ PDF or spreadsheet; a supplier catalog | Tainted; drafts only, one partner scope |

**Steps:**
1. **Extract** via `document_extraction` (Part 1 pipeline). Spreadsheets use cell-ref evidence. Drawings in Phase 1 have a person key the parts list beside the viewer; title-block and parts-list extraction come later.
2. **Normalize** units through the UoM design (ADR-0056 draft), number formats and spec tokens. This is code.
3. **Resolve each component** deterministically in this order: exact internal code → GTIN or barcode → supplier item code (cross-reference) → manufacturer part number → `rank_candidates` (blocked by category and UoM, lexical plus attribute score; embeddings later). The **LLM sees at most k candidates per line**. It picks one, or returns `new_item_needed` with the attributes it found and their evidence.
4. **Draft new items.** Code builds `CreateItem` and `CreateProduct` change proposals. Category drives required attributes, a sequence issues the number, and the description is generated from attributes. Each proposal carries its duplicate-candidate list and why each was rejected.
5. **Draft structures.** Code creates the draft BOM revision (levels, quantities, UoM, phantom flags, scrap only if stated) and the draft routing revision (operations, work centers chosen from existing ones, standard times only if stated in a source span; otherwise blank and flagged).
6. **Check.** `GetBillOfMaterialsRevisionCheck` plus readiness rules per category: cycles; UoM convertibility; every make item has a BOM and routing; work centers have activity rates; costing-relevant flags set.
7. **Cost.** `CreateCostEstimate` on the drafts. The result lists **gaps** (missing rate, time or purchase price) and never treats them as zero. If a previous released estimate exists, the evidence includes the delta per cost element.
8. **Evidence pack.** One change proposal for release, ECO-like, containing:
   - sources with evidence links;
   - resolution decisions with candidates;
   - check results;
   - the estimate and its gaps;
   - similar released items, later;
   - effectivity.
   The approver is not the requester (spec/03 r5). Approval routing uses the existing thresholds.

### B. How drafted master data reaches release

[inference]
- **Phase 1:**
  - Agent and import output = draft BOM and routing revisions plus item and product creation proposals.
  - Release = `ReleaseBillOfMaterialsRevision` / `ReleaseRoutingRevision` executed only through an approved change proposal.
  - Cost estimate released separately (`ReleaseCostEstimate`).
  - New items become usable for transactions only after their proposal is approved. A draft BOM may reference proposed items, but its release proposal is blocked until those items are approved (dependency check in code).
- **Engineering change on released structures (Phase 1).** A new draft revision plus a change proposal with impact evidence: where-used, open orders, stock of superseded components with a disposition choice (use up / scrap / rework), and effectivity date. This is the ECO; no separate object is needed in Phase 1.
- **Later:**
  - separate ECR (request, as a work item) from ECO (proposal);
  - an EBOM view imported from CAD or PLM (STEP AP242 or PLM CSV) with equivalence links to MBOM lines and out-of-date detection (Windchill pattern);
  - accountability checks (Teamcenter pattern);
  - release policies per plant or company (D365 pattern) if multi-company manufacturing arrives.

### C. Where taint applies (master data)

[inference]
- E3 runs are tainted: drafts only, one partner scope. Customer drawings and RFQs often contain supplier names, prices and notes. These are untrusted free text, shown to the person and never acted on.
- **The open read-scope question** (open-questions.md:43; a tainted run cannot read the catalog, which makes resolution useless).
  - Proposal: let the tainted run call **deterministic resolution queries** (step 3) that return a narrow catalog projection: item id, code, name, UoM, category, status. No costs, prices, partners or free-text notes.
  - Rationale: the run's outputs are internal drafts that a person reviews, and the run cannot send anything out. The exfiltration leg of the trifecta is already cut, and the projection limits what a manipulated draft could expose if a person later forwards it.
  - This is a decision for the architect and author.
- Cost and margin are declared field classes. E3 runs do not get them. Costing happens in code after the draft exists, and its result is shown to the person, not fed back to the tainted model.

### D. Personal data in master data

[inference]
- Contacts, the people at suppliers and customers, are personal. Business-card-derived contacts follow Part 1 C.
- Household-business suppliers, natural persons, make the supplier master itself personal. Their tax ID and bank account are personal.
- Items, BOMs and routings are normally non-personal. Free-text notes copied from outside documents may contain names, so keep them `is_untrusted` and label them by source.
- Supplier onboarding (Phase 1): look up the tax ID against the national business registry where the overlay supports it (Decree 254 requires identification to match the registry, per secondary sources). Mark tax status; route bank account creation or change as a proposal with out-of-band verification.

### E. Phase plan (master data)

| Capability | Phase 1 | Later | Tradeoff |
|---|---|---|---|
| Item and product creation via proposals with duplicate candidates | Yes (E1, E2, E3) | Embedding similarity, UNSPSC/eCl@ss classification suggestions | Lexical plus attribute matching first, because it is explainable and tunable as a parameter set |
| BOM and routing from spreadsheet | Yes, staged import with mapping reuse, multi-level by indent or level column | Direct PLM connectors | Covers most real cases for assembly makers |
| BOM from a description (person's note) | Yes, untainted, candidates first | - | Value depends on catalog quality |
| BOM from a drawing | Person keys lines beside the viewer; agent resolves components | Title-block and parts-list extraction (detect-then-read; local or vendor API); similar-drawing search | Parts-list extraction is unmeasured; a vendor API raises a data-export question for customer drawings |
| Cost estimate on drafts with gaps and delta | Yes (server rollup) | Similar-item actual-cost evidence; quote templates per process (Paperless Parts pattern) | Never ask the model for a number |
| ECO with impact evidence | Yes, as revision plus proposal | ECR/ECO split, MCN, accountability checks, release policies | Fewer objects in Phase 1 |
| EBOM/MBOM split | Single MBOM with source traceability | CAD/PLM EBOM import with equivalence links | Avoids a second structure before there is CAD integration |

---

# Part 3. Decisions for the architect

1. **Update all references to Decree 123/2020 → Decree 254/2026 + Circular 91/2026.** Confirm whether the XML format of Decision 1450/1510 still applies or was replaced by an annex of Circular 91. Add a schema-version dispatch to the l10n_vn reader [doc/blog; inference].
2. **Adopt the `document_extraction` record and the field evidence schema** of section 1.8 as the core seam. Every workflow starts from it [inference].
3. **Distinguish instruction taint from value trust** in ADR text. Taint narrows reads. Value trust is handled by alignment, rules and human verification [inference].
4. **Create one new seat**, "extraction with image and PDF reading, personal data allowed". Prefer self-hosted or in-country in Phase 1, with a transfer impact assessment recorded in l10n_vn before any foreign API [inference; legal facts blog].
5. **Build the verification screen in the ERP**, not in a vendor tool [doc: Google HITL deprecation; inference].
6. **Answer the tainted read-scope question** with the narrow catalog projection proposal (Part 2 C) [inference].
7. **Write `product_engineering`** as the DS-57 master-data workflow with the eight steps of Part 2 A [inference].
8. **Golden sets before vision goes live.** Use at least 50–100 real documents per case (invoices per supplier type, business cards, delivery notes), with per-field calibrated thresholds and recalibration on any model or prompt change [inference; doc: Azure and UiPath recalibration notes].

---

## Sources (primary first)

Legal and standards:
- Decision 1450/QD-TCT: https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Quyet-dinh-1450-QD-TCT-2021-thanh-phan-chua-du-lieu-nghiep-vu-hoa-don-dien-tu-490526.aspx
- Decision 1510/QD-TCT: https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Quyet-dinh-1510-QD-TCT-2022-sua-doi-Quyet-dinh-1450-QD-TCT-hoa-don-dien-tu-530232.aspx
- Decree 254/2026 and Circular 91/2026 (secondary):
  - https://www.crowe.com/vn/news/e-invoices-and-electronic-documents-from-1-july-2026
  - https://www.fiscal-requirements.com/news/5767-vietnams-new-e-invoice-regulations-decree-2542026nd-cp
  - https://thuvienphapluat.vn/phap-luat-doanh-nghiep/bai-viet/chinh-thuc-da-co-nghi-dinh-thay-the-nghi-dinh-123-va-nghi-dinh-70-ve-hoa-don-dien-tu-nghi-dinh-254-2026-nd-cp-22136.html
  - https://ihoadon.vn/hddt/hoa-don-dien-tu-tai-thong-tu-91-2026-tt-btc.html
  - https://bizzi.vn/en/decree-254-and-circular-91-on-electronic-invoices-new-points-and-what-businesses-need-to-update/
  - https://luatvietnam.vn/thue/cong-van-4831-ct-cs-2026-cua-cuc-thue-ve-noi-dung-moi-tai-nghi-dinh-254-2026-nd-cp-va-thong-tu-91-2026-tt-btc-440460-d6.html
- Decree 70/2025 (superseded): https://ihoadon.vn/hddt/nghi-dinh-70-2025-nd-cp-nhung-diem-moi-doanh-nghiep-can-luu-y-ve-hoa-don-chung-tu.html
- Personal data:
  - https://www.tilleke.com/insights/new-decree-provides-guidance-for-vietnams-personal-data-protection-law
  - https://fpf.org/blog/fpf-releases-updated-issue-brief-on-vietnams-law-on-protection-of-personal-data-and-the-law-on-data/
  - https://vn.rajahtannasia.com/?p=63882
- Factur-X / ZUGFeRD:
  - https://github.com/ZUGFeRD/ZUV
  - https://dev.to/facturata/your-factur-x-passes-xsd-and-still-gets-rejected-here-is-why-341g
  - https://econnect.eu/en/docs/knowledge/document-formats/basics/hybrid-invoices
- PEPPOL:
  - https://docs.peppol.eu/poacc/billing/3.0/release-notes/
  - https://docs.peppol.eu/poacc/billing/3.0/upcoming/files/PEPPOL-EN16931-UBL.sch
- STEP AP242: https://www.mbx-if.org/documents/rec_prac_ap242xml_assy_struct_v3.1.pdf
- OWASP CSV injection: https://owasp.org/www-community/attacks/CSV_Injection

Vendor documentation:
- Azure:
  - https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/invoice
  - https://learn.microsoft.com/azure/ai-services/document-intelligence/concept-accuracy-confidence
  - https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-business-card
  - https://learn.microsoft.com/azure/ai-services/content-understanding/overview
  - https://devblogs.microsoft.com/foundry/azure-content-understanding-gpt-5-series-guide-model-selection-grounding-improvements-and-confidence-enhancements/
- Google:
  - https://docs.cloud.google.com/document-ai/docs/custom-extractor-overview
  - https://docs.cloud.google.com/document-ai/docs/deprecation
  - https://ai.google.dev/gemini-api/docs/image-understanding
- AWS:
  - https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html
  - https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-textract-task-type.md
- SAP:
  - https://architecture.learning.sap.com/docs/ref-arch/LcR6Senh/2
  - https://developers.sap.com/tutorials/cp-aibus-dox-ui
  - https://blogs.sap.com/2023/09/04/introducing-document-information-extraction-premium-edition-unleashing-the-power-of-large-language-models-and-generative-ai/
  - https://help.sap.com/saphelp_mdg80/helpdata/en/df/79cc5284084a4ee10000000a423f68/content.htm
  - https://community.sap.com/t5/technology-blogs-by-sap/benefit-from-sap-master-data-governance-on-sap-s-4hana-2023-feature-pack/ba-p/13808294
  - https://learning.sap.com/courses/implementing-product-lifecycle-management-in-sap-s-4hana-cloud-public-edition/discovering-sap-ai-features_aa527e2d-a8af-4cd7-b215-0ae196e25fdd
  - https://help.sap.com/doc/6297d7531a4d414de10000000a174cb4/3.6/en-US/fb96d7531a4d414de10000000a174cb4.html
- ABBYY:
  - https://docs.abbyy.com/vantage/getting-started/results.md
  - https://docs.abbyy.com/vantage/documentation/skill-designer/process/manual-review
- Rossum:
  - https://knowledge-base.rossum.ai/docs/using-ai-confidence-thresholds-for-automation-in-rossum
  - https://knowledge-base.rossum.ai/docs/duplicate-detection-in-rossum
  - https://rossum.ai/blog/rossum-aurora/
- UiPath:
  - https://docs.uipath.com/document-understanding/automation-suite/2.2510/classic-user-guide/taxonomy-manager
  - https://www.uipath.com/product/ixp
- PaddleOCR: https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html
- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Presidio: https://microsoft.github.io/presidio/image-redactor
- Dangerzone: https://github.com/freedomofpress/dangerzone
- Dynamics 365:
  - https://learn.microsoft.com/dynamics365/supply-chain/engineering-change-management/product-engineering-overview
  - https://learn.microsoft.com/en-us/dynamics365/supply-chain/engineering-change-management/release-product-structure
- Oracle:
  - https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25d/fapim/how-items-are-matched.html
  - https://blogs.oracle.com/fusioninsider/post/new-genai-helps-launch-products-faster-demo
- Siemens:
  - https://www.siemens.com/en-us/products/teamcenter/teamcenter-ai/
  - https://blogs.sw.siemens.com/teamcenter-manufacturing/2026/08/24/mbom-management-keeping-manufacturing-aligned-with-product-changes/
- PTC: https://support.ptc.com/help/windchill/r13.0.1.0/en/Windchill_Help_Center/mpmlink/ExpMPM_EbomMbom.html
- Arena:
  - https://arenasolutions.com/products/plm/features/change-management
  - https://www.arenasolutions.com/resources/articles/part-numbering/
- Propel: https://www.sdcexec.com/software-technology/software-solutions/news/22969739/propel-software-propel-software-launches-production-model-context-protocol-for-plm-agents
- Paperless Parts:
  - https://www.paperlessparts.com/pricing-costing-automation/
  - https://www.paperlessparts.com/processes/cnc-machining
- Xometry: https://xometry.com/machine-learning-for-manufacturing
- CADDi: https://us.caddi.com/faq
- Werk24: https://werk24.io/use-cases/pmi-extraction

Papers:
- Invoice LLM benchmark: https://arxiv.org/abs/2509.04469
- SafePassage: https://arxiv.org/html/2510.00276v1
- LMDX: https://arxiv.org/abs/2309.10952
- Abstention probes: https://arxiv.org/abs/2511.19806
- Geometric risk control: https://arxiv.org/abs/2603.19790
- Spotlighting: https://arxiv.org/abs/2403.14720
- CaMeL: https://arxiv.org/abs/2503.18813
- CrackedPDFs: https://arxiv.org/pdf/2607.19396
- Hidden prompts in reviews: https://arxiv.org/pdf/2509.10248
- Malicious fonts: https://arxiv.org/pdf/2505.16957
- Image-based injection: https://arxiv.org/pdf/2603.03637
- Résumé injections: https://arxiv.org/pdf/2605.28999
- OmniDocBench: https://arxiv.org/html/2412.07626v2
- Donut: https://arxiv.org/pdf/2111.15664
- PhoWhisper: https://arxiv.org/pdf/2406.02555
- Drawing frameworks:
  - https://arxiv.org/pdf/2510.21862
  - https://arxiv.org/pdf/2505.01530
  - https://arxiv.org/pdf/2607.18997
- LLM production planning: https://link.springer.com/article/10.1007/s10845-025-02732-z
- LLM plan feasibility: https://arxiv.org/pdf/2606.29627
- Entity resolution: https://journals.ysu.am/bulletin-ysu-economics/article/download/14584/11393/36915

Blogs and secondary:
- Lethal trifecta: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Invoice engine comparisons:
  - https://invoicedataextraction.com/blog/aws-textract-vs-google-document-ai-vs-azure-document-intelligence
  - https://hackernoon.com/can-your-llm-handle-an-invoice-i-tested-5heres-the-truth
- VLM OCR quiet errors: https://www.llamaindex.ai/blog/llm-ocr
- Duplicate invoices: https://us.fitgap.com/stack-guides/flag-duplicate-invoices-before-payment-runs
- Whisper hallucination: https://www.news.cornell.edu/stories/2024/06/ai-speech-text-can-hallucinate-violent-language
- aPriori accuracy: https://www.apriori.com/blog/your-should-cost-estimate-is-not-accurate-but-thats-okay/
- EBOM/MBOM:
  - https://www.getleo.ai/blog/ebom-to-mbom-transformation-handoff
  - https://virtualdutchman.com/2015/09/27/the-importance-of-a-plm-data-model-ebom-mbom/
- Import staging: https://appmaster.io/blog/staging-tables-vs-direct-imports-csv-excel-uploads
- Part numbering: https://openbom.com/blog/part-numbers-best-practices-and-future-improvements
- E-invoice XML retention: https://vinatas.com.vn/hoa-don-dien-tu-can-phai-luu-file-xml/
- E-invoice lookup: https://www.meinvoice.vn/tin-tuc/771/tra-cuu-hoa-don-dien-tu/

Gaps I could not close:
- the official text of the Circular 91 format annex;
- whether Azure's invoice model supports Vietnamese;
- Vietnamese OCR accuracy for any engine;
- any parts-list extraction benchmark;
- any measured accuracy for AI-drafted BOMs or routings;
- an official tax-portal verification API.
