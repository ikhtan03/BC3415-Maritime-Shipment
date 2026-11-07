"""PortDoc AI: a shipment review workspace for dangerous goods document pre-checks (Streamlit).

Main flow: add shipment documents, check the shipment, review what needs attention.
Also: open a saved report, or load the sample case.

Run from the project root, in the PowerShell window where your model key is set:
    py -m streamlit run Backend/app.py

Layout and wording live here. The report logic is in report_view.py.
"""
import hashlib
import os
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
# Live checks and questions need a Gemini key in the environment. A public page without one shows the sample case only.
LIVE_AVAILABLE = bool(os.environ.get("GEMINI_API_KEY"))
LIVE_NOTE = ("Live checks are not available on this page. Load the sample case, or run the app on your own "
             "computer with your own key.")

RAG_DIR = BACKEND / "rag"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))
import answer as A  # noqa: E402
from retrieve import Retriever  # noqa: E402

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

for key, default in [("result", None), ("log", ""), ("answers", {})]:
    if key not in st.session_state:
        st.session_state[key] = default

KEY_PATTERNS = [r"AIza[0-9A-Za-z_\-]{20,}", r"sk-[A-Za-z0-9_\-]{20,}"]


def redact(text):
    """Remove anything that looks like an API key before the log is shown."""
    for pattern in KEY_PATTERNS:
        text = re.sub(pattern, "[key removed]", text)
    return text


@st.cache_resource
def load_retriever():
    """The regulatory corpus, loaded once per session of the app."""
    return Retriever.from_corpus()


def ask_about(question, topic=None):
    """Answer one question from the corpus, with citations. Uses one model call.

    topic: the finding's title, added to the question so the search finds the right rules.
    If nothing answers the question, the closest passages are listed as matches, not answers.
    """
    query = f"{topic}: {question}" if topic else question
    try:
        retriever = load_retriever()
        result = A.answer(query, retriever)
    except Exception as exc:  # shown to the user without the key or any raw API text
        return {"message": "The question could not be answered right now. Check your model key and quota, then try again.",
                "detail": redact(str(exc))[:200], "sources": [], "quotes": [], "checks": [], "answer": "", "closest": []}
    passages = {passage["id"]: passage for passage in retriever.passages}
    view = RV.answer_view(result, passages)
    if view["message"]:
        view["closest"] = [
            {"source": hit["source_title"], "url": hit["url"], "text": hit["text"][:220]}
            for hit in retriever.search(query, k=3)
        ]
    else:
        view["closest"] = []
    return view


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
    if view.get("files"):
        st.markdown("<h2>Files</h2>", unsafe_allow_html=True)
        st.caption("Each file is read to confirm its document type. A file that does not match what was expected is shown here.")
        st.dataframe(view["files"], width="stretch", hide_index=True)

    st.markdown("<h2>What we checked</h2>", unsafe_allow_html=True)
    st.dataframe([{"Check": row["check"], "Result": row["result"]} for row in view["checks"]],
                 width="stretch", hide_index=True)
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
                    if item.get("source") and item["source"].get("quote"):
                        page = item["source"].get("page")
                        column.caption(f"Page {page}: " + item["source"]["quote"][:200])
            if card["field"] and card["field"] != RV.NOT_AVAILABLE:
                st.markdown(f"<div class='muted'>Field: {card['field']}</div>", unsafe_allow_html=True)
            st.write(card["explanation"])
            if card["human_review"]:
                st.markdown("<div class='review'>Qualified human review is recommended for this finding.</div>",
                            unsafe_allow_html=True)
            st.markdown(f"**Next step:** {card['next_step']}")

            ask_key = f"{card['title']}|{index}"
            st.markdown("**Ask about this finding**")
            st.caption("Each question uses one model call from your quota. Answers come only from the project's limited corpus.")
            question = st.text_input("Your question", key=f"q_{index}",
                                     placeholder="For example: What must the declaration state about the class?")
            if st.button("Ask", key=f"ask_{index}", disabled=not LIVE_AVAILABLE) and question.strip():
                st.session_state.answers[ask_key] = ask_about(question.strip(), card["title"])
            answer = st.session_state.answers.get(ask_key)
            if answer:
                if answer.get("message"):
                    st.write(answer["message"])
                if answer.get("detail"):
                    st.caption(answer["detail"])
                if answer.get("answer"):
                    st.write(answer["answer"])
                for source in answer.get("sources", []):
                    st.markdown(f"- [{source['source']}]({source['url']})")
                for quote in answer.get("quotes", []):
                    st.markdown(f"> {quote.get('quote', '')}")
                if answer.get("corpus_note") and (answer.get("answer") or answer.get("sources")):
                    st.caption(answer["corpus_note"])
                if answer.get("closest"):
                    st.caption("Closest passages in the corpus. These are matches to check, not answers to your question.")
                    for hit in answer["closest"]:
                        st.markdown(f"- [{hit['source']}]({hit['url']}): {hit['text']}")

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
        if view["notes"]:
            st.markdown("**Extraction notes**")
            for note in view["notes"]:
                st.caption(f"{note['document']}: {note['note']}")
        if st.session_state.log:
            st.code(redact(st.session_state.log))
        st.json(report)


def run_check(uploads, stage_box, previous_report):
    """Save the uploaded files under their own names, run the pipeline, and follow its output.

    The pipeline reads each document to work out its type, so the names need not match the document.
    """
    work = Path(tempfile.mkdtemp(prefix="portdoc_"))
    pdf_folder, output_folder = work / "pdfs", work / "output"
    pdf_folder.mkdir()
    for file in uploads:
        (pdf_folder / Path(file.name).name).write_bytes(file.getbuffer())

    progress = RV.new_progress()
    stage_box.markdown(stage_html(progress), unsafe_allow_html=True)
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
        progress = RV.apply_outcome(RV.finish_progress(progress, completed=True), report)
        stage_box.markdown(stage_html(progress), unsafe_allow_html=True)
    else:
        st.session_state.result = previous_report
        stage_box.markdown(stage_html(RV.finish_progress(progress, completed=False)), unsafe_allow_html=True)
        st.error(RV.FAILURE_MESSAGE)


tab_check, tab_saved = st.tabs(["Check a shipment", "Open a saved report"])

with tab_check:
    st.markdown("<h2>1. Add shipment documents</h2>", unsafe_allow_html=True)
    st.markdown(f"<div class='muted'>{RV.UPLOAD_HELP}</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Drop all the PDFs at once. The tool reads each document to work out what it is, "
                "so file names do not need to match. PDF files with selectable text only; scanned PDFs are not supported. "
                f"Limit: {MAX_SIZE}.</div>", unsafe_allow_html=True)
    uploads = st.file_uploader("Shipment PDFs", type="pdf", accept_multiple_files=True,
                               key="shipment_files", label_visibility="collapsed") or []
    names = [file.name for file in uploads]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if uploads:
        st.markdown("<h3>Files to check</h3>", unsafe_allow_html=True)
        for file in uploads:
            hint = RV.filename_hint(file.name)
            note = f"  ·  the file name suggests: {hint}" if hint else ""
            st.markdown(f"- {file.name}{note}")
        st.markdown("<div class='muted'>The document type of each file is confirmed when you run the check.</div>",
                    unsafe_allow_html=True)
    if duplicate_names:
        st.error(f"Two files have the same name: {', '.join(duplicate_names)}. Rename one of them before checking.")

    st.markdown("<h2>2. Check the shipment</h2>", unsafe_allow_html=True)
    left, right = st.columns(2)
    check_clicked = left.button("Check shipment", type="primary",
                                disabled=not uploads or bool(duplicate_names) or not LIVE_AVAILABLE,
                                width="stretch")
    sample_clicked = right.button("Load sample case", type="secondary", width="stretch")
    if not LIVE_AVAILABLE:
        st.markdown(f"<div class='muted'>{LIVE_NOTE}</div>", unsafe_allow_html=True)
    if not uploads:
        st.markdown("<div class='muted'>Add at least one document to run a check, or load the sample case.</div>",
                    unsafe_allow_html=True)
    stage_box = st.empty()
    stage_box.markdown(stage_html(RV.new_progress()), unsafe_allow_html=True)

    if sample_clicked:
        st.session_state.result = (RV.load_report(SAMPLE), SAMPLE_LABEL)
        st.session_state.log = ""
    if check_clicked:
        run_check(uploads, stage_box, st.session_state.result)

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
                show_results(report, RV.summary(report)["saved"] + f" File: {report_file.name}")
