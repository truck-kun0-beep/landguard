# LANDGUARD

> **Digital Land Verification & Integrity Platform**

LANDGUARD is a parcel-centric verification layer for Bangladesh-style land
records. It correlates evidence from multiple sources, runs a
deterministic rule-based verification engine, and protects every
verification event with a tamper-evident cryptographic audit chain.

This repository is a hackathon prototype. It is **not** a replacement for
any government authority or land record system, and it does **not** claim
to make legal determinations.

---

## The problem

Land records in Bangladesh live in many places: deeds (registration),
mutations (Namjari), land-tax rolls, Khatian registers, and more. Each
authority is correct in isolation, but discrepancies across them are a
major source of fraud, double transfers, and contested ownership.

## The solution

Treat the **parcel** as the central entity. Gather evidence from every
source, compare them with a transparent rule engine, and seal every
verification event into an append-only hash chain so any later tampering
is detectable.

```
            Land records (deeds, mutations, tax, Khatian, GIS)
                              |
                              v
                  Adapters (per source)
                              |
                              v
                 Evidence collection service
                              |
                              v
                 Verification engine (7 rules)
                              |
                              v
            Findings + Risk score + Overall status
                              |
                              v
            Cryptographic audit chain (SHA-256)
```

## Core terminology

- **Parcel** &mdash; a physical land record (district / upazila / mouza /
  sheet / dag / khatian / area).
- **Land Passport** &mdash; the per-parcel dashboard in the UI.
- **Evidence** &mdash; any record describing the parcel (deed, mutation,
  tax, GIS, ownership).
- **Verification** &mdash; the engine run; produces findings.
- **Findings** &mdash; per-rule results with severity and explanation.
- **Risk Score** &mdash; transparent 0-100 number derived from finding
  weights (see `scoring.py`).
- **Audit Trail** &mdash; the chronological list of verification events.
- **Chain Integrity** &mdash; the SHA-256 hash chain over those events.

## Technology

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy-isms-free JSON store
  (we use a small `JsonStore` wrapper; swap for PostgreSQL when needed).
- **Frontend:** Plain HTML, plain CSS, vanilla JavaScript. Leaflet (via
  CDN) for the parcel map. No build system.
- **Cryptography:** Python `hashlib` + SHA-256 only.
- **GIS:** None &mdash; parcel coordinates live in the seed data and the
  map renders them as polygons over OpenStreetMap tiles.

## Project structure

```
landguard/
├── backend/
│   ├── main.py                  FastAPI app
│   ├── database.py              JsonStore + query helpers
│   ├── seed.py                  document-hash seeder
│   ├── reset.py                 demo data reset (one command)
│   ├── tamper_demo.py           tamper-detection walkthrough
│   ├── models/                  domain dataclasses
│   ├── schemas/                 Pydantic request/response models
│   ├── services/
│   │   ├── evidence_service.py  unified evidence bundle
│   │   ├── persistence.py       results + audit-event persistence
│   │   ├── verification/        rule engine + 7 rules + scoring
│   │   └── audit/               cryptographic chain (canonical + hash)
│   └── tests/                   52 pytest tests
├── frontend/
│   ├── index.html               landing
│   ├── dashboard.html           overview + scenario picker
│   ├── parcel.html              Land Passport
│   ├── verify.html              search + map
│   ├── css/main.css             design system
│   └── js/                      layout, api, map, page logic
├── data/
│   ├── parcels.json             12 deterministic demo parcels
│   ├── owners.json              synthetic owners
│   ├── documents.json           deeds (one is deliberately tampered)
│   ├── transactions.json
│   ├── mutations.json
│   ├── tax_records.json
│   └── verification_records.json  / audit_events.json  (cleared by reset)
├── docs/
│   ├── audit-chain.md           hash-chain explanation
│   ├── architecture.md          architecture notes
│   └── security.md              what we do / do not protect against
├── tests/
└── serve_frontend.py            mounts /frontend in dev
```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install fastapi uvicorn pydantic pytest httpx
```

## Run

```powershell
# Backend + frontend in one process:
python -m uvicorn serve_frontend:app --reload --port 8000
```

- Open <http://127.0.0.1:8000/frontend/index.html> for the landing.
- <http://127.0.0.1:8000/frontend/dashboard.html> for the dashboard.
- Swagger: <http://127.0.0.1:8000/docs>

## Test

```powershell
pytest -q
```

## Reset demo data

```powershell
python -m backend.reset
```

This:
- Re-stamps every document's SHA-256 hash (the HASH-MISMATCH demo is
  always as advertised).
- Clears `data/verification_records.json` and `data/audit_events.json`.

The other six JSON files (`parcels`, `owners`, `transactions`, `mutations`,
`tax_records`, `documents`) are source-controlled fixtures and are not
modified by `reset`.

## Tamper-detection demo

```powershell
python -m backend.tamper_demo
```

This is a local-only script. It:
1. Snapshots `audit_events.json`.
2. Seeds 5 demo events (skipped if already &ge;5).
3. Shows the chain is valid.
4. Tampers with the middle event's payload.
5. Shows the chain is now invalid at the tampered sequence.
6. Restores the original file from the snapshot.

The script always restores, even on Ctrl+C.

## Verification rules

| Code | Purpose |
|---|---|
| `OWNER_MATCH` | Check that the seller in each approved transfer is supported by the recorded ownership evidence. |
| `AREA_MATCH` | Compare parcel area with Khatian and GIS area. |
| `DEED_MUTATION_AREA_MATCH` | Compare transferred area in the deed vs the mutation record. |
| `PARCEL_AREA_OVERFLOW` | Sum of active transfers must not exceed parcel area. |
| `DUPLICATE_TRANSFER` | Two approved transfers overlapping in area to different buyers is suspicious. |
| `MISSING_MUTATION` | Warn (not fail) when an approved transfer has no mutation record. |
| `DOCUMENT_INTEGRITY` | Recompute SHA-256 of each document and compare with stored hash. |

Rule weights are documented in `backend/services/verification/scoring.py`.

## Demo scenarios

| Label | Parcel | What it demonstrates |
|---|---|---|
| CLEAN | `LG-BD-DHK-SAV-000001` | All rules pass; co-ownership is normal. |
| AREA MISMATCH | `LG-BD-DHK-GAZ-000004` | Deed says 4.00, mutation says 6.00. |
| OWNER MISMATCH | `LG-BD-DHK-NAR-000005` | Deed names a seller not supported by ownership. |
| DOUBLE TRANSFER | `LG-BD-CTG-PAH-000006` | Two approved transfers selling overlapping area. |
| AREA OVERFLOW | `LG-BD-DHK-GAZ-000007` | Active transfers sum to 11.00 against a 10.00 parcel. |
| MISSING MUTATION | `LG-BD-CHI-SAV-000008` | Approved deed has no mutation record. |
| DOCUMENT HASH MISMATCH | `LG-BD-DHK-SAV-000009` | Stored document hash disagrees with recomputed SHA-256. |

## Limitations

- **Synthetic data.** Parcel IDs, owner IDs, deed numbers, and geometry are
  not real. The system architecture is the deliverable.
- **No real government integration.** Adapters read the local JSON store.
  Replacing one adapter is the only change needed for a future real
  integration.
- **Local hash chain.** Anyone with write access to the audit log can
  rewrite the whole file. A trusted publication channel (or a true
  distributed ledger) would be needed for stronger guarantees.
- **English language only** for the UI.
- **No authentication.** Adding it would require a small session model
  and is intentionally out of scope for the prototype.

## Future integration possibilities

- Swap `MockRegistrationAdapter` for an HTTP client to the (future)
  e-Registration API.
- Swap `MockMutationAdapter` for an integration with the (future)
  e-Mutation API.
- Replace the JSON store with PostgreSQL + PostGIS for production.
- Add timestamping (publish chain head to a third-party service).
- Add user accounts + role-based access for sub-registrar review
  workflow.

---

For a detailed walkthrough of the chain, see `docs/audit-chain.md`. For
what it does and does not protect against, see `docs/security.md`. For
architecture details, see `docs/architecture.md`.