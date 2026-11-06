"""Illustrative triage for a validation result: a suggested priority and whether a person should review.

The rules are the prototype's policy (see the answer keys' triage_expectations). They are a
recommendation for human review, not a legal classification and not a compliance decision.

Rules:
- no findings: low priority, no review needed
- a dangerous goods class conflict, or two or more findings: high priority, review needed
- one other finding (weight, container, or a missing document): medium priority, review needed
- an upload that could not be extracted: medium priority, review needed (the result is inconclusive)
"""

POLICY_VERSION = "prototype-v1 (illustrative)"
NOTE = ("Prototype triage recommendation, not legally defined classification. All findings warrant "
        "verification; the absence of findings is not a compliance clearance.")


def triage(validation):
    """Return the triage for a validation result (the dict the validator returns, with 'findings')."""
    findings = validation.get("findings", [])
    types = [f["finding_type"] for f in findings]

    if not findings:
        priority, review, reasons = "low", False, ["no findings"]
    elif "dg_class_conflict" in types or len(findings) >= 2:
        priority, review = "high", True
        reasons = [f"{len(findings)} finding(s)" if len(findings) >= 2 else "dangerous goods class conflict"]
    else:
        priority, review = "medium", True
        reasons = [f"{types[0]} needs checking"]
    if "extraction_failed" in types and "extraction failed" not in " ".join(reasons):
        if priority == "low":
            priority = "medium"
        review = True
        reasons.append("an uploaded document could not be extracted, so the result is inconclusive")

    return {
        "policy_version": POLICY_VERSION,
        "suggested_priority": priority,
        "human_review_recommended": review,
        "reasons": reasons,
        "note": NOTE,
    }
