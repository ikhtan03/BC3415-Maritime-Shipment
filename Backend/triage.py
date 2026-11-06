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
PHRASE = {
    "weight_mismatch": "The gross cargo weight differs between documents.",
    "container_mismatch": "The container ID differs between documents.",
    "dg_class_conflict": "The dangerous goods class differs between documents.",
    "missing_document": "A required document is missing.",
    "extraction_failed": "An uploaded document could not be read, so the result is incomplete.",
}
NOTE = ("Prototype triage recommendation, not legally defined classification. All findings warrant "
        "verification; the absence of findings is not a compliance clearance.")


def triage(validation):
    """Return the triage for a validation result (the dict the validator returns, with 'findings')."""
    findings = validation.get("findings", [])
    types = [f["finding_type"] for f in findings]

    if not findings:
        priority, review = "low", False
        reasons = ["No findings were detected."]
    else:
        if "dg_class_conflict" in types or len(findings) >= 2:
            priority, review = "high", True
        else:
            priority, review = "medium", True
        # One plain reason per kind of finding, with no repeats.
        reasons = [PHRASE.get(t, "A finding needs checking.") for t in dict.fromkeys(types)]
        if "extraction_failed" in types:
            # An unreadable document makes the result incomplete, so it needs a person to look.
            priority = "medium" if priority == "low" else priority
            review = True

    return {
        "policy_version": POLICY_VERSION,
        "suggested_priority": priority,
        "human_review_recommended": review,
        "reasons": reasons,
        "note": NOTE,
    }
