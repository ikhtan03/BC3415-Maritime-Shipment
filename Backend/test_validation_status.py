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

# a weight written with commas and a unit matches the same number
check("'18,500 kg' matches 18500", V.clean("18,500 kg") == V.clean(18500))
check("'18500' matches 18500", V.clean("18500") == V.clean(18500))
check("text values are not turned into numbers", V.clean("MSCU6639878") == "MSCU6639878")

# a partial set: checks that need a missing document are reported as not completed, never as passed
partial = V.validate({"packing_list": {"gross_cargo_weight_kg": 18500, "container_id": "X1"}})
not_done = {c["check"]: c for c in partial["checks_not_completed"]}
check("a missing document leaves the weight check not completed",
      "Gross cargo weight" in not_done and "bill_of_lading is missing" in not_done["Gross cargo weight"]["reason"])
check("a missing document leaves the class check not completed", "Dangerous goods class" in not_done)
check("a check that did not run is not reported as a finding",
      not any(f["finding_type"] in ("weight_mismatch", "dg_class_conflict") for f in partial["findings"]))

full = {
    "bill_of_lading": {"gross_cargo_weight_kg": 18500, "container_id": "X1", "dg_class": "3"},
    "commercial_invoice": {},
    "packing_list": {"gross_cargo_weight_kg": 18500, "container_id": "X1"},
    "dangerous_goods_declaration": {"dg_class": "3"},
}
check("a complete set with agreeing values has no checks left undone", V.validate(full)["checks_not_completed"] == [])

unreadable = dict(full)
unreadable["packing_list"] = {"container_id": "X1"}
gap = {c["check"]: c for c in V.validate(unreadable)["checks_not_completed"]}
check("an unreadable weight field is reported as not completed",
      "Gross cargo weight" in gap and "gross_cargo_weight_kg could not be read from packing_list" in gap["Gross cargo weight"]["reason"])

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
