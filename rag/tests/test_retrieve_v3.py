"""Fresh retrieval test for list items in the customs prohibited-goods passages.

Written before any run, after the shisha retrieval miss. Each question names a phrase that must
appear in a passage the search returns. A question counts as a top-1 hit if the first result
contains the phrase, and a top-3 hit if any of the first three does. Questions are not about
shisha itself, which has been seen. Do not change a question or its phrase after a run.

Run from the repo root:
    python rag/tests/test_retrieve_v3.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("Do you know if nasal snuff is banned for travellers?", "Nasal snuff"),
    ("Can I carry dissolvable tobacco pouches into Singapore?", "Dissolvable tobacco"),
    ("Are smokeless cigarillos prohibited?", "Smokeless cigars"),
    ("Is it against the rules to bring obscene video tapes into Singapore?", "Obscene articles"),
    ("Are radio jamming devices prohibited goods?", "jamming devices"),
    ("Is electronic cigarette hardware prohibited?", "Imitation tobacco products"),
    ("What about seditious materials?", "Seditious"),
    ("Are nicotine products meant for injection allowed?", "injected"),
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
