"""Turns a validation report into what the user interface shows.

No display code here, so these functions can be tested without a browser. The Streamlit app
(Backend/app.py) only lays out what this module returns.
"""
import json
from pathlib import Path

DISCLAIMER = ("This is an academic prototype for document pre-checks. It is not an official "
              "regulatory clearance. Findings and regulatory answers are for human review.")
NO_SOURCE = "No supporting source found in the current corpus."
NOT_IN_CORPUS = "This is a document comparison, so no regulatory rule in the corpus applies to it."

PRIORITY_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}
FAILED_STATUSES = {"failed", "extraction_failed", "error", "unidentified", "identification_failed"}
DOCUMENT_TYPES = [
    ("bill_of_lading", "Bill of lading"),
    ("commercial_invoice", "Commercial invoice"),
    ("packing_list", "Packing list"),
    ("dangerous_goods_declaration", "Dangerous goods declaration"),
]
NEXT_STEP = {
    "weight_mismatch": "Check the gross cargo weight on the bill of lading and the packing list.",
    "container_mismatch": "Check the container ID on the bill of lading and the packing list.",
    "dg_class_conflict": "Qualified human review: check the dangerous goods class on the bill of lading and the declaration.",
    "missing_document": "Confirm whether this document was supplied. If it was not, obtain it before submission.",
    "extraction_failed": "Run extraction again for this document, then check the result.",
}
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


def new_progress():
    """Every stage starts as not run."""
    return {key: "not run" for key, _ in STAGES}


def apply_progress_line(line, progress):
    """Update the stages from one line of pipeline output. Returns the same dict."""
    for marker, updates in PROGRESS_MARKERS:
        if marker in line:
            progress.update(updates)
    return progress


def banner(report):
    """A one-line summary of the run, with its completeness."""
    findings = report.get("validation", {}).get("findings", [])
    if any(f.get("finding_type") == "extraction_failed" for f in findings):
        return {"level": "warning",
                "text": "Incomplete: some uploaded documents could not be read. Re-run the extraction before judging them."}
    if not findings:
        return {"level": "info", "text": "No configured issues found. This is not a compliance clearance."}
    return {"level": "error", "text": f"{len(findings)} finding(s) for review."}


def triage_view(report):
    """Suggested priority, the review flag and the reasons, if the pipeline produced them."""
    triage = report.get("validation", {}).get("triage")
    if not triage:
        return None
    return {
        "priority": PRIORITY_LABEL.get(triage.get("suggested_priority"), "Unknown"),
        "review": "Human review recommended" if triage.get("human_review_recommended") else "No review needed",
        "review_needed": bool(triage.get("human_review_recommended")),
        "reasons": triage.get("reasons", []),
    }


def findings_view(report):
    """One row per finding, for the summary table."""
    rows = []
    for f in report.get("validation", {}).get("findings", []):
        rows.append({
            "Finding": f.get("finding_type", "").replace("_", " "),
            "Document": f.get("affected_document", ""),
            "Field": f.get("affected_field") or "",
            "Action": f.get("expected_action", "").replace("_", " "),
            "Explanation": f.get("explanation", ""),
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
        "question": context.get("question", ""),
        "question_source": context.get("question_source", ""),
        "answer": context.get("answer", ""),
        "sources": sources,
        "quotes": context.get("quotes", []),
        "checks": context.get("problems", []),
        "warnings": context.get("warnings", []),
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
    """One card per finding, ready for the review queue."""
    triage = triage_view(report)
    review_flag = bool(triage and triage["review_needed"])
    cards = []
    for f in report.get("validation", {}).get("findings", []):
        ftype = f.get("finding_type", "")
        values = []
        if f.get("reference_document") is not None:
            values = [
                {"document": f["reference_document"].replace("_", " "), "value": f.get("reference_value")},
                {"document": f.get("affected_document", "").replace("_", " "), "value": f.get("observed_value")},
            ]
        cards.append({
            "title": ftype.replace("_", " ").capitalize(),
            "document": f.get("affected_document", "").replace("_", " "),
            "field": (f.get("affected_field") or "").replace("_", " "),
            "values": values,
            "explanation": f.get("explanation", ""),
            "action": f.get("expected_action", "").replace("_", " "),
            "next_step": NEXT_STEP.get(ftype, "Check this finding against the source documents."),
            "human_review": review_flag or f.get("expected_action") == "qualified_human_review",
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
        return "Document count unknown"
    return f"{info['extracted']} of {info['uploaded']} documents read"


def summary(report):
    """Everything the screen shows, in one dictionary."""
    return {
        "banner": banner(report),
        "documents_read": documents_read_text(report),
        "extraction": extraction_view(report),
        "triage": triage_view(report),
        "cards": review_cards(report),
        "findings": findings_view(report),
        "compliance": report.get("validation", {}).get("regulatory_compliance", "not_assessed"),
        "disclaimer": DISCLAIMER,
    }
