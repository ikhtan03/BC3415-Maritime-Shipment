"""Turn the raw HTML of each official Singapore source into a plain-text corpus.

Input:  rag/corpus/raw/<source_id>.html   (downloaded with curl or Invoke-WebRequest)
Output: rag/corpus/<source_id>.txt         (text kept in the page's own wording)
        rag/corpus/sources.json            (URL, retrieval date and section list for each source)

Only text inside the main content is kept: scripts, styles, navigation and footers are dropped.
Headings are kept as markdown-style '#' lines so the retriever can split the text into sections.
"""
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"

SOURCES = {
    "mpa_declaring_dangerous_goods": {
        "title": "Declaring Dangerous Goods | Maritime and Port Authority of Singapore",
        "url": "https://www.mpa.gov.sg/port-marine-ops/operations/gas-free-hazardous-cargo-info/declaring-dangerous-goods",
        "authority": "Maritime and Port Authority of Singapore (MPA)",
    },
    "customs_controlled_prohibited_imports": {
        "title": "Controlled and Prohibited Goods for Imports | Singapore Customs",
        "url": "https://www.customs.gov.sg/doing-business/import-operations/import-procedures/controlled-and-prohibited-goods-for-imports/",
        "authority": "Singapore Customs",
    },
    "customs_import_procedures_overview": {
        "title": "Import Procedures Overview | Singapore Customs",
        "url": "https://www.customs.gov.sg/doing-business/import-operations/import-procedures/import-procedures-overview/",
        "authority": "Singapore Customs",
    },
}

SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "button", "iframe"}
BLOCK_TAGS = {"p", "li", "tr", "br", "div", "section", "article", "dt", "dd", "table", "ul", "ol"}
HEADING_TAGS = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### "}


class MainTextParser(HTMLParser):
    """Collects visible text and headings, skipping non-content tags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.lines = []
        self.buf = []
        self.heading_prefix = None

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if text:
            prefix = self.heading_prefix or ""
            self.lines.append(prefix + text)
        self.buf = []
        self.heading_prefix = None

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in HEADING_TAGS:
            self._flush()
            self.heading_prefix = HEADING_TAGS[tag]
        elif tag in BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag in HEADING_TAGS or tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if not self.skip_depth:
            self.buf.append(data)

    def close_text(self):
        self._flush()
        return self.lines


def fix_mojibake(text):
    """Undo UTF-8 text that was decoded as Windows-1252 (for example 'vesselâ€™s' -> "vessel's")."""
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def html_to_lines(html):
    parser = MainTextParser()
    parser.feed(html)
    lines = parser.close_text()
    # Drop repeated menu-like lines and blank runs; keep order.
    cleaned, seen = [], set()
    for line in lines:
        line = fix_mojibake(line)
        key = line.lower()
        if len(line) < 2:
            continue
        if key in seen and len(line) < 60:
            continue
        seen.add(key)
        cleaned.append(line)
    return cleaned


def main():
    manifest = {}
    for source_id, meta in SOURCES.items():
        raw_path = RAW / f"{source_id}.html"
        if not raw_path.exists():
            print(f"missing: {raw_path}  (download it first)")
            continue
        html = raw_path.read_text(encoding="utf-8", errors="replace")
        lines = html_to_lines(html)
        header = [
            f"Source: {meta['title']}",
            f"Authority: {meta['authority']}",
            f"URL: {meta['url']}",
            f"Retrieved: {date.today().isoformat()}",
            "",
        ]
        out_path = HERE / f"{source_id}.txt"
        out_path.write_text("\n".join(header + lines) + "\n", encoding="utf-8")
        headings = [line for line in lines if line.startswith("#")]
        manifest[source_id] = {
            **meta,
            "retrieved": date.today().isoformat(),
            "text_file": out_path.name,
            "line_count": len(lines),
            "headings": headings,
        }
        print(f"{source_id}: {len(lines)} lines, {len(headings)} headings -> {out_path.name}")

    (HERE / "sources.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote sources.json")


if __name__ == "__main__":
    main()
