# Source verification checklist

Someone who did not build the corpus should complete this before the RAG results are reported.

## Step 1: run the automatic comparison

From the repo root:

```bash
python rag/corpus/check_sources.py
```

It downloads each live page, extracts the text the same way the corpus was built, and reports
any stored passage that no longer appears on the page. Differences in dates or page layout are
expected; wording changes are not.

## Step 2: check each source by hand

For each source, open the official page and tick each row. Compare with the text file in `rag/corpus/`.

| Source | Official URL | Text file | Numbers and deadlines match | Penalties and fees match | Sign-off (name, date) |
|---|---|---|---|---|---|
| MPA declaring dangerous goods | https://www.mpa.gov.sg/port-marine-ops/operations/gas-free-hazardous-cargo-info/declaring-dangerous-goods | `mpa_declaring_dangerous_goods.txt` | [ ] | [ ] | |
| Customs controlled and prohibited goods | https://www.customs.gov.sg/doing-business/import-operations/import-procedures/controlled-and-prohibited-goods-for-imports/ | `customs_controlled_prohibited_imports.txt` | [ ] | [ ] | |
| Customs import procedures overview | https://www.customs.gov.sg/doing-business/import-operations/import-procedures/import-procedures-overview/ | `customs_import_procedures_overview.txt` | [ ] | [ ] | |
| Multimodal Dangerous Goods Form, PDF pages 201 to 450 | https://unece.org/sites/default/files/2025-09/ST_SG_AC10_1_Rev24e_Vol_II_1.pdf (download in a browser; the server blocks scripts) | `mmdg_form_p201_onward.txt` | [ ] | [ ] | |

## What to record

- Any sentence in the text file that differs from the page: copy both versions into the notes below.
- Any page whose layout hides a rule (for example, a table or accordion that the text extraction missed).
- The page's "last updated" date, and the date you checked it.

## Notes

