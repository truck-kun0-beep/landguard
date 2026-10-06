"""Tamper-evident record hashing for the verification engine.

Each parcel + transaction record gets a SHA-256 content hash. The hash
chain lets the frontend show "this record hasn't been altered since it
was issued" — the cheap, prototype-grade equivalent of a real
blockchain-backed land registry.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def content_hash(record: dict[str, Any]) -> str:
    """Stable SHA-256 hash of a record's canonical JSON form."""
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def chain_hash(records: list[dict[str, Any]], field: str = "record_hash") -> str:
    """Hash an entire collection so any mutation is detectable.

    Each record's `field` is folded into a running hash along with its index.
    """
    running = hashlib.sha256(b"landguard:genesis")
    for idx, record in enumerate(records):
        h = record.get(field) or content_hash(record)
        running.update(f"{idx}:{h}".encode("utf-8"))
    return running.hexdigest()


def verify_chain(records: list[dict[str, Any]], field: str = "record_hash") -> bool:
    """True iff every record's stored hash still matches its content."""
    return all(record.get(field) == content_hash(record) for record in records)
