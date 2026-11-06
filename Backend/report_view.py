"""Turns a validation report into what the user interface shows.

No display code here, so these functions can be tested without a browser. The Streamlit app
(Backend/app.py) only lays out what this module returns. Field names come from the report schema
written by run_pipeline.py and validator.py; labels for people are translated here.
"""
import json
import re
from pathlib import Path

DISCLAIMER = ("This prototype provides a document pre-check. It does not assess regulatory compliance "
              "or replace qualified review.")
NO_SOURCE = "No supporting source found in the current corpus."
NOT_IN_CORPUS = "This is a document comparison, so no regulatory rule in the corpus applies to it."
NOT_AVAILABLE = "Not available"
CORPUS_NOTE = "Source: the project's limited corpus of official documents. For human review."

DOCUMENT_TYPES = [
    ("bill_of_lading", "Bill of lading"),
    ("commercial_invoice", "Commercial invoice"),
    ("packing_list", "Packing list"),
    ("dangerous_goods_declaration", "Dangerous goods declaration"),
]
DOCUMENT_LABELS = dict(DOCUMENT_TYPES)
FIELD_LABELS = {
    "gross_cargo_weight_kg": "Gross cargo weight",
    "container_id": "Container ID",
    "dg_class": "Dangerous goods class",
    "un_number": "UN number",
    "proper_shipping_name": "Proper shipping name",
    "port_of_discharge": "Port of discharge",
    "terminal": "Terminal",
}
TITLES = {
    "weight_mismatch": "Gross weight differs",
    "container_mismatch": "Container ID differs",
    "dg_class_conflict": "Dangerous goods class differs",
    "missing_document": "Document missing",
    "extraction_failed": "Document could not be read",
}
NEXT_STEP = {
    "weight_mismatch": "Check the gross cargo weight on the bill of lading and the packing list.",
    "container_mismatch": "Check the container ID on the bill of lading and the packing list.",
    "dg_class_conflict": "Qualified human review: check the dangerous goods class on the bill of lading and the declaration.",
    "missing_document": "Confirm whether this document was supplied. If it was not, obtain it before submission.",
    "extraction_failed": "Upload a readable copy of this document (selectable text, not a scan), then run the check again.",
}
FAILED_STATUSES = {"failed", "extraction_failed", "error", "unidentified", "identification_failed"}
PRIORITY_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}
# Stages shown to the user, in plain language.
STAGES = [
    ("read", "Reading documents"),
    ("check", "Checking fields"),
    ("verify", "Verifying mismatches"),
    ("triage", "Suggesting review priority"),
    ("context", "Finding regulatory context"),
    ("report", "Preparing report"),
]
# Lines the pipeline prints, and the stage updates each one means.
PROGRESS_MARKERS = [
    ("[1/3]", {"read": "in progress"}),
    ("Extraction result saved", {"read": "complete"}),
    ("[2/3]", {"check": "in progress"}),
    ("Re-checking flagged fields", {"check": "complete", "verify": "in progress"}),
    ("[3/3]", {"check": "complete", "verify": "complete", "triage": "complete"}),
    ("Attaching regulatory context", {"context": "in progress"}),
    ("Validation report saved", {"context": "complete", "report": "complete"}),
]


def load_report(path):
    """Read a validation_report.json saved by the pipeline."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def report_bytes(report):
    """The report as UTF-8 JSON, for download."""
    return json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")


def humanize(text):
    """Replace internal field and document names in a sentence with readable labels."""
    if not text:
        return ""
    for key, label in {**FIELD_LABELS, **DOCUMENT_LABELS}.items():
        text = re.sub(rf"\b{re.escape(key)}\b", label, text)
    return text


def value_text(value):
    """A value for display, or 'Not available' when the report has none."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return NOT_AVAILABLE
    return str(value)


def new_progress():
    """Every stage starts as not run."""
    return {key: "not run" for key, _ in STAGES}


def apply_progress_line(line, progress):
    """Update the stages from one line of pipeline output. Returns the same dict."""
    for marker, updates in PROGRESS_MARKERS:
        if marker in line:
            progress.update(updates)
    return progress


def slot_states(uploaded, report=None, running=False):
    """The state of each document slot: Missing, Uploaded, Reading, Read or Could not read.

    uploaded: {doc_key: True/False}. report: the result of the last check, if any.
    """
    failed = set()
    read = set()
    if report:
        failed = {Path(name).stem for name in extraction_view(report)["failed_files"]}
        read = {key for key, _ in DOCUMENT_TYPES if key not in failed and uploaded.get(key)}
    states = {}
    for key, _ in DOCUMENT_TYPES:
        if not uploaded.get(key):
            states[key] = "Missing"
        elif running:
            states[key] = "Reading"
        elif key in failed:
            states[key] = "Could not read"
        elif key in read:
            states[key] = "Read"
        else:
            states[key] = "Uploaded"
    return states


def banner(report):
    """A one-line summary of the run, with its completeness."""
    findings = report.get("validation", {}).get("findings", [])
    if any(f.get("finding_type") == "extraction_failed" for f in findings):
        return {"level": "warning",
                "text": "Incomplete: some documents could not be read, so this check cannot be complete. Upload readable copies and run the check again."}
    if not findings:
        return {"level": "info", "text": "No configured issues were found. This is not a compliance clearance."}
    return {"level": "error", "text": f"{len(findings)} finding(s) need review."}


def triage_view(report):
    """Suggested priority, the review flag and the reasons, if the pipeline produced them."""
    triage = report.get("validation", {}).get("triage")
    if not triage:
        return None
    return {
        "priority": PRIORITY_LABEL.get(triage.get("suggested_priority"), NOT_AVAILABLE),
        "review": "Review recommended" if triage.get("human_review_recommended") else "No review needed",
        "review_needed": bool(triage.get("human_review_recommended")),
        "reasons": [humanize(reason) for reason in triage.get("reasons", [])],
    }


def findings_view(report):
    """One row per finding, for the summary table, with readable labels."""
    rows = []
    for f in report.get("validation", {}).get("findings", []):
        rows.append({
            "Finding": TITLES.get(f.get("finding_type", ""), f.get("finding_type", "")),
            "Document": DOCUMENT_LABELS.get(f.get("affected_document", ""), f.get("affected_document", "")),
            "Field": FIELD_LABELS.get(f.get("affected_field") or "", f.get("affected_field") or NOT_AVAILABLE),
        })
    return rows


def regulatory_block(context):
    """The evidence for one finding: the answer, its sources and quotes, or why there is none."""
    if not context:
        return None
    status = context.get("status", "")
    sources = context.get("sources", [])
    block = {
        "status": status,
        "question": humanize(context.get("question", "")),
        "question_source": context.get("question_source", ""),
        "answer": context.get("answer", ""),
        "sources": sources,
        "quotes": context.get("quotes", []),
        "checks": context.get("problems", []),
        "warnings": context.get("warnings", []),
        "corpus_note": CORPUS_NOTE,
        "message": "",
    }
    if status == "not_applicable":
        block["message"] = context.get("reason") or NOT_IN_CORPUS
    elif status == "error":
        block["message"] = "The regulatory check could not run: " + "; ".join(context.get("problems", []))
    elif status in ("not_found", "") or not sources:
        block["message"] = NO_SOURCE
    return block


def review_cards(report):
    """One card per finding, with readable labels and the values side by side."""
    triage = triage_view(report)
    shipment_review = bool(triage and triage["review_needed"])
    cards = []
    for f in report.get("validation", {}).get("findings", []):
        ftype = f.get("finding_type", "")
        values = []
        if f.get("reference_document") is not None:
            values = [
                {"document": DOCUMENT_LABELS.get(f["reference_document"], f["reference_document"]),
                 "value": value_text(f.get("reference_value"))},
                {"document": DOCUMENT_LABELS.get(f.get("affected_document", ""), f.get("affected_document", "")),
                 "value": value_text(f.get("observed_value"))},
            ]
        cards.append({
            "title": TITLES.get(ftype, humanize(ftype)),
            "document": DOCUMENT_LABELS.get(f.get("affected_document", ""), NOT_AVAILABLE),
            "field": FIELD_LABELS.get(f.get("affected_field") or "", f.get("affected_field") or ""),
            "values": values,
            "explanation": humanize(f.get("explanation", "")),
            "next_step": NEXT_STEP.get(ftype, "Check this finding against the source documents."),
            "human_review": shipment_review or f.get("expected_action") == "qualified_human_review",
            "regulatory": regulatory_block(f.get("regulatory_context")),
        })
    return cards


def extraction_view(report):
    """How many uploaded PDFs were read, and any that failed."""
    input_info = report.get("input", {})
    inventory = report.get("extraction", {}).get("upload_inventory", []) or []
    failed = [item.get("filename", "") for item in inventory
              if isinstance(item, dict) and str(item.get("status", "")).lower() in FAILED_STATUSES]
    return {
        "uploaded": input_info.get("uploaded_pdf_count"),
        "extracted": input_info.get("extracted_document_count"),
        "failed_files": failed,
    }


def documents_read_text(report):
    """'4 of 4 documents read', or a plain note when the count is unknown."""
    info = extraction_view(report)
    if info["uploaded"] is None or info["extracted"] is None:
        return NOT_AVAILABLE
    return f"{info['extracted']} of {info['uploaded']}"


def summary(report):
    """Everything the screen shows, in one dictionary."""
    triage = triage_view(report)
    return {
        "banner": banner(report),
        "documents_read": documents_read_text(report),
        "extraction": extraction_view(report),
        "triage": triage,
        "cards": review_cards(report),
        "findings": findings_view(report),
        "compliance": "not assessed",
        "disclaimer": DISCLAIMER,
    }
