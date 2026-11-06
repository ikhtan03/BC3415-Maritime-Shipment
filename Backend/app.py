"""User interface for the PortDoc AI pipeline (Streamlit).

Two ways to use it:
- Run on uploaded PDFs: upload the four shipment PDFs, run the pipeline, and see the report.
- Open a saved report: show a validation_report.json the pipeline already wrote.

Run from the project root, in the PowerShell window where your model key is set:
    py -m streamlit run Backend/app.py

All the layout logic is in report_view.py. This file only displays it.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st

import report_view as RV

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent

st.set_page_config(page_title="PortDoc AI", layout="wide")
st.title("PortDoc AI: dangerous goods document pre-check")
st.caption(RV.DISCLAIMER)

LEVELS = {"info": st.info, "warning": st.warning, "error": st.error}


def show_report(report):
    """Display one validation report."""
    if "validation" not in report:
        st.error("The pipeline did not finish. Check the log above, then run it again.")
        return
    view = RV.summary(report)

    LEVELS[view["banner"]["level"]](view["banner"]["text"])

    extraction = view["extraction"]
    col1, col2 = st.columns(2)
    col1.metric("PDFs uploaded", extraction["uploaded"] if extraction["uploaded"] is not None else "unknown")
    col2.metric("Documents read", extraction["extracted"] if extraction["extracted"] is not None else "unknown")
    if extraction["failed_files"]:
        st.warning("Could not be read: " + ", ".join(extraction["failed_files"]))

    if view["triage"]:
        triage = view["triage"]
        st.subheader("Triage")
        col1, col2 = st.columns(2)
        col1.metric("Suggested priority", triage["priority"])
        col2.metric("Review", triage["review"])
        for reason in triage["reasons"]:
            st.write("- " + reason)

    st.subheader("Findings")
    if view["findings"]:
        st.dataframe(view["findings"], width="stretch")
    else:
        st.write("No configured issues found.")

    if view["regulatory"]:
        st.subheader("Regulatory context")
        st.caption("Answers come only from the official sources listed. They are for human review.")
        for item in view["regulatory"]:
            with st.expander(f"{item['finding'].capitalize()}: {item['status']}", expanded=True):
                if item["question"]:
                    source_note = "written by the planner" if item["question_source"] == "planner" else "fixed question"
                    st.write(f"Question ({source_note}): {item['question']}")
                if item["answer"]:
                    st.write(item["answer"])
                for source in item["sources"]:
                    st.markdown(f"- [{source['source']}]({source['url']})")
                for warning in item["warnings"]:
                    st.warning(warning)
                for check in item["checks"]:
                    st.caption("Check: " + check)

    st.caption(f"Regulatory compliance: {view['compliance'].replace('_', ' ')}")


tab_run, tab_saved = st.tabs(["Run on uploaded PDFs", "Open a saved report"])

with tab_run:
    st.write("Upload the four shipment PDFs (bill of lading, commercial invoice, packing list, dangerous goods declaration).")
    uploads = st.file_uploader("Shipment PDFs", type="pdf", accept_multiple_files=True)
    if st.button("Run pipeline", disabled=not uploads):
        work = Path(tempfile.mkdtemp(prefix="portdoc_"))
        pdf_folder, output_folder = work / "pdfs", work / "output"
        pdf_folder.mkdir()
        for upload in uploads:
            (pdf_folder / upload.name).write_bytes(upload.getbuffer())
        with st.spinner("Running extraction, validation, verification and the regulatory check..."):
            result = subprocess.run(
                [sys.executable, "-u", str(BACKEND / "run_pipeline.py"),
                 "--pdf-folder", str(pdf_folder), "--output-folder", str(output_folder)],
                capture_output=True, text=True, cwd=str(ROOT))
        with st.expander("Pipeline log"):
            st.code(result.stdout + result.stderr)
        report_path = output_folder / "validation_report.json"
        if report_path.exists():
            show_report(RV.load_report(report_path))
        else:
            st.error("No report was written. See the log above.")

with tab_saved:
    default = ROOT / "outputs" / "S06" / "validation_report.json"
    path_text = st.text_input("Path to a validation_report.json", value=str(default))
    if st.button("Open report"):
        path = Path(path_text)
        if path.exists():
            show_report(RV.load_report(path))
        else:
            st.error(f"No file at {path}")
