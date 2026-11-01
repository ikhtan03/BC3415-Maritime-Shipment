"""Answer a question from the retrieved passages only, with citations, and check the citations.

Flow:
1. retrieve.py finds the most relevant passages in rag/corpus/.
2. This module sends only those passages to Gemini, with instructions to answer from them and
   to cite passage IDs and quote the exact text it relies on.
3. The reply is checked in code, not trusted: every cited ID must be one of the passages that
   were sent, and every quote must appear word for word in that passage. If a check fails, the
   answer is marked "not_verified" and must not be used.

The model never decides the regulatory outcome of a shipment. It explains what the sources say.

Usage (from the repo root):
    python rag/answer.py "What is the penalty for importing without a permit?"
    python rag/answer.py "..." --dry-run      # print the prompt only, no API call

Needs GEMINI_API_KEY in the environment for a live call. The model name comes from GEMINI_MODEL.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from retrieve import Retriever  # noqa: E402

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
SUPPORTED, NOT_FOUND, NOT_VERIFIED = "supported", "not_found", "not_verified"


def build_prompt(question, passages):
    """Prompt that allows only the given passages as evidence."""
    blocks = []
    for p in passages:
        blocks.append(
            f"[{p['id']}] Source: {p['source_title']} | Section: {p['section']}\n{p['text']}"
        )
    passage_text = "\n\n".join(blocks)
    return f"""You answer questions about Singapore dangerous-goods and import requirements.

Use ONLY the passages below. Do not use outside knowledge. Do not decide whether any shipment
is compliant or safe; explain what the passages say.

Question: {question}

Passages:
{passage_text}

Return one JSON object with exactly these keys:
- "answer": a short answer in plain English. If the passages do not answer the question, say so.
- "status": "supported" if the passages answer the question, otherwise "not_found".
- "citations": the list of passage IDs (in square brackets above) that you relied on.
- "quotes": a list of objects with "id" and "quote". Each quote must be copied exactly, word for
  word, from the passage with that id. Keep quotes short (one sentence or part of one).

Return valid JSON only.
"""


def normalise(text):
    """Collapse whitespace and unify quote marks so a quote matches the source text."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def validate_answer(reply, passages):
    """Check the model's reply against the passages it was given. Returns the reply with a verdict."""
    by_id = {p["id"]: p for p in passages}
    problems = []

    if not isinstance(reply, dict):
        return {"status": NOT_VERIFIED, "problems": ["reply is not a JSON object"]}

    citations = reply.get("citations") or []
    for cid in citations:
        if cid not in by_id:
            problems.append(f"citation {cid} was not one of the passages given")

    for item in reply.get("quotes") or []:
        cid, quote = item.get("id"), item.get("quote", "")
        if cid not in by_id:
            problems.append(f"quote refers to {cid}, which was not given")
            continue
        if not quote or normalise(quote) not in normalise(by_id[cid]["text"]):
            problems.append(f"quote from {cid} does not appear in that passage: {quote[:60]!r}")

    if reply.get("status") == SUPPORTED and not citations:
        problems.append("status is supported but no citation was given")

    verdict = NOT_VERIFIED if problems else reply.get("status", NOT_VERIFIED)
    return {**reply, "status": verdict, "problems": problems}


def call_gemini(prompt):
    """Send the prompt to Gemini and return the parsed JSON reply."""
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Set it, or use --dry-run.")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty reply.")
    return json.loads(response.text)


def answer(question, retriever, k=3, model=None):
    """Retrieve, ask, and validate. `model` is a function(prompt) -> reply, used by tests."""
    passages = retriever.search(question, k=k, balanced=True)
    if not passages:
        return {"status": NOT_FOUND, "answer": "No passage in the corpus matches this question.",
                "citations": [], "quotes": [], "problems": [], "passages": []}
    prompt = build_prompt(question, passages)
    reply = (model or call_gemini)(prompt)
    result = validate_answer(reply, passages)
    result["passages"] = [p["id"] for p in passages]
    return result


def main():
    parser = argparse.ArgumentParser(description="Answer a question from the Singapore DG corpus.")
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", help="print the prompt without calling Gemini")
    args = parser.parse_args()

    retriever = Retriever.from_corpus()
    if args.dry_run:
        passages = retriever.search(args.question, k=args.k, balanced=True)
        print(build_prompt(args.question, passages))
        return
    result = answer(args.question, retriever, k=args.k)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
