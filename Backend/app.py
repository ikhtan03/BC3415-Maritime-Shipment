"""PortDoc AI: shipment review workspace (Streamlit).

Two ways in:
- Check a shipment: four labelled slots (bill of lading, commercial invoice, packing list,
  dangerous goods declaration), then Run pre-check. A sample shipment can be loaded instead.
- Open a saved report: upload a validation_report.json the pipeline wrote.

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
SAMPLE = BACKEND / "samples" / "S06_sample_report.json"
SAMPLE_LABEL = "Sample shipment (saved results from a live run, not a fresh pipeline run)"
LIVE_LABEL = "Live pre-check run"
ICON = {"complete": "✅", "in progress": "⏳", "not run": "⬜", "failed": "❌"}

st.set_page_config(page_title="PortDoc AI", layout="wide")
st.title("PortDoc AI")
st.caption("Shipment review workspace for dangerous goods documents")
st.info(RV.DISCLAIMER)

if "result" not in st.session_state:
    st.session_state.result = None  # (report, label)


def show_stages(progress):
    """The pipeline stages, with a status for each."""
    lines = [f"{ICON.get(progress[key], '')} {label}: {progress[key]}" for key, label in RV.STAGES]
    return "\n\n".join(lines)


def show_results(report, label):
    """The review workspace for one report."""
    view = RV.summary(report)
    st.caption(label)
    LEVELS = {"info": st.info, "warning": st.warning, "error": st.error}
    LEVELS[view["banner"]["level"]](view["banner"]["text"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Documents", view["documents_read"])
    col2.metric("Findings for review", len(view["cards"]))
    priority = view["triage"]["priority"] if view["triage"] else "Not set"
    col3.metric("Suggested priority", priority)
    if view["triage"]:
        st.write(f"**Review status:** {view['triage']['review']}")
        for reason in view["triage"]["reasons"]:
            st.caption("Priority reason: " + reason)
    if view["extraction"]["failed_files"]:
        st.warning("Could not be read: " + ", ".join(view["extraction"]["failed_files"]))

    st.subheader("Review queue")
    if not view["cards"]:
        st.success("No configured issues were found. Compliance is not assessed.")
    for index, card in enumerate(view["cards"]):
        flag = " (human review)" if card["human_review"] else ""
        with st.expander(f"{card['title']}: {card['document']}{flag}", expanded=index == 0):
            if card["values"]:
                left, right = st.columns(2)
                left.metric(card["values"][0]["document"].capitalize(), str(card["values"][0]["value"]))
                right.metric(card["values"][1]["document"].capitalize(), str(card["values"][1]["value"]))
            if card["field"]:
                st.write(f"**Field:** {card['field']}")
            st.write(card["explanation"])
            st.write(f"**Next step:** {card['next_step']}")
            if card["human_review"]:
                st.error("Qualified human review is recommended for this finding.")

            st.markdown("**Regulatory context**")
            reg = card["regulatory"]
            if reg is None:
                st.caption("Not checked against the regulations.")
            elif reg["message"]:
                st.write(reg["message"])
            if reg and reg["answer"]:
                st.write(reg["answer"])
                if reg["question_source"]:
                    note = "written by the AI planner" if reg["question_source"] == "planner" else "fixed question"
                    st.caption(f"Question ({note}): {reg['question']}")
            if reg:
                for source in reg["sources"]:
                    st.markdown(f"- [{source['source']}]({source['url']})")
                for quote in reg["quotes"]:
                    st.caption("Quoted: " + quote.get("quote", ""))
                for warning in reg["warnings"]:
                    st.warning(warning)
                for check in reg["checks"]:
                    st.caption("Check: " + check)
            st.caption("Answers come only from the project's limited corpus. They are for human review.")

    st.subheader("Summary table")
    if view["findings"]:
        st.dataframe(view["findings"], width="stretch")
    st.caption(f"Regulatory compliance: {view['compliance'].replace('_', ' ')}")

    st.download_button("Download report (JSON)", RV.report_bytes(report), file_name="validation_report.json",
                       mime="application/json")
    with st.expander("Technical details"):
        st.json(report)


tab_check, tab_saved = st.tabs(["Check a shipment", "Open a saved report"])

with tab_check:
    st.subheader("1. Add the four shipment documents")
    uploads = {}
    slot_cols = st.columns(4)
    for col, (doc_key, doc_label) in zip(slot_cols, RV.DOCUMENT_TYPES):
        with col:
            uploads[doc_key] = st.file_uploader(doc_label, type="pdf", key=f"slot_{doc_key}")
            st.caption("Uploaded" if uploads[doc_key] is not None else "Missing")
    ready = all(uploads[key] is not None for key, _ in RV.DOCUMENT_TYPES)

    left, right = st.columns([1, 1])
    run_clicked = left.button("Run pre-check", type="primary", disabled=not ready)
    sample_clicked = right.button("Load sample shipment")
    if not ready:
        st.caption("Add all four documents to run a pre-check, or load the sample shipment.")

    if sample_clicked:
        st.session_state.result = (RV.load_report(SAMPLE), SAMPLE_LABEL)

    if run_clicked:
        work = Path(tempfile.mkdtemp(prefix="portdoc_"))
        pdf_folder, output_folder = work / "pdfs", work / "output"
        pdf_folder.mkdir()
        for doc_key, _ in RV.DOCUMENT_TYPES:
            (pdf_folder / f"{doc_key}.pdf").write_bytes(uploads[doc_key].getbuffer())

        st.subheader("2. Pipeline progress")
        stage_box = st.empty()
        progress = RV.new_progress()
        stage_box.markdown(show_stages(progress))
        command = [sys.executable, "-u", str(BACKEND / "run_pipeline.py"),
                   "--pdf-folder", str(pdf_folder), "--output-folder", str(output_folder)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        log_lines = []
        for line in process.stdout:
            log_lines.append(line)
            RV.apply_progress_line(line, progress)
            stage_box.markdown(show_stages(progress))
        process.wait()
        with st.expander("Pipeline log"):
            st.code("".join(log_lines))

        report_path = output_folder / "validation_report.json"
        if report_path.exists() and "validation" in RV.load_report(report_path):
            st.session_state.result = (RV.load_report(report_path), LIVE_LABEL)
        else:
            st.session_state.result = None
            st.error("The pre-check did not finish. Open the pipeline log above, check the model key and quota, then run it again.")

    if st.session_state.result:
        st.subheader("3. Review")
        show_results(*st.session_state.result)

with tab_saved:
    st.write("Open a validation report the pipeline wrote earlier.")
    report_file = st.file_uploader("Validation report (JSON)", type="json", key="saved_report")
    if report_file is not None:
        try:
            report = RV.json.loads(report_file.getvalue().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            st.error("This file is not a valid JSON report.")
        else:
            if "validation" not in report:
                st.error("This file is not a validation report from the pipeline.")
            else:
                show_results(report, f"Saved report: {report_file.name}")
