"""PortDoc AI: a shipment review workspace for dangerous goods document pre-checks (Streamlit).

Main flow: add the four documents, check the shipment, review what needs attention.
Also: open a saved report, or load the sample case.

Run from the project root, in the PowerShell window where your model key is set:
    py -m streamlit run Backend/app.py

Layout and wording live here. The report logic is in report_view.py.
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
SAMPLE_LABEL = "Sample case: saved demo results from a live run. This is not a fresh pipeline run."
LIVE_LABEL = "Result of the check you just ran."
MAX_SIZE = "200 MB per file (the Streamlit default)"

st.set_page_config(page_title="PortDoc AI", layout="wide")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Source Sans 3', 'IBM Plex Sans', 'Segoe UI', sans-serif; }
.stApp { background: #F6F5F1; color: #18324A; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }
h1 { color: #18324A; font-weight: 600; font-size: 1.85rem; margin-bottom: 0; }
h2, h3 { color: #18324A; font-weight: 600; }
h2 { font-size: 1.25rem; margin-top: 1.6rem; }
h3 { font-size: 1.05rem; }
.subtitle { color: #687681; font-size: 1.02rem; margin-top: 0.15rem; }
.notice { background: #FFFFFF; border: 1px solid #D9DDDF; border-left: 3px solid #2F746F;
          border-radius: 4px; padding: 0.65rem 0.9rem; color: #18324A; margin: 0.9rem 0 0.4rem 0; }
.muted { color: #687681; font-size: 0.92rem; }
.state { font-weight: 600; font-size: 0.92rem; }
.state-missing { color: #687681; }
.state-uploaded { color: #18324A; }
.state-reading { color: #2F746F; }
.state-read { color: #2F746F; }
.state-failed { color: #B64B4B; }
.review { color: #B77932; font-weight: 600; }
.urgent { color: #B64B4B; font-weight: 600; }
.label { color: #687681; font-size: 0.85rem; margin-bottom: 0.1rem; }
.value { color: #18324A; font-weight: 600; font-size: 1.05rem; }
.stage-complete { color: #2F746F; font-weight: 600; }
.stage-progress { color: #18324A; font-weight: 600; }
.stage-notrun { color: #687681; }
div.stButton > button[kind="primary"] { background: #2F746F; border-color: #2F746F; color: #FFFFFF; }
div.stButton > button[kind="primary"]:hover { background: #26605C; border-color: #26605C; color: #FFFFFF; }
div.stButton > button[kind="secondary"] { color: #2F746F; border-color: #2F746F; background: #FFFFFF; }
[data-testid="stMetricValue"] { color: #18324A; font-size: 1.35rem; }
[data-testid="stMetricLabel"] { color: #687681; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

for key, default in [("result", None), ("log", "")]:
    if key not in st.session_state:
        st.session_state[key] = default


def state_html(state):
    """The slot state as coloured text, with the word itself, so colour is not the only cue."""
    css = {"Missing": "state-missing", "Uploaded": "state-uploaded", "Reading": "state-reading",
           "Read": "state-read", "Could not read": "state-failed"}.get(state, "state-uploaded")
    return f"<span class='state {css}'>{state}</span>"


def stage_html(progress):
    """The stages, in plain language, each with its status."""
    rows = []
    for key, label in RV.STAGES:
        status = progress[key]
        css = {"complete": "stage-complete", "in progress": "stage-progress"}.get(status, "stage-notrun")
        rows.append(f"<div>{label}: <span class='{css}'>{status.capitalize()}</span></div>")
    return "".join(rows)


def banner_message(level, text):
    """Show a banner in a calm way: a notice box for information, text for the rest."""
    if level == "error":
        st.markdown(f"<div class='notice'><span class='urgent'>Needs review.</span> {text}</div>", unsafe_allow_html=True)
    elif level == "warning":
        st.markdown(f"<div class='notice'><span class='review'>Incomplete.</span> {text}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='notice'>{text}</div>", unsafe_allow_html=True)


st.markdown("<h1>PortDoc AI</h1>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Check dangerous-goods shipment documents before human review.</div>",
            unsafe_allow_html=True)
st.markdown(f"<div class='notice'>{RV.DISCLAIMER}</div>", unsafe_allow_html=True)


def show_results(report, label):
    """The review workspace for one report: summary, review queue, evidence, download, details."""
    view = RV.summary(report)
    st.markdown(f"<div class='muted'>{label}</div>", unsafe_allow_html=True)
    banner_message(view["banner"]["level"], view["banner"]["text"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Documents read", view["documents_read"])
    col2.metric("Findings", len(view["cards"]))
    triage = view["triage"]
    col3.metric("Suggested priority", triage["priority"] if triage else RV.NOT_AVAILABLE)
    if triage:
        review_css = "review" if triage["review_needed"] else "muted"
        st.markdown(f"<div class='{review_css}'>{triage['review']}</div>", unsafe_allow_html=True)
        st.caption("The suggested priority is a suggestion for review order, not a risk rating.")
        for reason in triage["reasons"]:
            st.caption("Why: " + reason)
    if view["extraction"]["failed_files"]:
        st.warning("Could not be read: " + ", ".join(
            RV.DOCUMENT_LABELS.get(Path(name).stem, name) for name in view["extraction"]["failed_files"]))

    st.markdown("<h2>Review queue</h2>", unsafe_allow_html=True)
    if not view["cards"]:
        st.write("No configured issues were found. Regulatory compliance is not assessed.")
    for index, card in enumerate(view["cards"]):
        suffix = "  ·  Review recommended" if card["human_review"] else ""
        with st.expander(f"{card['title']}  ·  {card['document']}{suffix}", expanded=index == 0):
            if card["values"]:
                left, right = st.columns(2)
                for column, item in zip((left, right), card["values"]):
                    column.markdown(f"<div class='label'>{item['document']}</div>"
                                    f"<div class='value'>{item['value']}</div>", unsafe_allow_html=True)
                if card["field"]:
                    st.markdown(f"<div class='muted'>Field: {card['field']}</div>", unsafe_allow_html=True)
            st.write(card["explanation"])
            if card["human_review"]:
                st.markdown("<div class='review'>Qualified human review is recommended for this finding.</div>",
                            unsafe_allow_html=True)
            st.markdown(f"**Next step:** {card['next_step']}")

            reg = card["regulatory"]
            st.markdown("**Regulatory context**")
            if reg is None:
                st.caption("Not checked against the regulations.")
            else:
                if reg["message"]:
                    st.write(reg["message"])
                if reg["answer"]:
                    st.write(reg["answer"])
                if reg["question"]:
                    origin = "suggested by the AI planner" if reg["question_source"] == "planner" else "standard question"
                    st.caption(f"Question ({origin}): {reg['question']}")
                for source in reg["sources"]:
                    st.markdown(f"- [{source['source']}]({source['url']})")
                for quote in reg["quotes"]:
                    st.markdown(f"> {quote.get('quote', '')}")
                for warning in reg["warnings"]:
                    st.warning(warning)
                if reg["answer"] or reg["sources"]:
                    st.caption(reg["corpus_note"])
                for check in reg["checks"]:
                    st.caption("Check: " + check)

    if view["findings"]:
        st.markdown("<h2>Summary</h2>", unsafe_allow_html=True)
        st.dataframe(view["findings"], width="stretch", hide_index=True)

    st.markdown("<h2>Report</h2>", unsafe_allow_html=True)
    st.write("Regulatory compliance: not assessed")
    st.download_button("Download report (JSON)", RV.report_bytes(report), file_name="validation_report.json",
                       mime="application/json")
    with st.expander("Technical details (for developers)"):
        if st.session_state.log:
            st.code(st.session_state.log)
        st.json(report)


def run_check(uploads, slot_boxes, stage_box):
    """Save the four documents, run the pipeline, and follow its output into the stages."""
    work = Path(tempfile.mkdtemp(prefix="portdoc_"))
    pdf_folder, output_folder = work / "pdfs", work / "output"
    pdf_folder.mkdir()
    present = {key: uploads[key] is not None for key, _ in RV.DOCUMENT_TYPES}
    for key, _ in RV.DOCUMENT_TYPES:
        (pdf_folder / f"{key}.pdf").write_bytes(uploads[key].getbuffer())

    progress = RV.new_progress()
    stage_box.markdown(stage_html(progress), unsafe_allow_html=True)
    for key, box in slot_boxes.items():
        box.markdown(state_html("Reading" if present[key] else "Missing"), unsafe_allow_html=True)

    command = [sys.executable, "-u", str(BACKEND / "run_pipeline.py"),
               "--pdf-folder", str(pdf_folder), "--output-folder", str(output_folder)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    log_lines = []
    for line in process.stdout:
        log_lines.append(line)
        RV.apply_progress_line(line, progress)
        stage_box.markdown(stage_html(progress), unsafe_allow_html=True)
    process.wait()
    st.session_state.log = "".join(log_lines)

    report_path = output_folder / "validation_report.json"
    if report_path.exists() and "validation" in RV.load_report(report_path):
        report = RV.load_report(report_path)
        st.session_state.result = (report, LIVE_LABEL)
        states = RV.slot_states(present, report)
        for key, box in slot_boxes.items():
            box.markdown(state_html(states[key]), unsafe_allow_html=True)
    else:
        st.session_state.result = None
        st.error("The check did not finish. Open Technical details to see the log, check your model key and "
                 "quota, then try again.")


tab_check, tab_saved = st.tabs(["Check a shipment", "Open a saved report"])

with tab_check:
    st.markdown("<h2>1. Add the four documents</h2>", unsafe_allow_html=True)
    st.markdown(f"<div class='muted'>PDF files with selectable text. Scanned PDFs are not supported. "
                f"Limit: {MAX_SIZE}.</div>", unsafe_allow_html=True)
    uploads, slot_boxes = {}, {}
    columns = st.columns(4)
    for column, (key, label) in zip(columns, RV.DOCUMENT_TYPES):
        with column:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                uploads[key] = st.file_uploader(label, type="pdf", key=f"slot_{key}", label_visibility="collapsed")
                slot_boxes[key] = st.empty()
                current = RV.slot_states({key: uploads[key] is not None}, st.session_state.result[0]
                                         if st.session_state.result and st.session_state.result[1] == LIVE_LABEL else None)
                slot_boxes[key].markdown(state_html(current[key]), unsafe_allow_html=True)
    ready = all(uploads[key] is not None for key, _ in RV.DOCUMENT_TYPES)

    st.markdown("<h2>2. Check the shipment</h2>", unsafe_allow_html=True)
    left, right = st.columns([1, 1])
    check_clicked = left.button("Check shipment", type="primary", disabled=not ready, width="stretch")
    sample_clicked = right.button("Load sample case", type="secondary", width="stretch")
    if not ready:
        st.markdown("<div class='muted'>Add all four documents to check the shipment, or load the sample case.</div>",
                    unsafe_allow_html=True)
    stage_box = st.empty()
    stage_box.markdown(stage_html(RV.new_progress()), unsafe_allow_html=True)

    if sample_clicked:
        st.session_state.result = (RV.load_report(SAMPLE), SAMPLE_LABEL)
        st.session_state.log = ""
    if check_clicked:
        run_check(uploads, slot_boxes, stage_box)

    if st.session_state.result:
        st.markdown("<h2>3. Review</h2>", unsafe_allow_html=True)
        show_results(*st.session_state.result)

with tab_saved:
    st.markdown("<div class='muted'>Open a validation report saved from an earlier PortDoc AI check. "
                "Accepted format: the JSON report file from an earlier check.</div>", unsafe_allow_html=True)
    report_file = st.file_uploader("Validation report (.json)", type="json", key="saved_report")
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
