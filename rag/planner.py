"""AI planner: proposes the regulatory search question for each finding, from the shipment facts.

Without the planner, each finding type has one fixed question (regulatory_context.QUESTIONS). The
planner asks the model to write a more specific question from the findings and the shipment's
details. Its questions are checked before use, and anything that fails a check is dropped, so the
adapter falls back to the fixed question. The planner never sees or writes an answer; the answer
step still has to cite the corpus.

One model call per case, for all findings together.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import answer as A  # noqa: E402

MIN_LENGTH, MAX_LENGTH = 15, 200
# Fields from the extracted documents that help write a specific question.
FACT_FIELDS = ["un_number", "proper_shipping_name", "dg_class", "container_id", "port_of_discharge", "terminal"]


def plan_key(finding):
    """The key a planned question is stored under: the finding type and the affected document."""
    return f"{finding.get('finding_type')}:{finding.get('affected_document')}"


def shipment_facts(documents):
    """The fields the planner may use: only those that appear in the extracted documents."""
    facts = {}
    for fields in (documents or {}).values():
        if isinstance(fields, dict):
            for name in FACT_FIELDS:
                if fields.get(name) not in (None, "") and name not in facts:
                    facts[name] = fields[name]
    return facts


def build_prompt(findings, facts):
    lines = [
        "You write search questions for a Singapore dangerous-goods rulebook. For each finding below, "
        "write ONE short question that would find the rule that applies to it. Do not answer the question.",
        "",
        "Shipment facts: " + json.dumps(facts, ensure_ascii=False),
        "",
        "Findings:",
    ]
    for f in findings:
        lines.append(f"- key \"{plan_key(f)}\": {f.get('explanation', '')}")
    lines += [
        "",
        "Return one JSON object: {\"questions\": [{\"key\": \"...\", \"question\": \"...\"}]}, using the keys above.",
        "Return valid JSON only.",
    ]
    return "\n".join(lines)


def check_question(text):
    """A question is usable if it is a sensible length, has words, and is a single question."""
    if not isinstance(text, str):
        return False
    text = text.strip()
    if not (MIN_LENGTH <= len(text) <= MAX_LENGTH):
        return False
    if not re.search(r"[A-Za-z]{3,}", text):
        return False
    return text.count("?") <= 1 and "\n" not in text


def parse_plan(reply, keys):
    """Return {key: question} for the keys asked about, dropping anything that fails a check."""
    planned = {}
    if not isinstance(reply, dict):
        return planned
    for item in reply.get("questions") or []:
        if not isinstance(item, dict):
            continue
        key, text = item.get("key"), item.get("question")
        if key in keys and key not in planned and check_question(text):
            planned[key] = text.strip()
    return planned


def plan_questions(findings, facts, model=None):
    """Return {plan_key: question} for the findings given. Empty if the planner fails for any reason."""
    if not findings:
        return {}
    keys = {plan_key(f) for f in findings}
    try:
        reply = (model or A.call_model)(build_prompt(findings, facts))
    except Exception:  # quota, overload, bad key: the adapter uses its fixed questions instead
        return {}
    return parse_plan(reply, keys)
