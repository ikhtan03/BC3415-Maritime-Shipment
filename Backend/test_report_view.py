"""Checks for the report view. Offline: the reports are built here.

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

unread = {"input": {"uploaded_pdf_count": 1, "extracted_document_count": 0},
          "extraction": {"upload_inventory": [{"filename": "packing_list.pdf", "status": "extraction_failed"}]},
          "validation": {"findings": [{"finding_type": "extraction_failed", "affected_document": "packing_list",
                                       "expected_action": "re_run_extraction", "explanation": "x"}],
                         "regulatory_compliance": "not_assessed"}}
check("an unread upload makes the run incomplete", RV.banner(unread)["level"] == "warning")
check("the unread file is listed", RV.extraction_view(unread)["failed_files"] == ["packing_list.pdf"])

with_context = {"input": {"uploaded_pdf_count": 4, "extracted_document_count": 4},
                "extraction": {"upload_inventory": []},
                "validation": {"regulatory_compliance": "not_assessed", "findings": [
                    {"finding_type": "dg_class_conflict", "affected_document": "dangerous_goods_declaration",
                     "affected_field": "dg_class", "expected_action": "qualified_human_review",
                     "explanation": "e",
                     "regulatory_context": {"status": "supported", "question": "Q?", "question_source": "planner",
                                            "answer": "A.", "sources": [{"id": "x", "source": "UNECE", "url": "https://u"}],
                                            "problems": [], "warnings": []}}]}}
rows = RV.findings_view(with_context)
check("findings show type, document and action in words",
      rows[0]["Finding"] == "dg class conflict" and rows[0]["Action"] == "qualified human review")
reg = RV.regulatory_view(with_context)
check("regulatory items show the question, answer and source",
      reg[0]["answer"] == "A." and reg[0]["sources"][0]["url"] == "https://u" and reg[0]["question_source"] == "planner")
check("the disclaimer is always shown", RV.summary(with_context)["disclaimer"].startswith("This is an academic prototype"))
check("the compliance status is shown as not assessed", RV.summary(with_context)["compliance"] == "not_assessed")
check("a report without triage gives no triage view", RV.triage_view({"validation": {}}) is None)

print(f"\n{'all checks passed' if not FAILS else str(len(FAILS)) + ' failed'}")
raise SystemExit(1 if FAILS else 0)
