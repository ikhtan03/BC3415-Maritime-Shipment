"""Fresh retrieval test for the import wording, on items not used in v3 or v4.

Written before any change to retrieval, so it can measure a fix fairly. Same wording as the
shisha question ("Is X allowed to be imported into Singapore?"). A question is a top-1 hit if the
first result contains the phrase, and a top-3 hit if any of the first three does.

Run from the repo root:
    python rag/tests/test_retrieve_v5.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("Is smokeless cigarillos allowed to be imported into Singapore?", "Smokeless cigars"),
    ("Is electronic cigarette hardware allowed to be imported into Singapore?", "Imitation tobacco products"),
    ("Is an obscene video tape allowed to be imported into Singapore?", "Obscene articles"),
    ("Is seditious material allowed to be imported into Singapore?", "Seditious"),
    ("Are radio jamming devices allowed to be imported into Singapore?", "jamming devices"),
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
