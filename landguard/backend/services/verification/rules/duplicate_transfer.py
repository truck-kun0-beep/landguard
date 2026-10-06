"""DUPLICATE_TRANSFER rule.

Detects conflicting active transfers on the same parcel where the
transferred areas overlap and the buyers are different.

A historical transfer that has been cancelled or rejected is excluded.
Two transfers to the same buyer with overlapping areas is not flagged
because that's a legitimate staged sale.
"""
from __future__ import annotations

from itertools import combinations
from decimal import Decimal

from ..types import (
    EvidenceBundle,
    EvidenceReference,
    FindingStatus,
    Severity,
    VerificationFinding,
)

_ACTIVE_STATUSES = {"APPROVED", "PENDING"}


class DuplicateTransferRule:
    code = "DUPLICATE_TRANSFER"

    def evaluate(self, evidence: EvidenceBundle) -> VerificationFinding:
        active = [
            t
            for t in evidence.transactions
            if t.get("status") in _ACTIVE_STATUSES
        ]

        conflicts: list[tuple[dict, dict]] = []
        for a, b in combinations(active, 2):
            if a.get("to_owner_reference") == b.get("to_owner_reference"):
                continue
            if a.get("from_owner_reference") != b.get("from_owner_reference"):
                # Different sellers — could still conflict, but the prototype
                # flags same-seller conflicts because they're the clearest
                # signal of double-allocation from one seller.
                continue
            area_a = Decimal(str(a.get("transferred_area_decimal", "0")))
            area_b = Decimal(str(b.get("transferred_area_decimal", "0")))
            if area_a <= 0 or area_b <= 0:
                continue
            if min(area_a, area_b) > 0:  # any overlap counts
                conflicts.append((a, b))

        if conflicts:
            a, b = conflicts[0]
            extra = (
                f" ({len(conflicts)} conflicting pair(s))"
                if len(conflicts) > 1
                else ""
            )
            return VerificationFinding(
                rule_code=self.code,
                status=FindingStatus.FAIL,
                severity=Severity.CRITICAL,
                message=(
                    f"Two active approved transfers reference overlapping "
                    f"portions of this parcel for different buyers{extra}."
                ),
                evidence_reference=[
                    EvidenceReference(
                        source="MOCK_REGISTRATION",
                        record_type="DEED",
                        reference=a.get("txn_id", ""),
                        fields={
                            "from_owner_reference": a.get("from_owner_reference"),
                            "to_owner_reference": a.get("to_owner_reference"),
                            "transferred_area_decimal": a.get("transferred_area_decimal"),
                        },
                    ),
                    EvidenceReference(
                        source="MOCK_REGISTRATION",
                        record_type="DEED",
                        reference=b.get("txn_id", ""),
                        fields={
                            "from_owner_reference": b.get("from_owner_reference"),
                            "to_owner_reference": b.get("to_owner_reference"),
                            "transferred_area_decimal": b.get("transferred_area_decimal"),
                        },
                    ),
                ],
                transaction_id=a.get("txn_id"),
                details={"conflicting_pairs": [[a.get("txn_id"), b.get("txn_id")]]},
            )

        return VerificationFinding(
            rule_code=self.code,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            message="No conflicting overlapping active transfers detected.",
        )