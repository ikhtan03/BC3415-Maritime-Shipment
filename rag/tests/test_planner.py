"""Checks for the AI planner. No network or API key: the model is a stub.

Run from the repo root:
    python rag/tests/test_planner.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planner as P  # noqa: E402

FAILS = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILS.append(name)


DG = {"finding_type": "dg_class_conflict", "affected_document": "dangerous_goods_declaration",
      "explanation": "dg_class differs between bill_of_lading (3) and dangerous_goods_declaration (CLASS 9)."}
DGD_MISSING = {"finding_type": "missing_document", "affected_document": "dangerous_goods_declaration",
               "explanation": "dangerous_goods_declaration is missing."}
KEY_DG = P.plan_key(DG)

good = {"questions": [{"key": KEY_DG, "question": "What hazard class must a shipper state for dangerous goods?"}]}
check("a valid planned question is used", P.plan_questions([DG], {}, model=lambda p: good) == {KEY_DG: good["questions"][0]["question"]})

check("a question for a key that was not asked is dropped",
      P.parse_plan({"questions": [{"key": "other:key", "question": "What must a shipper state about class?"}]}, {KEY_DG}) == {})
check("an empty question is dropped", P.parse_plan({"questions": [{"key": KEY_DG, "question": "  "}]}, {KEY_DG}) == {})
check("a very long question is dropped", P.parse_plan({"questions": [{"key": KEY_DG, "question": "x" * 300}]}, {KEY_DG}) == {})
check("two questions in one are dropped",
      P.parse_plan({"questions": [{"key": KEY_DG, "question": "What class? And what packing group?"}]}, {KEY_DG}) == {})
check("a reply that is not a JSON object gives nothing", P.parse_plan("not json", {KEY_DG}) == {})
check("a question without words gives nothing", P.parse_plan({"questions": [{"key": KEY_DG, "question": "12345 6789 0000 0000"}]}, {KEY_DG}) == {})

def broken(prompt):
    raise RuntimeError("503 UNAVAILABLE (test)")

check("a failed planner call gives no questions (the fixed question is used)", P.plan_questions([DG], {}, model=broken) == {})
check("no findings means no planner call", P.plan_questions([], {}, model=broken) == {})

facts = P.shipment_facts({"bill_of_lading": {"dg_class": "3", "un_number": "UN1942"}, "packing_list": {"container_id": "X1"}})
check("only known fields are passed to the planner", set(facts) == {"dg_class", "un_number", "container_id"})
prompt = P.build_prompt([DG, DGD_MISSING], facts)
check("the prompt lists each finding key and the facts", KEY_DG in prompt and "un_number" in prompt)
check("the prompt asks for questions, not answers", "Do not answer" in prompt)

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
