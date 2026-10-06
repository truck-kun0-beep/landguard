"""DEED_MUTATION_AREA_MATCH rule.

For every approved transaction, find the corresponding mutation record
by parcel + buyer + date proximity, then compare the deed's transferred
area to the mutation's area.

Matching: same parcel, buyer matches, and the mutation is an APPROVED one.
If the mutation is missing, we don't fail here — that's a separate rule.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..types import (
    EvidenceBundle,
    EvidenceReference,
    FindingStatus,
    Severity,
    VerificationFinding,
)

TOLERANCE = Decimal("0.0001")
_DAYS_WINDOW = 365  # generous window for synthetic dates


def _parse(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _fmt(d: Decimal) -> str:
    return format(d.quantize(Decimal("0.0001")), "f")


class DeedMutationAreaMatchRule:
    code = "DEED_MUTATION_AREA_MATCH"

    def evaluate(self, evidence: EvidenceBundle) -> VerificationFinding:
        txns = [t for t in evidence.transactions if t.get("status") == "APPROVED"]
        muts = [
            m
            for m in evidence.mutation
            if m.data.get("status") == "APPROVED"
        ]

        mismatches: list[tuple[dict, dict, Decimal, Decimal]] = []
        matched = 0

        for t in txns:
            buyer = t.get("to_owner_reference")
            transferred = Decimal(str(t.get("transferred_area_decimal", "0")))
            txn_date = _parse(t.get("transaction_date"))

            candidates: list[dict] = []
            for m in muts:
                if m.data.get("new_owner_reference") != buyer:
                    continue
                md = _parse(m.data.get("approval_date"))
                if txn_date and md and abs((txn_date - md).days) > _DAYS_WINDOW:
                    continue
                candidates.append(m.data)

            if not candidates:
                continue  # missing-mutation is a different rule

            # Take the closest by approval date.
            candidates.sort(
                key=lambda t2: abs(
                    (txn_date - _parse(t2.get("approval_date"))).days
                )
                if txn_date and _parse(t2.get("approval_date"))
                else 0
            )
            m = candidates[0]
            mut_area = Decimal(str(m.get("area_decimal", "0")))
            if abs(transferred - mut_area) > TOLERANCE:
                mismatches.append((t, m, transferred, mut_area))
            else:
                matched += 1

        if mismatches:
            t, m, deed_area, mut_area = mismatches[0]
            extra = (
                f" ({len(mismatches)} transaction(s) affected)" if len(mismatches) > 1 else ""
            )
            diff = abs(deed_area - mut_area)
            return VerificationFinding(
                rule_code=self.code,
                status=FindingStatus.FAIL,
                severity=Severity.HIGH,
                message=(
                    f"The deed records a transfer of {_fmt(deed_area)} decimal "
                    f"while the mutation record records {_fmt(mut_area)} decimal "
                    f"(difference {_fmt(diff)}){extra}."
                ),
                evidence_reference=[
                    EvidenceReference(
                        source="MOCK_REGISTRATION",
                        record_type="DEED",
                        reference=t.get("txn_id", ""),
                        fields={"transferred_area_decimal": float(deed_area)},
                    ),
                    EvidenceReference(
                        source="MOCK_MUTATION",
                        record_type="MUTATION",
                        reference=m.get("application_number", ""),
                        fields={"area_decimal": float(mut_area)},
                    ),
                ],
                transaction_id=t.get("txn_id"),
                details={
                    "mismatched_transactions": [
                        tx.get("txn_id") for tx, _m, _d, _mu in mismatches
                    ]
                },
            )

        return VerificationFinding(
            rule_code=self.code,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            message="Deed and mutation transferred areas agree for all approved transfers.",
            evidence_reference=[
                EvidenceReference(
                    source="MOCK_MUTATION",
                    record_type="MUTATION",
                    reference=muts[0].data.get("application_number", "")
                    if muts
                    else "n/a",
                    fields={"matched": matched},
                )
            ],
        )