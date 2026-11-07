# Maritime DG Compliance Assistant — Synthetic Dataset

## 1. Scope

This dataset supports **PortDoc AI**, an academic prototype for preliminary document checks of containerised packaged dangerous-goods imports into Singapore via PSA.

The prototype extracts information from shipping PDFs, identifies selected document inconsistencies, supports re-extraction of flagged documents, retrieves regulatory context for applicable findings and suggests human-review priorities.

**Important:** The prototype does not determine regulatory compliance, verify the legal correctness of dangerous-goods classifications, submit permits or declarations, or replace qualified human review.

All shipping records are synthetic.

## 2. Dataset Contents

**6 scenarios · 23 PDFs · 6 ground-truth JSON files · 6 answer-key JSON files · 2 verification fixtures**

| Type | File | Purpose |
|---|---|---|
| A — Shipping documents | `test_cases/SXX_*/` | Synthetic PDF inputs: Bill of Lading, Commercial Invoice, Packing List and Dangerous Goods Declaration |
| B — Ground truth | `ground_truth.json` | Reference values printed in each PDF, including deliberately injected discrepancies |
| C — Answer key | `answer_key.json` | Expected discrepancy findings, verification expectations, suggested regulatory topics and illustrative triage outcomes |
| V — Verification fixtures | `verification_fixtures/` | Mock extraction results used to test verification behaviour without calling Gemini |

Only **A** is uploaded to the Streamlit application. B, C and V are offline testing references and must not be provided to the runtime model as answers or indexed in the regulatory knowledge base.

`dataset_manifest.csv` summarises the six scenarios.

## 3. Test Scenarios

| Case | Description | Expected findings |
|---|---|---|
| S01 | Correct shipment | 0 |
| S02 | Packing List gross weight differs | 1 — weight mismatch |
| S03 | Bill of Lading container ID differs | 1 — container mismatch |
| S04 | Dangerous Goods Declaration missing | 1 — missing document |
| S05 | DGD and B/L DG classes conflict | 1 — DG class conflict |
| S06 | Multiple injected discrepancies | 3 — weight, container and DG class |

S01–S03 and S05–S06 contain four PDFs each. S04 contains three PDFs because the DGD is intentionally absent.

The dataset uses one fictional shipment with controlled variations. It is an integration/demo benchmark, not a statistically representative model evaluation dataset.

## 4. Implemented Application Workflow

The application implementation is maintained in `Backend/` on the `feat/rag-in-pipeline` branch.

1. **PDF upload:** Streamlit accepts selectable-text PDFs. The prototype does not support scanned/image-only PDFs.
2. **Document extraction:** Gemini extracts structured fields into a document-type mapping, with upload inventory and extraction metadata.
3. **Deterministic validation:** `Backend/validator.py` compares selected fields and distinguishes missing documents from uploaded documents that failed extraction.
4. **Verification:** `Backend/verification.py` re-extracts selected documents associated with flagged comparison findings, up to two rounds, then reruns validation. Re-extraction is document-level rather than field-only.
5. **Triage:** `Backend/triage.py` assigns an illustrative suggested review priority and human-review recommendation.
6. **Regulatory context:** `Backend/rag/` retrieves supporting Singapore regulatory passages for applicable findings. Automatic regulatory-context questions currently cover DG class conflicts and missing DGD findings. The planner may generate more specific questions, with fixed-question fallback.
7. **Reporting:** The pipeline saves structured JSON results, and the Streamlit interface presents findings, evidence, review recommendations and applicable regulatory context.

The RAG system explains relevant source material and does not issue shipment compliance verdicts.

See `system_workflow.svg` for the corresponding architecture diagram.

## 5. Ground Truth and Evaluation

Each scenario's `ground_truth.json` contains:

- `shipment_truth`: Baseline shipment information.
- `document_truth`: Values appearing in each synthetic document, including deliberately incorrect values.

**Extraction accuracy must be evaluated against `document_truth`, not `shipment_truth`.**

The runtime extraction output is wrapped in a `documents` mapping. The validator consumes the document-type-to-fields mapping, not the entire extraction result.

Field comparison during extraction evaluation may require normalising harmless representation differences, such as `18500` versus `"18,500 kg"`. Missing or unreadable fields must not automatically be treated as correct.

Each `answer_key.json` contains expected discrepancy findings and additional test expectations. The deterministic validator does not consume answer keys during normal execution.

Some RAG topics in the answer keys are broader suggested research topics, not mandatory queries or verified legal outcomes.

## 6. Verification Fixtures

- **V01 — False weight mismatch:** The first extraction introduces a mismatch that does not exist in the underlying PDFs. Correct re-extraction should remove the finding.
- **V02 — Genuine weight mismatch:** The underlying documents disagree. Correct re-extraction should retain the finding.

These fixtures represent mock extraction data for offline tests, not extra PDFs or real Gemini outputs.

The implemented verification loop selects document groups according to finding type and re-extracts whole documents. Its behaviour should be evaluated using the actual `verify()` interface and the implemented recheck mapping.

## 7. Review Priorities

The implemented prototype triage policy is:

| Condition | Suggested priority |
|---|---|
| No findings | Low |
| One weight mismatch | Medium |
| One container mismatch | Medium |
| One missing document | Medium |
| DG class conflict | High |
| Two or more findings | High |

An uploaded document that fails extraction is flagged for review because the result is incomplete.

These are illustrative review priorities, **not legally defined risk classifications**. No findings detected does not mean a shipment is compliant.

## 8. Offline Testing

Run commands from the repository root.

**Validate the six labelled synthetic cases:**

```bash
python Backend/validator.py --test data
```

**Run the existing verification tests:**

```bash
python Backend/test_verification.py
```

**Run the existing triage tests:**

```bash
python Backend/test_triage.py
```

**Run the existing extraction-status tests:**

```bash
python Backend/test_validation_status.py
```

These tests do not require live Gemini API calls. They do not, by themselves, establish PDF extraction accuracy or full end-to-end regulatory correctness.

To start the Streamlit application locally, follow the setup and dependency instructions in `Backend/README.md`. Live model operations require the appropriate API configuration.

## 9. Dataset Generation

`build.py` is the original synthetic document generator.

**Caution:** The existing generator rewrites generated PDFs, ground-truth files, answer keys and the manifest. Its answer-key generation does not preserve all subsequently added verification, RAG and triage annotations.

Do not rerun `build.py` against the maintained dataset until its overwrite behaviour has been made safe and verified.

## 10. Limitations

- All documents and shipment parties are fictional.
- The DGD visually approximates a multimodal dangerous-goods form, but is not a valid executed shipping declaration.
- UN1263 / PAINT / Class 3 is illustrative; the complete shipping classification, packaging suitability and HS classification have not been independently verified.
- The validator only performs selected deterministic comparisons, not comprehensive field-level or legal checks.
- RAG outputs are limited by the included regulatory corpus and citation verification.
- A missing uploaded DGD is a document-completeness finding, not evidence that a separate MPA notification was omitted.
- The six cases share one baseline shipment and should not be presented as a statistically robust accuracy benchmark.

**All findings are preliminary and intended to support qualified human review.**
