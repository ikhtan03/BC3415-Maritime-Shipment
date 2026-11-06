"""Fresh retrieval test for the hazard class rule in the UNECE shipper's declaration (pages 201-202).

Written before any change to the regulatory adapter's question. Used to choose the question's
wording. v10 is kept apart and used only to confirm the choice. Do not change a question or its
phrase after a run.

Run from the repo root:
    python rag/tests/test_retrieve_v9.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("Is the hazard class something I have to put on the shipper's declaration?", "hazard class"),
    ("What class of danger must be written for dangerous goods on the consignment form?", "hazard class"),
    ("Does the declaration require the dangerous goods class to be recorded?", "hazard class"),
    ("Which classification details does the shipper have to enter for dangerous cargo?", "hazard class"),
    ("Must the class number appear in the shipper's statement for dangerous goods?", "hazard class"),
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
