
r"""
PortDoc AI - Shipment Validation Pipeline

Flow:
1. Extract document fields from PDFs using Gemini.
2. Save the extraction result, including inventory and metadata.
3. Validate the extracted document fields using deterministic rules.
4. Save a combined validation report for human review.

Run from the project root:
python -u .\backend\run_pipeline.py --pdf-folder ".\data\test_cases\S01_correct" --output-folder ".\outputs\S01"
"""

import argparse
import json
import sys
import traceback
from pathlib import Path
from datetime import datetime, timezone


# Allow imports from the backend directory when this script is run from
# the project root using: python .\backend\run_pipeline.py
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from extract_documents import extract_shipment
from validator import validate
from verification import reextractor, verify

# Regulatory context (RAG): the answer code and corpus live in Backend/rag.
RAG_DIR = BACKEND_DIR / "rag"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))
from regulatory_context import attach_context  # noqa: E402
from retrieve import Retriever  # noqa: E402


def save_json(file_path, data):
    """Save data as readable UTF-8 JSON."""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, default=str)


def count_pdf_files(pdf_folder):
    """Count PDFs supplied as pipeline input."""
    return len([
        path
        for path in Path(pdf_folder).rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    ])


def main():
    parser = argparse.ArgumentParser(
        description="Extract and validate maritime shipment documents."
    )
    parser.add_argument(
        "--pdf-folder",
        required=True,
        help="Folder containing shipment PDF documents.",
    )
    parser.add_argument(
        "--output-folder",
        required=True,
        help="Folder where extraction and validation JSON files will be saved.",
    )
    args = parser.parse_args()

    pdf_folder = Path(args.pdf_folder).resolve()
    output_folder = Path(args.output_folder).resolve()

    if not pdf_folder.exists() or not pdf_folder.is_dir():
        parser.error(f"PDF folder does not exist or is not a directory: {pdf_folder}")

    output_folder.mkdir(parents=True, exist_ok=True)

    extracted_json_path = output_folder / "extracted_documents.json"
    report_json_path = output_folder / "validation_report.json"

    print("run_pipeline.py has started")
    print(f"PDF folder: {pdf_folder}")
    print(f"Output folder: {output_folder}")

    uploaded_pdf_count = count_pdf_files(pdf_folder)
    if uploaded_pdf_count == 0:
        parser.error(f"No PDF files were found in: {pdf_folder}")

    try:
        # Step 1: Extract with Gemini.
        # The current Gemini extract_shipment() accepts only pdf_folder.
        print("\n[1/3] Extracting PDF documents with Gemini...")
        extraction_result = extract_shipment(pdf_folder=str(pdf_folder))

        if not isinstance(extraction_result, dict):
            raise TypeError(
                "extract_shipment() should return a dictionary containing "
                "'documents', 'upload_inventory', and 'extraction_metadata'."
            )

        # Save the full extraction result, preserving inventory and metadata.
        save_json(extracted_json_path, extraction_result)
        print(f"Extraction result saved to: {extracted_json_path}")

        # Step 2: Get the extracted document fields for validation.
        print("\n[2/3] Validating extracted document fields...")
        documents = extraction_result.get("documents", {})

        if not isinstance(documents, dict):
            raise TypeError(
                "The 'documents' value returned by extract_shipment() "
                "must be a dictionary."
            )

        # The validator expects document-type -> extracted-fields mapping,
        # not the entire extraction wrapper.
        # Uploaded PDFs, by file name, so a document that was uploaded but not extracted is reported
        # as an extraction failure rather than a missing document.
        uploaded_types = {
            Path(item.get("filename", "")).stem
            for item in extraction_result.get("upload_inventory", [])
            if isinstance(item, dict) and item.get("filename")
        }
        validation_result = validate(documents, uploaded=uploaded_types)

        # Verification rounds: flagged fields are re-extracted and re-checked, up to two rounds
        # (the answer keys' verification_expectations).
        if validation_result.get("findings"):
            print("\nRe-checking flagged fields...")
            verified = verify(documents, uploaded_types, reextractor(pdf_folder, extract_shipment))
            validation_result = verified["validation"]
            validation_result["verification_rounds"] = verified["rounds"]

        if not isinstance(validation_result, dict):
            raise TypeError(
                "validate(documents) should return a dictionary."
            )

        # Step 3: Assemble and save a combined report.
        print("\n[3/3] Building validation report...")

        inventory = extraction_result.get("upload_inventory", [])
        metadata = extraction_result.get("extraction_metadata", {})

        # Keep counts separate: a PDF being uploaded does not mean it was
        # successfully identified or extracted.
        identified_count = None
        extracted_count = len(documents)

        if isinstance(inventory, list):
            identified_count = sum(
                1 for item in inventory
                if isinstance(item, dict)
                and item.get("document_type")
            )

        report = {
            "project": "PortDoc AI",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "input": {
                "pdf_folder": str(pdf_folder),
                "uploaded_pdf_count": uploaded_pdf_count,
                "identified_pdf_count": identified_count,
                "extracted_document_count": extracted_count,
            },
            "extraction": {
                "upload_inventory": inventory,
                "extraction_metadata": metadata,
                "extraction_output_file": str(extracted_json_path),
            },
            "validation": validation_result,
            "review_notes": [
                (
                    "Automated field checks are not a determination of "
                    "regulatory compliance. Human review is required."
                ),
                (
                    "A missing document finding may be inconclusive if a PDF "
                    "failed extraction or could not be identified. Check the "
                    "upload inventory and extraction metadata before treating "
                    "a document as genuinely missing."
                ),
            ],
        }

        # Regulatory context: a cited answer for each finding with a regulatory side. Findings and the
        # compliance status are not changed. A failed model call is recorded on its finding.
        if report["validation"].get("findings"):
            print("\nAttaching regulatory context...")
            report = attach_context(report, Retriever.from_corpus())

        save_json(report_json_path, report)

        print(f"Validation report saved to: {report_json_path}")
        print(f"Uploaded PDFs: {uploaded_pdf_count}")
        print(f"Extracted document entries: {extracted_count}")
        print("Regulatory compliance: NOT ASSESSED")

         # Check whether every uploaded PDF was successfully extracted.
        failed_files = []

        if isinstance(inventory, list):
            for item in inventory:
                if not isinstance(item, dict):
                    continue

                status = str(item.get("status", "")).lower()

                if status in {
                    "failed",
                    "extraction_failed",
                    "error",
                    "unidentified",
                    "identification_failed",
                }:
                    failed_files.append(item.get("filename", "Unknown file"))

        if failed_files or extracted_count < uploaded_pdf_count:
            print("\nPipeline finished with incomplete extraction.")
            print("Do not treat this report as a complete validation.")
            if failed_files:
                print("Files needing attention:")
                for filename in failed_files:
                    print(f"  - {filename}")
        else:
            print("\nPipeline completed successfully.")


    except Exception as exc:
        print(f"\nPipeline failed: {exc}", file=sys.stderr)
        traceback.print_exc()

        # Save a failure record so the error is visible in the output folder.
        failure_report = {
            "project": "PortDoc AI",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline_status": "failed",
            "pdf_folder": str(pdf_folder),
            "uploaded_pdf_count": uploaded_pdf_count,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "regulatory_compliance": "NOT ASSESSED",
        }

        try:
            save_json(report_json_path, failure_report)
            print(f"Failure details saved to: {report_json_path}")
        except Exception as save_exc:
            print(
                f"Could not save failure report: {save_exc}",
                file=sys.stderr,
            )

        sys.exit(1)


if __name__ == "__main__":
    main()
