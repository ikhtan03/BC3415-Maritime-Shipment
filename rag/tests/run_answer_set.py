"""Run the fixed answer set once against the live model and record the results.

Run from the repo root (needs GEMINI_API_KEY):
    python rag/tests/run_answer_set.py

For each question it records:
- whether the reply passed the citation and quote checks (not_verified otherwise)
- whether the reply's status is right (supported, or not_found for the negative control)
- whether the cited passages come from the expected source
- whether the expected facts appear in the answer text

Results are written to rag/tests/answer_results.csv. Do not edit answer_set.json after a run.
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import answer as A  # noqa: E402
from retrieve import Retriever  # noqa: E402

SET = HERE / "answer_set.json"
RESULTS = HERE / "answer_results.csv"


def main():
    cases = json.loads(SET.read_text(encoding="utf-8"))["cases"]
    retriever = Retriever.from_corpus()
    rows = []
    for case in cases:
        result = A.answer(case["question"], retriever, k=3)
        status = result.get("status")
        answer_text = result.get("answer", "")
        cited = result.get("citations", [])
        cited_sources = {cid.split("#")[0] for cid in cited}

        if case.get("should_be_not_found"):
            status_ok = status == A.NOT_FOUND
            source_ok = None
        else:
            status_ok = status == A.SUPPORTED
            source_ok = case["expected_source"] in cited_sources

        facts_missing = [f for f in case.get("must_mention", []) if f.lower() not in answer_text.lower()]
        row = {
            "question": case["question"],
            "status": status,
            "status_ok": "PASS" if status_ok else "FAIL",
            "cited_ids": " | ".join(cited),
            "source_ok": "" if source_ok is None else ("PASS" if source_ok else "FAIL"),
            "facts_missing": " | ".join(facts_missing),
            "verification_problems": " | ".join(result.get("problems", [])),
            "answer": answer_text,
        }
        rows.append(row)
        print(f"status {row['status_ok']}  source {row['source_ok'] or '-'}  facts missing: {len(facts_missing)}  [{status}]  {case['question']}")

    with RESULTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    n = len(rows)
    print(f"\nstatus correct:         {sum(r['status_ok'] == 'PASS' for r in rows)} of {n}")
    print(f"right source cited:     {sum(r['source_ok'] == 'PASS' for r in rows)} of {sum(r['source_ok'] != '' for r in rows)}")
    print(f"verification failures:  {sum(r['status'] == A.NOT_VERIFIED for r in rows)} of {n}")
    print(f"results saved to {RESULTS}")


if __name__ == "__main__":
    main()
