"""Domain model definitions for LandGuard.

Centralizes the data classes shared by the API layer and the verification
engine. Keeps the JSON store decoupled from the schemas exposed to the
frontend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Parcel:
    parcel_id: str
    district: str
    upazila: str
    mouza: str
    survey_no: str
    owner_nid: str
    owner_name: str
    area_sqm: float
    geometry: dict[str, Any]  # GeoJSON-style polygon
    recorded_value_bdt: float
    last_transfer_date: str | None = None
    encumbrances: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Transaction:
    txn_id: str
    parcel_id: str
    from_nid: str
    to_nid: str
    sale_price_bdt: float
    stamp_duty_bdt: float
    registration_date: str
    status: str  # "pending" | "verified" | "flagged" | "rejected"
    flags: list[str] = field(default_factory=list)
