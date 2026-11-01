"""TF-IDF retriever over the Singapore dangerous-goods and import corpus in rag/corpus/.

It finds the passages most relevant to a question and returns them with their source, URL
and section, so any answer built on them can cite where it came from.

No language model is used here. Retrieval is a plain TF-IDF search, which keeps the step
explainable and easy to test. Gemini only sees the passages this module returns.

Usage (from the repo root):
    python rag/retrieve.py "what does a dangerous goods declaration need to include" -k 3
"""
import argparse
import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
MAX_CHARS = 900          # passages are kept short so a match points to a specific rule
HEADER_PREFIXES = ("Source:", "Authority:", "URL:", "Retrieved:")
# Short lines that start a separate rule in the MPA and UNECE text. Each one starts a new passage,
# so a rule is scored on its own words rather than mixed with the timelines or contacts above it.
SUBHEADING_PREFIXES = ("For ", "Radioactive Material", "Nuclear Material", "Declaring Bulk", "Additional Information")
GLOSSARY = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))


def expand_query(query):
    """Add the regulatory terms for any plain-language words in the question (see glossary.json)."""
    lowered = query.lower()
    extra = []
    for plain, entry in GLOSSARY.items():
        if plain.startswith("_") or not isinstance(entry, dict):
            continue
        if plain in lowered:
            extra.extend(entry["expands_to"])
    return query if not extra else f"{query} {' '.join(extra)}"


def split_source(source_id, meta, text):
    """Split one source into passages. Headings and PDF page labels start a new passage."""
    passages = []
    heading, buffer, size, count = "", [], 0, 0

    def flush():
        nonlocal buffer, size, count
        body = "\n".join(buffer).strip()
        if body:
            count += 1
            passages.append({
                "id": f"{source_id}#{count}",
                "source_id": source_id,
                "source_title": meta["title"],
                "url": meta["url"],
                "section": heading or "(no heading)",
                "text": body,
            })
        buffer, size = [], 0

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(HEADER_PREFIXES):
            continue
        if line.startswith("[PDF page"):
            flush()
            heading = line.strip("[]")
            continue
        if line.startswith("#"):
            flush()
            heading = line.lstrip("# ").strip()
            continue
        if len(line) < 120 and line.startswith(SUBHEADING_PREFIXES):
            flush()
            heading = f"{heading} > {line}" if heading else line
        if buffer and size + len(line) > MAX_CHARS:
            flush()
        buffer.append(line)
        size += len(line)
    flush()
    return passages


def load_passages():
    """Read every source listed in sources.json and split it into passages."""
    manifest = json.loads((CORPUS / "sources.json").read_text(encoding="utf-8"))
    passages = []
    for source_id, meta in manifest.items():
        text = (CORPUS / meta["text_file"]).read_text(encoding="utf-8")
        passages.extend(split_source(source_id, meta, text))
    return passages


class Retriever:
    def __init__(self, passages):
        self.passages = passages
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([p["text"] for p in passages])

    @classmethod
    def from_corpus(cls):
        return cls(load_passages())

    def search(self, query, k=3, balanced=True):
        """Return up to k passages with similarity scores (0 to 1), best first.

        balanced=True: the best passage from each source is considered first, so a very long
        source (the UNECE form has most of the passages) cannot fill every slot. The remaining
        slots are filled by overall score.
        balanced=False: plain ranking by score, with no source guarantee.
        """
        query_vector = self.vectorizer.transform([expand_query(query)])
        scores = cosine_similarity(query_vector, self.matrix)[0]

        first_pass = []
        if balanced:
            best_per_source = {}
            for index in scores.argsort()[::-1]:
                if scores[index] <= 0:
                    break
                best_per_source.setdefault(self.passages[index]["source_id"], index)
            first_pass = sorted(best_per_source.values(), key=lambda i: -scores[i])[:k]
        chosen = list(first_pass)
        for index in scores.argsort()[::-1]:
            if len(chosen) >= k or scores[index] <= 0:
                break
            if index not in chosen:
                chosen.append(index)

        results = []
        for index in sorted(chosen, key=lambda i: -scores[i]):
            result = dict(self.passages[index])
            result["score"] = round(float(scores[index]), 3)
            results.append(result)
        return results


def main():
    parser = argparse.ArgumentParser(description="Search the Singapore DG corpus.")
    parser.add_argument("query", help="The question or topic to search for.")
    parser.add_argument("-k", type=int, default=3, help="How many passages to return.")
    args = parser.parse_args()

    retriever = Retriever.from_corpus()
    print(f"{len(retriever.passages)} passages indexed\n")
    for hit in retriever.search(args.query, k=args.k):
        print(f"[{hit['score']}] {hit['id']}  {hit['source_title']}")
        print(f"    section: {hit['section']}")
        print(f"    url:     {hit['url']}")
        print(f"    {hit['text'][:300]}")
        print()


if __name__ == "__main__":
    main()
