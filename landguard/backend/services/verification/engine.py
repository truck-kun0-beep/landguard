"""Verification engine orchestrator.

Collects the bundle (or accepts one), runs every rule in stable order,
persists findings + audit, and returns a `VerificationResult`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .rules import (
    RULES
)
from .scoring import RISK_LABEL, score_findings
from .types import (
    EvidenceBundle,
    VerificationFinding,
    VerificationResult,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class VerificationEngine:
    """Run all registered rules against an evidence bundle."""

    def __init__(self) -> None:
        self.rules = RULES

    def evaluate(self, evidence: EvidenceBundle) -> VerificationResult:
        findings: list[VerificationFinding] = []
        for rule in self.rules:
            findings.append(rule.evaluate(evidence))

        score, risk_level, overall = score_findings(findings)
        return VerificationResult(
            parcel_id=evidence.parcel.get("parcel_id", ""),
            overall_status=overall,
            risk_score=score,
            risk_level=risk_level,
            risk_label=RISK_LABEL,
            finding_count=len(findings),
            findings=findings,
            verified_at=_utcnow_iso(),
        )

    def evaluate_bundle_dict(self, bundle_dict: dict) -> VerificationResult:
        """Convenience adapter that rehydrates a dict into an EvidenceBundle.

        Used by tests + the API layer so they don't have to construct the
        dataclass manually.
        """
        from .types import SourcedEvidence

        def _sourced_list(items):
            return [
                SourcedEvidence(
                    source=item.get("source", ""),
                    record_type=item.get("record_type", ""),
                    data=item.get("data", {}),
                )
                for item in items
            ]

        evidence = EvidenceBundle(
            parcel=bundle_dict["parcel"],
            ownerships=_sourced_list(bundle_dict.get("ownerships", [])),
            registration=_sourced_list(bundle_dict.get("registration", [])),
            mutation=_sourced_list(bundle_dict.get("mutation", [])),
            tax=_sourced_list(bundle_dict.get("tax", [])),
            gis=_sourced_list(bundle_dict.get("gis", [])),
            documents=_sourced_list(bundle_dict.get("documents", [])),
            transactions=bundle_dict.get("transactions", []),
            sources=bundle_dict.get("sources", []),
        )
        return self.evaluate(evidence)