"""Checks for the verification rounds. No network or API key: re-extraction is a fake function.

Run from the project root:
    python Backend/test_verification.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verification as VR  # noqa: E402

FAILS = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILS.append(name)


DOCS = {
    "bill_of_lading": {"gross_cargo_weight_kg": 18500, "container_id": "MSCU6639878", "dg_class": "3"},
    "commercial_invoice": {},
    "packing_list": {"gross_cargo_weight_kg": 19500, "container_id": "MSCU6639878"},
    "dangerous_goods_declaration": {"dg_class": "3"},
}
UPLOADED = list(DOCS)

# Re-extraction returns the same values: the weight mismatch is kept after the rounds.
calls = []


def same(doc):
    calls.append(doc)
    return dict(DOCS[doc])


kept = VR.verify(DOCS, UPLOADED, same, max_rounds=2)
check("a mismatch that survives re-extraction is kept",
      any(f["finding_type"] == "weight_mismatch" for f in kept["validation"]["findings"]))
check("it runs no more than two rounds", len(kept["rounds"]) == 2)
check("the input documents are not changed", DOCS["packing_list"]["gross_cargo_weight_kg"] == 19500)

# Re-extraction reads the correct weight on the packing list: the finding is resolved in round 1.
def corrected(doc):
    fixed = dict(DOCS[doc])
    if doc == "packing_list":
        fixed["gross_cargo_weight_kg"] = 18500
    return fixed


resolved = VR.verify(DOCS, UPLOADED, corrected, max_rounds=2)
check("a mismatch that disappears on re-extraction is resolved",
      not any(f["finding_type"] == "weight_mismatch" for f in resolved["validation"]["findings"]))
check("resolution stops the rounds early", len(resolved["rounds"]) == 1)

# A failed re-extraction (None) leaves the document as it was.
failed = VR.verify(DOCS, UPLOADED, lambda doc: None, max_rounds=2)
check("a failed re-extraction keeps the original document",
      any(f["finding_type"] == "weight_mismatch" for f in failed["validation"]["findings"]))

# A clean report needs no rounds at all.
clean_docs = {
    "bill_of_lading": {"gross_cargo_weight_kg": 18500, "container_id": "X1", "dg_class": "3"},
    "commercial_invoice": {}, "packing_list": {"gross_cargo_weight_kg": 18500, "container_id": "X1"},
    "dangerous_goods_declaration": {"dg_class": "3"},
}
calls.clear()
clean = VR.verify(clean_docs, list(clean_docs), same, max_rounds=2)
check("a report with no flagged fields needs no re-extraction", clean["rounds"] == [] and calls == [])

# reextractor copies only the named document's PDF and returns that document's fields
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as source:
    Path(source, "bill_of_lading.pdf").write_bytes(b"%PDF-fake")

    def fake_extract(pdf_folder):
        present = [p.stem for p in Path(pdf_folder).glob("*.pdf")]
        return {"documents": {doc: {"gross_cargo_weight_kg": 18500} for doc in present}}

    rex = VR.reextractor(source, fake_extract)
    check("reextractor returns the fields for the document that has a PDF",
          rex("bill_of_lading") == {"gross_cargo_weight_kg": 18500})
    check("reextractor returns None for a document with no PDF", rex("packing_list") is None)

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
