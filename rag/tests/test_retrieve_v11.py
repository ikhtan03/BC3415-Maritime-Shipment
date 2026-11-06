"""Fresh retrieval test for the shipper's declaration rules (UNECE form, pages 201-202).

Written before any change to retrieval, so a later fix can be measured on questions it has not
seen. Wording is different from v6 to v10. A question is a top-1 hit if the first result contains
the phrase, and a top-3 hit if any of the first three does. Do not change a question or its phrase
after a run.

Run from the repo root:
    python rag/tests/test_retrieve_v11.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("Which dangerous goods particulars go into the consignor's statement?", "proper shipping name"),
    ("Is there a box for a UN identification number for hazardous cargo?", "UN No."),
    ("Does a packing group need to be recorded for hazardous cargo on the form?", "packing group"),
    ("What hazard identification goes in the dangerous goods lines of the form?", "hazard class"),
    ("Does the statement have to confirm that the goods are properly labelled?", "labelled"),
    ("What condition must the goods be in when the consignor signs the form?", "proper condition for transport"),
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
