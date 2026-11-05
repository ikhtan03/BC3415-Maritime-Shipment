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

# check 2a: a figure in the answer that no quote or cited passage contains is rejected
PASSAGES_FIG = [
    {"id": "f1", "source_title": "T", "section": "S",
     "text": "The declaration shall be submitted not less than 12 hours before arrival."},
]
figure_not_in_source = {"answer": "It must be submitted 48 hours before arrival.", "status": "supported",
                        "citations": ["f1"], "quotes": [{"id": "f1", "quote": "not less than 12 hours before arrival"}]}
v = A.validate_answer(figure_not_in_source, PASSAGES_FIG)
check("a figure the sources do not contain is flagged (check 2a)", v["status"] == A.NOT_VERIFIED and any("48" in p for p in v["problems"]))

figure_in_source = {"answer": "It must be submitted 12 hours before arrival.", "status": "supported",
                    "citations": ["f1"], "quotes": [{"id": "f1", "quote": "not less than 12 hours before arrival"}]}
check("a figure that matches the source is accepted", A.validate_answer(figure_in_source, PASSAGES_FIG)["status"] == A.SUPPORTED)

# a money figure followed by a comma is the same figure as the source (fix: trailing comma)
PASSAGES_MONEY = [
    {"id": "m1", "source_title": "T", "section": "S",
     "text": "Making a false declaration: fine up to S$10,000 or imprisonment up to 2 years, or both."},
]
money_comma = {"answer": "The fine is up to S$10,000, or imprisonment up to 2 years.", "status": "supported",
               "citations": ["m1"], "quotes": [{"id": "m1", "quote": "fine up to S$10,000 or imprisonment up to 2 years"}]}
v = A.validate_answer(money_comma, PASSAGES_MONEY)
check("a money figure followed by a comma matches the source", v["status"] == A.SUPPORTED, str(v["problems"]))

# citation IDs written in square brackets name the same passage (fix: bracketed citations)
bracketed = {"answer": "Use the email address.", "status": "supported",
             "citations": ["[p1]"], "quotes": [{"id": "[p1]", "quote": "A Certificate of Analysis (COA) is required for ammonium nitrate."}]}
v = A.validate_answer(bracketed, PASSAGES)
check("bracketed citation IDs are accepted", v["status"] == A.SUPPORTED, str(v["problems"]))
check("bracketed citation IDs are cleaned in the result", v["citations"] == ["p1"] and v["quotes"][0]["id"] == "p1")

# check 2b: says a detail is missing, but the cited passage has a timed figure -> contradiction flagged
contradiction = {"answer": "The passages do not specify a timeframe.", "status": "supported",
                 "citations": ["f1"], "quotes": [{"id": "f1", "quote": "12 hours before arrival"}]}
v = A.validate_answer(contradiction, PASSAGES_FIG)
check("an answer that denies a timeframe the source gives is flagged (check 2b)", v["status"] == A.NOT_VERIFIED)

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

# warning: a quoted rule has a figure that the answer leaves out (does not change the verdict)
PASSAGES_OMIT = [
    {"id": "o1", "source_title": "T", "section": "S",
     "text": "Fine up to S$10,000 or imprisonment up to 12 months, or both."},
]
omits = {"answer": "The fine is up to S$10,000.", "status": "supported", "citations": ["o1"],
         "quotes": [{"id": "o1", "quote": "Fine up to S$10,000 or imprisonment up to 12 months, or both."}]}
v = A.validate_answer(omits, PASSAGES_OMIT)
check("an omitted figure in the quoted rule gives a warning", any("12 months" in w for w in v["warnings"]), str(v["warnings"]))
check("an omitted figure does not change the verdict", v["status"] == A.SUPPORTED, str(v["problems"]))

full = {"answer": "The fine is up to S$10,000, or imprisonment up to 12 months.", "status": "supported",
        "citations": ["o1"],
        "quotes": [{"id": "o1", "quote": "Fine up to S$10,000 or imprisonment up to 12 months, or both."}]}
check("a complete answer gives no omission warning", A.validate_answer(full, PASSAGES_OMIT)["warnings"] == [])

# a "not found" answer with passages retrieved gets a review warning (verdict unchanged)
nf_with_passages = {"answer": "The passages do not say.", "status": "not_found", "citations": [], "quotes": []}
v = A.validate_answer(nf_with_passages, PASSAGES)
check("not_found with passages retrieved gets a review warning",
      v["status"] == A.NOT_FOUND and any("check whether they answer" in w for w in v["warnings"]))
v = A.validate_answer(nf, [])
check("not_found with no passages gets no review warning", v["warnings"] == [])

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
