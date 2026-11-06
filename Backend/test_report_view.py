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
      RV.banner(clean)["level"] == "info" and "No findings" in RV.banner(clean)["text"])
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
      [v["value"] for v in card["values"]] == ["Class 3", "Class 9"])
check("a class conflict is flagged for human review prominently", card["human_review"] is True)
check("the card explains the class conflict and asks a qualified reviewer", "qualified reviewer" in card["explanation"])
check("the regulatory evidence shows the answer, source and quote",
      card["regulatory"]["answer"] == "A." and card["regulatory"]["sources"][0]["url"] == "https://u"
      and card["regulatory"]["quotes"][0]["quote"] == "hazard class")
check("the priority reason is kept", RV.triage_view(with_context)["reasons"] == ["dangerous goods class conflict"])

no_source = RV.regulatory_block({"status": "not_found", "answer": "The passages do not say.", "sources": []})
check("no source found says so plainly", no_source["message"] == RV.NO_SOURCE)
not_in_corpus = RV.regulatory_block({"status": "not_applicable"})
check("a document comparison shows no regulatory block", not_in_corpus is None)
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

check("a file named like a packing list in the declaration slot prompts a type check",
      RV.type_hint("packing_list.pdf", "dangerous_goods_declaration") == "packing_list")
check("a file in its own slot gives no prompt", RV.type_hint("packing_list.pdf", "packing_list") is None)
check("an unclear file name gives no prompt", RV.type_hint("scan0001.pdf", "packing_list") is None)
check("the same file in two slots is detected", RV.same_file_slots({"packing_list": "abc", "bill_of_lading": "abc",
                                                                   "commercial_invoice": "xyz"}) == {"packing_list", "bill_of_lading"})
check("different files are not flagged", RV.same_file_slots({"packing_list": "abc", "bill_of_lading": "def"}) == set())
states = RV.slot_states({"packing_list": True}, mismatch={"packing_list": True})
check("a slot whose file may be the wrong type says so", states["packing_list"] == "Type may not match")
prog = RV.finish_progress({"read": "in progress", "check": "complete", "verify": "not run", "triage": "not run",
                           "context": "not run", "report": "not run"}, completed=False)
check("a failed run marks in-progress stages not completed, never in progress",
      prog["read"] == "not completed" and "in progress" not in prog.values())
check("a value in kilograms shows its unit", RV.value_text("18500", "gross_cargo_weight_kg") == "18500 kg")
check("a class value reads as Class n", RV.value_text("CLASS 9", "dg_class") == "Class 9")
partial_report = {"validation": {"findings": [], "checks_not_completed": [
    {"check": "Gross cargo weight", "field": "gross_cargo_weight_kg", "documents": ["bill_of_lading", "packing_list"],
     "reason": "bill_of_lading is missing"}]}}
not_done = RV.summary(partial_report)["not_completed"]
check("a check that could not run names the document it needed",
      "could not be checked" in not_done[0]["text"] and "Bill of lading" in not_done[0]["needed"])
check("the compliance line is always not assessed", RV.summary(partial_report)["compliance"] == "not assessed")

one_unread = {"input": {"uploaded_pdf_count": 1, "extracted_document_count": 0},
              "extraction": {"upload_inventory": [{"filename": "bill_of_lading.pdf", "status": "extraction_failed"}]},
              "validation": {"regulatory_compliance": "not_assessed", "findings": [
                  {"finding_type": "extraction_failed", "affected_document": "bill_of_lading", "expected_action": "re_run_extraction", "explanation": "x"},
                  {"finding_type": "missing_document", "affected_document": "packing_list", "expected_action": "verify_or_correct_documents", "explanation": "x"}]}}
done = RV.apply_outcome(RV.finish_progress(RV.new_progress(), completed=True), one_unread)
check("reading is incomplete when a document could not be read", done["read"] == "incomplete")
view = RV.summary(one_unread)
check("missing documents are listed on their own, not as review cards",
      view["missing"] == ["Packing list"] and all(c["title"] != RV.TITLES["missing_document"] for c in view["cards"]))
check("the unread document is still a review card", any(c["title"] == RV.TITLES["extraction_failed"] for c in view["cards"]))
import triage as TR  # noqa: E402
reasons = TR.triage(one_unread["validation"])["reasons"]
check("triage reasons are not repeated", len(reasons) == len(set(reasons)))

prov_report = {"extraction": {"extraction_metadata": {"packing_list": {"provenance": {
                   "gross_cargo_weight_kg": {"page": 1, "quote": "Gross Cargo Mass (kg) 19,500 kg"}},
                   "extraction_notes": ["Gross and net weights converted to numbers."]}}},
               "validation": {"findings": [], "checks_not_completed": []}}
check("a value shows its page and quote from the document",
      RV.field_source(prov_report, "packing_list", "gross_cargo_weight_kg")["quote"].startswith("Gross Cargo"))
check("a value with no recorded source gives none", RV.field_source(prov_report, "packing_list", "container_id") is None)
check("extraction notes are listed by document", RV.extraction_notes_view(prov_report)[0]["document"] == "Packing list")
rows = {r["check"]: r["result"] for r in RV.checks_view({"validation": {"findings": [
    {"finding_type": "weight_mismatch", "affected_document": "packing_list"},
    {"finding_type": "missing_document", "affected_document": "commercial_invoice"}],
    "checks_not_completed": [{"check": "Container ID"}]}})}
check("the checks table says which checks found a difference", rows["Gross cargo weight"] == "Difference found")
check("the checks table says which checks could not run", rows["Container ID"] == "Not completed")
check("the checks table says which documents were supplied",
      rows["Commercial invoice supplied"] == "No" and rows["Packing list supplied"] == "Yes")
check("a saved report says it is a record, not a fresh run",
      "not a fresh run" in RV.saved_info({"generated_at_utc": "2026-10-27T10:51:53+00:00"}))
ans = RV.answer_view({"status": "supported", "answer": "A.", "citations": ["p1"], "quotes": [],
                      "problems": []}, {"p1": {"source_title": "UNECE form", "url": "https://u"}})
check("an answer shows its source and text", ans["answer"] == "A." and ans["sources"][0]["url"] == "https://u")
none = RV.answer_view({"status": "not_found", "answer": "No.", "citations": []}, {})
check("a question with no source says so plainly", none["message"] == RV.NO_SOURCE and none["answer"] == "")

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
