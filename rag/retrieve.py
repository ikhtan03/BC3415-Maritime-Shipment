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

    def search(self, query, k=3):
        """Return the k most relevant passages, each with its similarity score (0 to 1)."""
        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix)[0]
        ranked = scores.argsort()[::-1][:k]
        results = []
        for index in ranked:
            if scores[index] <= 0:
                break
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
