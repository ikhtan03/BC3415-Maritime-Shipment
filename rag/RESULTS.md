# RAG results: what was tested, what passed, what didn't

This summary is for the report. It separates fair tests from tests that have been used for tuning, and it lists the known failures.

## 1. Retrieval (finding the right passage)

| Test set | Status | Result |
|---|---|---|
| Original 10 questions (`test_retrieve.py`) | Used for development | 10 of 10 right source first |
| Holdout 2, 15 fresh questions (`test_retrieve_holdout2.py`) | Run once, then used as a regression check | Right source first: 13 of 15. Right source in top 3: 15 of 15 |

Holdout 2 is now seen. Its numbers are only a regression check for later changes, not a fair test of the current system.

Known retrieval misses:
- "What is the phone number for the MPA hazmat team?" ranks a different passage first. The right passage is in the top 3.
- "I am not sure whether my cargo counts as dangerous. Who should I ask first?" ranks the UNECE form first. The right passage is in the top 3.
- The question "Which goods are classed as dutiable goods?" returned the wrong passage in an earlier run. It hasn't been re-checked since the retrieval changes.

Changes that affected retrieval:
- Each passage now carries its section heading in its text, so a rule split from its heading keeps the words that name its topic.
- Balanced search takes up to two passages per source first, instead of one. This let the MPA page's bulk-notice rule rank in the top 3. The bulk-notice question was used to diagnose this, so it is not a fair test.

## 2. Answers (writing a cited answer from the passages)

**Set v2 (9 fresh questions plus 1 negative control), first live run.** This is the fairest answer test so far, but it has now been seen.

| Outcome | Count | Detail |
|---|---|---|
| Substantively correct | 8 of 9 that ran | Includes the negative control, which was correctly declined |
| Partly correct | 1 | The customs penalty answer left out the 12-month imprisonment term |
| No answer | 1 | Shisha question: repeated 503 errors from the model. Re-run pending |

Checker flags in this run: 3, all false alarms.
- Bracketed citation IDs (2 cases): the model copied the brackets from the prompt.
- A trailing comma after a money figure (1 case).

Both were fixed in commit `74ec7b5`. The fixes are tested but have not been re-run against the model, since the saved answers didn't keep the quotes.

**Set 1 (13 questions), earlier live run, before the heading change.** 12 of 13 status correct, 11 of 13 fully right from search to answer, and no invented quotes. This set has been used for development, so it is not a fair test.

Known answer failures:
- The bulk-notice question, in set 1: the model said no timeframe was given, because the 24-hour sentence was not in the passages it received. The heading change and the two-per-source change address this in retrieval. The answer step has not been re-run since.
- The model can leave out part of an answer, as in the customs penalty case above. The checks only test what the answer says, not whether it is complete.

## 3. Source checks

- Automatic comparison (`rag/corpus/check_sources.py`): every stored sentence from the three web sources still appears on the live pages, 0 missing.
- The UNECE Multimodal Dangerous Goods Form PDF can't be downloaded by script, so it still needs a manual check (`rag/corpus/VERIFY.md`).

## 4. Limits to state in the report

- The test sets are small: 10 to 15 questions each, so one or two results change the percentages a lot.
- Some sets have been used for development, so their scores are optimistic. Only the holdout 2 and v2 sets were kept apart from development, and both have now been seen.
- The checks confirm that quotes and figures appear in the passages the model was given. They can't catch an answer that leaves out part of the rule, or a rule that was never retrieved.
- Live answer results depend on the model being available. Repeated 503 errors mean some questions have no result.
- The UNECE form has not been checked by hand.
