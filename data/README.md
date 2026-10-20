# Maritime DG Compliance Assistant — Agentic Synthetic Dataset

## Scope

**Academic pre-check of containerised packaged dangerous-goods imports into Singapore through PSA.** Not a Customs permit, MPA/PSA notification, legal compliance decision or regulatory approval.

## Dataset (unchanged PDFs; expanded answer keys)

**6 test cases · 23 PDFs · 6 ground-truth JSONs · 6 answer-key JSONs · 2 verification fixtures**

| Label | File | Role |
|---|---|---|
| **A** | Shipping PDFs in `test_cases/SXX.../` | **Actual web-app input**: Bill of Lading, Invoice, Packing List, DGD (S04 intentionally lacks DGD) |
| **B** | `ground_truth.json` | **Hidden extraction reference**: compare the LLM-extracted JSON with `ground_truth.json → document_truth`, which holds exact PDF values, including deliberately incorrect values; `shipment_truth` holds intended baseline |
| **C** | `answer_key.json` | **Hidden evaluation reference**: compare Python findings with `answer_key.json → expected_findings`; also records injected issues, expected rechecks, suggested RAG search topics, and illustrative triage decisions |
| **V** | `verification_fixtures/*.json` | **Test-only mock LLM outputs** to verify that the loop can clear a false positive and retain a genuine mismatch |

**Only A is uploaded to the app. B, C and V must not be placed into the runtime prompt or RAG index.**

## Agentic system workflow and data mapping

![Agentic system workflow](system_workflow.svg)

1. **Upload A** → LLM extracts PDFs into JSON. **Offline test B:** compare extracted JSON against `ground_truth.json → document_truth` (not against the PDFs manually).
2. **Run `backend/validator.py`** on the extracted JSON. **Offline test C:** compare its findings against `answer_key.json → expected_findings`. The validator does not read answer keys at runtime.
3. **Verify loop (maximum 2 rounds):** for each flagged field, request targeted re-extraction; if values change, rerun affected rules. If unchanged, retain supported discrepancies. A missing document requires an upload-inventory check, not re-extraction. **C** describes expected checks. **V** supplies simulated extraction mistakes for isolated loop tests.
4. **Agentic RAG query planning:** planner selects pertinent regulatory search topics using extracted DG details; RAG retrieves sources curated by the regulatory workstream. **C** has *suggested topics only*, not verified regulatory ground truth.
5. **Python triage → report → human review when needed.** Compare issue types and illustrative escalation decisions with **C**.

## Exact JSON field mapping by workflow stage

The following files are **test-only references**, not inputs to the live LLM, Python validator or RAG engine. Their values are used *after* a stage runs to evaluate the result.

| Workflow stage | JSON file | Fields used | What it evaluates |
|---|---|---|---|
| **Agentic Verification Loop** | **B:** `ground_truth.json` | `document_truth` | Whether re-extracted values match the labelled values printed in the PDFs |
| **Agentic Verification Loop** | **C:** `answer_key.json` | `verification_expectations` | Which fields should be rechecked and which findings should remain |
| **Agentic Verification Loop** | **V:** `verification_fixtures/*.json` | Mock first-pass and corrected extraction values | Whether verification removes a simulated extraction error or preserves a real discrepancy |
| **Agentic RAG Planning** | **C:** `answer_key.json` | `rag_planning_expectations` | Whether the planner selects relevant regulatory topics; these are suggestions, **not verified legal verdicts** |
| **Python Triage & Reporting** | **C:** `answer_key.json` | `expected_findings`, `expected_issue_count`, `triage_expectations` | Whether the system identifies the expected issues and matches the illustrative risk/escalation labels |

**Other essential comparisons:** After initial extraction, compare the LLM output to **B → `document_truth`**. After `run_rules`, compare the returned findings to **C → `expected_findings`**. These comparisons belong in the test harness; the runtime validator should see neither B nor C.

## Six scenarios

| Case | Injected discrepancy | Expected after accurate verification |
|---|---|---|
| S01 | None | No injected issues |
| S02 | Packing List gross cargo mass differs | Retain weight mismatch |
| S03 | B/L container ID differs | Retain container mismatch |
| S04 | Missing uploaded DGD | Retain missing-document finding |
| S05 | DGD DG class differs from B/L | Retain class conflict |
| S06 | Weight, container ID, class | Retain all three findings |

**Verification fixtures:** `V01` injects a *false* first-pass weight mismatch into S01 extraction JSON, then corrects it; `V02` confirms S02's genuine mismatch remains. These are **not extra shipping PDFs**.

## Python validator

Run all six test cases from the repository root:

```bash
python backend/validator.py --test .
```

Validate a real LLM output saved as JSON (document-type keys mapping to field objects):

```bash
python backend/validator.py --input extracted_documents.json
```

Import in the backend: `from backend.validator import validate` then `validate(extracted_documents)`. No extra packages are required. `--test` uses B as mock extraction output and C to score findings; it does **not** test live PDF extraction, agent loops or RAG.

## Integration notes

- Extracted JSON should have the same document keys and field names as `ground_truth.json → document_truth`.
- The verification loop is bounded to **two rounds** and must keep provenance (PDF, field, value, extraction attempt). A second extraction agreeing with the first is evidence of repeatability, not independent proof that the document is correct.
- `C.verification_expectations`, `C.rag_planning_expectations`, and `C.triage_expectations` describe *expected tests*, not data to feed the agent.
- Suggested RAG queries can vary in wording. Evaluate retrieved citations and rule applicability after the regulatory workstream adds verified reference labels. Existing `regulatory_checks` remains empty; no compliance verdict is asserted.
- `dataset_manifest.csv` indexes cases. `build.py` is the **original PDF generator**. **Caution:** rerunning it overwrites these augmented JSON files; retain the supplied dataset ZIP as the evaluation reference.

## Limits

The forms are fictional educational approximations; DGD layout follows the supplied UNECE reference visually. `UN1263 / PAINT / Class 3`, packaging, HS classification and shipping suitability are **not fully verified**. A missing uploaded DGD does not establish that an external MPA DG notification was omitted. One underlying shipment and six variants are a **demo/integration benchmark**, not a statistically representative evaluation.

## Video scope line

“Our prototype conducts explainable pre-submission checks for containerised packaged dangerous-goods imports into Singapore through PSA. A bounded verification loop rechecks flagged document fields, and an AI planner selects relevant regulatory retrieval queries; Python rules support issue detection and triage. Findings are recommendations for human review, not official clearance.”
