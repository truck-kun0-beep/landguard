"""Evidence collection service.

Aggregates evidence from every source for one parcel, wraps each piece
in a `SourcedEvidence` (so later findings can attribute themselves to a
specific source), and returns a unified `EvidenceBundle`.

This service does NOT perform any verification — that's the
VerificationEngine's job.
"""
from __future__ import annotations

from .. import database
from .verification.types import EvidenceBundle, SourcedEvidence


SOURCES = ["KHATIAN", "MOCK_REGISTRATION", "MOCK_MUTATION", "MOCK_TAX", "MOCK_GIS"]


def collect_parcel_evidence(parcel_id: str) -> EvidenceBundle:
    parcel = database.find_parcel(parcel_id)
    if parcel is None:
        raise LookupError(parcel_id)

    ownerships = [
        SourcedEvidence(
            source="KHATIAN",
            record_type="OWNERSHIP",
            data={
                "parcel_id": parcel_id,
                "owner_references": parcel.get("owner_references", []),
            },
        )
    ]

    registration = [
        SourcedEvidence(
            source="MOCK_REGISTRATION",
            record_type="DEED",
            data=doc,
        )
        for doc in database.documents_for_parcel(parcel_id)
        if doc.get("document_type") == "DEED"
    ]

    mutation = [
        SourcedEvidence(
            source="MOCK_MUTATION",
            record_type="MUTATION",
            data=m,
        )
        for m in database.mutations_for_parcel(parcel_id)
    ]

    tax = [
        SourcedEvidence(
            source="MOCK_TAX",
            record_type="TAX_RECORD",
            data=t,
        )
        for t in database.tax_records_for_parcel(parcel_id)
    ]

    gis = [
        SourcedEvidence(
            source="MOCK_GIS",
            record_type="GIS",
            data={
                "parcel_id": parcel_id,
                "area_decimal": parcel.get("gis_area_decimal"),
                "geometry": parcel.get("geometry_geojson"),
            },
        )
    ]

    documents = [
        SourcedEvidence(
            source="MOCK_REGISTRATION",
            record_type=doc.get("document_type", "OTHER"),
            data=doc,
        )
        for doc in database.documents_for_parcel(parcel_id)
    ]

    transactions = database.transactions_for_parcel(parcel_id)

    return EvidenceBundle(
        parcel=parcel,
        ownerships=ownerships,
        registration=registration,
        mutation=mutation,
        tax=tax,
        gis=gis,
        documents=documents,
        transactions=transactions,
        sources=list(SOURCES),
    )