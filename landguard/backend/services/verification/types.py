"""Data types for the verification engine.

Kept as plain dataclasses so rules and the engine don't pull in any
framework. Every type is JSON-serializable via `asdict()`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class FindingStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OverallStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class EvidenceReference:
    """One specific piece of evidence that contributed to a finding."""

    source: str  # MOCK_REGISTRATION, MOCK_MUTATION, MOCK_TAX, MOCK_GIS, Khatian, etc.
    record_type: str  # DEED, MUTATION, TAX_RECORD, GIS, OWNERSHIP
    reference: str  # doc/mtx/txn id, or a parcel/kanha label
    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourcedEvidence:
    """Wraps a record with its source label so findings can be attributed."""

    source: str
    record_type: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "record_type": self.record_type, "data": self.data}


@dataclass
class VerificationFinding:
    rule_code: str
    status: FindingStatus
    severity: Severity
    message: str
    evidence_reference: list[EvidenceReference] = field(default_factory=list)
    transaction_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_code": self.rule_code,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "evidence_reference": [r.to_dict() for r in self.evidence_reference],
            "transaction_id": self.transaction_id,
            "details": self.details,
        }


@dataclass
class VerificationResult:
    parcel_id: str
    overall_status: OverallStatus
    risk_score: int
    risk_level: RiskLevel
    risk_label: str
    finding_count: int
    findings: list[VerificationFinding] = field(default_factory=list)
    verified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "parcel_id": self.parcel_id,
            "overall_status": self.overall_status.value,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "risk_label": self.risk_label,
            "finding_count": self.finding_count,
            "findings": [f.to_dict() for f in self.findings],
            "verified_at": self.verified_at,
        }


@dataclass
class EvidenceBundle:
    """Unified evidence for one parcel, gathered by the evidence service."""

    parcel: dict[str, Any]
    ownerships: list[SourcedEvidence] = field(default_factory=list)
    registration: list[SourcedEvidence] = field(default_factory=list)
    mutation: list[SourcedEvidence] = field(default_factory=list)
    tax: list[SourcedEvidence] = field(default_factory=list)
    gis: list[SourcedEvidence] = field(default_factory=list)
    documents: list[SourcedEvidence] = field(default_factory=list)
    transactions: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parcel": self.parcel,
            "ownerships": [e.to_dict() for e in self.ownerships],
            "registration": [e.to_dict() for e in self.registration],
            "mutation": [e.to_dict() for e in self.mutation],
            "tax": [e.to_dict() for e in self.tax],
            "gis": [e.to_dict() for e in self.gis],
            "documents": [e.to_dict() for e in self.documents],
            "transactions": self.transactions,
            "sources": self.sources,
        }