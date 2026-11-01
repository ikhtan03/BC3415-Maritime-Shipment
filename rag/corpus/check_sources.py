"""Compare the stored corpus text with the live official pages.

For each HTML source, downloads the live page, extracts its text the same way build_corpus.py did,
and reports stored lines that do not appear on the live page. Date and layout differences are
expected; changed wording, numbers or deadlines are what a person should look at.

The UNECE PDF cannot be checked here, because the server blocks scripted downloads. Check it by hand
using VERIFY.md.

Usage (from the repo root):
    python rag/corpus/check_sources.py
"""
import re
import urllib.request
from pathlib import Path

from build_corpus import SOURCES, html_to_lines, fix_mojibake

HERE = Path(__file__).resolve().parent
HEADER = ("Source:", "Authority:", "URL:", "Retrieved:")


def normalise(text):
    text = fix_mojibake(text).replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip().lower()


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def main():
    for source_id, meta in SOURCES.items():
        stored_path = HERE / f"{source_id}.txt"
        if not stored_path.exists():
            print(f"{source_id}: no stored text file, skipped")
            continue
        try:
            live_html = fetch(meta["url"])
        except Exception as exc:  # network or server problem: report it, do not hide it
            print(f"{source_id}: could not fetch the live page ({exc})")
            continue

        live_text = normalise(" ".join(html_to_lines(live_html)))
        stored_lines = [
            line for line in stored_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith(HEADER) and not line.startswith("#")
        ]
        missing = [line for line in stored_lines if len(line) > 40 and normalise(line) not in live_text]

        print(f"{source_id}: {len(stored_lines)} stored lines, {len(missing)} not found on the live page")
        for line in missing[:8]:
            print(f"    - {line[:160]}")
        if len(missing) > 8:
            print(f"    ... and {len(missing) - 8} more (see the notes in VERIFY.md)")
        print()


if __name__ == "__main__":
    main()
