"""Persistence helpers for the verification engine.

- `persist_result(result)` upserts the current rule findings into
  `verification_records.json`, keyed by (parcel_id, rule_code) so repeated
  verifications don't pile up unbounded copies.
- `record_audit_event(...)` appends an entry to `audit_events.json`. Each
  event gets a sequence number based on the existing event count.
- `latest_result_for(parcel_id)` returns the most recent result snapshot.
- `latest_findings_for(parcel_id)` returns the per-rule current findings.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .. import database
from .verification.types import VerificationResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def persist_result(result: VerificationResult) -> None:
    """Upsert the current rule findings for one parcel.

    The latest run replaces previous findings with the same rule_code for
    this parcel. Historical runs are still discoverable via
    `audit_events.json`.
    """
    existing = database.verification_records.all()
    keep = [r for r in existing if r.get("parcel_id") != result.parcel_id]
    snapshot_at = _now_iso()
    new_rows: list[dict] = []
    for f in result.findings:
        new_rows.append(
            {
                "parcel_id": result.parcel_id,
                "rule_code": f.rule_code,
                "status": f.status.value,
                "severity": f.severity.value,
                "message": f.message,
                "evidence_reference": [r.to_dict() for r in f.evidence_reference],
                "transaction_id": f.transaction_id,
                "details": f.details,
                "snapshot_at": snapshot_at,
                "updated_at": snapshot_at,
            }
        )
    database.verification_records.save(keep + new_rows)


def record_audit_event(
    parcel_id: str,
    event_type: str,
    payload: dict,
) -> dict:
    """Append a new audit event."""
    existing = database.audit_events.all()
    seq = len(existing) + 1
    event = {
        "event_id": f"EVT-{seq:05d}",
        "seq": seq,
        "parcel_id": parcel_id,
        "event_type": event_type,
        "actor_reference": "landguard-prototype",
        "payload": payload,
        "timestamp": _now_iso(),
        # Chain fields are placeholders until Milestone 04 builds the
        # cryptographic chain.
        "previous_event_hash": None,
        "current_event_hash": None,
    }
    database.audit_events.save(existing + [event])
    return event


def latest_result_for(parcel_id: str) -> dict | None:
    """Reconstruct a result-shape dict from the latest persisted snapshot."""
    from .verification.scoring import RISK_LABEL, score_findings
    from .verification.types import (
        EvidenceReference,
        FindingStatus,
        Severity,
        VerificationFinding,
    )

    rows = [r for r in database.verification_records.all() if r.get("parcel_id") == parcel_id]
    if not rows:
        return None
    # Pick the most recent snapshot_at.
    rows.sort(key=lambda r: r.get("snapshot_at", ""), reverse=True)
    snapshot_at = rows[0]["snapshot_at"]
    current = [r for r in rows if r.get("snapshot_at") == snapshot_at]

    findings: list[VerificationFinding] = []
    for r in current:
        findings.append(
            VerificationFinding(
                rule_code=r["rule_code"],
                status=FindingStatus(r["status"]),
                severity=Severity(r["severity"]),
                message=r["message"],
                evidence_reference=[EvidenceReference(**ref) for ref in r.get("evidence_reference", [])],
                transaction_id=r.get("transaction_id"),
                details=r.get("details", {}),
            )
        )
    score, level, overall = score_findings(findings)
    return {
        "parcel_id": parcel_id,
        "overall_status": overall.value,
        "risk_score": score,
        "risk_level": level.value,
        "risk_label": RISK_LABEL,
        "finding_count": len(findings),
        "findings": [f.to_dict() for f in findings],
        "verified_at": snapshot_at,
    }


def latest_findings_for(parcel_id: str) -> list[dict] | None:
    rows = [r for r in database.verification_records.all() if r.get("parcel_id") == parcel_id]
    if not rows:
        return None
    rows.sort(key=lambda r: r.get("snapshot_at", ""), reverse=True)
    snapshot_at = rows[0]["snapshot_at"]
    return [r for r in rows if r.get("snapshot_at") == snapshot_at]