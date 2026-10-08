"""Reset LANDGUARD demo data to its canonical, deterministic state.

Repeated `/api/parcels/{id}/verify` calls mutate two files:
- `data/audit_events.json` (append)
- `data/verification_records.json` (upsert per rule)

This script restores BOTH to empty, and re-stamps document hashes so
the HASH-MISMATCH scenario is always exactly as advertised.

Run with:
    python -m backend.reset
"""
from __future__ import annotations

import json
from pathlib import Path

from . import database
from .services.verification.rules.document_integrity import compute_document_hash

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCS_PATH = DATA_DIR / "documents.json"
DELIBERATELY_TAMPERED = "DOC-DHK-SAV-009-D1"
WRONG_HASH = "0" * 64


def _reseed_document_hashes() -> int:
    """(Re)stamp every document's hash. Tampered one stays wrong."""
    raw = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
    changed = 0
    for doc in raw:
        if doc.get("document_id") == DELIBERATELY_TAMPERED:
            if doc.get("document_hash") != WRONG_HASH:
                doc["document_hash"] = WRONG_HASH
                changed += 1
            continue
        correct = compute_document_hash(doc)
        if doc.get("document_hash") != correct:
            doc["document_hash"] = correct
            changed += 1
    DOCS_PATH.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return changed


def reset() -> dict[str, int]:
    """Restore canonical demo state. Returns a count summary."""
    _reseed_document_hashes()

    database.verification_records.save([])
    database.audit_events.save([])
    database.verification_records.load()
    database.audit_events.load()
    database.documents.load()

    return {
        "parcels": len(database.parcels.all()),
        "transactions": len(database.transactions.all()),
        "documents": len(database.documents.all()),
        "mutations": len(database.mutations.all()),
        "tax_records": len(database.tax_records.all()),
        "owners": len(database.owners.all()),
        "verification_records": 0,
        "audit_events": 0,
    }


def main() -> int:
    counts = reset()
    print("LANDGUARD demo data reset to canonical state:")
    for k, v in counts.items():
        print(f"  {k:>22}: {v}")
    print()
    print("Audit chain cleared. Run a parcel through /verify to repopulate.")
    print(f"Deliberately-tampered document: {DELIBERATELY_TAMPERED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())