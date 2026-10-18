"""MISSING_MUTATION rule.

For every approved transfer on the parcel, expect at least one APPROVED
mutation record that lines up by buyer + date proximity.

Missing mutation → WARNING (not FAIL): incomplete evidence is different
from contradictory evidence.
"""
from __future__ import annotations

from datetime import date

from ..types import (
    EvidenceBundle,
    EvidenceReference,
    FindingStatus,
    Severity,
    VerificationFinding,
)

_DAYS_WINDOW = 365


def _parse(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


class MissingMutationRule:
    code = "MISSING_MUTATION"

    def evaluate(self, evidence: EvidenceBundle) -> VerificationFinding:
        txns = [t for t in evidence.transactions if t.get("status") == "APPROVED"]
        muts = [
            m.data
            for m in evidence.mutation
            if m.data.get("status") == "APPROVED"
        ]

        missing: list[dict] = []
        for t in txns:
            buyer = t.get("to_owner_reference")
            txn_date = _parse(t.get("transaction_date"))
            found = False
            for m in muts:
                if m.get("new_owner_reference") != buyer:
                    continue
                md = _parse(m.get("approval_date"))
                if txn_date and md and abs((txn_date - md).days) > _DAYS_WINDOW:
                    continue
                found = True
                break
            if not found:
                missing.append(t)

        if missing:
            t = missing[0]
            extra = (
                f" ({len(missing)} transfer(s) affected)"
                if len(missing) > 1
                else ""
            )
            return VerificationFinding(
                rule_code=self.code,
                status=FindingStatus.WARNING,
                severity=Severity.MEDIUM,
                message=(
                    f"A transfer record exists, but no corresponding mutation "
                    f"record was found in the available evidence{extra}."
                ),
                evidence_reference=[
                    EvidenceReference(
                        source="MOCK_REGISTRATION",
                        record_type="DEED",
                        reference=t.get("txn_id", ""),
                        fields={
                            "buyer_reference": t.get("to_owner_reference"),
                            "transaction_date": t.get("transaction_date"),
                        },
                    )
                ],
                transaction_id=t.get("txn_id"),
                details={
                    "transactions_without_mutation": [
                        tx.get("txn_id") for tx in missing
                    ]
                },
            )

        return VerificationFinding(
            rule_code=self.code,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            message="All approved transfers have a corresponding mutation record.",
        )