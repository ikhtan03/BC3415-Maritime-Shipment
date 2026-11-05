"""Fresh retrieval test for the shipper's declaration rule on dangerous goods (the UNECE form,
pages 201 and 202): a shipper must specify the UN number, proper shipping name, hazard class and
packing group. Written before any change, after the DG class question ranked this passage out
of the top 3. A question is a top-1 hit if the first result contains the phrase, and a top-3 hit
if any of the first three does. Do not change a question or its phrase after a run.

Run from the repo root:
    python rag/tests/test_retrieve_v6.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("Which details must a shipper give for dangerous goods on the shipper's declaration?", "proper shipping name"),
    ("What hazard information has to be filled in for dangerous goods on the declaration form?", "hazard class"),
    ("Do I need to give the UN number when declaring dangerous goods?", "UN No."),
    ("Is the packing group required on a dangerous goods declaration?", "packing group"),
    ("What does the shipper have to specify about a dangerous good's class?", "hazard class"),
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
