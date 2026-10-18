# LANDGUARD — Architecture

A short note on how the pieces fit together. The shape of the system is
the deliverable; the synthetic dataset is a stand-in.

## Parcel-centric evidence graph

```
                          PARCEL
                            |
        +-------------------+--------------------+
        |                   |                    |
        v                   v                    v
   OWNERSHIP             DOCUMENTS          TRANSACTIONS
        |                   |                    |
        +---------+---------+---------+----------+
                  |                   |
                  v                   v
              MUTATION               TAX
                  |                   |
                  +---------+---------+
                            |
                            v
                           GIS
                            |
                            v
                      VERIFICATION
                            |
                            v
                       AUDIT CHAIN
```

The parcel is the central entity. Every other table references a parcel by
its canonical `parcel_id`. Ownership is intentionally many-to-many
through `parcel_ownerships` so co-ownership is a first-class concept.

## Layered backend

```
FastAPI  ─►  api/routes/*.py   (thin)
            services/evidence_service.py      (collects evidence per parcel)
            services/verification/engine.py   (runs all 7 rules)
            services/verification/scoring.py  (risk score + status mapping)
            services/verification/rules/*       (one file per rule)
            services/audit/chain.py           (canonical JSON + SHA-256 + chain)
            services/persistence.py           (upsert findings + append audit)
            database.py                       (JSON store)
```

Rules are pure functions over an `EvidenceBundle` dataclass. The
`VerificationEngine` runs them in a stable order and produces
`VerificationFinding` records. Findings are persisted with
`(parcel_id, rule_code)` upsert so repeated runs never grow unbounded.

## Frontend

```
frontend/
  index.html      landing + product briefing
  dashboard.html  metrics, scenario picker, map, parcel list
  parcel.html     Land Passport (identity, verification, evidence,
                  ownership, documents, transactions, mutations, tax,
                  audit trail)
  verify.html     search + map preview

  js/
    api.js        LandGuard client (fetch wrapper)
    layout.js     shared top nav, status pills, helpers
    map.js        Leaflet integration
    dashboard.js  dashboard page logic
    parcel.js     Land Passport logic
    verify.js     search + map logic

  css/main.css    design system (one stylesheet, design tokens via
                  :root CSS variables)
```

The frontend is plain HTML + vanilla JS. Leaflet is loaded from the
public CDN with no build step.

## Audit chain design

Every audit event carries:

- `sequence_number` (monotonically increasing from 1)
- `previous_event_hash` (64 lowercase hex SHA-256; the well-known
  genesis value for the first event)
- `current_event_hash` = `SHA-256(previous_event_hash || canonical_event)`

`canonical_event` is the deterministic JSON of every hash-relevant field,
serialized with `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
`current_event_hash` is intentionally excluded from the canonical form so
the hash does not depend on itself.

The chain is verified by recomputing every hash from scratch and checking
that:
1. Sequence numbers are continuous.
2. Genesis is recognised.
3. Each event's `previous_event_hash` matches the previous event's
   `current_event_hash`.
4. Each event's `current_event_hash` matches the recomputed SHA-256.

Verification returns a structured `{valid, event_count,
first_invalid_sequence, error}` so the UI can show exactly where the
chain broke.

## What this is not

- Not blockchain. No consensus, no peer network, no proof of work.
- Not a real cadastral system. Polygon coordinates are placeholders.
- Not a legal decision engine. Output language is intentionally about
  "potential inconsistencies" and "review required", never "fraud
  confirmed" or "legal owner".