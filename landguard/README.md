# LandGuard

A prototype land-title verification system for Bangladesh.

**Status:** skeleton only. The backend (fake government API surface + fraud
rules + FastAPI server) is in place; the frontend is placeholder HTML. UI
comes after the verification engine is stable.

## Layout

```
landguard/
├── backend/        # FastAPI app, fraud rules, fake gov API
│   ├── main.py
│   ├── models/
│   ├── schemas/
│   ├── services/   # verification, crypto, fraud
│   └── database.py
├── frontend/       # Static HTML/CSS/JS
├── data/           # JSON data store + reserved geo folder
└── README.md
```

## Running the backend

```bash
cd landguard
pip install fastapi uvicorn pydantic
uvicorn backend.main:app --reload --port 8000
```

Then open <http://localhost:8000/docs> for the auto-generated API explorer.

## Key endpoints

- `GET  /api/parcels` — list every parcel in the store
- `GET  /api/parcels/{id}` — single parcel
- `GET  /api/transactions` — recorded transfers
- `POST /api/verify` — run the fraud engine against a (parcel, NID) pair
- `POST /api/transfers` — submit a new transfer through the engine
- `GET  /api/integrity` — verify the content-hash chain

## What the verification engine does

1. Pulls the parcel from the local store (stands in for DLRS).
2. Looks up the NID (stands in for NID Wing) by searching owned parcels.
3. Runs a fixed set of fraud rules: owner mismatch, rapid succession,
   undervalued sale, low stamp duty, existing encumbrance.
4. Returns a `risk_score` in `[0, 1]` plus the flag list and
   recommendations. The frontend reads this and decides what to show.
