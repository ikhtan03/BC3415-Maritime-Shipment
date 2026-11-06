"""Attach regulatory context to validation findings from the extraction pipeline.

The pipeline's validator reports document findings (for example a weight mismatch). This module
adds, to the findings that have a regulatory side, a cited answer from the Singapore corpus.
It does not change any finding's status, and it never gives a compliance verdict: the pipeline's
regulatory_compliance field stays "not_assessed".

Usage from Python:
    from regulatory_context import attach_context
    report = attach_context(report, Retriever.from_corpus())
"""
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import answer as A  # noqa: E402

# Questions for findings that have a regulatory side, keyed by finding type. A missing document
# only has a regulatory side when it is the dangerous goods declaration.
QUESTIONS = {
    "dg_class_conflict": "What must a shipper specify about the hazard class of dangerous goods?",
    ("missing_document", "dangerous_goods_declaration"): "What must a dangerous goods declaration contain?",
}


def question_for(finding):
    """Return the regulatory question for a finding, or None if it is a document-only check."""
    key = (finding.get("finding_type"), finding.get("affected_document"))
    return QUESTIONS.get(key) or QUESTIONS.get(finding.get("finding_type"))


def regulatory_context(finding, retriever, model=None):
    """Return the cited regulatory answer for one finding, or a not_applicable note."""
    question = question_for(finding)
    if question is None:
        return {
            "status": "not_applicable",
            "reason": "This finding is a document comparison; the Singapore corpus does not cover it.",
        }
    try:
        result = A.answer(question, retriever, model=model)
    except Exception as exc:  # a failed model call (quota, overload, bad key) must not stop the other findings
        return {
            "status": "error",
            "question": question,
            "answer": "",
            "quotes": [],
            "sources": [],
            "problems": [f"model call failed: {str(exc)[:200]}"],
            "warnings": [],
        }
    by_id = {p["id"]: p for p in retriever.passages}
    sources = []
    for cid in result.get("citations", []):
        passage = by_id.get(cid)
        if passage:
            sources.append({"id": cid, "source": passage["source_title"], "url": passage["url"]})
    return {
        "status": result.get("status"),
        "question": question,
        "answer": result.get("answer", ""),
        "quotes": result.get("quotes", []),
        "sources": sources,
        "problems": result.get("problems", []),
        "warnings": result.get("warnings", []),
    }


def uploaded_document_types(report):
    """Document types whose PDF was in the upload inventory, from the file names (for example
    "dangerous_goods_declaration.pdf" -> "dangerous_goods_declaration")."""
    inventory = report.get("extraction", {}).get("upload_inventory", []) or []
    return {Path(item.get("filename", "")).stem for item in inventory if isinstance(item, dict)}


def attach_context(report, retriever, model=None):
    """Return a copy of a validation report with regulatory_context added to each finding.

    A "missing document" finding whose PDF was uploaded is inconclusive, not missing: the file was
    received but not extracted (the pipeline's own review notes say to check the inventory). It gets
    no regulatory question. The findings' status, the validation status and regulatory_compliance
    are not changed.
    """
    updated = copy.deepcopy(report)
    uploaded = uploaded_document_types(report)
    for finding in updated.get("validation", {}).get("findings", []):
        if finding.get("finding_type") == "missing_document" and finding.get("affected_document") in uploaded:
            finding["regulatory_context"] = {
                "status": "inconclusive",
                "reason": "The PDF was uploaded but not extracted, so it cannot be said to be missing. Check the extraction metadata.",
            }
        else:
            finding["regulatory_context"] = regulatory_context(finding, retriever, model=model)
    return updated
