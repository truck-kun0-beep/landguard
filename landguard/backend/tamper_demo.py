"""Tamper-detection demo.

A safe, local-only demonstration of LANDGUARD's cryptographic audit
chain. It does NOT expose anything over HTTP. It:

  1. seeds an audit chain (5 events) if none exists,
  2. shows the chain is valid,
  3. tampers with one payload,
  4. shows the chain is now invalid at the tampered sequence,
  5. restores the original file from a snapshot.

Run with:
    python -m backend.tamper_demo

Always restores the file even on Ctrl+C.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import database
from .services.audit import append_event, verify_chain

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
AUDIT_PATH = DATA_DIR / "audit_events.json"


def _short(h: str | None) -> str:
    if not h:
        return "-"
    if h.startswith("0" * 8):
        return "GENESIS"
    return f"{h[:8]}..{h[-8:]}"


def _print_chain(label: str, result: dict) -> None:
    valid = "✓" if result["valid"] else "✕"
    print(f"  {label}: {valid} {result['event_count']} event(s)" +
          (f", first invalid sequence = {result['first_invalid_sequence']}"
           if not result["valid"] else ""))
    if not result["valid"]:
        print(f"        reason: {result['error']}")


def _seed_five_events() -> None:
    """Append 5 demo events to the chain (idempotent if already 5)."""
    existing = database.audit_events.all()
    if len(existing) >= 5:
        return
    for i in range(len(existing), 5):
        append_event(
            event_type="DEMO_TAMPER_WALK",
            parcel_id=f"LG-BD-DEMO-{i:03d}",
            actor="tamper-demo",
            payload={"step": i, "note": "synthetic demo event"},
        )


def _restore_backup(backup_path: Path) -> None:
    if backup_path.exists():
        shutil.copy(backup_path, AUDIT_PATH)
        backup_path.unlink()


def main() -> int:
    backup = DATA_DIR / "audit_events.json.bak"
    shutil.copy(AUDIT_PATH, backup)
    print("-> Snapshot saved to", backup.name, "(will be restored on exit).")

    try:
        database.audit_events.load()
        database.audit_events.save([])
        _seed_five_events()
        database.audit_events.load()

        print()
        print("BEFORE")
        before = verify_chain()
        _print_chain("chain status", before)

        # Tamper with the middle event's payload.
        events = database.audit_events.all()
        tampered_seq = 3  # middle of 5
        events[tampered_seq - 1]["payload"]["note"] = "MALICIOUS_TAMPER"
        database.audit_events.save(events)

        print()
        print("AFTER TAMPER")
        after = verify_chain()
        _print_chain("chain status", after)

        print()
        print("Showing the tampered event:")
        tampered = events[tampered_seq - 1]
        print(f"  sequence_number : {tampered.get('sequence_number')}")
        print(f"  event_type      : {tampered.get('event_type')}")
        print(f"  payload.note    : {tampered['payload']['note']}")
        print(f"  previous_event_hash: {_short(tampered.get('previous_event_hash'))}")
        print(f"  current_event_hash : {_short(tampered.get('current_event_hash'))}")

        print()
        if before["valid"] and not after["valid"] and after["first_invalid_sequence"] == tampered_seq:
            print("✓ Demonstration successful: chain rejected the tamper at the right link.")
            rc = 0
        else:
            print("✗ Demonstration result unexpected — see above.")
            rc = 1
        return rc
    finally:
        print()
        print("RESTORED")
        _restore_backup(backup)
        database.audit_events.load()
        restored = verify_chain()
        _print_chain("chain status", restored)


if __name__ == "__main__":
    raise SystemExit(main())