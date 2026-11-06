"""Turns a validation report into what the user interface shows.

No display code here, so these functions can be tested without a browser. The Streamlit app
(Backend/app.py) only lays out what this module returns. Field names come from the report schema
written by run_pipeline.py and validator.py; the words shown to people are written here.
"""
import json
import re
from pathlib import Path

DISCLAIMER = ("This prototype provides a document pre-check. It does not assess regulatory compliance "
              "or replace qualified review.")
NO_SOURCE = "No relevant source was found in the current corpus."
NOT_AVAILABLE = "Not available"
CORPUS_NOTE = "Source: the project's limited corpus of official documents. For human review."
FAILURE_MESSAGE = ("We couldn't finish reading the documents. Check that the extraction service is available, "
                   "then try again.")
UPLOAD_HELP = ("Upload the documents you have. We'll run the checks possible with this set and identify "
               "anything we could not check.")

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
# Words that suggest which document a file is. Used only to prompt a check, never to decide.
TYPE_WORDS = {
    "bill_of_lading": ["bill of lading", "bill_of_lading", "b/l", "bl_", "lading"],
    "commercial_invoice": ["invoice"],
    "packing_list": ["packing"],
    "dangerous_goods_declaration": ["declaration", "dgd", "dangerous"],
}
TITLES = {
    "weight_mismatch": "Gross weight does not match",
    "container_mismatch": "Container ID does not match",
    "dg_class_conflict": "Dangerous-goods class does not match",
    "missing_document": "Document missing",
    "extraction_failed": "Document could not be read",
}
EXPLANATIONS = {
    "weight_mismatch": "The gross cargo weight differs between the bill of lading and the packing list. Check both documents.",
    "container_mismatch": "The container ID differs between the packing list and the bill of lading. Check both documents.",
    "dg_class_conflict": ("The two documents list different dangerous-goods classes. Check both documents and ask a "
                          "qualified reviewer to confirm which information is correct."),
    "missing_document": "This document was not supplied, so checks that need it could not be completed.",
    "extraction_failed": "This document was uploaded but could not be read, so checks that need it are incomplete.",
}
NEXT_STEP = {
    "weight_mismatch": "Check the gross cargo weight on the bill of lading and the packing list.",
    "container_mismatch": "Check the container ID on the bill of lading and the packing list.",
    "dg_class_conflict": "Review the dangerous-goods class on the bill of lading and the declaration.",
    "missing_document": "Upload this document if you have it, then run the check again.",
    "extraction_failed": "Check that the file has selectable text (not a scan), then run the check again.",
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


def value_text(value, field=None):
    """A value for display, with its unit where the field has one. 'Not available' when missing."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return NOT_AVAILABLE
    text = str(value).strip()
    if field == "dg_class":
        number = re.sub(r"^class\s*", "", text, flags=re.IGNORECASE)
        return f"Class {number}"
    if field == "gross_cargo_weight_kg" and re.fullmatch(r"[\d,.]+", text):
        return f"{text} kg"
    return text


def new_progress():
    """Every stage starts as not run."""
    return {key: "not run" for key, _ in STAGES}


def apply_progress_line(line, progress):
    """Update the stages from one line of pipeline output. Returns the same dict."""
    for marker, updates in PROGRESS_MARKERS:
        if marker in line:
            progress.update(updates)
    return progress


def finish_progress(progress, completed):
    """After a run ends: stages still in progress are marked not completed, never left as 'in progress'."""
    if completed:
        return progress
    for key in progress:
        if progress[key] == "in progress":
            progress[key] = "not completed"
    return progress


def apply_outcome(progress, report):
    """After a run that finished: reading is incomplete when any uploaded document could not be read."""
    if extraction_view(report)["failed_files"]:
        progress["read"] = "incomplete"
    return progress


def type_hint(filename, slot):
    """The document type a file name suggests, if it clearly points to a different slot. A prompt only."""
    name = re.sub(r"[_\-.]+", " ", (filename or "").lower())
    hinted = [key for key, words in TYPE_WORDS.items() if any(word.replace("_", " ") in name for word in words)]
    if len(hinted) == 1 and hinted[0] != slot:
        return hinted[0]
    return None


def identified_types(report):
    """The document type the pipeline identified for each uploaded file, by file name stem."""
    inventory = (report or {}).get("extraction", {}).get("upload_inventory", []) or []
    return {Path(item.get("filename", "")).stem: item.get("document_type")
            for item in inventory if isinstance(item, dict) and item.get("document_type")}


def same_file_slots(fingerprints):
    """Slots that hold the same file (same content), which would make a misleading comparison."""
    seen, duplicates = {}, set()
    for slot, digest in fingerprints.items():
        if digest is None:
            continue
        if digest in seen:
            duplicates.update({slot, seen[digest]})
        else:
            seen[digest] = slot
    return duplicates


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


def slot_states(uploaded, report=None, running=False, mismatch=None):
    """The state of each document slot: Missing, Uploaded, Reading, Read, Could not read or Type may not match.

    uploaded: {doc_key: True/False}. report: the last check's result, if any.
    mismatch: {doc_key: True} for slots whose file name or identified type points to another document.
    """
    failed, read = set(), set()
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
        if states[key] in ("Uploaded", "Read") and (mismatch or {}).get(key):
            states[key] = "Type may not match"
    return states


def banner(report):
    """A one-line summary of the run, with its completeness."""
    validation = report.get("validation", {})
    findings = validation.get("findings", [])
    if any(f.get("finding_type") == "extraction_failed" for f in findings):
        return {"level": "warning",
                "text": "Some documents could not be read, so the checks that need them are incomplete."}
    if not findings:
        return {"level": "info", "text": "No findings were detected in the checks that could run."}
    return {"level": "error", "text": f"{len(findings)} finding(s) need review."}


def triage_view(report):
    """Suggested review order and the reasons, if the pipeline produced them."""
    triage = report.get("validation", {}).get("triage")
    if not triage:
        return None
    return {
        "priority": PRIORITY_LABEL.get(triage.get("suggested_priority"), NOT_AVAILABLE),
        "review": "Human review recommended" if triage.get("human_review_recommended") else "No review needed",
        "review_needed": bool(triage.get("human_review_recommended")),
        "reasons": [humanize(reason) for reason in triage.get("reasons", [])],
    }


def checks_not_completed_view(report):
    """Checks that could not run, each with the document or field that was needed."""
    rows = []
    for item in report.get("validation", {}).get("checks_not_completed", []) or []:
        rows.append({
            "check": item.get("check", ""),
            "text": f"{item.get('check', 'This check')} could not be checked: {humanize(item.get('reason', ''))}.",
            "needed": [DOCUMENT_LABELS.get(doc, doc) for doc in item.get("documents", [])],
        })
    return rows


def regulatory_block(context):
    """Regulatory context to show for one finding, or None when there is nothing useful to show."""
    if not context:
        return None
    status = context.get("status", "")
    sources = context.get("sources", [])
    if status == "not_applicable":
        return None
    if status == "error":
        return {"message": "The regulatory check could not run.", "answer": "", "sources": [], "quotes": [],
                "question": "", "corpus_note": CORPUS_NOTE}
    if status == "supported" and sources:
        return {
            "message": "",
            "answer": context.get("answer", ""),
            "sources": sources,
            "quotes": context.get("quotes", []),
            "question": humanize(context.get("question", "")),
            "corpus_note": CORPUS_NOTE,
        }
    return {"message": NO_SOURCE, "answer": "", "sources": [], "quotes": [],
            "question": humanize(context.get("question", "")), "corpus_note": CORPUS_NOTE}


def findings_view(report):
    """One row per finding, for the summary table, with readable labels."""
    rows = []
    for f in report.get("validation", {}).get("findings", []):
        field = f.get("affected_field") or ""
        rows.append({
            "Finding": TITLES.get(f.get("finding_type", ""), humanize(f.get("finding_type", ""))),
            "Document": DOCUMENT_LABELS.get(f.get("affected_document", ""), NOT_AVAILABLE),
            "Field": FIELD_LABELS.get(field, NOT_AVAILABLE if not field else field),
        })
    return rows


def review_cards(report):
    """One card per finding: plain title and explanation, values side by side, the next step."""
    triage = triage_view(report)
    shipment_review = bool(triage and triage["review_needed"])
    cards = []
    for f in report.get("validation", {}).get("findings", []):
        ftype = f.get("finding_type", "")
        field = f.get("affected_field") or ""
        values = []
        if f.get("reference_document") is not None:
            values = [
                {"document": DOCUMENT_LABELS.get(f["reference_document"], f["reference_document"]),
                 "value": value_text(f.get("reference_value"), field),
                 "source": field_source(report, f["reference_document"], field)},
                {"document": DOCUMENT_LABELS.get(f.get("affected_document", ""), f.get("affected_document", "")),
                 "value": value_text(f.get("observed_value"), field),
                 "source": field_source(report, f.get("affected_document", ""), field)},
            ]
        cards.append({
            "title": TITLES.get(ftype, humanize(ftype)),
            "document": DOCUMENT_LABELS.get(f.get("affected_document", ""), NOT_AVAILABLE),
            "field": FIELD_LABELS.get(field, NOT_AVAILABLE if not field else field),
            "values": values,
            "explanation": EXPLANATIONS.get(ftype, humanize(f.get("explanation", ""))),
            "next_step": NEXT_STEP.get(ftype, "Check this finding against the source documents."),
            "human_review": shipment_review or f.get("expected_action") == "qualified_human_review",
            "regulatory": regulatory_block(f.get("regulatory_context")),
        })
    return cards


def documents_read_text(report):
    """'4 of 4', or 'Not available' when the count is unknown."""
    info = extraction_view(report)
    if info["uploaded"] is None or info["extracted"] is None:
        return NOT_AVAILABLE
    return f"{info['extracted']} of {info['uploaded']}"


def missing_documents_view(report):
    """Document types that were not supplied. Listed on their own, not as findings."""
    return [DOCUMENT_LABELS.get(f.get("affected_document", ""), NOT_AVAILABLE)
            for f in report.get("validation", {}).get("findings", [])
            if f.get("finding_type") == "missing_document"]


def summary(report):
    """Everything the screen shows, in one dictionary. Compliance is always 'not assessed'."""
    cards = review_cards(report)
    return {
        "banner": banner(report),
        "documents_read": documents_read_text(report),
        "extraction": extraction_view(report),
        "triage": triage_view(report),
        "cards": [c for c in cards if c["title"] != TITLES["missing_document"]],
        "missing": missing_documents_view(report),
        "findings": findings_view(report),
        "not_completed": checks_not_completed_view(report),
        "checks": checks_view(report),
        "notes": extraction_notes_view(report),
        "saved": saved_info(report),
        "compliance": "not assessed",
        "disclaimer": DISCLAIMER,
    }


def field_source(report, doc, field):
    """Where a value came from in its document: the page and the quoted text, if the report has them."""
    metadata = (report.get("extraction", {}).get("extraction_metadata", {}) or {}).get(doc, {})
    provenance = (metadata.get("provenance", {}) or {}).get(field)
    if not provenance:
        return None
    return {"page": provenance.get("page"), "quote": provenance.get("quote", "")}


def extraction_notes_view(report):
    """Notes the extraction step recorded for each document, for the technical view and the review."""
    notes = []
    for doc, metadata in (report.get("extraction", {}).get("extraction_metadata", {}) or {}).items():
        for note in metadata.get("extraction_notes", []) or []:
            notes.append({"document": DOCUMENT_LABELS.get(doc, doc), "note": note})
    return notes


def checks_view(report):
    """Every check the tool runs, and what happened: a finding, no difference, or not completed."""
    validation = report.get("validation", {})
    findings = {(f.get("finding_type"), f.get("affected_document")) for f in validation.get("findings", [])}
    not_done = {c.get("check") for c in validation.get("checks_not_completed", []) or []}
    rows = []
    for label, finding_type in [("Gross cargo weight", "weight_mismatch"),
                                ("Container ID", "container_mismatch"),
                                ("Dangerous goods class", "dg_class_conflict")]:
        if label in not_done:
            result = "Not completed"
        elif any(ftype == finding_type for ftype, _ in findings):
            result = "Difference found"
        else:
            result = "No difference found"
        rows.append({"check": label, "result": result})
    for doc, label in DOCUMENT_TYPES:
        present = not any(f.get("finding_type") == "missing_document" and f.get("affected_document") == doc
                          for f in validation.get("findings", []))
        rows.append({"check": f"{label} supplied", "result": "Yes" if present else "No"})
    return rows


def saved_info(report):
    """A line that says when the saved report was made and that it is a record, not a fresh check."""
    stamp = report.get("generated_at_utc", "")
    when = stamp[:16].replace("T", " ") + " UTC" if stamp else "an unknown time"
    return f"Saved report from {when}. This is a record of an earlier check, not a fresh run."


def answer_view(result, passages_by_id):
    """Shape an answer from the answer step for the screen: the answer, its sources, quotes and checks."""
    sources = []
    for cid in result.get("citations", []):
        passage = passages_by_id.get(cid)
        if passage:
            sources.append({"source": passage.get("source_title", ""), "url": passage.get("url", "")})
    status = result.get("status", "")
    if status == "not_found" or not sources:
        message = NO_SOURCE
    else:
        message = ""
    return {
        "status": status,
        "answer": result.get("answer", "") if not message else "",
        "message": message,
        "sources": sources,
        "quotes": result.get("quotes", []),
        "checks": result.get("problems", []),
        "corpus_note": CORPUS_NOTE,
    }
