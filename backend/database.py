"""Database access layer for LandGuard.

Loads every JSON-backed store used by the prototype (parcels, transactions,
documents, mutations, tax, owners, verification findings, audit events) and
exposes small query helpers. File-based for the prototype — swap for
PostgreSQL/PostGIS later.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class JsonStore:
    """Thread-safe lazy loader for a single JSON file.

    - `load()` re-reads from disk; call after writes to refresh state.
    - `all()` returns the parsed collection (empty list if file missing).
    - `save()` writes atomically via a temp file.
    """

    def __init__(self, filename: str, default: list[dict[str, Any]] | None = None) -> None:
        self.path = DATA_DIR / filename
        self._default = default or []
        self._cache: list[dict[str, Any]] | None = None
        self._lock = Lock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return list(self._default)
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._cache is None:
                self._cache = self._read()
            return list(self._cache)

    def load(self) -> list[dict[str, Any]]:
        with self._lock:
            self._cache = self._read()
            return list(self._cache)

    def save(self, records: list[dict[str, Any]]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            # On Windows, antivirus / indexer services occasionally hold
            # a brief handle on the target file. os.replace is atomic
            # when it works, but it surfaces a WinError 5 immediately.
            # A short retry loop absorbs that flake without changing the
            # semantics: each attempt is still an atomic rename.
            last_err: Exception | None = None
            for attempt in range(5):
                try:
                    tmp.replace(self.path)
                    break
                except PermissionError as e:
                    last_err = e
                    import time as _t
                    _t.sleep(0.05 * (attempt + 1))
            else:
                raise last_err or RuntimeError("save: atomic rename failed")
            self._cache = list(records)


# Module-level stores — re-used across the app.
parcels = JsonStore("parcels.json", default=[])
transactions = JsonStore("transactions.json", default=[])
documents = JsonStore("documents.json", default=[])
mutations = JsonStore("mutations.json", default=[])
tax_records = JsonStore("tax_records.json", default=[])
owners = JsonStore("owners.json", default=[])
verification_records = JsonStore("verification_records.json", default=[])
audit_events = JsonStore("audit_events.json", default=[])


# ---------- Query helpers ----------

def find_parcel(parcel_id: str) -> dict[str, Any] | None:
    for record in parcels.all():
        if record.get("parcel_id") == parcel_id:
            return record
    return None


def find_parcels_by_owner(identifier: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in parcels.all():
        for ref in p.get("owner_references", []):
            if ref.get("identifier") == identifier:
                out.append(p)
                break
    return out


def documents_for_parcel(parcel_id: str) -> list[dict[str, Any]]:
    return [d for d in documents.all() if d.get("parcel_id") == parcel_id]


def transactions_for_parcel(parcel_id: str) -> list[dict[str, Any]]:
    return [t for t in transactions.all() if t.get("parcel_id") == parcel_id]


def mutations_for_parcel(parcel_id: str) -> list[dict[str, Any]]:
    return [m for m in mutations.all() if m.get("parcel_id") == parcel_id]


def tax_records_for_parcel(parcel_id: str) -> list[dict[str, Any]]:
    return [t for t in tax_records.all() if t.get("parcel_id") == parcel_id]


def owner_lookup(identifier: str) -> dict[str, Any] | None:
    for o in owners.all():
        if o.get("identifier") == identifier:
            return o
    return None