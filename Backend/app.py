"""PortDoc AI: a shipment review workspace for dangerous goods document pre-checks (Streamlit).

Main flow: add shipment documents, check the shipment, review what needs attention.
Also: open a saved report, or load the sample case.

Run from the project root, in the PowerShell window where your model key is set:
    py -m streamlit run Backend/app.py

Layout and wording live here. The report logic is in report_view.py.
"""
import hashlib
import re
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
.subtitle { color: #18324A; font-size: 1.02rem; margin-top: 0.15rem; }
.notice { background: #FFFFFF; border: 1px solid #D9DDDF; border-left: 3px solid #2F746F;
          border-radius: 4px; padding: 0.65rem 0.9rem; color: #18324A; margin: 0.9rem 0 0.4rem 0; }
.muted { color: #5A6772; font-size: 0.93rem; }
.state { font-weight: 600; font-size: 0.93rem; }
.state-missing { color: #5A6772; }
.state-uploaded { color: #18324A; }
.state-reading { color: #2F746F; }
.state-read { color: #2F746F; }
.state-failed { color: #B64B4B; }
.state-check { color: #B77932; }
.review { color: #B77932; font-weight: 600; }
.urgent { color: #B64B4B; font-weight: 600; }
.label { color: #5A6772; font-size: 0.85rem; margin-bottom: 0.1rem; }
.value { color: #18324A; font-weight: 600; font-size: 1.05rem; }
.stage-complete { color: #2F746F; font-weight: 600; }
.stage-progress { color: #18324A; font-weight: 600; }
.stage-notrun { color: #5A6772; }
.stage-notcompleted { color: #B64B4B; font-weight: 600; }
.stage-incomplete { color: #B77932; font-weight: 600; }
[data-testid="stFileUploaderDropzone"] { background: #FFFFFF; border: 1px dashed #687681; }
[data-testid="stFileUploaderDropzone"] * { color: #18324A; }
[data-testid="stFileUploaderFile"] { background: #FFFFFF; }
[data-testid="stFileUploaderFile"] * { color: #18324A; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: #18324A; background: #FFFFFF; }
[data-testid="stExpander"] { background: #FFFFFF; border-color: #D9DDDF; }
div.stButton > button[kind="primary"] { background: #2F746F; border-color: #2F746F; color: #FFFFFF; }
div.stButton > button[kind="primary"]:hover { background: #26605C; border-color: #26605C; color: #FFFFFF; }
div.stButton > button[kind="secondary"] { color: #2F746F; border-color: #2F746F; background: #FFFFFF; }
[data-testid="stMetricValue"] { color: #18324A; font-size: 1.35rem; }
[data-testid="stMetricLabel"] { color: #5A6772; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

for key, default in [("result", None), ("log", "")]:
    if key not in st.session_state:
        st.session_state[key] = default

KEY_PATTERNS = [r"AIza[0-9A-Za-z_\-]{20,}", r"sk-[A-Za-z0-9_\-]{20,}"]


def redact(text):
    """Remove anything that looks like an API key before the log is shown."""
    for pattern in KEY_PATTERNS:
        text = re.sub(pattern, "[key removed]", text)
    return text


def state_html(state):
    """A slot state as coloured text. The words carry the meaning, not the colour."""
    css = {"Missing": "state-missing", "Uploaded": "state-uploaded", "Reading": "state-reading",
           "Read": "state-read", "Could not read": "state-failed", "Type may not match": "state-check"}.get(state, "state-uploaded")
    return f"<span class='state {css}'>{state}</span>"


def stage_html(progress):
    """The stages in plain language, each with its status."""
    rows = []
    css = {"complete": "stage-complete", "in progress": "stage-progress", "not completed": "stage-notcompleted",
           "incomplete": "stage-incomplete"}
    for key, label in RV.STAGES:
        status = progress[key]
        rows.append(f"<div>{label}: <span class='{css.get(status, 'stage-notrun')}'>{status.capitalize()}</span></div>")
    return "".join(rows)


def banner_message(level, text):
    """A banner that states its meaning in words."""
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
    """The review workspace for one report."""
    view = RV.summary(report)
    st.markdown(f"<div class='muted'>{label}</div>", unsafe_allow_html=True)
    banner_message(view["banner"]["level"], view["banner"]["text"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Documents read", view["documents_read"])
    col2.metric("Findings", len(view["cards"]))
    triage = view["triage"]
    col3.metric("Suggested review order", triage["priority"] if triage else RV.NOT_AVAILABLE)
    if triage:
        css = "review" if triage["review_needed"] else "muted"
        st.markdown(f"<div class='{css}'>{triage['review']}</div>", unsafe_allow_html=True)
        st.caption("The suggested review order is a suggestion, not a risk rating or a compliance result.")
        for reason in triage["reasons"]:
            st.caption("Reason: " + reason)
    if view["extraction"]["failed_files"]:
        names = [RV.DOCUMENT_LABELS.get(Path(name).stem, name) for name in view["extraction"]["failed_files"]]
        st.warning("Could not be read: " + ", ".join(names) + ". Checks that need these documents are not complete.")

    st.markdown("<h2>Findings</h2>", unsafe_allow_html=True)
    if not view["cards"]:
        st.write("No findings were detected in the checks that could run.")
    for index, card in enumerate(view["cards"]):
        suffix = "  ·  Review recommended" if card["human_review"] else ""
        with st.expander(f"{card['title']}  ·  {card['document']}{suffix}", expanded=index == 0):
            if card["values"]:
                left, right = st.columns(2)
                for column, item in zip((left, right), card["values"]):
                    column.markdown(f"<div class='label'>{item['document']}</div>"
                                    f"<div class='value'>{item['value']}</div>", unsafe_allow_html=True)
            if card["field"] and card["field"] != RV.NOT_AVAILABLE:
                st.markdown(f"<div class='muted'>Field: {card['field']}</div>", unsafe_allow_html=True)
            st.write(card["explanation"])
            if card["human_review"]:
                st.markdown("<div class='review'>Qualified human review is recommended for this finding.</div>",
                            unsafe_allow_html=True)
            st.markdown(f"**Next step:** {card['next_step']}")

            reg = card["regulatory"]
            if reg:
                st.markdown("**Regulatory context**")
                if reg["message"]:
                    st.write(reg["message"])
                if reg["answer"]:
                    st.write(reg["answer"])
                for source in reg["sources"]:
                    st.markdown(f"- [{source['source']}]({source['url']})")
                for quote in reg["quotes"]:
                    st.markdown(f"> {quote.get('quote', '')}")
                if reg["answer"] or reg["sources"]:
                    st.caption(reg["corpus_note"])

    if view["missing"]:
        st.markdown("<h2>Documents not supplied</h2>", unsafe_allow_html=True)
        st.caption("Checks that need these documents are not complete.")
        for name in view["missing"]:
            st.markdown(f"- {name}: not supplied")

    if view["not_completed"]:
        st.markdown("<h2>Checks not completed</h2>", unsafe_allow_html=True)
        st.caption("These checks did not run, so they are not passes.")
        for item in view["not_completed"]:
            st.markdown(f"- {item['text']}")

    if view["findings"]:
        st.markdown("<h2>Summary</h2>", unsafe_allow_html=True)
        st.dataframe(view["findings"], width="stretch", hide_index=True)

    st.markdown("<h2>Report</h2>", unsafe_allow_html=True)
    st.write("Regulatory compliance: not assessed")
    st.download_button("Download report (JSON)", RV.report_bytes(report), file_name="validation_report.json",
                       mime="application/json")
    with st.expander("Technical details (for developers)"):
        if st.session_state.log:
            st.code(redact(st.session_state.log))
        st.json(report)


def run_check(uploads, slot_boxes, stage_box, previous_report):
    """Save the uploaded documents, run the pipeline, and follow its output into the stages."""
    work = Path(tempfile.mkdtemp(prefix="portdoc_"))
    pdf_folder, output_folder = work / "pdfs", work / "output"
    pdf_folder.mkdir()
    present = {key: uploads[key] is not None for key, _ in RV.DOCUMENT_TYPES}
    for key, _ in RV.DOCUMENT_TYPES:
        if present[key]:
            (pdf_folder / f"{key}.pdf").write_bytes(uploads[key].getbuffer())

    progress = RV.new_progress()
    stage_box.markdown(stage_html(progress), unsafe_allow_html=True)
    for key, box in slot_boxes.items():
        if present[key]:
            box.markdown(state_html("Reading"), unsafe_allow_html=True)

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
    finished = report_path.exists() and "validation" in RV.load_report(report_path)
    if finished:
        report = RV.load_report(report_path)
        st.session_state.result = (report, LIVE_LABEL)
        states = RV.slot_states(present, report)
        for key, box in slot_boxes.items():
            if present[key]:
                box.markdown(state_html(states[key]), unsafe_allow_html=True)
        progress = RV.apply_outcome(RV.finish_progress(progress, completed=True), report)
        stage_box.markdown(stage_html(progress), unsafe_allow_html=True)
    else:
        st.session_state.result = previous_report
        stage_box.markdown(stage_html(RV.finish_progress(progress, completed=False)), unsafe_allow_html=True)
        for key, box in slot_boxes.items():
            if present[key]:
                box.markdown(state_html("Could not read"), unsafe_allow_html=True)
        st.error(RV.FAILURE_MESSAGE)


tab_check, tab_saved = st.tabs(["Check a shipment", "Open a saved report"])

with tab_check:
    st.markdown("<h2>1. Add shipment documents</h2>", unsafe_allow_html=True)
    st.markdown(f"<div class='muted'>{RV.UPLOAD_HELP}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='muted'>PDF files with selectable text. Scanned PDFs are not supported. "
                f"Limit: {MAX_SIZE}.</div>", unsafe_allow_html=True)

    live_report = st.session_state.result[0] if (st.session_state.result and st.session_state.result[1] == LIVE_LABEL) else None
    uploads, slot_boxes, fingerprints, mismatch = {}, {}, {}, {}
    columns = st.columns(4)
    for column, (key, label) in zip(columns, RV.DOCUMENT_TYPES):
        with column:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                uploads[key] = st.file_uploader(label, type="pdf", key=f"slot_{key}", label_visibility="collapsed")
                file = uploads[key]
                fingerprints[key] = hashlib.sha256(file.getbuffer()).hexdigest() if file is not None else None
                if file is not None:
                    st.caption(file.name)
                    hint = RV.type_hint(file.name, key)
                    identified = RV.identified_types(live_report).get(Path(file.name).stem)
                    if hint or (identified and identified != key):
                        mismatch[key] = True
                        suggested = RV.DOCUMENT_LABELS.get(hint or identified, "another document type")
                        st.markdown(f"<div class='muted'>The file may be a {suggested.lower()}. "
                                    f"Check the document type before you run the check.</div>", unsafe_allow_html=True)
                slot_boxes[key] = st.empty()
                states = RV.slot_states({key: file is not None}, live_report, mismatch=mismatch)
                slot_boxes[key].markdown(state_html(states[key]), unsafe_allow_html=True)

    duplicates = RV.same_file_slots(fingerprints)
    if duplicates:
        names = ", ".join(RV.DOCUMENT_LABELS[key] for key in sorted(duplicates))
        st.error(f"The same file is in more than one slot ({names}). Remove one of them before checking.")
    any_present = any(file is not None for file in uploads.values())

    st.markdown("<h2>2. Check the shipment</h2>", unsafe_allow_html=True)
    left, right = st.columns(2)
    check_clicked = left.button("Check shipment", type="primary", disabled=not any_present or bool(duplicates),
                                width="stretch")
    sample_clicked = right.button("Load sample case", type="secondary", width="stretch")
    if not any_present:
        st.markdown("<div class='muted'>Add at least one document to run a check, or load the sample case.</div>",
                    unsafe_allow_html=True)
    stage_box = st.empty()
    stage_box.markdown(stage_html(RV.new_progress()), unsafe_allow_html=True)

    if sample_clicked:
        st.session_state.result = (RV.load_report(SAMPLE), SAMPLE_LABEL)
        st.session_state.log = ""
    if check_clicked:
        run_check(uploads, slot_boxes, stage_box, st.session_state.result)

    if st.session_state.result:
        st.markdown("<h2>3. Review</h2>", unsafe_allow_html=True)
        show_results(*st.session_state.result)

with tab_saved:
    st.markdown("<div class='muted'>Open a report saved from an earlier check. Accepted format: the JSON "
                "report file the pipeline writes.</div>", unsafe_allow_html=True)
    report_file = st.file_uploader("Saved report (.json)", type="json", key="saved_report")
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
