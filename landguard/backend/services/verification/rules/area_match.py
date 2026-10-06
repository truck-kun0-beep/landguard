"""AREA_MATCH rule.

Compares the parcel's `area_decimal` against the most authoritative area
recorded elsewhere — Khatian first, then the recorded GIS figure.

This prototype does not compute area from geometry coordinates; the
stored numbers are what get compared.
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

TOLERANCE = Decimal("0.0001")


class AreaMatchRule:
    code = "AREA_MATCH"

    def evaluate(self, evidence: EvidenceBundle) -> VerificationFinding:
        parcel = evidence.parcel
        parcel_area = Decimal(str(parcel.get("area_decimal", "0")))

        khatian = parcel.get("khatian_area_decimal")
        gis = parcel.get("gis_area_decimal")

        refs: list[EvidenceReference] = [
            EvidenceReference(
                source="KHATIAN",
                record_type="AREA",
                reference=parcel.get("khatian_no", ""),
                fields={"khatian_area_decimal": khatian},
            )
        ]
        if gis is not None:
            refs.append(
                EvidenceReference(
                    source="MOCK_GIS",
                    record_type="AREA",
                    reference=parcel.get("dag_no", ""),
                    fields={"gis_area_decimal": gis},
                )
            )

        # Khatian mismatch is the strong signal.
        if khatian is not None:
            k = Decimal(str(khatian))
            if abs(parcel_area - k) > TOLERANCE:
                return VerificationFinding(
                    rule_code=self.code,
                    status=FindingStatus.FAIL,
                    severity=Severity.HIGH,
                    message=(
                        f"Parcel area {parcel_area} decimal differs from Khatian "
                        f"recorded area {k.normalize()} decimal."
                    ),
                    evidence_reference=refs,
                )
        if gis is not None:
            g = Decimal(str(gis))
            if abs(parcel_area - g) > TOLERANCE:
                return VerificationFinding(
                    rule_code=self.code,
                    status=FindingStatus.WARNING,
                    severity=Severity.MEDIUM,
                    message=(
                        f"GIS recorded area {g.normalize()} decimal differs from parcel "
                        f"area {parcel_area} decimal."
                    ),
                    evidence_reference=refs,
                )

        return VerificationFinding(
            rule_code=self.code,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            message="Parcel area is consistent with Khatian and GIS evidence.",
            evidence_reference=refs,
        )