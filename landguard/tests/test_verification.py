"""Tests for the verification engine.

Covers:
- Per-rule unit behaviour (PASS / FAIL / WARNING)
- All 7 milestone scenarios on the real seeded data
- Repeated /verify idempotency
- 404 handling
"""
from __future__ import annotations

import pytest

from backend import database
from backend.services import evidence_service, persistence
from backend.services.verification import VerificationEngine
from backend.services.verification.rules import RULES
from backend.services.verification.rules.document_integrity import (
    compute_document_hash,
)
from backend.services.verification.types import (
    EvidenceBundle,
    EvidenceReference,
    FindingStatus,
    Severity,
    SourcedEvidence,
)


# ---------- helpers ----------

def _fresh_engine() -> VerificationEngine:
    return VerificationEngine()


def _run(parcel_id: str):
    eng = _fresh_engine()
    bundle = evidence_service.collect_parcel_evidence(parcel_id)
    return eng.evaluate(bundle)


def _finding(result, code: str):
    for f in result.findings:
        if f.rule_code == code:
            return f
    raise AssertionError(f"no finding with code {code}; got {[f.rule_code for f in result.findings]}")


def _reset_persistence() -> None:
    """Wipe findings + audit events between calls so test ordering is clean."""
    database.verification_records.save([])
    database.audit_events.save([])


# ---------- registry / unit tests ----------

def test_rule_registry_has_all_seven_rules():
    codes = [r.code for r in RULES]
    assert codes == [
        "OWNER_MATCH",
        "AREA_MATCH",
        "DEED_MUTATION_AREA_MATCH",
        "PARCEL_AREA_OVERFLOW",
        "DUPLICATE_TRANSFER",
        "MISSING_MUTATION",
        "DOCUMENT_INTEGRITY",
    ]


def test_document_integrity_detects_corruption():
    """The integrity rule must independently recompute the SHA-256.

    We construct one document with a known-correct hash and a tampered
    hash, hand it to the rule, and assert FAIL/CRITICAL.
    """
    doc = {
        "document_id": "DOC-TEST-1",
        "document_type": "DEED",
        "document_number": "DEED-TEST-1",
        "parcel_id": "LG-BD-TEST-000001",
        "issuing_authority": "Test Authority",
        "issue_date": "2024-01-01",
        "metadata": {"seller_reference": "A", "buyer_reference": "B"},
        "status": "VALID",
        "document_hash": "deadbeef" * 8,  # wrong
    }
    bundle = EvidenceBundle(
        parcel={"parcel_id": "LG-BD-TEST-000001"},
        documents=[SourcedEvidence(source="MOCK_REGISTRATION", record_type="DEED", data=doc)],
    )
    rule = [r for r in RULES if r.code == "DOCUMENT_INTEGRITY"][0]
    finding = rule.evaluate(bundle)
    assert finding.status == FindingStatus.FAIL
    assert finding.severity == Severity.CRITICAL
    assert "DOC-TEST-1" in finding.message

    # And the correct hash matches what the rule would compute.
    assert doc["document_hash"] != compute_document_hash(doc)
    doc["document_hash"] = compute_document_hash(doc)
    passing = rule.evaluate(bundle)
    assert passing.status == FindingStatus.PASS


def test_owner_match_fails_when_seller_unsupported():
    parcel = {
        "parcel_id": "LG-BD-TEST-000099",
        "area_decimal": 10.0,
        "owner_references": [{"identifier": "OWN-1", "name": "Rahim", "share_percent": 100}],
    }
    transactions = [
        {
            "txn_id": "TXN-1",
            "status": "APPROVED",
            "from_owner_reference": "OWN-NOT-RECORDED",
            "to_owner_reference": "OWN-2",
            "transferred_area_decimal": 4.0,
        }
    ]
    bundle = EvidenceBundle(parcel=parcel, transactions=transactions)
    rule = [r for r in RULES if r.code == "OWNER_MATCH"][0]
    f = rule.evaluate(bundle)
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.HIGH


def test_owner_match_passes_for_clean_transfer():
    parcel = {
        "parcel_id": "LG-BD-TEST-000098",
        "area_decimal": 10.0,
        "owner_references": [{"identifier": "OWN-1", "name": "Rahim", "share_percent": 100}],
    }
    transactions = [
        {
            "txn_id": "TXN-1",
            "status": "APPROVED",
            "from_owner_reference": "OWN-1",
            "to_owner_reference": "OWN-2",
            "transferred_area_decimal": 4.0,
        }
    ]
    bundle = EvidenceBundle(parcel=parcel, transactions=transactions)
    rule = [r for r in RULES if r.code == "OWNER_MATCH"][0]
    f = rule.evaluate(bundle)
    assert f.status == FindingStatus.PASS


def test_parcel_overflow_flags_overallocation():
    parcel = {"parcel_id": "X", "area_decimal": 10.0}
    transactions = [
        {"txn_id": "A", "status": "APPROVED", "transferred_area_decimal": 4.0},
        {"txn_id": "B", "status": "APPROVED", "transferred_area_decimal": 7.0},
    ]
    bundle = EvidenceBundle(parcel=parcel, transactions=transactions)
    rule = [r for r in RULES if r.code == "PARCEL_AREA_OVERFLOW"][0]
    f = rule.evaluate(bundle)
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.CRITICAL
    assert "11.0000" in f.message


def test_parcel_overflow_excludes_cancelled():
    rule = [r for r in RULES if r.code == "PARCEL_AREA_OVERFLOW"][0]
    parcel = {"parcel_id": "X", "area_decimal": 10.0}
    transactions = [
        {"txn_id": "A", "status": "APPROVED", "transferred_area_decimal": 4.0},
        {"txn_id": "B", "status": "CANCELLED", "transferred_area_decimal": 7.0},
    ]
    f = rule.evaluate(EvidenceBundle(parcel=parcel, transactions=transactions))
    assert f.status == FindingStatus.PASS


def test_duplicate_transfer_flags_overlap_with_different_buyers():
    rule = [r for r in RULES if r.code == "DUPLICATE_TRANSFER"][0]
    transactions = [
        {"txn_id": "A", "status": "APPROVED", "from_owner_reference": "S", "to_owner_reference": "B1", "transferred_area_decimal": 4.0},
        {"txn_id": "B", "status": "APPROVED", "from_owner_reference": "S", "to_owner_reference": "B2", "transferred_area_decimal": 4.0},
    ]
    f = rule.evaluate(EvidenceBundle(parcel={"parcel_id": "X"}, transactions=transactions))
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.CRITICAL


def test_missing_mutation_warns_when_no_record():
    rule = [r for r in RULES if r.code == "MISSING_MUTATION"][0]
    transactions = [
        {"txn_id": "T", "status": "APPROVED", "to_owner_reference": "B", "transaction_date": "2024-01-01"}
    ]
    bundle = EvidenceBundle(parcel={"parcel_id": "X"}, transactions=transactions, mutation=[])
    f = rule.evaluate(bundle)
    assert f.status == FindingStatus.WARNING
    assert f.severity == Severity.MEDIUM


# ---------- scenario tests on the real seeded data ----------

def test_clean_parcel_verified():
    _reset_persistence()
    result = _run("LG-BD-DHK-SAV-000001")
    assert result.overall_status.value == "VERIFIED"
    assert result.risk_score == 0
    assert all(f.status == FindingStatus.PASS for f in result.findings)


def test_area_mismatch_scenario():
    _reset_persistence()
    result = _run("LG-BD-DHK-GAZ-000004")
    assert result.overall_status.value == "CONFLICT_DETECTED"
    f = _finding(result, "DEED_MUTATION_AREA_MATCH")
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.HIGH
    assert "4.0000" in f.message and "6.0000" in f.message


def test_owner_mismatch_scenario():
    _reset_persistence()
    result = _run("LG-BD-DHK-NAR-000005")
    assert result.overall_status.value == "CONFLICT_DETECTED"
    f = _finding(result, "OWNER_MATCH")
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.HIGH


def test_double_transfer_scenario():
    _reset_persistence()
    result = _run("LG-BD-CTG-PAH-000006")
    assert result.overall_status.value == "CONFLICT_DETECTED"
    f = _finding(result, "DUPLICATE_TRANSFER")
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.CRITICAL


def test_area_overflow_scenario():
    _reset_persistence()
    result = _run("LG-BD-DHK-GAZ-000007")
    assert result.overall_status.value == "CONFLICT_DETECTED"
    f = _finding(result, "PARCEL_AREA_OVERFLOW")
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.CRITICAL
    assert "11.0000" in f.message and "10.0000" in f.message


def test_missing_mutation_scenario():
    _reset_persistence()
    result = _run("LG-BD-CHI-SAV-000008")
    assert result.overall_status.value == "REVIEW_REQUIRED"
    f = _finding(result, "MISSING_MUTATION")
    assert f.status == FindingStatus.WARNING
    assert f.severity == Severity.MEDIUM


def test_hash_mismatch_scenario():
    """The integrity rule must detect the deliberate corruption by
    recomputing SHA-256 — no scenario-name branching."""
    _reset_persistence()
    result = _run("LG-BD-DHK-SAV-000009")
    assert result.overall_status.value == "CONFLICT_DETECTED"
    f = _finding(result, "DOCUMENT_INTEGRITY")
    assert f.status == FindingStatus.FAIL
    assert f.severity == Severity.CRITICAL
    # The finding should reference the document by id, not by parcel.
    refs = f.evidence_reference
    assert any("DOC-DHK-SAV-009-D1" in r.reference for r in refs)


# ---------- API + idempotency ----------

@pytest.fixture(autouse=True)
def reset_before_each():
    _reset_persistence()


def test_repeated_verify_does_not_grow_findings_unbounded():
    eng = VerificationEngine()
    for _ in range(3):
        bundle = evidence_service.collect_parcel_evidence("LG-BD-DHK-SAV-000001")
        result = eng.evaluate(bundle)
        persistence.persist_result(result)

    rows = database.verification_records.all()
    # 7 rules × 1 parcel → exactly 7 rows after repeated runs.
    assert len(rows) == 7
    parcel_ids = {r["parcel_id"] for r in rows}
    assert parcel_ids == {"LG-BD-DHK-SAV-000001"}


def test_audit_event_recorded():
    eng = VerificationEngine()
    bundle = evidence_service.collect_parcel_evidence("LG-BD-DHK-SAV-000001")
    result = eng.evaluate(bundle)
    persistence.persist_result(result)
    persistence.record_audit_event(
        parcel_id="LG-BD-DHK-SAV-000001",
        event_type="VERIFICATION_COMPLETED",
        payload={"overall_status": result.overall_status.value, "risk_score": result.risk_score},
    )
    events = database.audit_events.all()
    assert len(events) == 1
    assert events[0]["event_type"] == "VERIFICATION_COMPLETED"
    assert events[0]["payload"]["risk_score"] == result.risk_score