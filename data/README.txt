MARITIME DG SYNTHETIC DATASET STARTER

Six variants of one fictional import shipment.
A: PDFs in each test_cases folder. B: ground_truth.json records correct baseline and exact values printed in each PDF. C: answer_key.json lists deliberately injected findings.

Only PDFs are inputs to the deployed web app; never supply answer keys to extraction or report LLMs.

IMPORTANT: PDFs are simplified educational representations, NOT official forms, not submission-ready, and DO NOT prove compliance. Base cargo identification is illustrative. HS code intentionally unverified. Member 2 must review DG classification, packaging, applicability, and sourced regulatory checks before declaring a scenario compliant. Missing DGD means missing from configured upload set, not proof of failure of the separate MPA vessel declaration process.

Regulatory sources: https://www.mpa.gov.sg/port-marine-ops/operations/gas-free-hazardous-cargo-info/declaring-dangerous-goods ; https://www.customs.gov.sg/doing-business/import-operations/import-procedures/import-procedures-overview/

Regenerate with: python build.py (requires reportlab).
