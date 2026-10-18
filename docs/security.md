# LANDGUARD — What this system does and does not protect against

This is an explicit boundary. Everything below is part of the prototype
specification, not an accident of implementation.

## What LANDGUARD detects

- **Inconsistent ownership evidence.** A deed names a seller whose name
  is not in the recorded ownership list for the parcel.
- **Area mismatch.** Deed, mutation, Khatian, or GIS records describe
  the same parcel with materially different areas.
- **Duplicate active transfers.** Two approved transfers claim the same
  portion of a parcel for different buyers.
- **Transfer overflow.** Sum of active transfers exceeds the parcel's
  recorded area.
- **Missing mutation.** A transfer record has no corresponding mutation
  record (reported as WARNING, not FAIL &mdash; missing is not
  contradictory).
- **Document integrity.** A registered document's stored hash does not
  match the recomputed SHA-256 over its canonical content.
- **Audit chain tampering.** Any modification, reordering, or hash
  change to a past audit event is detected by independent recomputation.

## What LANDGUARD does not claim to solve

- **Legal adjudication.** LANDGUARD never determines who lawfully owns a
  parcel. The UI explicitly avoids language like "legal owner",
  "legally valid", or "fraud confirmed".
- **Identity verification.** Owner references are identifiers, not
  authenticated persons. The system never authenticates a citizen and
  never collects or stores PII.
- **Cadastral surveying.** The map shows placeholder polygons, not
  professional survey geometry. Area comparisons are over stored
  numeric values, not latitude/longitude calculations.
- **Government database synchronisation.** Adapters read the local JSON
  store; nothing here connects to any real Bangladesh government
  system.
- **Determining criminal fraud.** A high risk score or a CONFLICT
  DETECTED status is a signal for review by an authorised human &mdash;
  not a legal finding.
- **Replacing government land authorities.** LANDGUARD is a screening
  layer; humans and the relevant authorities remain the decision-makers.

## Trust boundaries

```
                        +----------------------------+
                        |     Public Internet        |
                        +-------------+--------------+
                                      |
                                      v
                            +---------+----------+
                            |   FastAPI server   |
                            +---------+----------+
                                      |
                                      v
                            +---------+----------+
                            |  Evidence service  |
                            |  + rule engine     |
                            |  + scoring         |
                            +---------+----------+
                                      |
                                      v
                            +---------+----------+
                            |   JSON data store  |
                            |  + audit chain log |
                            +---------+----------+
```

- Everything inside the JSON store is at the prototype's trust
  boundary. Anyone with write access to `audit_events.json` can rewrite
  the chain and produce a valid-looking chain of their own &mdash; the
  detection only works against in-place modifications of existing events.
- The frontend reads from the same API the operator would use. There is
  no separate "demo" endpoint.
- The audit chain is **not** blockchain. Do not present it as such.

## Synthetic-data disclaimer

Every parcel ID, owner reference, deed number, mutation reference,
tax record, and coordinate in `data/*.json` is synthetic. Names are
common Bangladeshi names; identifiers follow the pattern `DEMO-ID-NNNN`.
Do not present any of it as a real record. The UI labels these clearly
as synthetic demo data.