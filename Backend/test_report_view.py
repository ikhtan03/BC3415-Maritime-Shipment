"""Checks for the report view. Offline: the reports are built here, or the labelled sample is used.

Run from the project root:
    python Backend/test_report_view.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report_view as RV  # noqa: E402

FAILS = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILS.append(name)


clean = {"input": {"uploaded_pdf_count": 4, "extracted_document_count": 4},
         "extraction": {"upload_inventory": []},
         "validation": {"findings": [], "regulatory_compliance": "not_assessed",
                        "triage": {"suggested_priority": "low", "human_review_recommended": False,
                                   "reasons": ["no findings"]}}}
check("a clean run says so, without claiming clearance",
      RV.banner(clean)["level"] == "info" and "not a compliance clearance" in RV.banner(clean)["text"])
check("triage shows priority and review in plain words",
      RV.triage_view(clean)["priority"] == "Low" and RV.triage_view(clean)["review"] == "No review needed")
check("documents read reads as 'n of n'", RV.documents_read_text(clean) == "4 of 4")

unread = {"input": {"uploaded_pdf_count": 1, "extracted_document_count": 0},
          "extraction": {"upload_inventory": [{"filename": "packing_list.pdf", "status": "extraction_failed"}]},
          "validation": {"findings": [{"finding_type": "extraction_failed", "affected_document": "packing_list",
                                       "expected_action": "re_run_extraction", "explanation": "x"}],
                         "regulatory_compliance": "not_assessed"}}
check("an unread upload makes the run incomplete", RV.banner(unread)["level"] == "warning")
check("the unread file is listed", RV.extraction_view(unread)["failed_files"] == ["packing_list.pdf"])

with_context = {"input": {"uploaded_pdf_count": 4, "extracted_document_count": 4},
                "extraction": {"upload_inventory": []},
                "validation": {"regulatory_compliance": "not_assessed",
                               "triage": {"suggested_priority": "high", "human_review_recommended": True,
                                          "reasons": ["dangerous goods class conflict"]},
                               "findings": [
                    {"finding_type": "dg_class_conflict", "affected_document": "dangerous_goods_declaration",
                     "affected_field": "dg_class", "expected_action": "qualified_human_review",
                     "reference_document": "bill_of_lading", "reference_value": "3",
                     "observed_value": "CLASS 9", "explanation": "e",
                     "regulatory_context": {"status": "supported", "question": "Q?", "question_source": "planner",
                                            "answer": "A.", "sources": [{"id": "x", "source": "UNECE", "url": "https://u"}],
                                            "quotes": [{"id": "x", "quote": "hazard class"}],
                                            "problems": [], "warnings": []}}]}}
card = RV.review_cards(with_context)[0]
check("a card shows the two values side by side",
      [v["value"] for v in card["values"]] == ["3", "CLASS 9"])
check("a class conflict is flagged for human review prominently", card["human_review"] is True)
check("the card gives a next step", "Qualified human review" in card["next_step"])
check("the regulatory evidence shows the answer, source and quote",
      card["regulatory"]["answer"] == "A." and card["regulatory"]["sources"][0]["url"] == "https://u"
      and card["regulatory"]["quotes"][0]["quote"] == "hazard class")
check("the priority reason is kept", RV.triage_view(with_context)["reasons"] == ["dangerous goods class conflict"])

no_source = RV.regulatory_block({"status": "not_found", "answer": "The passages do not say.", "sources": []})
check("no source found says so plainly", no_source["message"] == RV.NO_SOURCE)
not_in_corpus = RV.regulatory_block({"status": "not_applicable"})
check("a document comparison says no rule applies", "document comparison" in not_in_corpus["message"])
check("no regulatory context gives no block", RV.regulatory_block(None) is None)

progress = RV.new_progress()
for line in ["[1/3] Extracting", "Extraction result saved to x", "[2/3] Validating",
             "Re-checking flagged fields...", "[3/3] Building validation report...",
             "Attaching regulatory context...", "Validation report saved to y"]:
    RV.apply_progress_line(line, progress)
check("the progress lines drive every stage to complete",
      all(state == "complete" for state in progress.values()))
check("stages not reached stay 'not run'", RV.new_progress()["read"] == "not run")

sample = RV.load_report(Path(__file__).resolve().parent / "samples" / "S06_sample_report.json")
view = RV.summary(sample)
check("the labelled sample loads and shows its three findings", len(view["cards"]) == 3)
check("the sample keeps compliance as not assessed", view["compliance"] == "not assessed")
check("the report can be downloaded as JSON", RV.report_bytes(sample).startswith(b"{"))

check("field names are translated for people",
      RV.humanize("gross_cargo_weight_kg differs between bill_of_lading (18500) and packing_list (19500).")
      == "Gross cargo weight differs between Bill of lading (18500) and Packing list (19500).")
check("a missing value shows as not available", RV.value_text(None) == "Not available" and RV.value_text("") == "Not available")
check("a slot shows Missing when no file is added", RV.slot_states({})["packing_list"] == "Missing")
check("a slot shows Uploaded before a check runs", RV.slot_states({"packing_list": True})["packing_list"] == "Uploaded")
check("a slot shows Reading while the check runs", RV.slot_states({"packing_list": True}, running=True)["packing_list"] == "Reading")
failed_report = {"input": {"uploaded_pdf_count": 1, "extracted_document_count": 0},
                 "extraction": {"upload_inventory": [{"filename": "packing_list.pdf", "status": "extraction_failed"}]},
                 "validation": {"findings": []}}
check("a slot shows Could not read when extraction failed",
      RV.slot_states({"packing_list": True}, failed_report)["packing_list"] == "Could not read")

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
