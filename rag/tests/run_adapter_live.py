"""Run the regulatory-context adapter live on a saved pipeline validation report.

Uses the model chosen by LLM_PROVIDER (gemini by default, or openai), with the matching key set in
the same PowerShell window. Writes the report with regulatory_context added to each finding, next
to the input file, and prints a summary.

Run from the repo root:
    python rag/tests/run_adapter_live.py rag/tests/pipeline_reports/S06_validation_report.json
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import regulatory_context as R  # noqa: E402
from retrieve import Retriever  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Attach live regulatory context to a pipeline report.")
    parser.add_argument("report", type=Path, help="validation_report.json saved by the pipeline")
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    retriever = Retriever.from_corpus()
    print(f"Attaching regulatory context to {len(report['validation']['findings'])} finding(s)...")
    updated = R.attach_context(report, retriever)

    for finding in updated["validation"]["findings"]:
        context = finding["regulatory_context"]
        print()
        print(f"{finding['finding_type']} | {finding['affected_document']}")
        print(f"  status: {context['status']}")
        if context.get("question"):
            print(f"  question: {context['question']}")
            print(f"  answer: {context.get('answer', '')[:300]}")
            for source in context.get("sources", []):
                print(f"  source: {source['source']} | {source['url']}")
            for problem in context.get("problems", []):
                print(f"  check: {problem[:200]}")

    output = args.report.with_name(args.report.stem + "_with_context.json")
    output.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved to {output}")
    print("Regulatory compliance: NOT ASSESSED (unchanged)")


if __name__ == "__main__":
    main()
