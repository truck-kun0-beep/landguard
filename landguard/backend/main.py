"""LandGuard backend.

FastAPI app exposing:
- /api/health
- /api/parcels                 list
- /api/parcels/{id}            detail
- /api/parcels/{id}/evidence   unified evidence bundle
- /api/parcels/{id}/documents  documents
- /api/parcels/{id}/transactions
- /api/parcels/{id}/mutations
- /api/parcels/{id}/tax
- /api/parcels/{id}/verify     POST → run engine, persist findings + audit
- /api/parcels/{id}/verification        GET → latest result
- /api/parcels/{id}/verification/findings GET → just the findings
- /api/transfers  POST
- /api/integrity  GET

Run with:
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .services import evidence_service, persistence
from .services.verification import VerificationEngine

app = FastAPI(title="LandGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = VerificationEngine()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "landguard"}


@app.get("/api/parcels")
def list_parcels() -> list[dict[str, Any]]:
    return database.parcels.all()


@app.get("/api/parcels/{parcel_id}")
def get_parcel(parcel_id: str) -> dict[str, Any]:
    parcel = database.find_parcel(parcel_id)
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@app.get("/api/parcels/{parcel_id}/evidence")
def get_evidence(parcel_id: str) -> dict[str, Any]:
    try:
        bundle = evidence_service.collect_parcel_evidence(parcel_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return bundle.to_dict()


@app.get("/api/parcels/{parcel_id}/documents")
def get_documents(parcel_id: str) -> list[dict[str, Any]]:
    if not database.find_parcel(parcel_id):
        raise HTTPException(status_code=404, detail="Parcel not found")
    return database.documents_for_parcel(parcel_id)


@app.get("/api/parcels/{parcel_id}/transactions")
def get_parcel_transactions(parcel_id: str) -> list[dict[str, Any]]:
    if not database.find_parcel(parcel_id):
        raise HTTPException(status_code=404, detail="Parcel not found")
    return database.transactions_for_parcel(parcel_id)


@app.get("/api/parcels/{parcel_id}/mutations")
def get_parcel_mutations(parcel_id: str) -> list[dict[str, Any]]:
    if not database.find_parcel(parcel_id):
        raise HTTPException(status_code=404, detail="Parcel not found")
    return database.mutations_for_parcel(parcel_id)


@app.get("/api/parcels/{parcel_id}/tax")
def get_parcel_tax(parcel_id: str) -> list[dict[str, Any]]:
    if not database.find_parcel(parcel_id):
        raise HTTPException(status_code=404, detail="Parcel not found")
    return database.tax_records_for_parcel(parcel_id)


@app.post("/api/parcels/{parcel_id}/verify")
def verify(parcel_id: str) -> dict[str, Any]:
    try:
        bundle = evidence_service.collect_parcel_evidence(parcel_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Parcel not found")

    result = engine.evaluate(bundle)
    persistence.persist_result(result)
    persistence.record_audit_event(
        parcel_id=parcel_id,
        event_type="VERIFICATION_COMPLETED",
        payload={
            "overall_status": result.overall_status.value,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level.value,
            "finding_count": result.finding_count,
            "rule_codes": [f.rule_code for f in result.findings],
        },
    )
    return result.to_dict()


@app.get("/api/parcels/{parcel_id}/verification")
def get_verification(parcel_id: str) -> dict[str, Any]:
    if not database.find_parcel(parcel_id):
        raise HTTPException(status_code=404, detail="Parcel not found")
    result = persistence.latest_result_for(parcel_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No verification recorded yet")
    return result


@app.get("/api/parcels/{parcel_id}/verification/findings")
def get_verification_findings(parcel_id: str) -> list[dict[str, Any]]:
    if not database.find_parcel(parcel_id):
        raise HTTPException(status_code=404, detail="Parcel not found")
    findings = persistence.latest_findings_for(parcel_id)
    if findings is None:
        raise HTTPException(status_code=404, detail="No verification recorded yet")
    return findings


@app.get("/api/transactions")
def list_transactions() -> list[dict[str, Any]]:
    return database.transactions.all()


@app.post("/api/transfers")
def create_transfer(payload: dict[str, Any]) -> dict[str, Any]:
    parcel_id = payload.get("parcel_id")
    parcel = database.find_parcel(parcel_id) if parcel_id else None
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    txn = {
        "txn_id": f"TXN-{len(database.transactions.all()) + 1:05d}",
        "parcel_id": parcel_id,
        "transaction_type": payload.get("transaction_type", "SALE"),
        "from_owner_reference": payload.get("from_owner_reference"),
        "to_owner_reference": payload.get("to_owner_reference"),
        "transferred_area_decimal": payload.get("transferred_area_decimal"),
        "transaction_date": payload.get("transaction_date"),
        "status": "PENDING",
        "reference_document_id": payload.get("reference_document_id"),
    }
    database.transactions.save(database.transactions.all() + [txn])

    # Auto-verify after new transfer.
    bundle = evidence_service.collect_parcel_evidence(parcel_id)
    result = engine.evaluate(bundle)
    persistence.persist_result(result)
    persistence.record_audit_event(
        parcel_id=parcel_id,
        event_type="TRANSACTION_CREATED",
        payload={"txn_id": txn["txn_id"]},
    )
    persistence.record_audit_event(
        parcel_id=parcel_id,
        event_type="VERIFICATION_COMPLETED",
        payload={
            "overall_status": result.overall_status.value,
            "risk_score": result.risk_score,
            "trigger": "TRANSFER_CREATED",
        },
    )
    return {"transaction": txn, "verification": result.to_dict()}


@app.get("/api/integrity")
def integrity() -> dict[str, Any]:
    """Inspect the persisted audit log + verification records.

    NOTE: this is the lightweight integrity view for the verification
    findings store. The tamper-evident hash chain over audit events is
    Milestone 04's job.
    """
    audits = database.audit_events.all()
    verifications = database.verification_records.all()
    return {
        "audit_events": {"count": len(audits)},
        "verification_records": {"count": len(verifications)},
    }