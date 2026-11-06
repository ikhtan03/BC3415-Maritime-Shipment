# RAG results: what was tested, what passed, what didn't

This summary is for the report. It separates fair tests from tests that have been used for tuning, and it lists the known failures.

## 1. Retrieval (finding the right passage)

| Test set | Status | Result |
|---|---|---|
| Original 10 questions (`test_retrieve.py`) | Used for development | 10 of 10 right source first |
| Holdout 2, 15 fresh questions (`test_retrieve_holdout2.py`) | Run once, then used as a regression check | Right source first: 13 of 15. Right source in top 3: 15 of 15 |
| v3, 8 fresh list-item questions (`test_retrieve_v3.py`) | Fresh when first run; now used | Right passage first: 7 of 8. In top 3: 8 of 8 |
| v4, 4 questions in the shisha wording (`test_retrieve_v4.py`) | Fresh when first run; now used | Right passage first: 1 of 4 before the fix, 4 of 4 after. In top 3: 4 of 4 before and after |
| v5, 5 unseen questions in the shisha wording (`test_retrieve_v5.py`) | Fair test of the fix | Right passage first: 0 of 5 before, 3 of 5 after. In top 3: 2 of 5 before, 5 of 5 after |

Holdout 2, v3, v4 and v5 have all been seen now, so they are regression checks for later changes, not fair tests of the current system. v5 was written before the fix and is the only fair measure of it, but the word list in the fix was chosen after looking at v4's failures.

Known retrieval misses after the fix:
- v5: "Is electronic cigarette hardware allowed to be imported into Singapore?" and "Is an obscene video tape allowed to be imported into Singapore?" put the right passage in the top 3 but not first.
- "What is the phone number for the MPA hazmat team?" ranks a different passage first. The right passage is in the top 3.
- "I am not sure whether my cargo counts as dangerous. Who should I ask first?" ranks the UNECE form first. The right passage is in the top 3.
- "Which goods are classed as dutiable goods?" returned the wrong passage in an earlier run. It hasn't been re-checked since the retrieval changes.

Changes that affected retrieval:
- Each passage now carries its section heading in its text, so a rule split from its heading keeps the words that name its topic.
- Balanced search takes up to two passages per source first, instead of one. This let the MPA page's bulk-notice rule rank in the top 3. The bulk-notice question was used to diagnose this, so it is not a fair test.
- Question-only words ("allowed", "import", "singapore") are removed from the query before searching (`strip_question_words`). This fixed the import-wording misses, including the shisha question, which now returns the right passage first. Passages are not changed.

**Shipper's declaration (UNECE form, pages 201-202).** Three fresh sets, each written before its measurement.

| Set | Before | Notes |
|---|---|---|
| v6 (5 questions) | 3 of 5 first, 3 of 5 top 3 | Now seen |
| v7 (5 questions) | 3 of 5 first, 3 of 5 top 3 | Now seen; a glossary change made it 2 of 5 first, so it was reverted |
| v8 (5 questions) | 3 of 5 first, 3 of 5 top 3 | Fresh. Adding each UNECE page's title as its heading left it at 3 of 5, so it was reverted |

The shipper's declaration rule is retrieved in the top 3 about three times in five. Recorded as a known weakness, not fixed.

**Adapter on real pipeline reports.** The adapter flags a "missing" document as inconclusive when it was uploaded, which is what S01 and S05 need. It was run on all six reports with a stub model, not a live one.

**Shipper's declaration retrieval, fixes tried after v11 (fresh set, 6 questions, baseline 2 of 6 first, 3 of 6 in top 3).** Neither candidate was kept.
- Dropping the shared words ("dangerous", "goods", "shipper", "declaration" and similar) from the query: worse on v11 (2 of 6 in top 3) and on most older sets.
- Indexing the section heading three times, to give topic words more weight: v11 unchanged (2 of 6 first, 3 of 6 in top 3). It helped only the sets already seen, so it was not adopted.

The shipper's declaration rule is still found reliably only some of the time. Recorded as a known limit.

**Dangerous goods class question in the adapter (wording change, `a68b5b2`).** The first live run on S06 returned "not found" for the old wording, "What must a dangerous goods declaration state about the class of the goods?", although the UNECE shipper's declaration requires the hazard class. Three wordings were compared on retrieval. The new one, "What must a shipper specify about the hazard class of dangerous goods?", puts the hazard class passage first.

The shipper's declaration sets show that retrieval for this rule is still unreliable with other wordings. v9 (5 questions, used to choose the wording): right passage first 2 of 5, in top 3 2 of 5. v10 (5 confirmation questions): first 1 of 5, in top 3 3 of 5. The new wording itself was checked directly, not in v9 or v10. The live run on S06 with the new wording returned "supported": "The shipper must specify the dangerous goods' hazard class," citing the UNECE form (PDF pages 201 onward) with its URL. Regulatory compliance stays not assessed. One question, one model run, so it is a single check, not a measure of reliability.

## 2. Answers (writing a cited answer from the passages)

**Set v2 (9 fresh questions plus 1 negative control), full re-run after the checker fixes.** The set was run once before the checker fixes and once after. The second run is the one reported here. It is a re-run, because the set has already been seen. Results are in `rag/tests/answer_set_v2_results.csv`.

| Outcome | Count | Detail |
|---|---|---|
| Correct | 9 of 10 | Includes the negative control, which was correctly declined |
| Partly correct | 1 | Customs penalty answer left out the 12-month imprisonment term |
| Wrong | 0 | The shisha question was wrong before the retrieval fix (missed passage). Re-run after the fix: correct, see below |

Checker flags before the fixes: 3, all false alarms (bracketed citation IDs, a trailing comma after a money figure). After the fixes (commit `74ec7b5`), the RIEA and codes answers pass. These fixes are tested but the checker has not been re-run against the saved quotes.

The first (pre-fix) run is not kept as a separate file. It is described above only.

**Shisha re-run (`rag/tests/shisha_rerun.json`), after the retrieval fix (`79b31fb`).** Supported, cited `customs_controlled_prohibited_imports#5`, answer "No, shisha is listed as a prohibited good for import into Singapore." Status correct, source correct, no facts missing. This is a re-run of a question that has already been seen, so it is a regression check, not a fresh result. Results are in `rag/tests/shisha_rerun_results.csv`.

**Set 1 (13 questions), earlier live run, before the heading change.** 12 of 13 status correct, 11 of 13 fully right from search to answer, and no invented quotes. This set has been used for development, so it is not a fair test.

Known answer failures:
- The bulk-notice question, in set 1: the model said no timeframe was given, because the 24-hour sentence was not in the passages it received. The heading change and the two-per-source change address this in retrieval. The answer step has not been re-run since.
- The model can leave out part of an answer, as in the customs penalty case above. The checks only test what the answer says, not whether it is complete.

**Set v3 (6 questions plus 1 negative control), first complete run, OpenAI model.** A different model from the earlier Gemini runs, so not directly comparable with them. Run once, at the model's default temperature, so answers can vary a little between runs. Results are in `rag/tests/answer_set_v3_openai_results.csv`.

| Question | Result | Note |
|---|---|---|
| First-conviction penalty | Correct | The "facts missing" flag is a wording mismatch: the answer says "three times", the expected fact is "3 times". The set is not changed, since it has been run |
| Tampering with safeguards, fine S$8,000 | Wrong, flagged | The answer says no fixed fine is stated. The search cited the compounding passages instead. The checker flagged it (denial check) |
| Removing goods from customs control, S$5,000 | Correct | |
| Packing group required on dangerous cargo? | Wrong, not flagged | The search returned the MPA page, not the UNECE passage. The model said the passages don't cover it. No check fires on a wrong "not found" without a figure |
| Shipper's declaration details | Correct | |
| Hazard class in a declaration | Correct | |
| Strategic goods licence fee (negative control) | Correct | Declined, as it should be |

Status correct: 5 of 7. Right source cited: 5 of 6 answered.

Both failures are retrieval misses, not model errors. The packing group miss is the shipper's declaration weakness recorded above. The checker's blind spot is a wrong "not found" with no figure to check, which is recorded as a known limit.

## 3. Source checks

- Automatic comparison (`rag/corpus/check_sources.py`): every stored sentence from the three web sources still appears on the live pages, 0 missing.
- The UNECE Multimodal Dangerous Goods Form PDF can't be downloaded by script, so it still needs a manual check (`rag/corpus/VERIFY.md`).

## 4. Limits to state in the report

- The test sets are small: 10 to 15 questions each, so one or two results change the percentages a lot.
- Some sets have been used for development, so their scores are optimistic. Holdout 2 and v2 were kept apart from development at first, but both have now been seen.
- The checks confirm that quotes and figures appear in the passages the model was given. They can't catch an answer that leaves out part of the rule, or a rule that was never retrieved.
- Live answer results depend on the model being available. Repeated 503 errors mean some questions have no result.
- The UNECE form has not been checked by hand.
