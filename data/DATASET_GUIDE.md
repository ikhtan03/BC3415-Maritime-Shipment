# Maritime DG Compliance Assistant — Synthetic benchmark v2

## Prototype assumption
**Containerised packaged dangerous goods IMPORT into Singapore through PSA.** This is a simulated pre-submission document check, not a customs permit, MPA/PSA notification, or regulatory approval. State this explicitly in the team video.

## Contents
Six cases based on one fictional shipment, 23 PDFs total. Each `test_cases/SXX...` directory contains:
- **A — PDFs**: upload *only* these to the web application (Bill of Lading, Commercial Invoice, Packing List, Multimodal Dangerous Goods Form). Case S04 deliberately lacks a DGD.
- **B — `ground_truth.json`**: `shipment_truth` stores baseline shipment values; `document_truth` stores expected extracted fields **as printed in each synthetic document** (including deliberately altered values). Use this to score field extraction; do NOT provide it to the LLM during evaluation.
- **C — `answer_key.json`**: list of injected mismatches and missing files. Use to score Python checks, report issue detection, and escalation decisions. Do NOT give it to the runtime LLM.

`dataset_manifest.csv` indexes cases. `build.py` regenerates the PDFs/JSON files (`pip install reportlab` first). Regenerate in this folder to preserve paths.

## Expected checks
S01 correct baseline; S02 packing-list gross cargo mass mismatch; S03 B/L container-ID mismatch; S04 missing DGD from uploaded set; S05 DGD declared DG class conflicts with B/L; S06 weight + container + DG-class conflicts. **The expected issue labels are controlled injected discrepancies, not validated legal determinations.**

## Integration contracts
- PDF inputs -> LLM extraction -> JSON per document. Compare extracted values with `ground_truth.json` > `document_truth`.
- Extracted JSON -> deterministic completeness and cross-document rules. Compare to `answer_key.json` > `expected_findings`.
- Extracted shipment attributes -> RAG query -> official regulatory passages curated by Member 2. **RAG corpus is official regulatory material, NOT these synthetic PDFs.** Member 2 should label relevant rule IDs, applicability, supporting citations and expected outcomes before a regulatory accuracy claim can be scored.
- Risk report -> user UI. Missing DGD in app upload set does NOT prove that MPA's separate vessel DG notification did not happen.

## Key limitations
- Educational sample forms only; DGD box arrangement is adapted from user-provided UNECE form screenshots, not a legally valid completed form. Signatures/certifications deliberately unsigned.
- The invented cargo record uses `UN1263 / PAINT / class 3` as a plausible illustrative pairing; actual packing group, packaging authorization, dangerous goods transport description, hazard controls, and commercial HS classification are NOT verified. Do not use this for actual dangerous-goods shipments.
- Commercial invoices, Bills of Lading, and Packing Lists use streamlined templates, not exact operator forms.
- One underlying shipment and six cases form an **integration/demo benchmark**, not a statistically robust model-evaluation dataset.

## Video scope line
“Our academic prototype focuses on containerised packaged dangerous-goods imports arriving in Singapore through PSA, using four synthetic shipment documents and selected, source-backed Singapore regulatory checks. It provides explainable pre-submission review findings and human escalation rather than official regulatory clearance.”
