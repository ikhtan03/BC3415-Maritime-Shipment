"""Check the triage rules against the six answer keys. No network or API key.

Run from the project root:
    python Backend/test_triage.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import triage as T  # noqa: E402
import validator as V  # noqa: E402

FAILS = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILS.append(name)


for folder in sorted((ROOT / "data" / "test_cases").iterdir()):
    if not folder.is_dir():
        continue
    truth = json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))
    key = json.loads((folder / "answer_key.json").read_text(encoding="utf-8"))
    got = T.triage(V.validate(truth["document_truth"]))
    want = key["triage_expectations"]
    ok = (got["suggested_priority"] == want["suggested_priority"]
          and got["human_review_recommended"] == want["human_review_recommended"])
    check(f"{folder.name}: priority {got['suggested_priority']}, review {got['human_review_recommended']}", ok)

# an upload that could not be extracted needs review, even when nothing else was found
inconclusive = {"findings": [{"finding_type": "extraction_failed", "affected_document": "packing_list"}]}
check("an extraction failure is medium priority and needs review",
      T.triage(inconclusive)["suggested_priority"] == "medium" and T.triage(inconclusive)["human_review_recommended"])

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
