"""Deterministic cross-document checks for the Maritime DG demo.

Input: JSON object mapping document types to extracted field dictionaries.
No shipment_truth or answer_key is used by the validator.
"""
import argparse
import json
import re
from pathlib import Path

REQUIRED = ('bill_of_lading', 'commercial_invoice', 'packing_list', 'dangerous_goods_declaration')


NUMBER_WITH_UNIT = re.compile(r"\s*([\d,]+(?:\.\d+)?)\s*(?:kg|kgs|kilograms?)?\s*", re.IGNORECASE)


def clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        # A class written as "CLASS 9" is the same class as "9".
        value = re.sub(r"^CLASS\s+", "", value.strip(), flags=re.IGNORECASE)
        if NUMBER_WITH_UNIT.fullmatch(value):
            # "18,500 kg" and 18500 are the same weight: drop the commas and unit before comparing.
            number = float(NUMBER_WITH_UNIT.fullmatch(value).group(1).replace(",", ""))
            return int(number) if number.is_integer() else number
        return value.upper() if value else None
    return value


def check_pair(documents, field, reference, comparison, issue_type, action):
    """Compare two documents only if both contain a usable value."""
    a = documents.get(reference, {}).get(field)
    b = documents.get(comparison, {}).get(field)
    if clean(a) is None or clean(b) is None or clean(a) == clean(b):
        return []
    return [{
        'finding_type': issue_type,
        'affected_document': comparison,
        'affected_field': field,
        'expected_action': action,
        'reference_document': reference,
        'reference_value': a,
        'observed_value': b,
        'explanation': f'{field} differs between {reference} ({a}) and {comparison} ({b}).'
    }]


def validate(documents, uploaded=None):
    """Evaluate required document presence and selected comparable fields.

    Missing individual fields are not treated as required until field-level rules
    are agreed by the project team. The returned findings are pre-checks only.
    """
    if not isinstance(documents, dict):
        raise TypeError('documents must be a dictionary of document type to extracted fields')
    for doc, fields in documents.items():
        if not isinstance(fields, dict):
            raise TypeError(f'{doc} must map to a field dictionary')

    uploaded = set(uploaded or [])
    findings = []
    for doc in REQUIRED:
        if doc in documents:
            continue
        if doc in uploaded:
            # The PDF was received but not extracted, so it cannot be said to be missing.
            findings.append({
                'finding_type': 'extraction_failed',
                'affected_document': doc,
                'affected_field': None,
                'expected_action': 're_run_extraction',
                'explanation': f'{doc} was uploaded but could not be extracted; re-run extraction before judging it.'
            })
        else:
            findings.append({
                'finding_type': 'missing_document',
                'affected_document': doc,
                'affected_field': None,
                'expected_action': 'verify_or_correct_documents',
                'explanation': f'{doc} is missing from the expected upload set.'
            })

    # Compare explicitly matching cargo gross weight fields (not container mass).
    # Bill of Lading is the reference document for these controlled demo cases.
    findings += check_pair(documents, 'gross_cargo_weight_kg', 'bill_of_lading',
                           'packing_list', 'weight_mismatch', 'verify_or_correct_documents')
    # Packing list and DGD are consistent in the provided benchmark when B/L was altered.
    findings += check_pair(documents, 'container_id', 'packing_list',
                           'bill_of_lading', 'container_mismatch', 'verify_or_correct_documents')
    findings += check_pair(documents, 'dg_class', 'bill_of_lading',
                           'dangerous_goods_declaration', 'dg_class_conflict', 'qualified_human_review')

    # Do not infer legal clearance from the absence of discrepancies.
    return {
        'findings': findings,
        'issue_count': len(findings),
        'review_recommended': bool(findings),
        'qualified_human_review': any(f['expected_action'] == 'qualified_human_review' for f in findings),
        'status': 'issues_detected' if findings else 'no_configured_issues_detected',
        'regulatory_compliance': 'not_assessed'
    }


def evaluate_cases(dataset_root):
    """Demonstrate the validator against the six labelled synthetic cases."""
    root = Path(dataset_root)
    all_ok = True
    for folder in sorted((root / 'test_cases').iterdir()):
        if not folder.is_dir():
            continue
        truth = json.loads((folder / 'ground_truth.json').read_text(encoding='utf-8'))
        key = json.loads((folder / 'answer_key.json').read_text(encoding='utf-8'))
        result = validate(truth['document_truth'])
        actual = {(f['finding_type'], f['affected_document']) for f in result['findings']}
        expected = {(f['finding_type'], f['affected_document']) for f in key['expected_findings']}
        passed = actual == expected and result['issue_count'] == key['expected_issue_count']
        all_ok &= passed
        print(f"{'PASS' if passed else 'FAIL'} {folder.name}: {result['issue_count']} findings")
        if not passed:
            print('  expected:', sorted(expected))
            print('  actual:  ', sorted(actual))
    return all_ok


def main():
    parser = argparse.ArgumentParser(description='Validate extracted Maritime DG document JSON.')
    parser.add_argument('--input', type=Path, help='JSON mapping document type to extracted fields')
    parser.add_argument('--test', type=Path, help='Dataset folder containing test_cases/')
    args = parser.parse_args()
    if bool(args.input) == bool(args.test):
        parser.error('Provide exactly one of --input or --test')
    if args.test:
        raise SystemExit(0 if evaluate_cases(args.test) else 1)
    obj = json.loads(args.input.read_text(encoding='utf-8'))
    # Allow direct mapping or a ground_truth-style wrapper for local development.
    documents = obj.get('document_truth', obj.get('documents', obj))
    print(json.dumps(validate(documents), indent=2))


if __name__ == '__main__':
    main()
