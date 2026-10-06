"""OWNER_MATCH rule.

For every approved transaction on the parcel, check that the seller is
supported by recorded ownership evidence (one of the parcel's
`owner_references`). The seller's `transferred_area_decimal` must not
exceed their recorded share of the parcel area.

Co-ownership handling: each co-owner's share is treated independently;
the engine does not flag a parcel merely for being co-owned.
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


class OwnerMatchRule:
    code = "OWNER_MATCH"

    def evaluate(self, evidence: EvidenceBundle) -> VerificationFinding:
        parcel = evidence.parcel
        parcel_area = Decimal(str(parcel.get("area_decimal", "0")))
        owners_by_id: dict[str, dict] = {
            ref["identifier"]: ref for ref in parcel.get("owner_references", [])
        }

        # No transactions → nothing to verify, but record ownership evidence.
        txns = [t for t in evidence.transactions if t.get("status") == "APPROVED"]
        if not txns:
            return VerificationFinding(
                rule_code=self.code,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                message=(
                    "No approved transfers on record. Current ownership evidence: "
                    + ", ".join(
                        f"{o.get('name')} ({o.get('identifier')}, "
                        f"{o.get('share_percent')}%)"
                        for o in parcel.get("owner_references", [])
                    )
                    + "."
                ),
                evidence_reference=[
                    EvidenceReference(
                        source="KHATIAN",
                        record_type="OWNERSHIP",
                        reference=parcel.get("parcel_id", ""),
                        fields={"owners": parcel.get("owner_references", [])},
                    )
                ],
            )

        bad: list[VerificationFinding] = []
        refs: list[EvidenceReference] = []

        for t in txns:
            seller = t.get("from_owner_reference")
            transferred = Decimal(str(t.get("transferred_area_decimal", "0")))
            owner = owners_by_id.get(seller)
            if owner is None:
                bad.append(
                    VerificationFinding(
                        rule_code=self.code,
                        status=FindingStatus.FAIL,
                        severity=Severity.HIGH,
                        message=(
                            f"Transaction {t.get('txn_id')} names {seller} as seller, "
                            "but no active ownership evidence supports that transfer."
                        ),
                        evidence_reference=[
                            EvidenceReference(
                                source="MOCK_REGISTRATION",
                                record_type="DEED",
                                reference=t.get("txn_id", ""),
                                fields={
                                    "seller_reference": seller,
                                    "buyer_reference": t.get("to_owner_reference"),
                                    "transferred_area_decimal": float(transferred),
                                },
                            ),
                            EvidenceReference(
                                source="KHATIAN",
                                record_type="OWNERSHIP",
                                reference=parcel.get("parcel_id", ""),
                                fields={"recorded_owners": list(owners_by_id.keys())},
                            ),
                        ],
                        transaction_id=t.get("txn_id"),
                        details={"seller": seller, "transferred_area": float(transferred)},
                    )
                )
                continue

            # Share check: transferred area must not exceed the seller's recorded
            # share of the parcel area. share_percent is out of 100.
            share_percent = float(owner.get("share_percent", 0))
            seller_share = parcel_area * Decimal(str(share_percent)) / Decimal(100)
            if transferred > seller_share:
                bad.append(
                    VerificationFinding(
                        rule_code=self.code,
                        status=FindingStatus.FAIL,
                        severity=Severity.HIGH,
                        message=(
                            f"Transaction {t.get('txn_id')} transfers "
                            f"{transferred} decimal, exceeding seller {seller}'s "
                            f"recorded {share_percent}% share "
                            f"({seller_share.normalize()} decimal)."
                        ),
                        evidence_reference=[
                            EvidenceReference(
                                source="MOCK_REGISTRATION",
                                record_type="DEED",
                                reference=t.get("txn_id", ""),
                                fields={"transferred_area_decimal": float(transferred)},
                            ),
                            EvidenceReference(
                                source="KHATIAN",
                                record_type="OWNERSHIP",
                                reference=parcel.get("parcel_id", ""),
                                fields={
                                    "identifier": seller,
                                    "share_percent": share_percent,
                                    "computed_share": float(seller_share),
                                },
                            ),
                        ],
                        transaction_id=t.get("txn_id"),
                    )
                )

        if bad:
            # Aggregate failures into a single finding so the API stays compact.
            return VerificationFinding(
                rule_code=self.code,
                status=FindingStatus.FAIL,
                severity=Severity.HIGH,
                message=(
                    f"{len(bad)} transfer(s) are not supported by current ownership evidence."
                ),
                evidence_reference=[r for f in bad for r in f.evidence_reference],
                details={"conflicting_transactions": [f.transaction_id for f in bad]},
            )

        # Build the PASS finding with evidence refs to each transfer.
        for t in txns:
            refs.append(
                EvidenceReference(
                    source="MOCK_REGISTRATION",
                    record_type="DEED",
                    reference=t.get("txn_id", ""),
                    fields={
                        "seller_reference": t.get("from_owner_reference"),
                        "buyer_reference": t.get("to_owner_reference"),
                        "transferred_area_decimal": t.get("transferred_area_decimal"),
                    },
                )
            )
        refs.append(
            EvidenceReference(
                source="KHATIAN",
                record_type="OWNERSHIP",
                reference=parcel.get("parcel_id", ""),
                fields={"owners": parcel.get("owner_references", [])},
            )
        )
        return VerificationFinding(
            rule_code=self.code,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            message="Ownership evidence supports all approved transfers.",
            evidence_reference=refs,
        )