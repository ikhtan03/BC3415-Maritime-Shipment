"""Verification rounds for flagged findings (the answer keys' verification_expectations).

When the validator flags a field, the flagged documents are extracted again, up to max_rounds times.
If the mismatch is still there after the last round, the finding is kept for human review. If a
re-extraction fails (reextract returns None), that document is left unchanged.

reextract(doc_type) is supplied by the caller: a function that re-runs extraction for one document
and returns its fields as a dict, or None if extraction failed. Keeping it as a parameter lets the
round logic be tested without the Gemini API.
"""
import copy
import shutil
import tempfile
from pathlib import Path

from validator import validate

# Documents to re-check for each flagged finding type, from the answer keys' documents_to_recheck.
RECHECK = {
    "weight_mismatch": ["bill_of_lading", "commercial_invoice", "packing_list", "dangerous_goods_declaration"],
    "container_mismatch": ["bill_of_lading", "packing_list", "dangerous_goods_declaration"],
    "dg_class_conflict": ["bill_of_lading", "dangerous_goods_declaration"],
}


def verify(documents, uploaded, reextract, max_rounds=2):
    """Re-extract flagged documents and re-validate, up to max_rounds. Returns the final validation
    result, the documents used for it, and a record of each round."""
    documents = copy.deepcopy(documents)
    result = validate(documents, uploaded=uploaded)
    rounds = []
    for round_number in range(1, max_rounds + 1):
        flagged = [f for f in result["findings"] if f["finding_type"] in RECHECK]
        if not flagged:
            break
        to_recheck = sorted({doc for f in flagged for doc in RECHECK[f["finding_type"]]})
        for doc in to_recheck:
            fresh = reextract(doc)
            if fresh is not None:
                documents[doc] = fresh
        result = validate(documents, uploaded=uploaded)
        rounds.append({
            "round": round_number,
            "rechecked": to_recheck,
            "remaining": sorted({f["finding_type"] for f in result["findings"] if f["finding_type"] in RECHECK}),
        })
    return {"validation": result, "documents": documents, "rounds": rounds}


def reextractor(pdf_folder, extract_fn):
    """Return reextract(doc_type) for verify(): it copies the PDF for that document into a temporary
    folder on its own, runs extract_fn on that folder, and returns the document's fields (or None)."""
    def reextract(doc_type):
        pdfs = [path for path in Path(pdf_folder).rglob("*.pdf") if path.stem == doc_type]
        if not pdfs:
            return None
        with tempfile.TemporaryDirectory() as folder:
            shutil.copy(pdfs[0], folder)
            result = extract_fn(pdf_folder=folder)
        return result.get("documents", {}).get(doc_type)
    return reextract
