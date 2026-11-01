"""Paraphrase test: plain-language questions that do not reuse the source wording.

Run from the repo root:
    python rag/tests/test_retrieve_paraphrase.py

These are harder than test_retrieve.py, because the questions use everyday words instead of the
exact phrases in the sources. The result is written to rag/tests/paraphrase_results.csv so the
team can compare runs after each change.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "paraphrase_results.csv"

CASES = [
    ("How far ahead do I have to tell the port about dangerous cargo on a ship coming in?",
     "mpa_declaring_dangerous_goods"),
    ("Do I need a lab report for fertiliser that contains ammonium nitrate?",
     "mpa_declaring_dangerous_goods"),
    ("Do I need permission from the NEA to move radioactive cargo through Singapore?",
     "mpa_declaring_dangerous_goods"),
    ("Can I bring e-cigarettes or vapes into Singapore?",
     "customs_controlled_prohibited_imports"),
    ("What goods am I not allowed to import into Singapore at all?",
     "customs_controlled_prohibited_imports"),
    ("Can I import a controlled drug such as morphine?",
     "customs_controlled_prohibited_imports"),
    ("Who counts as the importer when the seller is overseas?",
     "customs_import_procedures_overview"),
    ("What happens if I lie about the value on my import declaration?",
     "customs_import_procedures_overview"),
    ("Which box on the form is for the name of the person shipping the goods?",
     "mmdg_form_p201_onward"),
    ("What is the reference number of the transport document called?",
     "mmdg_form_p201_onward"),
    ("Which parts of the form does the carrier fill in?",
     "mmdg_form_p201_onward"),
    ("Where on the form do I write the weight of the packages?",
     "mmdg_form_p201_onward"),
]


def main():
    retriever = Retriever.from_corpus()
    rows, passed_balanced, passed_plain = [], 0, 0
    for question, expected in CASES:
        balanced_hits = retriever.search(question, k=3, balanced=True)
        plain_hits = retriever.search(question, k=3, balanced=False)
        balanced_sources = [h["source_id"] for h in balanced_hits]
        plain_sources = [h["source_id"] for h in plain_hits]
        ok_balanced = expected in balanced_sources
        ok_plain = expected in plain_sources
        passed_balanced += ok_balanced
        passed_plain += ok_plain
        rows.append({
            "question": question,
            "expected_source": expected,
            "plain_top3": " | ".join(plain_sources),
            "plain_result": "PASS" if ok_plain else "FAIL",
            "balanced_top3": " | ".join(balanced_sources),
            "balanced_result": "PASS" if ok_balanced else "FAIL",
        })
        print(f"plain {'PASS' if ok_plain else 'FAIL'}  balanced {'PASS' if ok_balanced else 'FAIL'}  {question}")
        if not ok_plain:
            print(f"      plain top 3: {plain_sources or 'nothing'}")

    with RESULTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    total = len(CASES)
    print(f"\nplain score ranking:   {passed_plain} of {total} found the right source in the top 3")
    print(f"balanced ranking:      {passed_balanced} of {total} found the right source in the top 3")
    print(f"results saved to {RESULTS}")


if __name__ == "__main__":
    main()
