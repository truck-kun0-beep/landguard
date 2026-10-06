"""HTTP-level tests for the verification endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend.main import app


@pytest.fixture(autouse=True)
def reset_persistence():
    database.verification_records.save([])
    database.audit_events.save([])


@pytest.fixture()
def c():
    return TestClient(app)


def test_health(c):
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "landguard"}


def test_parcels_list(c):
    r = c.get("/api/parcels")
    assert r.status_code == 200
    parcels = r.json()
    assert len(parcels) == 12
    assert {p["scenario_tag"] for p in parcels} >= {
        "CLEAN",
        "AREA-MISMATCH",
        "OWNER-MISMATCH",
        "DOUBLE-TRANSFER",
        "AREA-OVERFLOW",
        "MISSING-MUTATION",
        "HASH-MISMATCH",
    }


def test_parcel_detail(c):
    r = c.get("/api/parcels/LG-BD-DHK-SAV-000001")
    assert r.status_code == 200
    assert r.json()["parcel_id"] == "LG-BD-DHK-SAV-000001"


def test_parcel_not_found(c):
    assert c.get("/api/parcels/DOES-NOT-EXIST").status_code == 404
    assert c.get("/api/parcels/DOES-NOT-EXIST/evidence").status_code == 404
    assert c.post("/api/parcels/DOES-NOT-EXIST/verify").status_code == 404
    assert c.get("/api/parcels/DOES-NOT-EXIST/verification").status_code == 404
    assert c.get("/api/parcels/DOES-NOT-EXIST/verification/findings").status_code == 404


def test_evidence_endpoint(c):
    r = c.get("/api/parcels/LG-BD-DHK-SAV-000001/evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["parcel"]["parcel_id"] == "LG-BD-DHK-SAV-000001"
    assert body["registration"]  # at least one deed
    assert body["mutation"]  # at least one mutation
    assert body["tax"]  # at least one tax record
    assert body["gis"]  # gis evidence


def test_missing_mutation_parcel_has_no_mutation_records(c):
    r = c.get("/api/parcels/LG-BD-CHI-SAV-000008/evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["mutation"] == []
    assert body["registration"]  # deed still there
    assert body["tax"]


def test_verify_then_get_latest(c):
    v = c.post("/api/parcels/LG-BD-DHK-GAZ-000004/verify")
    assert v.status_code == 200
    body = v.json()
    assert body["overall_status"] == "CONFLICT_DETECTED"
    codes = {f["rule_code"] for f in body["findings"]}
    assert "DEED_MUTATION_AREA_MATCH" in codes

    latest = c.get("/api/parcels/LG-BD-DHK-GAZ-000004/verification")
    assert latest.status_code == 200
    assert latest.json()["overall_status"] == "CONFLICT_DETECTED"

    only_findings = c.get("/api/parcels/LG-BD-DHK-GAZ-000004/verification/findings")
    assert only_findings.status_code == 200
    assert isinstance(only_findings.json(), list)
    assert any(f["rule_code"] == "DEED_MUTATION_AREA_MATCH" for f in only_findings.json())


def test_verify_returns_NOT_IMPLEMENTED_for_missing_parcel(c):
    r = c.post("/api/parcels/NOPE/verify")
    assert r.status_code == 404


def test_repeated_verify_does_not_multiply(c):
    pid = "LG-BD-DHK-SAV-000001"
    for _ in range(3):
        c.post(f"/api/parcels/{pid}/verify")
    findings = c.get(f"/api/parcels/{pid}/verification/findings").json()
    # One row per rule, no growth across calls.
    assert len(findings) == 7
    assert len({f["rule_code"] for f in findings}) == 7