
"""
PortDoc AI - Gemini-powered maritime document extraction.

Reads PDFs from a shipment folder and extracts structured fields using Gemini.
Returns a structure compatible with the pipeline:
{
    "documents": {...},
    "upload_inventory": [...],
    "extraction_metadata": {...}
}

This module must not read ground_truth.json, answer_key.json,
or verification fixtures.
"""

import json
import os
import re
from pathlib import Path

import pymupdf
from google import genai
from google.genai import types

import time

#---------------------------------------------------------
# Retry Gemini API calls with exponential backoff
#------------------------------------------------

def generate_with_retry(client, model, prompt, config, max_attempts=4):
    """Retry temporary Gemini service errors, but not exhausted quotas."""

    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

        except Exception as exc:
            error_text = str(exc).upper()

            # A 429 quota error will not be fixed by short retries.
            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                raise

            # Retry temporary server/service errors.
            temporary_error = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or "500" in error_text
                or "INTERNAL" in error_text
            )

            if not temporary_error or attempt == max_attempts - 1:
                raise

            wait_seconds = 2 ** (attempt + 2)
            print(
                f"Temporary Gemini service error. "
                f"Retrying in {wait_seconds} seconds "
                f"(attempt {attempt + 2}/{max_attempts})...",
                flush=True,
            )
            time.sleep(wait_seconds)



# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

DOCUMENT_FIELDS = {
    "bill_of_lading": [
        "document_reference",
        "shipment_date",
        "shipper",
        "consignee",
        "carrier",
        "vessel",
        "voyage",
        "port_of_loading",
        "port_of_discharge",
        "container_id",
        "seal_number",
        "cargo_description",
        "package_count",
        "gross_cargo_weight_kg",
        "un_number",
        "dg_class",
    ],
    "commercial_invoice": [
        "invoice_number",
        "shipment_date",
        "shipper",
        "consignee",
        "port_of_loading",
        "port_of_discharge",
        "cargo_description",
        "package_count",
        "gross_cargo_weight_kg",
        "hs_code",
        "declared_invoice_value_usd",
    ],
    "packing_list": [
        "document_reference",
        "shipper",
        "consignee",
        "container_id",
        "seal_number",
        "cargo_description",
        "package_count",
        "package_type",
        "gross_cargo_weight_kg",
        "net_cargo_weight_kg",
    ],
    "dangerous_goods_declaration": [
        "document_reference",
        "shipper",
        "consignee",
        "carrier",
        "seal_number",
        "vessel",
        "voyage",
        "port_of_loading",
        "port_of_discharge",
        "container_id",
        "un_number",
        "proper_shipping_name",
        "dg_class",
        "package_count",
        "package_type",
        "gross_cargo_weight_kg",
    ],
}


# ---------------------------------------------------------
# Gemini client
# ---------------------------------------------------------

def get_gemini_client():
    """Create the Gemini client using the environment API key."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. In PowerShell, run:\n"
            '$env:GEMINI_API_KEY="your-gemini-api-key"'
        )

    return genai.Client(api_key=api_key)


# ---------------------------------------------------------
# PDF reading
# ---------------------------------------------------------

def read_pdf_text(pdf_path):
    """
    Extract selectable text from a PDF.

    Scanned/image-only PDFs need an OCR step, which is not
    implemented in this version.
    """
    page_texts = []

    with pymupdf.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()

            if text:
                page_texts.append(
                    f"[Page {page_number}]\n{text}"
                )

    full_text = "\n\n".join(page_texts).strip()

    if not full_text:
        raise ValueError(
            "No selectable text found. This PDF may be scanned "
            "and require OCR."
        )

    return full_text


# ---------------------------------------------------------
# Document type detection
# ---------------------------------------------------------

def identify_document_type(filename, pdf_text):
    """
    Identify document type using the filename first,
    then fall back to document text.
    """
    name = Path(filename).stem.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")

    filename_rules = [
        (
            "dangerous_goods_declaration",
            [
                "dangerous_goods_declaration",
                "dangerous_goods",
                "dg_declaration",
                "dgd",
            ],
        ),
        (
            "bill_of_lading",
            [
                "bill_of_lading",
                "bill_lading",
                "billoflading",
                "bol",
                "bl",
            ],
        ),
        (
            "commercial_invoice",
            [
                "commercial_invoice",
                "commercialinvoice",
                "invoice",
            ],
        ),
        (
            "packing_list",
            [
                "packing_list",
                "packinglist",
                "pack_list",
            ],
        ),
    ]

    for doc_type, aliases in filename_rules:
        if any(alias in name for alias in aliases):
            return doc_type

    # Fallback: use text from the document itself.
    text = pdf_text[:10000].lower()

    if (
        "dangerous goods declaration" in text
        or "multimodal dangerous goods form" in text
    ):
        return "dangerous_goods_declaration"

    if "bill of lading" in text:
        return "bill_of_lading"

    if "packing list" in text or "packing-list" in text:
        return "packing_list"

    if "commercial invoice" in text or "invoice number" in text:
        return "commercial_invoice"

    return None


# ---------------------------------------------------------
# Gemini extraction
# ---------------------------------------------------------

def extract_fields_with_gemini(
    client,
    document_type,
    pdf_text,
):
    """Ask Gemini to extract fields from one document."""
    fields = DOCUMENT_FIELDS[document_type]

    prompt = f"""
You are an information-extraction component for PortDoc AI,
a prototype that reviews maritime shipping documentation.

Document type: {document_type}

Extract exactly these field names:
{json.dumps(fields, indent=2)}

Document text:
--- BEGIN DOCUMENT TEXT ---
{pdf_text}
--- END DOCUMENT TEXT ---

Instructions:
1. Extract values as they are printed in this document.
2. Never correct, normalize to another document, or reconcile a value.
3. Do not invent values or fill gaps using assumptions.
4. If a field is absent or unclear, use null for its value.
5. Keep identifiers such as container IDs, seal numbers and UN
   numbers as strings.
6. Preserve units and wording where practical. For weight fields,
   return a number only when the document clearly gives a numeric
   value in the stated unit; otherwise preserve the printed value
   as a string or use null.
7. Include field-level provenance: page number and a short exact
   quote supporting each extracted value. Use an empty string for
   provenance if the value cannot be located.
8. List any ambiguity or extraction limitation in extraction_notes.
9. This task extracts document content only. Do not assess legal
   compliance or decide whether the shipment is safe.

Return one JSON object with exactly these top-level keys:
- fields: an object containing every requested field
- provenance: an object keyed by field name; each value contains
  page and quote
- extraction_notes: a list of strings

Use valid JSON only.
"""

    response = generate_with_retry(
    client=client,
    model=MODEL_NAME,
    prompt=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0,
    ),
)

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    result = json.loads(response.text)

    if not isinstance(result, dict):
        raise ValueError("Gemini response was not a JSON object.")

    extracted_fields = result.get("fields")
    if not isinstance(extracted_fields, dict):
        raise ValueError(
            "Gemini response did not contain a valid 'fields' object."
        )

    # Ensure every expected field exists. Do not invent values.
    cleaned_fields = {
        field: extracted_fields.get(field)
        for field in fields
    }

    provenance = result.get("provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}

    extraction_notes = result.get("extraction_notes", [])
    if not isinstance(extraction_notes, list):
        extraction_notes = [str(extraction_notes)]

    return {
        "fields": cleaned_fields,
        "provenance": provenance,
        "extraction_notes": extraction_notes,
    }


# ---------------------------------------------------------
# Process one shipment folder
# ---------------------------------------------------------

def extract_shipment(pdf_folder):
    """
    Process all PDFs in one shipment folder.

    Returns a dictionary containing:
      - documents: extracted fields for the validator
      - upload_inventory: one record per uploaded PDF
      - extraction_metadata: source and extraction details
    """
    folder = Path(pdf_folder)

    if not folder.exists():
        raise FileNotFoundError(
            f"PDF folder does not exist: {folder.resolve()}"
        )

    if not folder.is_dir():
        raise NotADirectoryError(
            f"Expected a folder, received: {folder}"
        )

    pdf_files = sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found in: {folder.resolve()}"
        )

    client = get_gemini_client()

    documents = {}
    upload_inventory = []
    extraction_metadata = {}
    used_document_types = set()

    total = len(pdf_files)

    for index, pdf_path in enumerate(pdf_files, start=1):
        print(
            f"[{index}/{total}] Processing {pdf_path.name}...",
            flush=True,
        )

        inventory_record = {
            "filename": pdf_path.name,
            "path": str(pdf_path.resolve()),
            "document_type": None,
            "status": "pending",
            "error": None,
        }

        try:
            pdf_text = read_pdf_text(pdf_path)
            document_type = identify_document_type(
                pdf_path.name,
                pdf_text,
            )

            inventory_record["document_type"] = document_type

            if document_type is None:
                inventory_record["status"] = "unidentified"
                inventory_record["error"] = (
                    "Could not identify the document type."
                )
                print(
                    f"  Warning: document type unidentified.",
                    flush=True,
                )
                upload_inventory.append(inventory_record)
                continue

            if document_type in used_document_types:
                inventory_record["status"] = "duplicate_type"
                inventory_record["error"] = (
                    "Another PDF has already been assigned this "
                    f"document type: {document_type}"
                )
                print(
                    f"  Warning: duplicate document type "
                    f"{document_type}; not overwriting earlier extraction.",
                    flush=True,
                )
                upload_inventory.append(inventory_record)
                continue

            extracted = extract_fields_with_gemini(
                client=client,
                document_type=document_type,
                pdf_text=pdf_text,
            )

            documents[document_type] = extracted["fields"]
            used_document_types.add(document_type)

            extraction_metadata[document_type] = {
                "source_pdf": pdf_path.name,
                "document_type": document_type,
                "fields": extracted["fields"],
                "provenance": extracted["provenance"],
                "extraction_notes": extracted["extraction_notes"],
                "status": "extracted",
            }

            inventory_record["status"] = "extracted"
            print(
                f"  Extracted as {document_type}.",
                flush=True,
            )

        except Exception as exc:
            inventory_record["status"] = "extraction_failed"
            inventory_record["error"] = str(exc)

            print(
                f"  Extraction failed: {exc}",
                flush=True,
            )

            # Keep failure information separate from the validator's
            # documents dictionary. A failed extraction is not proof
            # that a required document was absent.
            extraction_metadata[pdf_path.name] = {
                "source_pdf": pdf_path.name,
                "document_type": inventory_record["document_type"],
                "status": "extraction_failed",
                "error": str(exc),
            }

        upload_inventory.append(inventory_record)

    return {
        "documents": documents,
        "upload_inventory": upload_inventory,
        "extraction_metadata": extraction_metadata,
    }


# ---------------------------------------------------------
# Optional standalone command-line use
# ---------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract maritime document fields using Gemini."
    )
    parser.add_argument(
        "--pdf-folder",
        required=True,
        help="Folder containing the shipment PDFs.",
    )
    parser.add_argument(
        "--output",
        default="extracted_documents.json",
        help="Path for the JSON extraction output.",
    )
    args = parser.parse_args()

    result = extract_shipment(args.pdf_folder)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nExtraction output saved to: {output_path.resolve()}")
    print(f"Uploaded PDFs: {len(result['upload_inventory'])}")
    print(f"Successfully extracted document types: {len(result['documents'])}")
