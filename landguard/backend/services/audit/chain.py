"""Cryptographic audit chain.

Design (kept deliberately simple for a hackathon demo):

- Every audit event has a `sequence_number` and a `previous_event_hash`.
- The genesis event's `previous_event_hash` is the well-known sentinel
  `GENESIS_PREV_HASH` (64 zeros). It is documented and stable, so any
  rebuild or migration can recognise it without ambiguity.
- `canonical_event(event_without_hash)` returns a deterministic JSON
  representation of every hash-relevant field of an event using
  `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
- `current_event_hash = SHA-256(previous_event_hash_bytes || canonical_event_bytes)`.
  SHA-256 produces 64 lowercase hex characters.
- `current_event_hash` is NOT part of the canonical input (no self-reference).
- `append_event()` is the single function that allocates the next slot,
  fills in `previous_event_hash`, computes `current_event_hash`, and
  persists the result.
- `verify_chain()` walks every stored event and independently recomputes
  every hash. It returns a structured result so callers can show
  *where* the chain failed.

This is NOT blockchain. There is no consensus, no P2P layer, no proof
of work. It is a local append-only hash chain over a JSON file. Anyone
with filesystem write access to `audit_events.json` can still truncate
or rewrite the file; this layer guarantees only that any such change
is detectable through recomputation.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ... import database

# Fields that participate in the hash. Everything else is excluded.
HASH_FIELDS = (
    "sequence_number",
    "event_id",
    "event_type",
    "parcel_id",
    "actor",
    "timestamp",
    "payload",
    "previous_event_hash",
)

# 64 hex zeros — chosen so genesis is unambiguous in any verifier output
# and trivially distinguishable from a real SHA-256 hash.
GENESIS_PREV_HASH = "0" * 64


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_event(event_without_hash: dict[str, Any]) -> str:
    """Deterministic JSON of every hash-relevant field.

    `current_event_hash` is intentionally excluded so that hashing the
    event does not require its own hash (no self-reference).
    """
    payload = {field: event_without_hash.get(field) for field in HASH_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_event_hash(event_without_hash: dict[str, Any]) -> str:
    """SHA-256 over (previous_event_hash || canonical_event).

    The previous hash is included as raw bytes (hex decoded) so that
    flipping a hex digit changes the hash deterministically.
    """
    prev = event_without_hash.get("previous_event_hash") or GENESIS_PREV_HASH
    prev_bytes = bytes.fromhex(prev)
    body = canonical_event(event_without_hash).encode("utf-8")
    return hashlib.sha256(prev_bytes + body).hexdigest()


def _normalize_existing(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise an event dict read from the legacy store.

    Older records used `seq` and `actor_reference`. We accept both and
    map them onto the canonical field names so the chain code never
    has to branch.
    """
    out: list[dict[str, Any]] = []
    for e in events:
        out.append(
            {
                "event_id": e.get("event_id"),
                "sequence_number": e.get("sequence_number", e.get("seq")),
                "event_type": e.get("event_type"),
                "parcel_id": e.get("parcel_id"),
                "actor": e.get("actor", e.get("actor_reference")),
                "timestamp": e.get("timestamp"),
                "payload": e.get("payload", {}),
                "previous_event_hash": e.get("previous_event_hash"),
                "current_event_hash": e.get("current_event_hash"),
            }
        )
    return out


def _is_initialized(events: list[dict[str, Any]]) -> bool:
    """True if at least one event already carries a real chain hash."""
    return any(
        e.get("current_event_hash")
        and e["current_event_hash"] != GENESIS_PREV_HASH
        for e in events
    )


def _normalise_existing(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise an event dict read from the legacy store.

    Older records used `seq` and `actor_reference`. We accept both and
    map them onto the canonical field names so the chain code never
    has to branch.
    """
    out: list[dict[str, Any]] = []
    for e in events:
        out.append(
            {
                "event_id": e.get("event_id"),
                "sequence_number": e.get("sequence_number", e.get("seq")),
                "event_type": e.get("event_type"),
                "parcel_id": e.get("parcel_id"),
                "actor": e.get("actor", e.get("actor_reference")),
                "timestamp": e.get("timestamp"),
                "payload": e.get("payload", {}),
                "previous_event_hash": e.get("previous_event_hash"),
                "current_event_hash": e.get("current_event_hash"),
            }
        )
    return out


def _rechain_from_scratch(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-link a pre-chain list of events into a fresh chain.

    Order is preserved exactly as stored. Sequence numbers are
    renumbered 1..N so any gaps in the legacy data are removed. This is
    the only place the chain can rewrite historical hashes; callers
    always go through `append_event`.
    """
    chained: list[dict[str, Any]] = []
    prev_hash = GENESIS_PREV_HASH
    normalised = _normalise_existing(events)
    for idx, raw in enumerate(normalised, start=1):
        event = deepcopy(raw)
        event["sequence_number"] = idx
        event["previous_event_hash"] = prev_hash
        event["current_event_hash"] = compute_event_hash(event)
        prev_hash = event["current_event_hash"]
        chained.append(event)
    return chained


def _load_chain() -> list[dict[str, Any]]:
    """Return the normalised chain, migrating pre-chain data if needed."""
    raw = database.audit_events.all()
    normalised = _normalise_existing(raw)
    if not normalised:
        return []
    if _is_initialized(normalised):
        return normalised
    # Pre-chain legacy data — rebuild from scratch.
    return _rechain_from_scratch(raw)


def append_event(
    *,
    event_type: str,
    parcel_id: str | None,
    actor: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Append exactly one event to the chain.

    Loads the current chain (auto-migrating legacy data), computes the
    next sequence number, links it to the previous hash, canonicalises
    it, computes `current_event_hash`, and persists.

    Returns the fully-formed event dict (including both hash fields).
    """
    chain = _load_chain()
    seq = (chain[-1]["sequence_number"] if chain else 0) + 1
    previous_hash = chain[-1]["current_event_hash"] if chain else GENESIS_PREV_HASH

    event_id = f"EVT-{seq:05d}"
    event: dict[str, Any] = {
        "event_id": event_id,
        "sequence_number": seq,
        "event_type": event_type,
        "parcel_id": parcel_id,
        "actor": actor,
        "timestamp": _now_iso(),
        "payload": payload,
        "previous_event_hash": previous_hash,
    }
    event["current_event_hash"] = compute_event_hash(event)

    # Normalise any legacy rows still in storage so the on-disk file
    # shape is consistent (no half-migrated records).
    existing = database.audit_events.all()
    existing_normalised = _normalise_existing(existing)
    migrated: list[dict[str, Any]] = []
    if existing and not _is_initialized(existing_normalised):
        migrated = _rechain_from_scratch(existing)
    elif existing:
        migrated = existing_normalised

    database.audit_events.save(migrated + [event])
    return event


def verify_chain(events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Independently re-derive every hash and report the result.

    Always loads fresh from storage unless `events` is provided (used by
    tests to validate tampering in-memory).

    Returns:
        {
            "valid": bool,
            "event_count": int,
            "first_invalid_sequence": int | None,
            "error": str | None,
        }
    """
    if events is None:
        events = _load_chain()

    if not events:
        return {
            "valid": True,
            "event_count": 0,
            "first_invalid_sequence": None,
            "error": None,
        }

    # Normalise in case the caller hands us raw legacy data.
    chain = _normalise_existing(events)

    # Sequence continuity.
    expected_seq = 1
    for ev in chain:
        if ev.get("sequence_number") != expected_seq:
            return {
                "valid": False,
                "event_count": len(chain),
                "first_invalid_sequence": ev.get("sequence_number"),
                "error": (
                    f"sequence gap or out-of-order entry: expected {expected_seq}, "
                    f"got {ev.get('sequence_number')}"
                ),
            }
        expected_seq += 1

    # Genesis linkage.
    first = chain[0]
    if first.get("previous_event_hash") not in (None, GENESIS_PREV_HASH):
        return {
            "valid": False,
            "event_count": len(chain),
            "first_invalid_sequence": first.get("sequence_number"),
            "error": "first event has non-genesis previous_event_hash",
        }

    # Per-event hash + link integrity.
    expected_prev = GENESIS_PREV_HASH
    for ev in chain:
        stored_prev = ev.get("previous_event_hash")
        if stored_prev != expected_prev:
            return {
                "valid": False,
                "event_count": len(chain),
                "first_invalid_sequence": ev.get("sequence_number"),
                "error": (
                    f"event {ev.get('sequence_number')} previous_event_hash "
                    f"does not match event {ev.get('sequence_number') - 1} "
                    "current_event_hash"
                ),
            }
        recomputed = compute_event_hash(ev)
        if recomputed != ev.get("current_event_hash"):
            return {
                "valid": False,
                "event_count": len(chain),
                "first_invalid_sequence": ev.get("sequence_number"),
                "error": (
                    f"event {ev.get('sequence_number')} current_event_hash "
                    "does not match recomputed SHA-256"
                ),
            }
        expected_prev = ev.get("current_event_hash")

    return {
        "valid": True,
        "event_count": len(chain),
        "first_invalid_sequence": None,
        "error": None,
    }