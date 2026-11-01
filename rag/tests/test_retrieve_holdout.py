"""Held-out paraphrase test. These 15 questions were written BEFORE the retriever was run on them.

Rules for this file:
- Do not change a question or its expected source after seeing a result. If a question is wrong,
  say so in a note and keep the original in the history.
- Do not add glossary entries to make these pass. That would make the test unfair.

Run from the repo root:
    python rag/tests/test_retrieve_holdout.py

The result is written to rag/tests/holdout_results.csv.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "holdout_results.csv"

CASES = [
    ("I'm handling a ship carrying explosives into Singapore. How early do I have to file the paperwork?",
     "mpa_declaring_dangerous_goods"),
    ("My cargo is bulk chemicals. Does the port need to be told before the ship arrives?",
     "mpa_declaring_dangerous_goods"),
    ("Who do I call at the MPA about dangerous goods questions?",
     "mpa_declaring_dangerous_goods"),
    ("Can I import a product that contains tobacco from overseas?",
     "customs_controlled_prohibited_imports"),
    ("Are radio jamming devices allowed into Singapore?",
     "customs_controlled_prohibited_imports"),
    ("Which schedule lists the controlled drugs that cannot be imported?",
     "customs_controlled_prohibited_imports"),
    ("Do I need a permit before goods come into Singapore?",
     "customs_import_procedures_overview"),
    ("What is the penalty for bringing goods in without a permit?",
     "customs_import_procedures_overview"),
    ("I used my import permit already and now need to change it. Can I amend it?",
     "customs_import_procedures_overview"),
    ("The importer's name on the permit is wrong. What should be done?",
     "customs_import_procedures_overview"),
    ("On the shipper's section of the form, what do I confirm about the packaging and labels?",
     "mmdg_form_p201_onward"),
    ("Where on the form does the carrier record the vessel and voyage?",
     "mmdg_form_p201_onward"),
    ("Where do the gross and net weights go on the dangerous goods form?",
     "mmdg_form_p201_onward"),
    ("Which authority gives the licence for moving nuclear material through Singapore?",
     "mpa_declaring_dangerous_goods"),
    ("Where on the dangerous goods declaration do I write the UN number and the proper shipping name?",
     "mmdg_form_p201_onward"),
]


def main():
    retriever = Retriever.from_corpus()
    rows, top1_plain, top1_balanced, top3_balanced = [], 0, 0, 0
    for question, expected in CASES:
        plain = retriever.search(question, k=3, balanced=False)
        balanced = retriever.search(question, k=3, balanced=True)
        plain_sources = [h["source_id"] for h in plain]
        balanced_sources = [h["source_id"] for h in balanced]
        ok_top1_plain = bool(plain_sources) and plain_sources[0] == expected
        ok_top1_balanced = bool(balanced_sources) and balanced_sources[0] == expected
        ok_top3_balanced = expected in balanced_sources
        top1_plain += ok_top1_plain
        top1_balanced += ok_top1_balanced
        top3_balanced += ok_top3_balanced
        rows.append({
            "question": question,
            "expected_source": expected,
            "plain_top3": " | ".join(plain_sources),
            "balanced_top3": " | ".join(balanced_sources),
            "top1_plain": "PASS" if ok_top1_plain else "FAIL",
            "top1_balanced": "PASS" if ok_top1_balanced else "FAIL",
            "top3_balanced": "PASS" if ok_top3_balanced else "FAIL",
        })
        print(f"top1 plain {'PASS' if ok_top1_plain else 'FAIL'} | top1 balanced {'PASS' if ok_top1_balanced else 'FAIL'} | top3 balanced {'PASS' if ok_top3_balanced else 'FAIL'}  {question}")

    with RESULTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    total = len(CASES)
    print(f"\nright source ranked first, plain:    {top1_plain} of {total}")
    print(f"right source ranked first, balanced: {top1_balanced} of {total}")
    print(f"right source in top 3, balanced:     {top3_balanced} of {total}")
    print(f"results saved to {RESULTS}")


if __name__ == "__main__":
    main()
