"""Pydantic request/response schemas.

Kept thin for the prototype — the JSON store is the source of truth, and
these schemas only describe what crosses the HTTP boundary.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    parcel_id: str = Field(..., description="Canonical parcel id, e.g. 'DHK-MIR-001'")
    claimed_owner_nid: str = Field(..., min_length=10, max_length=17)


class VerifyResponse(BaseModel):
    parcel_id: str
    is_valid: bool
    risk_score: float = Field(..., ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)
    owner_match: bool
    encumbrances: list[dict[str, Any]] = Field(default_factory=list)
    last_transfer_date: str | None = None
    recommendations: list[str] = Field(default_factory=list)


class TransferRequest(BaseModel):
    parcel_id: str
    from_nid: str
    to_nid: str
    sale_price_bdt: float = Field(..., gt=0)
    stamp_duty_bdt: float = Field(..., ge=0)
