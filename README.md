# LANDGUARD

> **Digital Land Verification & Integrity Platform**
> A prototype for multi-source land-record verification, deterministic
> risk screening, and tamper-evident audit trails in Bangladesh.

[![Tests](https://img.shields.io/badge/tests-57%20passed-1d6f42)]()
[![Python](https://img.shields.io/badge/python-3.12%2B-0f4c81)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## Overview

Land records in Bangladesh live in many places &mdash; registration deeds,
mutations, land-tax rolls, Khatian registers, and GIS layers &mdash; maintained
by different authorities, often in isolation. Discrepancies between
these records are a major source of fraud, double transfers, and
contested ownership.

**LANDGUARD** treats the **parcel** as the central entity and correlates
every available record into a single, explainable verification result.
The system runs a deterministic rule engine over the evidence, produces
a transparent risk score, and seals every verification event into a
tamper-evident cryptographic audit chain.

```
        Land records          Adapters          Evidence            Rule engine         Cryptographic
        (deeds, mutations,    (per source)      bundle              (7 rules,           audit chain
         tax, Khatian, GIS)                     per parcel           score)              (SHA-256)
              |                  |                  |                   |                   |
              +-------&gt;-------+------&gt;-------+--------&gt;-----+--------&gt;----+
```

## Features

- **Multi-source evidence collection** &mdash; one bundle per parcel, sourced
  from registration, mutation, tax, Khatian, and GIS adapters.
- **Deterministic rule engine** &mdash; seven rules covering owner
  consistency, area agreement, document integrity, transfer overflow,
  duplicate transfers, and missing mutations.
- **Transparent risk scoring** &mdash; weighted findings produce a
  0&ndash;100 score and a `LOW / MEDIUM / HIGH / CRITICAL` level.
- **Tamper-evident audit chain** &mdash; every verification event is
  sealed with a SHA-256 hash linked to the previous event. Independent
  recomputation detects any modification, reordering, or deletion.
- **Land Passport UI** &mdash; per-parcel page with full evidence,
  findings, and audit trail.
- **Demo scenario picker** &mdash; seven hand-crafted cases that
  exercise each rule.
- **Demo data reset** &mdash; one command restores the canonical state.
- **Tamper-detection demo** &mdash; terminal walkthrough that mutates an
  audit event and shows the chain rejecting it.
- **Dark mode** &mdash; system-default plus a manual toggle, persisted
  in `localStorage`.
- **No build step** &mdash; the frontend is plain HTML / CSS / vanilla
  JS. Run from any Python interpreter.

## Quick start

```powershell
# 1. Install dependencies
python -m pip install fastapi uvicorn pydantic pytest httpx Pillow

# 2. Run the bundled server (API + frontend in one process)
python -m uvicorn serve_frontend:app --port 8000
```

Open one of these URLs in your browser:

| URL | What you'll see |
|---|---|
| <http://127.0.0.1:8000/frontend/index.html> | Landing page &amp; product briefing |
| <http://127.0.0.1:8000/frontend/dashboard.html> | System-wide verification dashboard |
| <http://127.0.0.1:8000/frontend/verify.html> | Parcel search |
| <http://127.0.0.1:8000/frontend/parcel.html?id=LG-BD-DHK-SAV-000001> | Sample Land Passport |
| <http://127.0.0.1:8000/docs> | Interactive API (Swagger UI) |

**Tip.** Set `LANDGUARD_NOCACHE=1` in the environment to disable HTTP
caching for frontend assets during development &mdash; you won't need to
hard-reload after every edit.

```powershell
$env:LANDGUARD_NOCACHE = "1"
python -m uvicorn serve_frontend:app --port 8000
```

## Verification rules

| Code | Severity | Purpose |
|---|---|---|
| `OWNER_MATCH` | CRITICAL | Each approved transfer's seller must appear in the recorded ownership evidence. |
| `AREA_MATCH` | CRITICAL | Parcel area must agree with Khatian and GIS areas (within tolerance). |
| `DEED_MUTATION_AREA_MATCH` | CRITICAL | Each approved deed's transferred area must match its mutation record. |
| `PARCEL_AREA_OVERFLOW` | CRITICAL | Sum of active approved transfers must not exceed the parcel area. |
| `DUPLICATE_TRANSFER` | CRITICAL | Two approved transfers selling overlapping area to different buyers. |
| `MISSING_MUTATION` | WARNING | An approved transfer exists with no corresponding mutation record. |
| `DOCUMENT_INTEGRITY` | CRITICAL | Stored document hash must match the recomputed SHA-256. |

Rule weights and severity mapping are documented in
`backend/services/verification/scoring.py`.

## Demo scenarios

The seed dataset ships with seven hand-crafted scenarios plus five
baseline parcels:

| Label | Parcel ID | Demonstrates |
|---|---|---|
| **CLEAN** | `LG-BD-DHK-SAV-000001` | Co-owned parcel; all rules pass. |
| **AREA MISMATCH** | `LG-BD-DHK-GAZ-000004` | Deed transferred area disagrees with mutation area. |
| **OWNER MISMATCH** | `LG-BD-DHK-NAR-000005` | Deed names a seller not in the ownership evidence. |
| **DOUBLE TRANSFER** | `LG-BD-CTG-PAH-000006` | Two approved transfers sell overlapping area. |
| **AREA OVERFLOW** | `LG-BD-DHK-GAZ-000007` | Active transfers sum to 11.00 against a 10.00 parcel. |
| **MISSING MUTATION** | `LG-BD-CHI-SAV-000008` | Approved deed has no mutation record. |
| **DOCUMENT HASH MISMATCH** | `LG-BD-DHK-SAV-000009` | Stored document hash disagrees with recomputed SHA-256. |

## Tamper-evident audit chain

Each event is hashed with `current_event_hash = SHA-256(
previous_event_hash || canonical_event)` where `canonical_event` is a
sorted-key JSON serialization. The first event's `previous_event_hash`
is the well-known `GENESIS_PREV_HASH` constant. The chain is verified
by recomputing every hash and checking sequence continuity, genesis,
linkage, and content integrity. A failed verification returns the exact
`first_invalid_sequence` and the failure reason.

Read the full specification: [`docs/audit-chain.md`](docs/audit-chain.md).

## Operations

| Command | Purpose |
|---|---|
| `python -m backend.reset` | Restore the canonical demo state. Re-stamps every document hash (the `HASH-MISMATCH` demo is always as advertised) and clears `audit_events.json` / `verification_records.json`. |
| `python -m backend.tamper_demo` | Run a self-contained walkthrough: seed 5 events &rarr; show chain valid &rarr; mutate one event &rarr; show chain invalid &rarr; restore. |
| `python -m backend.seed` | Re-seed document integrity hashes only. |
| `python -m pytest -q` | Run the test suite (57 tests). |

## Project structure

```
landguard/
├── backend/                          # FastAPI app
│   ├── main.py                       # API routes (parcels, evidence, verify, audit, integrity)
│   ├── database.py                   # JSON store wrapper
│   ├── seed.py                       # Document-hash seeder
│   ├── reset.py                      # Demo data reset
│   ├── tamper_demo.py                # Tamper-detection walkthrough
│   ├── models/                       # Domain dataclasses
│   ├── schemas/                      # Pydantic request/response models
│   └── services/
│       ├── evidence_service.py       # Multi-source evidence collection
│       ├── persistence.py            # Verification + audit persistence
│       ├── verification/             # Rule engine (7 rules) + scoring
│       └── audit/                    # Cryptographic chain
├── frontend/                         # Static HTML / CSS / JS UI
│   ├── index.html                    # Landing page
│   ├── dashboard.html                # Verification dashboard
│   ├── parcel.html                   # Land Passport
│   ├── verify.html                   # Search
│   ├── favicon.ico                   # 16/32/48 multi-resolution favicon
│   ├── favicon-32.png                # Standard tab favicon
│   ├── favicon-16.png                # Small tab favicon
│   ├── apple-touch-icon.png          # iOS pinned-tab icon
│   ├── logo/landguard.jpg            # Source logo
│   ├── css/
│   │   ├── main.css                  # Design system + dark mode
│   │   └── theme.css                 # Cream / parchment palette (custom)
│   └── js/
│       ├── layout.js                 # Top nav, theme, status pills, helpers
│       ├── api.js                    # Backend client (auto-detected base)
│       ├── map.js                    # Leaflet integration
│       ├── dashboard.js              # Dashboard page logic
│       ├── parcel.js                 # Land Passport page logic
│       ├── verify.js                 # Search page logic
│       └── fx.js                     # Animation utility
├── data/                             # Source-controlled synthetic fixtures
│   ├── parcels.json                  # 12 demo parcels
│   ├── owners.json
│   ├── documents.json                # 14 deeds (1 deliberately tampered)
│   ├── transactions.json
│   ├── mutations.json
│   └── tax_records.json
├── docs/
│   ├── audit-chain.md                # Hash-chain specification
│   ├── architecture.md               # Architecture notes
│   └── security.md                   # Threat model + non-goals
├── tests/                            # 57 pytest tests
├── serve_frontend.py                 # Bundled server (API + frontend)
├── pyproject.toml
├── README.md
└── .gitignore
```

## API reference (summary)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness probe. |
| `GET` | `/api/parcels` | List all parcels. |
| `GET` | `/api/parcels/{id}` | Parcel detail with ownership, geometry, Khatian. |
| `GET` | `/api/parcels/{id}/evidence` | Multi-source evidence bundle. |
| `GET` | `/api/parcels/{id}/documents` | Registered documents. |
| `GET` | `/api/parcels/{id}/transactions` | Transfer history. |
| `GET` | `/api/parcels/{id}/mutations` | Mutation (Namjari) records. |
| `GET` | `/api/parcels/{id}/tax` | Land-tax records. |
| `POST` | `/api/parcels/{id}/verify` | Run the verification engine. |
| `GET` | `/api/parcels/{id}/verification` | Latest verification result. |
| `GET` | `/api/parcels/{id}/audit` | Audit events for this parcel. |
| `GET` | `/api/audit` | Full audit log. |
| `GET` | `/api/audit/verify` | Verify the cryptographic chain. |
| `GET` | `/api/integrity` | Combined integrity report. |

The Swagger UI is at `/docs`.

## Security &amp; trust boundaries

The prototype is built for evaluation, not production. The cryptographic
chain protects the audit log **after the fact** &mdash; it is not a
replacement for write-access controls, identity verification, or a
trusted timestamping authority.

- **Detected:** record inconsistencies, owner mismatches, area overflows,
  duplicate transfers, missing mutations, document-tampering,
  audit-log tampering.
- **Not detected:** legal adjudication, identity spoofing, real-time
  record forgery at the source, government-database compromise.
- **Trust boundary:** anyone with write access to `data/` can rewrite
  the chain. The chain detects in-place modification of existing
  events; it does not protect against replacement of the entire file.

Full threat model: [`docs/security.md`](docs/security.md).

## Roadmap

- Replace `MockRegistrationAdapter` / `MockMutationAdapter` / etc. with
  HTTP clients to real government APIs.
- Move the JSON store to PostgreSQL + PostGIS for production.
- Add timestamping: publish the chain head to a third-party service.
- Add role-based access for sub-registrar review workflow.
- i18n (Bengali language support).
- ML-based evidence-quality scoring (out-of-scope for current prototype).

## License

MIT. See header in source files.

## Acknowledgements

- OpenStreetMap contributors &mdash; base map tiles.
- Leaflet &mdash; map rendering.
- Bangladesh land record conventions &mdash; synthesised for demo
  purposes only; **not** authoritative.
