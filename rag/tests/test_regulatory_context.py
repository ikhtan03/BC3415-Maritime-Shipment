"""Checks for the regulatory-context adapter. No network or API key: the model is a stub.

Run from the repo root:
    python rag/tests/test_regulatory_context.py
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import regulatory_context as R  # noqa: E402
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

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
