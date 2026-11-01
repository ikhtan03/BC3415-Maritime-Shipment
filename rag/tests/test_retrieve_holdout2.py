"""Second held-out test set. Written AFTER the search fix in retrieve.py was made, but BEFORE the
retriever was run on these questions. None of these questions were used to choose the fix.

Rules for this file (same as test_retrieve_holdout.py):
- Do not change a question or its expected source after seeing a result.
- Do not add glossary entries or other changes to make these pass. Report what happens.

Run from the repo root:
    python rag/tests/test_retrieve_holdout2.py

The result is written to rag/tests/holdout2_results.csv.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "holdout2_results.csv"

CASES = [
    ("How long do I have to keep my trade documents after an import?",
     "customs_import_procedures_overview"),
    ("If the shipper pays for insurance, must I add it to the value I declare?",
     "customs_import_procedures_overview"),
    ("I want to send a sample product free of charge. Can I declare a very low value for it?",
     "customs_import_procedures_overview"),
    ("Can I use a pro forma invoice to apply for my import permit?",
     "customs_import_procedures_overview"),
    ("Is a company named as the consignee the importer, even when the seller is overseas?",
     "customs_import_procedures_overview"),
    ("What is the fine for tampering with a customs seal on a container?",
     "customs_import_procedures_overview"),
    ("What is the maximum fine for importing without a permit on a second offence?",
     "customs_import_procedures_overview"),
    ("Can I bring gutkha into Singapore?",
     "customs_controlled_prohibited_imports"),
    ("Are products made from endangered animals banned from import?",
     "customs_controlled_prohibited_imports"),
    ("Does moving nuclear cargo through Singapore need a licence, and where do I apply?",
     "mpa_declaring_dangerous_goods"),
    ("How much notice does the port need before a ship carrying liquefied gases in bulk arrives?",
     "mpa_declaring_dangerous_goods"),
    ("What is the phone number for the MPA hazmat team?",
     "mpa_declaring_dangerous_goods"),
    ("What is the weight limit for First Schedule dangerous goods that can stay on board at Jurong Port?",
     "mpa_declaring_dangerous_goods"),
    ("I am not sure whether my cargo counts as dangerous. Who should I ask first?",
     "mpa_declaring_dangerous_goods"),
    ("On the dangerous goods form, where does the consignee's name go?",
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
