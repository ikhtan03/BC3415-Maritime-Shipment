"""Second fresh retrieval test for the shipper's declaration rule (UNECE form, pages 201-202).

Written before the glossary change that follows the v6 misses, so the change can be measured on
questions it has not seen. Phrasing is different from v6. Do not change a question or its phrase
after a run.

Run from the repo root:
    python rag/tests/test_retrieve_v7.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("What must be written for dangerous goods on a shipper's declaration form?", "proper shipping name"),
    ("Does a dangerous goods declaration need the hazard class?", "hazard class"),
    ("Is a UN number needed when I declare dangerous goods to the carrier?", "UN No."),
    ("Should the packing group be stated for dangerous cargo?", "packing group"),
    ("What do I have to fill in for dangerous goods on the declaration?", "hazard class"),
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
