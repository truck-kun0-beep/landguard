"""Fraud / risk scoring rules for land transactions.

Pure functions over a `(parcel, claimed_owner_nid, txn?)` tuple so they
can be unit-tested without FastAPI. Each rule returns a `(flag, weight)`
pair; the verification engine sums weights into a `risk_score` in
`[0.0, 1.0]`.
"""
from __future__ import annotations

from typing import Any

# Each rule contributes at most this much to the final risk score.
_MAX_RULE_WEIGHT = 0.4


def _flag(flag: str, weight: float) -> tuple[str, float]:
    return flag, min(weight, _MAX_RULE_WEIGHT)


def rule_owner_mismatch(parcel: dict[str, Any], claimed_nid: str) -> tuple[str, float] | None:
    """Hardest signal: claimed NID does not equal the recorded owner NID."""
    if parcel.get("owner_nid") != claimed_nid:
        return _flag("OWNER_MISMATCH", 0.4)
    return None


def rule_duplicate_buyer(
    parcel: dict[str, Any], _claimed_nid: str, recent_txns: list[dict[str, Any]]
) -> tuple[str, float] | None:
    """Two or more pending transfers in the last 30 days — classic benami signal."""
    pending = [t for t in recent_txns if t.get("status") == "pending"]
    if len(pending) >= 2:
        return _flag("RAPID_SUCCESSION", 0.3)
    return None


def rule_undervalued(parcel: dict[str, Any], sale_price_bdt: float | None) -> tuple[str, float] | None:
    """Sale price below 60% of recorded value — common in laundering."""
    if sale_price_bdt is None or sale_price_bdt <= 0:
        return None
    recorded = parcel.get("recorded_value_bdt", 0)
    if recorded > 0 and sale_price_bdt < 0.6 * recorded:
        return _flag("UNDERVALUED_SALE", 0.25)
    return None


def rule_stamp_duty_mismatch(
    parcel: dict[str, Any], sale_price_bdt: float | None, stamp_duty_bdt: float | None
) -> tuple[str, float] | None:
    """Dhaka circle stamp duty on land is currently 7% for males, 5% for females.
    We use 5% as a conservative floor — anything below is suspicious.
    """
    if sale_price_bdt is None or stamp_duty_bdt is None:
        return None
    if sale_price_bdt <= 0:
        return None
    if stamp_duty_bdt < 0.05 * sale_price_bdt:
        return _flag("STAMP_DUTY_LOW", 0.2)
    return None


def rule_existing_encumbrance(parcel: dict[str, Any]) -> tuple[str, float] | None:
    """Outstanding mortgage or court order attached to the parcel."""
    if parcel.get("encumbrances"):
        return _flag("ENCUMBRANCE_PRESENT", 0.15)
    return None


ALL_RULES = [
    rule_owner_mismatch,
    rule_duplicate_buyer,
    rule_undervalued,
    rule_stamp_duty_mismatch,
    rule_existing_encumbrance,
]
