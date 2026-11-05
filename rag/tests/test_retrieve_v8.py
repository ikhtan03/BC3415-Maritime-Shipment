"""Fresh retrieval test for the UNECE form's page 201 (the shipper's declaration page).

Written before any change that adds page titles to the UNECE passages. Each question names a
phrase that a correct result must contain; the phrases appear in the page's text, not only in its
heading. A question is a top-1 hit if the first result contains the phrase, and a top-3 hit if any of
the first three does. Do not change a question or its phrase after a run.

Run from the repo root:
    python rag/tests/test_retrieve_v8.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("Who makes the statement that the consignment is properly classified and labelled?", "I hereby declare"),
    ("Does the shipper confirm that the cargo is in proper condition for transport?", "proper condition for transport"),
    ("Which box on the form is for additional handling information?", "Additional handling information"),
    ("Where is the vessel or flight number recorded on the form?", "Vessel / flight no."),
    ("What must the consignment be within when the form says it is limited?", "limitations prescribed for"),
]


def main():
    retriever = Retriever.from_corpus()
    top1 = top3 = 0
    for question, phrase in CASES:
        hits = retriever.search(question, k=3, balanced=True)
        in_first = phrase.lower() in hits[0]["text"].lower() if hits else False
        in_top3 = any(phrase.lower() in h["text"].lower() for h in hits)
        top1 += in_first
        top3 += in_top3
        ids = ", ".join(h["id"] for h in hits)
        print(f"top1 {'PASS' if in_first else 'FAIL'} | top3 {'PASS' if in_top3 else 'FAIL'}  {question}  [{ids}]")
    print(f"\nright passage first: {top1} of {len(CASES)}")
    print(f"right passage in top 3: {top3} of {len(CASES)}")


if __name__ == "__main__":
    main()
