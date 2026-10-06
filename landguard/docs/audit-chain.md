# LANDGUARD — Cryptographic Audit Chain

## What the audit chain is

Every important action LANDGUARD performs is recorded as an **audit
event** in `data/audit_events.json`. The events are stitched together
with cryptographic hashes so any later change to a past event is
detectable by recomputing the chain.

In short: it's an **append-only hash-chained log**.

```
event 1                 event 2                 event 3
+--------------+        +--------------+        +--------------+
| previous = G |  --->  | previous = h1|  --->  | previous = h2|
| current = h1 |        | current = h2 |        | current = h3 |
+--------------+        +--------------+        +--------------+
       |                       |                       |
       +------- h1 depends on event 1's content -------+
               h2 depends on (h1 || event 2's content)
               h3 depends on (h2 || event 3's content)
```

`G` is a well-known sentinel (`"0" * 64`, the genesis previous-hash).
It is documented and stable so anyone running `verify_chain()` knows
what to expect at the head of the chain.

## Why normal audit logs can be modified

A plain JSON log file is just text. Anyone with filesystem access can:

- change a payload (e.g. rewrite a risk score)
- change a recorded timestamp
- delete an event that was inconvenient
- reorder events to hide what happened first
- forge a fake "current_event_hash" to make the file look consistent

There is no built-in way to tell whether the file you are looking at
still matches the events that actually happened.

## How `previous_event_hash` works

Every event stores the `current_event_hash` of the event immediately
before it. So the chain forms a single forward-linked list:

```
event N-1.current_event_hash == event N.previous_event_hash
```

If you delete or reorder events, this equality breaks at the first
affected link, and the chain verifier reports the exact sequence
number that no longer matches.

## How `current_event_hash` is calculated

For an event with all fields except `current_event_hash` itself:

1. Build the **canonical JSON** of the hash-relevant fields
   (`sequence_number`, `event_id`, `event_type`, `parcel_id`, `actor`,
   `timestamp`, `payload`, `previous_event_hash`) using
   `sort_keys=True` and `separators=(",", ":")`.
2. Decode `previous_event_hash` from hex to raw bytes.
3. Concatenate `previous_bytes || canonical_json_bytes`.
4. `current_event_hash = SHA-256(...)` as 64 lowercase hex characters.

`current_event_hash` is intentionally **not** part of the canonical
input — that would make the hash depend on itself and break the
algorithm.

```python
canonical_event_bytes = json.dumps(
    {field: event[field] for field in HASH_FIELDS},
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")

previous_bytes = bytes.fromhex(event["previous_event_hash"])
current_event_hash = sha256(previous_bytes + canonical_event_bytes).hexdigest()
```

## What tampering looks like

| Tampering | Detection mechanism |
|---|---|
| Editing a payload (e.g. flipping a `risk_score`) | recomputed hash no longer matches stored `current_event_hash` for that event |
| Editing `current_event_hash` of any event | recomputed hash differs from stored value |
| Editing `previous_event_hash` of event N | sequence N's stored prev ≠ event N-1's stored current |
| Deleting a middle event | every later event's stored prev ≠ previous event's stored current |
| Swapping two events | every swapped event's stored prev ≠ previous event's stored current |

In every case `verify_chain()` returns:

```json
{
  "valid": false,
  "event_count": 5,
  "first_invalid_sequence": 3,
  "error": "event 3 current_event_hash does not match recomputed SHA-256"
}
```

The `first_invalid_sequence` field tells the operator exactly where
the chain broke so they can investigate that event first.

## How LANDGUARD detects it

There is exactly one function that appends to the chain —
`audit.append_event()` — and one function that verifies it —
`audit.verify_chain()`. Every other piece of code (the verification
endpoint, the transfer endpoint, any future tooling) goes through
`append_event()`. The chain is therefore maintained in a single place
and verified through a single function.

## Why this is tamper-evident rather than blockchain

This is **not blockchain**:

- No consensus protocol
- No peer-to-peer network
- No proof of work, proof of authority, or any consensus mechanism
- No external services or dependencies

It is just SHA-256 + a forward-linked list, written to a JSON file.

What this gives you:

- Any modification, deletion, or reordering of stored events is
  detectable through recomputation.
- The first tampered event is identified by sequence number.

What this does **not** give you:

- Resistance against an attacker who can rewrite the *entire* file
  and recompute the hashes themselves (they can forge a consistent
  fake chain). To defend against that you need either a separate
  trusted publication channel (e.g. publish the chain head to a
  third-party timestamping service) or a true distributed ledger.
- Resistance against deletion of the whole file. The chain only
  detects tampering of the events that still exist.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/audit` | Return every audit event, in sequence order |
| `GET /api/audit/verify` | Independently recompute and verify the whole chain |
| `GET /api/parcels/{parcel_id}/audit` | Audit events for one parcel |
| `GET /api/integrity` | Lightweight summary that includes audit chain status |

## Code map

| Module | Role |
|---|---|
| `backend/services/audit/chain.py` | Canonical serialization, hashing, append, verify |
| `backend/services/audit/__init__.py` | Public API |
| `backend/services/persistence.py` | `record_audit_event()` — the single caller-facing entry point |
| `backend/main.py` | HTTP endpoints |
| `tests/test_audit_chain.py` | 5 tamper cases + canonicalization + append + verify + API + legacy migration |
| `docs/audit-chain.md` | This file |

## Limitations

- **Local chain only.** Anyone with write access to `audit_events.json`
  can rewrite the whole file and produce a valid-looking chain. The
  design does not attempt to defend against that.
- **No external timestamping.** A trusted third party (audit log
  service, government archive) would be needed to prove the chain
  existed at a particular point in time.
- **JSON storage.** For a production deployment, an append-only
  database or signed log service would replace this file. The chain
  algorithm itself does not change.
- **Schema-level trust.** Like any database, the schema and parser must
  match for verification to be meaningful. A future attacker who can
  change the parser code can also change what "verified" means.