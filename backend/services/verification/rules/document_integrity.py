"""DOCUMENT_INTEGRITY rule.

For each registered document, recompute SHA-256 over a canonical
representation of its content and compare against the stored
`document_hash`. Mismatches indicate the record has been altered since
it was issued.

The rule inspects only document content — it does not look at parcel
scenario tags or any other parcel-level signal.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ..types import (
    EvidenceBundle,
    EvidenceReference,
    FindingStatus,
    Severity,
    VerificationFinding,
)


def _canonical_payload(doc: dict[str, Any]) -> str:
    """Build a stable, JSON-canonical string from the parts of the record
    that should be integrity-protected. Excludes `document_hash` itself
    (so the rule isn't tautological) and dynamic fields like `created_at`
    that aren't part of the content.
    """
    protected = {
        "document_id": doc.get("document_id"),
        "document_type": doc.get("document_type"),
        "document_number": doc.get("document_number"),
        "parcel_id": doc.get("parcel_id"),
        "issuing_authority": doc.get("issuing_authority"),
        "issue_date": doc.get("issue_date"),
        "metadata": doc.get("metadata"),
        "status": doc.get("status"),
    }
    return json.dumps(protected, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_document_hash(doc: dict[str, Any]) -> str:
    payload = _canonical_payload(doc)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DocumentIntegrityRule:
    code = "DOCUMENT_INTEGRITY"

    def evaluate(self, evidence: EvidenceBundle) -> VerificationFinding:
        mismatches: list[tuple[dict, str, str]] = []
        checked = 0

        for sourced in evidence.documents:
            doc = sourced.data
            stored_hash = doc.get("document_hash")
            if not stored_hash or stored_hash == "pending":
                continue
            computed = compute_document_hash(doc)
            checked += 1
            if computed != stored_hash:
                mismatches.append((doc, stored_hash, computed))

        if mismatches:
            doc, stored, computed = mismatches[0]
            extra = (
                f" ({len(mismatches)} document(s) affected)"
                if len(mismatches) > 1
                else ""
            )
            return VerificationFinding(
                rule_code=self.code,
                status=FindingStatus.FAIL,
                severity=Severity.CRITICAL,
                message=(
                    f"Document integrity check failed: stored hash does not "
                    f"match calculated hash for {doc.get('document_id')}{extra}."
                ),
                evidence_reference=[
                    EvidenceReference(
                        source="MOCK_REGISTRATION",
                        record_type="DEED",
                        reference=doc.get("document_id", ""),
                        fields={
                            "stored_hash": stored,
                            "calculated_hash": computed,
                        },
                    )
                ],
                details={
                    "tampered_documents": [d.get("document_id") for d, _, _ in mismatches]
                },
            )

        if checked == 0:
            return VerificationFinding(
                rule_code=self.code,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                message="No hashed documents present to verify.",
            )

        return VerificationFinding(
            rule_code=self.code,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            message=f"Document integrity verified for {checked} document(s).",
        )