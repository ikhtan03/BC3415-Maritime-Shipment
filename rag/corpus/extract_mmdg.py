"""Extract the text of the Multimodal Dangerous Goods Form pages (page 201 onward) from the UNECE PDF.

Input:  the PDF saved locally, path given with --pdf (downloaded in a browser; the UNECE server blocks scripted downloads)
Output: rag/corpus/mmdg_form_p201_onward.txt
        rag/corpus/sources.json (adds an entry for this source)

Each page is labelled with its PDF page number so an answer can cite it. Blank pages are skipped.
"""
import argparse
import json
from datetime import date
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
SOURCE_ID = "mmdg_form_p201_onward"
META = {
    "title": "UN ST/SG/AC.10/1/Rev.24 Volume II (Multimodal Dangerous Goods Form), PDF pages 201 onward",
    "authority": "International Maritime Organization (IMO) and UN Economic Commission for Europe (UNECE)",
    "url": "https://unece.org/sites/default/files/2025-09/ST_SG_AC10_1_Rev24e_Vol_II_1.pdf",
    "start_page": 201,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    args = parser.parse_args()

    doc = pymupdf.open(str(args.pdf))
    pages = []
    skipped = 0
    for index in range(META["start_page"] - 1, doc.page_count):
        text = doc[index].get_text("text")
        lines = [" ".join(line.split()) for line in text.splitlines()]
        body = "\n".join(line for line in lines if line)
        if len(body) < 40:          # blank or near-blank page
            skipped += 1
            continue
        pages.append(f"[PDF page {index + 1}]\n{body}")

    header = [
        f"Source: {META['title']}",
        f"Authority: {META['authority']}",
        f"URL: {META['url']}",
        f"Retrieved: {date.today().isoformat()} (PDF pages {META['start_page']} to {doc.page_count})",
        "",
    ]
    out_path = HERE / f"{SOURCE_ID}.txt"
    out_path.write_text("\n\n".join(header + pages) + "\n", encoding="utf-8")

    manifest_path = HERE / "sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest[SOURCE_ID] = {
        **META,
        "retrieved": date.today().isoformat(),
        "text_file": out_path.name,
        "pages_kept": len(pages),
        "pages_skipped_blank": skipped,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"kept {len(pages)} pages, skipped {skipped} blank -> {out_path.name}")


if __name__ == "__main__":
    main()
