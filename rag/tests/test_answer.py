"""Checks for the answer step. No API key and no network are needed: the model is replaced by a stub.

Run from the repo root:
    python rag/tests/test_answer.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import answer as A  # noqa: E402
from retrieve import Retriever  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


PASSAGES = [
    {"id": "p1", "source_title": "T", "section": "S", "text": "A Certificate of Analysis (COA) is required for ammonium nitrate."},
    {"id": "p2", "source_title": "T", "section": "S", "text": "Packing lists must give the net mass of each package."},
]

# validation: good reply
good = {"answer": "A certificate of analysis is needed.", "status": "supported", "citations": ["p1"],
        "quotes": [{"id": "p1", "quote": "A Certificate of Analysis (COA) is required for ammonium nitrate."}]}
v = A.validate_answer(good, PASSAGES)
check("a correct reply is accepted", v["status"] == "supported" and not v["problems"], str(v["problems"]))

# quote with curly apostrophe and different spacing still matches
curly = {"status": "supported", "citations": ["p2"],
         "quotes": [{"id": "p2", "quote": "packing lists must give the net  mass of each package."}]}
check("quote matching ignores spacing and case", A.validate_answer(curly, PASSAGES)["status"] == "supported")

# a quote that is not in the passage
fake_quote = {"status": "supported", "citations": ["p1"],
              "quotes": [{"id": "p1", "quote": "Hazardous goods need a helmet."}]}
v = A.validate_answer(fake_quote, PASSAGES)
check("an invented quote is rejected", v["status"] == A.NOT_VERIFIED and any("does not appear" in p for p in v["problems"]))

# a citation that was not given
bad_cite = {"status": "supported", "citations": ["p9"], "quotes": []}
v = A.validate_answer(bad_cite, PASSAGES)
check("a citation outside the given passages is rejected", v["status"] == A.NOT_VERIFIED)

# supported with no citation
no_cite = {"status": "supported", "citations": [], "quotes": []}
check("supported without a citation is rejected", A.validate_answer(no_cite, PASSAGES)["status"] == A.NOT_VERIFIED)

# not-found is allowed with no citations
nf = {"status": "not_found", "citations": [], "quotes": []}
check("not_found with no citations is accepted", A.validate_answer(nf, PASSAGES)["status"] == A.NOT_FOUND)

# prompt contains every passage id and the no-outside-knowledge instruction
prompt = A.build_prompt("q?", PASSAGES)
check("prompt includes each passage id and text", "[p1]" in prompt and "[p2]" in prompt and "net mass" in prompt)
check("prompt forbids outside knowledge and compliance judgements",
      "Do not use outside knowledge" in prompt and "Do not decide whether any shipment" in prompt)

# end to end with a stub model on the real corpus
retriever = Retriever.from_corpus()
seen = {}


def stub(prompt):
    seen["prompt"] = prompt
    # cite the first passage that appears in the prompt, quoting its first sentence exactly
    first_id = prompt.split("[", 1)[1].split("]", 1)[0]
    first_text = prompt.split(f"[{first_id}] ", 1)[1].split("\n", 1)[1]
    sentence = first_text.split(". ")[0][:80]
    return {"answer": "stub", "status": "supported", "citations": [first_id],
            "quotes": [{"id": first_id, "quote": sentence}]}


result = A.answer("What is the penalty for importing without a permit?", retriever, model=stub)
check("end to end: stub reply is verified against the real corpus", result["status"] == A.SUPPORTED, str(result.get("problems")))
check("end to end: the prompt was built from retrieved passages", "[" in seen.get("prompt", ""))

empty = A.answer("zzqxv wrvk", retriever, model=stub)
check("nothing relevant gives not_found without calling the model", empty["status"] == A.NOT_FOUND)

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
