"""Tests for the demo data reset + tamper-detection demo."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend import database
from backend.reset import reset
from backend.services.audit import (
    append_event,
    compute_event_hash,
    verify_chain,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(autouse=True)
def _restore_data_files():
    """Snapshot the source-controlled data files so tests can't pollute them."""
    snapshots = {}
    for name in ["audit_events.json", "verification_records.json"]:
        p = DATA_DIR / name
        snapshots[name] = p.read_text(encoding="utf-8") if p.exists() else None
    yield
    for name, content in snapshots.items():
        p = DATA_DIR / name
        if content is None:
            if p.exists():
                p.unlink()
        else:
            p.write_text(content, encoding="utf-8")
    database.audit_events.load()
    database.verification_records.load()


def test_reset_clears_audit_and_verification_records():
    # First populate both stores.
    append_event(event_type="X", parcel_id="P", actor="t", payload={})
    append_event(event_type="Y", parcel_id="P", actor="t", payload={})
    database.verification_records.save([{"parcel_id": "P", "rule_code": "OWNER_MATCH", "status": "PASS"}])
    assert len(database.audit_events.all()) >= 2
    assert len(database.verification_records.all()) == 1

    counts = reset()
    assert counts["audit_events"] == 0
    assert counts["verification_records"] == 0


def test_reset_re_stamps_document_hashes():
    """The HASH-MISMATCH demo must remain after initial conditions."""
    reset()
    raw = json.loads((DATA_DIR / "documents.json").read_text(encoding="utf-8"))
    by_id = {d["document_id"]: d for d in raw}
    # Tampered doc has the all-zeros placeholder.
    assert by_id["DOC-DHK-SAV-009-D1"]["document_hash"] == "0" * 64
    # The rest are correct.
    from backend.services.verification.rules.document_integrity import (
        compute_document_hash,
    )
    for d in raw:
        if d["document_id"] == "DOC-DHK-SAV-009-D1":
            continue
        assert d["document_hash"] == compute_document_hash(d), d["document_id"]


def test_reset_is_idempotent():
    reset()
    reset()
    reset()
    assert database.audit_events.all() == []
    assert database.verification_records.all() == []


def test_tamper_demo_detects_payload_mutation(tmp_path, monkeypatch, capsys):
    """Run the tamper demo in-process and assert it detects the change."""
    # Redirect DATA_DIR to a temp dir so we don't touch the real on-disk data.
    fake = tmp_path / "data"
    fake.mkdir()
    # Copy the real fixtures over so the demo has parcels etc. available.
    for fname in [
        "parcels.json",
        "owners.json",
        "transactions.json",
        "mutations.json",
        "tax_records.json",
        "documents.json",
    ]:
        (fake / fname).write_text((DATA_DIR / fname).read_text(encoding="utf-8"), encoding="utf-8")
    (fake / "audit_events.json").write_text("[]", encoding="utf-8")
    (fake / "verification_records.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr("backend.tamper_demo.AUDIT_PATH", fake / "audit_events.json")
    monkeypatch.setattr("backend.tamper_demo.DATA_DIR", fake)
    monkeypatch.setattr("backend.database.DATA_DIR", str(fake))
    # Force the JsonStore caches to point at the fake files.
    for store_name in ("parcels", "transactions", "documents", "mutations", "tax_records", "owners", "verification_records", "audit_events"):
        store = getattr(database, store_name)
        store.path = fake / f"{store_name}.json"
        store._cache = None

    from backend import tamper_demo
    rc = tamper_demo.main()
    out = capsys.readouterr().out
    assert "BEFORE" in out
    assert "AFTER TAMPER" in out
    assert "RESTORED" in out
    assert "first invalid sequence = 3" in out
    assert rc == 0
    # Verify the audit file was actually restored to empty.
    assert (fake / "audit_events.json").read_text(encoding="utf-8") == "[]"


def test_chain_verifier_reports_invalid_after_tampering():
    """Smaller test: mutate a stored event and ensure verify_chain flags it."""
    for i in range(3):
        append_event(event_type="T", parcel_id="P", actor="alice", payload={"i": i})
    raw = database.audit_events.all()
    raw[1]["payload"]["note"] = "TAMPER"
    database.audit_events.save(raw)
    result = verify_chain()
    assert result["valid"] is False
    assert result["first_invalid_sequence"] == 2