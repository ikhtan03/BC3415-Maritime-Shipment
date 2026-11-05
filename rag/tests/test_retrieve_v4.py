"""Fresh retrieval test using the same wording as the shisha question, on other items from the
same prohibited-goods list. The shisha question wording was "Is X allowed to be imported into
Singapore?", which missed the list passage. These questions test whether that wording misses
the list passage in general or only for shisha.

Written before any run. Do not change a question or its phrase after a run.

Run from the repo root:
    python rag/tests/test_retrieve_v4.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("Is nasal snuff allowed to be imported into Singapore?", "Nasal snuff"),
    ("Is oral snuff allowed to be imported into Singapore?", "Oral snuff"),
    ("Is chewing tobacco allowed to be imported into Singapore?", "Chewing tobacco"),
    ("Is dissolvable tobacco allowed to be imported into Singapore?", "Dissolvable tobacco"),
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
