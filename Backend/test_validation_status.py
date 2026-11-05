"""Checks for how the validator reports documents that were uploaded but not extracted.

No network or API key: the documents are given directly.

Run from the project root:
    python Backend/test_validation_status.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validator as V  # noqa: E402

FAILS = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILS.append(name)


def kinds(result):
    return sorted((f["finding_type"], f["affected_document"]) for f in result["findings"])


ALL_FOUR = ["bill_of_lading", "commercial_invoice", "packing_list", "dangerous_goods_declaration"]

# Uploaded but nothing extracted (the S01 situation after the free-tier quota ran out).
check("uploaded but not extracted is an extraction failure, not a missing document",
      kinds(V.validate({}, uploaded=ALL_FOUR)) == sorted(("extraction_failed", d) for d in ALL_FOUR))

# Not uploaded at all is still a missing document.
check("not uploaded is still a missing document",
      kinds(V.validate({}, uploaded=[])) == sorted(("missing_document", d) for d in ALL_FOUR))

# The old call (no uploaded argument) behaves as before.
check("calling without the uploaded argument still reports missing documents",
      kinds(V.validate({})) == sorted(("missing_document", d) for d in ALL_FOUR))

# "CLASS 9" and "9" are the same class value, so no false conflict.
check("a class written as 'CLASS 9' matches '9'", V.clean("CLASS 9") == V.clean("9"))
check("a class written as 'class 3' matches '3'", V.clean("class 3") == V.clean("3"))

docs = {
    "bill_of_lading": {"dg_class": "3", "gross_cargo_weight_kg": 18500, "container_id": "MSCU6639878"},
    "commercial_invoice": {}, "packing_list": {"gross_cargo_weight_kg": 18500, "container_id": "MSCU6639878"},
    "dangerous_goods_declaration": {"dg_class": "CLASS 3"},
}
check("matching class with a 'CLASS' prefix is not a conflict",
      not any(f["finding_type"] == "dg_class_conflict" for f in V.validate(docs)["findings"]))

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
