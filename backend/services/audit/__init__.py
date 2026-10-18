"""Tamper-evident audit chain for LANDGUARD.

Public API:
    canonical_event(event)            stable JSON string used for hashing
    compute_event_hash(event)         SHA-256 of (prev || canonical_event)
    append_event(event_type, ...)      the only sanctioned way to add events
    verify_chain(events)               independently recheck every link
"""
from __future__ import annotations

from .chain import (
    GENESIS_PREV_HASH,
    append_event,
    canonical_event,
    compute_event_hash,
    verify_chain,
)

__all__ = [
    "GENESIS_PREV_HASH",
    "append_event",
    "canonical_event",
    "compute_event_hash",
    "verify_chain",
]