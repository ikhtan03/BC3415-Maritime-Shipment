# PortDoc AI — Extraction and Validation Pipeline

## Overview

PortDoc AI is a prototype for assisting with the review of maritime shipment documents. The current implementation uses Google's Gemini API to extract structured information from PDFs, then applies deterministic Python rules to identify selected inconsistencies across documents.

The current workflow focuses on document extraction and cross-document consistency checks. **It does not yet provide a comprehensive assessment of compliance with Singapore port regulations.** Integrating retrieval-augmented generation (RAG) with relevant official regulatory sources is a planned next stage.

## Core Files

| File | Purpose |
|---|---|
| `backend/extract_documents.py` | Reads PDFs, identifies document types, extracts structured fields using Gemini, and records extraction outcomes and supporting evidence. |
| `backend/run_pipeline.py` | Coordinates extraction and validation, saves the intermediate extraction data, and generates the validation report. |
| `backend/validator.py` | Applies deterministic rules to compare selected fields across extracted documents. |

## 1. `extract_documents.py`

### Inputs

The main function is:

```python
extract_shipment(pdf_folder)
```

It accepts a folder containing the shipment PDFs. Gemini API access requires `GEMINI_API_KEY` to be configured in the environment.

The script uses PyMuPDF to read PDF text and the Google Gen AI SDK to request structured field extraction from Gemini. The fields to extract for each document type are defined in `DOCUMENT_FIELDS`.

The current implementation works with selectable PDF text; scanned documents may require OCR support in a future version.

### Processing

For each PDF, the script attempts to identify its document type and extract the relevant fields. It also records extraction status, errors, notes and field-level provenance where available.

The `generate_with_retry()` helper is intended to retry temporary Gemini service errors. Exhausted API quotas, such as `429 RESOURCE_EXHAUSTED`, should be recorded rather than repeatedly retried with short delays.

### Outputs

The `extract_shipment()` function returns a dictionary containing:

- **`documents`** — successfully extracted fields organised by document type. This is the data passed to the validator.
- **`upload_inventory`** — a record of the input PDFs and their processing outcomes, including failures and unidentified or duplicate documents.
- **`extraction_metadata`** — additional extraction details, including provenance, notes and error information.

These outputs help distinguish a document that was not supplied from one that was uploaded but could not be extracted.

## 2. `run_pipeline.py`

### Inputs

The pipeline accepts two command-line arguments:

| Argument | Purpose |
|---|---|
| `--pdf-folder` | Folder containing the shipment PDFs |
| `--output-folder` | Destination for generated JSON files |

Example, run from the project root:

```powershell
python -u .\backend\run_pipeline.py --pdf-folder ".\data\test_cases\S01_correct" --output-folder ".\outputs\S01"
```

### Processing

The pipeline:

1. Calls `extract_shipment()` to process the PDFs using Gemini.
2. Saves the extraction result.
3. Passes the extracted `documents` mapping to `validate()` in `validator.py`.
4. Combines the validation results and extraction information into a report.

### Outputs

Each run produces two main files in the specified output folder:

| Output | Contents |
|---|---|
| `extracted_documents.json` | Extracted fields, upload inventory, extraction metadata and errors. |
| `validation_report.json` | Input and extraction counts, extraction information, deterministic validation findings and review notes. |

A saved report does not necessarily mean the run was complete. If one or more PDFs fail extraction, the report may contain incomplete validation results. The pipeline should distinguish complete, incomplete and failed runs.

## 3. Understanding `validation_report.json`

The report combines the validator's findings with information about the extraction process.

Its main sections include:

- **`input`** — the source folder and document counts.
- **`extraction`** — upload inventory, extraction metadata and the location of the extraction output.
- **`validation`** — the findings returned by `validator.py`.
- **`review_notes`** — warnings and limitations relevant to interpreting the results.

The exact validation fields are determined by the implementation of `validator.py`.

### Current validation checks

The deterministic validator checks selected relationships between extracted document fields, including:

- Required document types represented in the extracted data.
- Gross-weight consistency between the Bill of Lading and Packing List.
- Container-ID consistency between the Bill of Lading and Packing List.
- Dangerous-goods class consistency between the Bill of Lading and Dangerous Goods Declaration.

The validator can return findings, an issue count, review flags, a status and a regulatory-compliance indicator.

### Interpreting the results

| Result | Meaning |
|---|---|
| No discrepancies found | The implemented checks found no mismatch in the available extracted fields. |
| Field mismatch | Values differ across the documents being compared and require review. |
| Required document missing | A required document type is absent from the extracted document mapping; check the inventory to establish whether the PDF was actually supplied. |
| Extraction failure | A PDF could not be processed successfully, so related validation findings may be incomplete. |
| `regulatory_compliance: not_assessed` | The current system has not made a comprehensive regulatory compliance determination. |

The issue count reflects the validator's implemented rules, not the number of regulatory violations.

**A clean validation result does not establish regulatory compliance.** Extraction errors, missing fields and unsupported checks can all affect the outcome. Important values and findings should be reviewed against the source PDFs.

## 4. Current Limitations and Planned Development

The current implementation is an initial document extraction and consistency-checking workflow. Its limitations include:

- Gemini requests can fail because of temporary service errors or API quota limits.
- Extracted values may be inaccurate even when extraction succeeds.
- OCR for scanned PDFs is not currently implemented.
- The validator covers only the rules explicitly programmed in `validator.py`.
- A failed extraction can lead to an inconclusive missing-document finding if the inventory is not considered.
- The current workflow does not comprehensively evaluate regulatory compliance.

### Planned RAG integration

A planned extension is to incorporate retrieval-augmented generation (RAG) using relevant, authoritative regulatory and operational sources applicable to Singapore port operations and dangerous-goods shipments.

The intended direction is to retrieve relevant source material, assess the shipment documents against applicable requirements, and provide traceable findings with source references for human review. This will require careful source selection, validation of regulatory applicability, and clear handling of cases where the available evidence is insufficient.

Until that functionality is implemented and evaluated, the system's findings should be understood as **document-extraction and consistency-checking results**, not confirmation that a shipment meets Singapore port or dangerous-goods regulatory requirements.
