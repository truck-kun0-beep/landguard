"""PARCEL_AREA_OVERFLOW rule.

Sums the transferred area of every active transfer (status APPROVED or
PENDING — explicitly excluding CANCELLED / REJECTED) and compares it to
the parcel's recorded area.

A genuine historical transfer that was rejected or cancelled is not part
of the active area accounting.
"""
from __future__ import annotations

from decimal import Decimal

from ..types import (
    EvidenceBundle,
    EvidenceReference,
    FindingStatus,
    Severity,
    VerificationFinding,
)

_ACTIVE_STATUSES = {"APPROVED", "PENDING"}
_EXCLUDED_STATUSES = {"CANCELLED", "REJECTED"}


def _fmt(d: Decimal) -> str:
    """Stable 4-decimal-place string for land areas.

    Avoids Decimal.normalize()'s `1E+1` notation on whole numbers.
    """
    return format(d.quantize(Decimal("0.0001")), "f")


class ParcelAreaOverflowRule:
    code = "PARCEL_AREA_OVERFLOW"

    def evaluate(self, evidence: EvidenceBundle) -> VerificationFinding:
        parcel = evidence.parcel
        parcel_area = Decimal(str(parcel.get("area_decimal", "0")))

        # Defence in depth: still exclude statuses explicitly even if a caller
        # forgot to filter.
        active = [
            t
            for t in evidence.transactions
            if t.get("status") in _ACTIVE_STATUSES
            and t.get("status") not in _EXCLUDED_STATUSES
        ]

        total = sum(
            (Decimal(str(t.get("transferred_area_decimal", "0"))) for t in active),
            Decimal("0"),
        )

        refs: list[EvidenceReference] = [
            EvidenceReference(
                source="PARCEL",
                record_type="AREA",
                reference=parcel.get("parcel_id", ""),
                fields={"parcel_area_decimal": float(parcel_area)},
            )
        ]
        for t in active:
            refs.append(
                EvidenceReference(
                    source="MOCK_REGISTRATION",
                    record_type="DEED",
                    reference=t.get("txn_id", ""),
                    fields={
                        "transferred_area_decimal": t.get("transferred_area_decimal"),
                        "status": t.get("status"),
                    },
                )
            )

        if total > parcel_area:
            diff = total - parcel_area
            return VerificationFinding(
                rule_code=self.code,
                status=FindingStatus.FAIL,
                severity=Severity.CRITICAL,
                message=(
                    f"Recorded transfers total {_fmt(total)} decimal, "
                    f"exceeding the parcel area of {_fmt(parcel_area)} "
                    f"decimal by {_fmt(diff)} decimal."
                ),
                evidence_reference=refs,
                details={
                    "transfers_total": float(total),
                    "parcel_area": float(parcel_area),
                    "overflow": float(diff),
                },
            )

        return VerificationFinding(
            rule_code=self.code,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            message=(
                f"Recorded transfers total {_fmt(total)} decimal; "
                f"parcel area is {_fmt(parcel_area)} decimal."
            ),
            evidence_reference=refs,
        )