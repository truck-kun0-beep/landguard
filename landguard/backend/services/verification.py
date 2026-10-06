"""Fake Bangladesh government API surface.

These are the read-only endpoints a real product would call against
- e-Government NID (NID Wing)
- Digital Land Record System (DLRS / ভূমি)
- Sub-Registrar's stamp duty register

We model them as in-process functions backed by the JSON store so the
rest of the system can be developed and tested without network calls.
Swap each function for an HTTP client when the real APIs are wired up.
"""
from __future__ import annotations

import re
from typing import Any

from .. import database

# Bangladesh NID is 10 or 13 (legacy) or 17 digits. The 17-digit form is the
# current standard; we accept both but normalize.
_NID_RE = re.compile(r"^\d{10}$|^\d{13}$|^\d{17}$")


def is_valid_nid(nid: str) -> bool:
    """Quick format check. A real API would also verify the check digit."""
    return bool(nid) and bool(_NID_RE.match(nid))


def fetch_nid_record(nid: str) -> dict[str, Any] | None:
    """Pretend to call the NID Wing. Returns the linked owner profile, if any.

    In reality this is an HTTP call. Here we just find every parcel where
    `owner_nid` matches and synthesize a profile.
    """
    if not is_valid_nid(nid):
        return None
    owned = database.find_parcels_by_owner(nid)
    if not owned:
        return None
    first = owned[0]
    return {
        "nid": nid,
        "name": first.get("owner_name"),
        "verified": True,
        "issued_at": "2018-04-12",
        "parcel_ids": [p["parcel_id"] for p in owned],
    }


def fetch_land_record(parcel_id: str) -> dict[str, Any] | None:
    """Pretend to call DLRS for a parcel's canonical record."""
    return database.find_parcel(parcel_id)


def fetch_recent_transfers(parcel_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return the most recent transfer attempts for a parcel, newest first."""
    matching = [t for t in database.transactions.all() if t.get("parcel_id") == parcel_id]
    matching.sort(key=lambda t: t.get("registration_date", ""), reverse=True)
    return matching[:limit]
