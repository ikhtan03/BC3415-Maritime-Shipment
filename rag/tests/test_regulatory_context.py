"""Checks for the regulatory-context adapter. No network or API key: the model is a stub.

Run from the repo root:
    python rag/tests/test_regulatory_context.py
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import regulatory_context as R  # noqa: E402
import planner as P  # noqa: E402
from retrieve import Retriever  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def stub(prompt):
    """Cite the first passage in the prompt, quoting its first sentence exactly."""
    first_id = prompt.split("[", 1)[1].split("]", 1)[0]
    first_text = prompt.split(f"[{first_id}] ", 1)[1].split("\n", 1)[1]
    return {"answer": "stub", "status": "supported", "citations": [first_id],
            "quotes": [{"id": first_id, "quote": first_text.split(". ")[0][:80]}]}


retriever = Retriever.from_corpus()

weight = {"finding_type": "weight_mismatch", "affected_document": "packing_list",
          "affected_field": "gross_cargo_weight_kg"}
check("weight mismatch is a document check, not applicable",
      R.regulatory_context(weight, retriever, model=stub)["status"] == "not_applicable")

dg_class = {"finding_type": "dg_class_conflict", "affected_document": "dangerous_goods_declaration"}
check("DG class conflict gets a regulatory question", R.question_for(dg_class) is not None)
dg_result = R.regulatory_context(dg_class, retriever, model=stub)
check("DG class conflict returns a verified answer with sources",
      dg_result["status"] == "supported" and dg_result["sources"] and dg_result["sources"][0]["url"].startswith("http"),
      str(dg_result.get("problems")))

missing_dgd = {"finding_type": "missing_document", "affected_document": "dangerous_goods_declaration"}
check("missing dangerous goods declaration gets a regulatory question", R.question_for(missing_dgd) is not None)

missing_invoice = {"finding_type": "missing_document", "affected_document": "commercial_invoice"}
check("missing commercial invoice is not applicable",
      R.regulatory_context(missing_invoice, retriever, model=stub)["status"] == "not_applicable")

# attach_context keeps the report's own verdicts and adds context only to findings
report = {"validation": {"findings": [weight, dg_class], "status": "findings_present",
                         "regulatory_compliance": "not_assessed"}}
before = copy.deepcopy(report)
attached = R.attach_context(report, retriever, model=stub)
check("attach_context does not change the input report", report == before)
check("attach_context keeps status and regulatory_compliance",
      attached["validation"]["status"] == "findings_present"
      and attached["validation"]["regulatory_compliance"] == "not_assessed")
check("each finding gets regulatory_context",
      all("regulatory_context" in f for f in attached["validation"]["findings"]))
check("finding fields are unchanged",
      {k: v for k, v in attached["validation"]["findings"][1].items() if k != "regulatory_context"} == dg_class)

# a missing DGD whose PDF was uploaded is inconclusive, not a regulatory question
uploaded_report = {
    "extraction": {"upload_inventory": [{"filename": "dangerous_goods_declaration.pdf"}]},
    "validation": {"findings": [dict(missing_dgd)], "regulatory_compliance": "not_assessed"},
}
ctx = R.attach_context(uploaded_report, retriever, model=stub)["validation"]["findings"][0]["regulatory_context"]
check("uploaded but unextracted DGD is inconclusive, not a regulatory question", ctx["status"] == "inconclusive")

# a missing DGD that was not uploaded still gets the regulatory question
not_uploaded_report = {
    "extraction": {"upload_inventory": []},
    "validation": {"findings": [dict(missing_dgd)], "regulatory_compliance": "not_assessed"},
}
ctx = R.attach_context(not_uploaded_report, retriever, model=stub)["validation"]["findings"][0]["regulatory_context"]
check("a DGD that was not uploaded still gets the regulatory question", ctx["status"] != "inconclusive" and ctx["status"] != "not_applicable")

# review warnings from the answer step reach the report (a not_found answer with passages retrieved)
check("regulatory context passes on the review warnings",
      "warnings" in dg_result and isinstance(dg_result["warnings"], list))

# a failed model call is recorded on its finding; the other findings are still attached
def broken(prompt):
    raise RuntimeError("503 UNAVAILABLE (test)")


broken_report = {
    "extraction": {"upload_inventory": []},
    "validation": {"findings": [dict(weight), dict(dg_class)], "regulatory_compliance": "not_assessed"},
}
out = R.attach_context(broken_report, retriever, model=broken)["validation"]["findings"]
check("a failed model call does not stop attach_context", len(out) == 2)
check("the failed finding is recorded as an error", out[1]["regulatory_context"]["status"] == "error")
check("the error names the failure", "503" in out[1]["regulatory_context"]["problems"][0])
check("the other findings are still attached", out[0]["regulatory_context"]["status"] == "not_applicable")

# the planner's question is used when valid; the fixed question is used otherwise
DG_ONLY = {"findings": [dict(dg_class)], "regulatory_compliance": "not_assessed"}
planner_text = "What hazard class must a shipper state for dangerous goods?"
key_dg = P.plan_key(dg_class)
planner_ok = lambda prompt: {"questions": [{"key": key_dg, "question": planner_text}]}  # noqa: E731
used = R.attach_context({"extraction": {"upload_inventory": []}, "validation": dict(DG_ONLY)},
                        retriever, model=stub, documents={"dangerous_goods_declaration": {"dg_class": "CLASS 9"}},
                        planner_model=planner_ok)["validation"]["findings"][0]["regulatory_context"]
check("a valid planned question is used and recorded as the planner's", used["question"] == planner_text and used["question_source"] == "planner")

planner_bad = lambda prompt: {"questions": [{"key": key_dg, "question": "12345 6789"}]}  # noqa: E731
fallback = R.attach_context({"extraction": {"upload_inventory": []}, "validation": dict(DG_ONLY)},
                            retriever, model=stub, planner_model=planner_bad)["validation"]["findings"][0]["regulatory_context"]
check("an invalid planned question falls back to the fixed question",
      fallback["question"] == R.question_for(dg_class) and fallback["question_source"] == "fixed")

planner_fails = lambda prompt: (_ for _ in ()).throw(RuntimeError("503 (test)"))  # noqa: E731
fallback2 = R.attach_context({"extraction": {"upload_inventory": []}, "validation": dict(DG_ONLY)},
                             retriever, model=stub, planner_model=planner_fails)["validation"]["findings"][0]["regulatory_context"]
check("a failed planner call falls back to the fixed question", fallback2["question_source"] == "fixed")

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
