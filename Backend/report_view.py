"""Turns a saved validation report into what the user interface shows.

No display code here, so these functions can be tested without a browser. The Streamlit app
(Backend/app.py) only lays out what this module returns.
"""
import json
from pathlib import Path

DISCLAIMER = ("This is an academic prototype for document pre-checks. It is not an official "
              "regulatory clearance. Findings and regulatory answers are for human review.")

PRIORITY_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}
FAILED_STATUSES = {"failed", "extraction_failed", "error", "unidentified", "identification_failed"}


def load_report(path):
    """Read a validation_report.json saved by the pipeline."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
    """Suggested priority and review flag, if the pipeline produced them."""
    triage = report.get("validation", {}).get("triage")
    if not triage:
        return None
    return {
        "priority": PRIORITY_LABEL.get(triage.get("suggested_priority"), "Unknown"),
        "review": "Human review recommended" if triage.get("human_review_recommended") else "No review needed",
        "reasons": triage.get("reasons", []),
    }


def findings_view(report):
    """One row per finding: what it is, where, and what to do."""
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


def regulatory_view(report):
    """For each finding that has regulatory context: the question, answer, sources and checks."""
    items = []
    for f in report.get("validation", {}).get("findings", []):
        context = f.get("regulatory_context")
        if not context:
            continue
        items.append({
            "finding": f.get("finding_type", "").replace("_", " "),
            "status": context.get("status", ""),
            "question": context.get("question", ""),
            "question_source": context.get("question_source", ""),
            "answer": context.get("answer", "") or context.get("reason", ""),
            "sources": context.get("sources", []),
            "checks": context.get("problems", []),
            "warnings": context.get("warnings", []),
        })
    return items


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


def summary(report):
    """Everything the screen shows, in one dictionary."""
    return {
        "banner": banner(report),
        "extraction": extraction_view(report),
        "triage": triage_view(report),
        "findings": findings_view(report),
        "regulatory": regulatory_view(report),
        "compliance": report.get("validation", {}).get("regulatory_compliance", "not_assessed"),
        "disclaimer": DISCLAIMER,
    }
