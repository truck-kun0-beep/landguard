"""One-shot seeder for document integrity hashes.

Run with: `python -m backend.seed`

For every document in `data/documents.json`:
- If `document_hash` is "pending" or missing, compute SHA-256 over its
  canonical payload and write it back.
- For the deliberate hash-mismatch demo (DOC-DHK-SAV-009-D1) write a
  wrong hash so the integrity rule can discover the mismatch by
  recomputation.

This script does NOT know what the integrity rule computes. It just
writes a hash; the rule reads the hash and independently recomputes.
"""
from __future__ import annotations

from pathlib import Path
import json

from .services.verification.rules.document_integrity import compute_document_hash

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCS_PATH = DATA_DIR / "documents.json"
DELIBERATELY_TAMPERED = "DOC-DHK-SAV-009-D1"
WRONG_HASH = "0" * 64  # visibly wrong, but rule never reads this constant


def main() -> int:
    raw_docs = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
    changed = 0
    for doc in raw_docs:
        doc_id = doc.get("document_id")
        stored = doc.get("document_hash")
        if doc_id == DELIBERATELY_TAMPERED:
            # Persist a wrong hash; the integrity rule will recompute and
            # detect the mismatch organically.
            if stored != WRONG_HASH:
                doc["document_hash"] = WRONG_HASH
                changed += 1
            continue
        if not stored or stored == "pending":
            doc["document_hash"] = compute_document_hash(doc)
            changed += 1
    if changed:
        DOCS_PATH.write_text(
            json.dumps(raw_docs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(f"Seeded {changed} document hash(es); total documents: {len(raw_docs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())