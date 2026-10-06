"""Tests for the cryptographic audit chain.

Covers:
- canonical serialization
- hash computation (self-contained)
- append-only behaviour, sequence numbers, linking
- chain verification (valid)
- 5 tamper cases (payload, hash, prev-hash, deletion, reordering)
- pre-chain legacy data migration
- HTTP endpoints + integration with /verify
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend.main import app
from backend.services.audit import (
    GENESIS_PREV_HASH,
    append_event,
    canonical_event,
    compute_event_hash,
    verify_chain,
)


@pytest.fixture(autouse=True)
def _clean_audit():
    """Reset audit + verification state before every test in this file."""
    database.audit_events.save([])
    database.verification_records.save([])
    yield
    database.audit_events.save([])
    database.verification_records.save([])


@pytest.fixture()
def c():
    return TestClient(app)


# ---------- canonical + hash unit tests ----------

def test_canonical_is_deterministic_regardless_of_dict_order():
    a = {"sequence_number": 1, "event_type": "X", "actor": "alice", "payload": {"b": 2, "a": 1}}
    b = {"actor": "alice", "payload": {"a": 1, "b": 2}, "event_type": "X", "sequence_number": 1}
    assert canonical_event(a) == canonical_event(b)


def test_canonical_excludes_current_event_hash():
    """Self-reference must be impossible: hashing must not need the hash."""
    event = {
        "sequence_number": 1,
        "event_id": "EVT-00001",
        "event_type": "VERIFICATION_COMPLETED",
        "parcel_id": "P-1",
        "actor": "alice",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "payload": {"risk_score": 0},
        "previous_event_hash": GENESIS_PREV_HASH,
        "current_event_hash": "deadbeef" * 8,  # poison
    }
    canon = canonical_event(event)
    # The poison hash is not part of the canonical form.
    assert "deadbeef" not in canon


def test_compute_event_hash_is_64_hex_lowercase():
    event = {
        "sequence_number": 1,
        "event_id": "EVT-00001",
        "event_type": "X",
        "parcel_id": None,
        "actor": "a",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "payload": {},
        "previous_event_hash": GENESIS_PREV_HASH,
    }
    h = compute_event_hash(event)
    assert len(h) == 64
    assert h == h.lower()
    int(h, 16)  # raises if not hex


def test_compute_event_hash_changes_when_payload_changes():
    base = {
        "sequence_number": 1,
        "event_id": "EVT-00001",
        "event_type": "X",
        "parcel_id": None,
        "actor": "a",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "payload": {"k": "v1"},
        "previous_event_hash": GENESIS_PREV_HASH,
    }
    h1 = compute_event_hash(base)
    base["payload"] = {"k": "v2"}
    h2 = compute_event_hash(base)
    assert h1 != h2


def test_compute_event_hash_changes_when_prev_changes():
    base = {
        "sequence_number": 1,
        "event_id": "EVT-00001",
        "event_type": "X",
        "parcel_id": None,
        "actor": "a",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "payload": {},
        "previous_event_hash": GENESIS_PREV_HASH,
    }
    h1 = compute_event_hash(base)
    base["previous_event_hash"] = "1" * 64
    h2 = compute_event_hash(base)
    assert h1 != h2


# ---------- append behaviour ----------

def test_append_first_event_uses_genesis_prev_hash():
    e = append_event(
        event_type="VERIFICATION_COMPLETED",
        parcel_id="P-1",
        actor="alice",
        payload={"risk_score": 0},
    )
    assert e["sequence_number"] == 1
    assert e["previous_event_hash"] == GENESIS_PREV_HASH
    assert len(e["current_event_hash"]) == 64


def test_append_increments_sequence_and_links_to_previous():
    a = append_event(event_type="A", parcel_id="P", actor="x", payload={"i": 1})
    b = append_event(event_type="B", parcel_id="P", actor="x", payload={"i": 2})
    c = append_event(event_type="C", parcel_id="P", actor="x", payload={"i": 3})
    assert (a["sequence_number"], b["sequence_number"], c["sequence_number"]) == (1, 2, 3)
    assert b["previous_event_hash"] == a["current_event_hash"]
    assert c["previous_event_hash"] == b["current_event_hash"]


def test_append_persists_to_storage():
    append_event(event_type="X", parcel_id="P", actor="alice", payload={})
    append_event(event_type="Y", parcel_id="P", actor="alice", payload={})
    stored = database.audit_events.all()
    assert len(stored) == 2
    assert stored[0]["current_event_hash"] == stored[1]["previous_event_hash"]


def test_append_handles_empty_initial_storage():
    database.audit_events.save([])
    e = append_event(event_type="X", parcel_id="P", actor="alice", payload={})
    assert e["sequence_number"] == 1
    assert e["previous_event_hash"] == GENESIS_PREV_HASH


# ---------- chain verification ----------

def test_verify_chain_reports_empty_when_no_events():
    database.audit_events.save([])
    result = verify_chain()
    assert result == {
        "valid": True,
        "event_count": 0,
        "first_invalid_sequence": None,
        "error": None,
    }


def test_verify_chain_valid_after_appends():
    for i in range(5):
        append_event(event_type="T", parcel_id="P", actor="alice", payload={"i": i})
    result = verify_chain()
    assert result["valid"] is True
    assert result["event_count"] == 5
    assert result["first_invalid_sequence"] is None
    assert result["error"] is None


# ---------- 5 tamper cases ----------

def _seed_chain(n: int = 4) -> list[dict]:
    out = []
    for i in range(n):
        out.append(
            append_event(
                event_type="T",
                parcel_id="P",
                actor="alice",
                payload={"i": i},
            )
        )
    return out


def test_tamper_payload_change_detected():
    _seed_chain(4)
    raw = database.audit_events.all()
    raw[2]["payload"]["i"] = 999  # tamper
    database.audit_events.save(raw)
    result = verify_chain()
    assert result["valid"] is False
    assert result["first_invalid_sequence"] == 3


def test_tamper_current_hash_change_detected():
    _seed_chain(4)
    raw = database.audit_events.all()
    raw[2]["current_event_hash"] = "f" * 64  # tamper
    database.audit_events.save(raw)
    result = verify_chain()
    assert result["valid"] is False
    assert result["first_invalid_sequence"] == 3


def test_tamper_previous_hash_change_detected():
    _seed_chain(4)
    raw = database.audit_events.all()
    raw[3]["previous_event_hash"] = "a" * 64  # tamper
    database.audit_events.save(raw)
    result = verify_chain()
    assert result["valid"] is False
    assert result["first_invalid_sequence"] == 4


def test_tamper_event_deletion_detected():
    _seed_chain(5)
    raw = database.audit_events.all()
    del raw[2]  # remove middle event
    database.audit_events.save(raw)
    result = verify_chain()
    assert result["valid"] is False
    assert result["first_invalid_sequence"] is not None


def test_tamper_event_reordering_detected():
    events = _seed_chain(4)
    # Mutate stored file directly to swap two non-adjacent events but
    # preserve length and sequence numbers so the test genuinely
    # exercises the cryptographic link rather than the sequence check.
    raw = database.audit_events.all()
    a = copy.deepcopy(raw[1])
    b = copy.deepcopy(raw[3])
    # Swap bodies but keep the surrounding sequence + hash slots, so
    # the recomputed hash for each slot will no longer match its
    # recorded current_event_hash.
    raw[1].update({k: v for k, v in b.items() if k != "sequence_number"})
    raw[3].update({k: v for k, v in a.items() if k != "sequence_number"})
    database.audit_events.save(raw)
    result = verify_chain()
    assert result["valid"] is False
    assert result["first_invalid_sequence"] in (2, 4)


# ---------- pre-chain legacy data migration ----------

def test_legacy_pre_chain_events_get_migrated_to_chained_form():
    legacy = [
        {
            "event_id": "EVT-00001",
            "seq": 1,
            "parcel_id": "P",
            "event_type": "VERIFICATION_COMPLETED",
            "actor_reference": "landguard-prototype",
            "payload": {"overall_status": "VERIFIED", "risk_score": 0},
            "timestamp": "2024-01-01T00:00:00+00:00",
            "previous_event_hash": None,
            "current_event_hash": None,
        },
        {
            "event_id": "EVT-00002",
            "seq": 2,
            "parcel_id": "P",
            "event_type": "VERIFICATION_COMPLETED",
            "actor_reference": "landguard-prototype",
            "payload": {"overall_status": "VERIFIED", "risk_score": 0},
            "timestamp": "2024-01-02T00:00:00+00:00",
            "previous_event_hash": None,
            "current_event_hash": None,
        },
    ]
    database.audit_events.save(legacy)
    # First migration attempt via a fresh append.
    append_event(event_type="VERIFICATION_COMPLETED", parcel_id="P", actor="alice", payload={"x": 1})
    # Stored form must now be a real chain.
    stored = database.audit_events.all()
    assert len(stored) == 3
    # Sequence numbers monotonically increasing from 1.
    seqs = [e["sequence_number"] for e in stored]
    assert seqs == [1, 2, 3]
    # Genesis prev hash on first, link integrity, all real hashes.
    assert stored[0]["previous_event_hash"] == GENESIS_PREV_HASH
    for i, ev in enumerate(stored):
        assert ev["current_event_hash"] and ev["current_event_hash"] != GENESIS_PREV_HASH
        assert len(ev["current_event_hash"]) == 64
        if i > 0:
            assert ev["previous_event_hash"] == stored[i - 1]["current_event_hash"]
    # Verification independently confirms.
    result = verify_chain()
    assert result["valid"] is True
    assert result["event_count"] == 3


# ---------- HTTP endpoints ----------

def test_api_audit_returns_events_in_sequence_order(c):
    c.post("/api/parcels/LG-BD-DHK-SAV-000001/verify")
    c.post("/api/parcels/LG-BD-DHK-GAZ-000004/verify")
    events = c.get("/api/audit").json()
    assert len(events) == 2
    assert events[0]["sequence_number"] == 1
    assert events[1]["sequence_number"] == 2
    assert events[0]["current_event_hash"] == events[1]["previous_event_hash"]


def test_api_audit_verify_returns_valid_after_creation(c):
    c.post("/api/parcels/LG-BD-DHK-SAV-000001/verify")
    result = c.get("/api/audit/verify").json()
    assert result["valid"] is True
    assert result["event_count"] >= 1


def test_api_audit_verify_detects_tampering(c):
    c.post("/api/parcels/LG-BD-DHK-SAV-000001/verify")
    # Tamper the storage directly.
    raw = database.audit_events.all()
    raw[0]["payload"]["overall_status"] = "FORGED"
    database.audit_events.save(raw)
    result = c.get("/api/audit/verify").json()
    assert result["valid"] is False
    assert result["first_invalid_sequence"] == 1


def test_api_parcel_audit_filters_by_parcel(c):
    c.post("/api/parcels/LG-BD-DHK-SAV-000001/verify")
    c.post("/api/parcels/LG-BD-DHK-GAZ-000004/verify")
    events = c.get("/api/parcels/LG-BD-DHK-SAV-000001/audit").json()
    assert all(e["parcel_id"] == "LG-BD-DHK-SAV-000001" for e in events)
    assert len(events) == 1


def test_api_parcel_audit_404_for_unknown_parcel(c):
    r = c.get("/api/parcels/DOES-NOT-EXIST/audit")
    assert r.status_code == 404


def test_api_audit_returns_404_chain_view_when_empty(c):
    result = c.get("/api/audit/verify").json()
    assert result == {
        "valid": True,
        "event_count": 0,
        "first_invalid_sequence": None,
        "error": None,
    }


# ---------- integration: /verify automatically chains ----------

def test_verify_endpoint_creates_chained_audit_event(c):
    v = c.post("/api/parcels/LG-BD-DHK-SAV-000001/verify")
    assert v.status_code == 200
    events = database.audit_events.all()
    assert len(events) == 1
    e = events[0]
    # Real hashes, not None.
    assert e["current_event_hash"] and e["current_event_hash"] != GENESIS_PREV_HASH
    assert e["previous_event_hash"] == GENESIS_PREV_HASH
    assert e["sequence_number"] == 1
    # Chain still verifies.
    assert verify_chain()["valid"] is True


def test_repeated_verify_keeps_chain_valid(c):
    for _ in range(3):
        c.post("/api/parcels/LG-BD-DHK-SAV-000001/verify")
    assert verify_chain()["valid"] is True
    assert verify_chain()["event_count"] == 3


def test_existing_verification_results_unchanged_by_chain(c):
    """The audit chain must NOT change verification outcomes."""
    cases = [
        ("LG-BD-DHK-SAV-000001", "VERIFIED"),
        ("LG-BD-DHK-GAZ-000004", "CONFLICT_DETECTED"),
        ("LG-BD-DHK-NAR-000005", "CONFLICT_DETECTED"),
        ("LG-BD-CTG-PAH-000006", "CONFLICT_DETECTED"),
        ("LG-BD-DHK-GAZ-000007", "CONFLICT_DETECTED"),
        ("LG-BD-CHI-SAV-000008", "REVIEW_REQUIRED"),
        ("LG-BD-DHK-SAV-000009", "CONFLICT_DETECTED"),
    ]
    for pid, expected in cases:
        r = c.post(f"/api/parcels/{pid}/verify")
        assert r.status_code == 200, pid
        assert r.json()["overall_status"] == expected, pid
    # Whole chain valid.
    assert verify_chain()["valid"] is True