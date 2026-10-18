"""Verification engine for LANDGUARD.

Exports the public types and the `VerificationEngine` orchestrator. Rules
live in `rules/` and are executed in a fixed order so output is stable
across runs.
"""
from __future__ import annotations

from .engine import VerificationEngine
from .types import (
    EvidenceBundle,
    EvidenceReference,
    FindingStatus,
    OverallStatus,
    RiskLevel,
    SourcedEvidence,
    VerificationFinding,
    VerificationResult,
)

__all__ = [
    "VerificationEngine",
    "EvidenceBundle",
    "EvidenceReference",
    "FindingStatus",
    "OverallStatus",
    "RiskLevel",
    "SourcedEvidence",
    "VerificationFinding",
    "VerificationResult",
]