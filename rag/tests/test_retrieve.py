"""Checks that the retriever finds the right source for known questions.

Run from the repo root:
    python rag/tests/test_retrieve.py

Each question names the source that must appear in the top 3 results. The questions are
written from the sources themselves, so a failure means retrieval missed text that is in the corpus.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieve import Retriever  # noqa: E402

CASES = [
    ("When must a dangerous goods declaration be submitted before a vessel arrives?",
     "mpa_declaring_dangerous_goods"),
    ("ammonium nitrate certificate of analysis combustible matter",
     "mpa_declaring_dangerous_goods"),
    ("radioactive material transhipment approval National Environment Agency",
     "mpa_declaring_dangerous_goods"),
    ("is chewing gum prohibited from import into Singapore",
     "customs_controlled_prohibited_imports"),
    ("tobacco and nicotine products cannot be imported",
     "customs_controlled_prohibited_imports"),
    ("importers must obtain the customs permit before the goods are imported",
     "customs_import_procedures_overview"),
    ("penalties for failing to declare goods to Customs",
     "customs_import_procedures_overview"),
    ("shipper's declaration proper shipping name classified packaged marked and labelled",
     "mmdg_form_p201_onward"),
    ("transport document number freight forwarder reference consignee carrier",
     "mmdg_form_p201_onward"),
    ("gross mass net mass cube shipping marks number and kind of packages",
     "mmdg_form_p201_onward"),
]


def main():
    retriever = Retriever.from_corpus()
    failures = 0
    for question, expected in CASES:
        hits = retriever.search(question, k=3)
        sources = [h["source_id"] for h in hits]
        passed = expected in sources
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'}  {question}")
        if not passed:
            print(f"      expected {expected}, got {sources or 'nothing'}")
    print(f"\n{len(CASES) - failures} of {len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
