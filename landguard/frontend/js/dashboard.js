// LANDGUARD — dashboard.js
// Loads parcels + latest verification results + audit chain status
// and renders the dashboard.

const LandGuardDashboard = (() => {
  const {
    esc, statusPill, setHTML, setText, banner, empty, chainCard, auditRow,
    scenarioCard,
  } = LandGuardLayout;
  const api = LandGuard;

  // The seven demo scenarios. Labels are identifiers, not scenario
  // tags &mdash; the engine determines the outcome from real evidence.
  const SCENARIOS = [
    { name: "CLEAN",            id: "LG-BD-DHK-SAV-000001",
      desc: "Co-owned parcel; all evidence aligned." },
    { name: "AREA MISMATCH",    id: "LG-BD-DHK-GAZ-000004",
      desc: "Deed transferred area disagrees with mutation area." },
    { name: "OWNER MISMATCH",   id: "LG-BD-DHK-NAR-000005",
      desc: "Deed names a seller not supported by ownership evidence." },
    { name: "DOUBLE TRANSFER",  id: "LG-BD-CTG-PAH-000006",
      desc: "Two approved transfers selling the same area to different buyers." },
    { name: "AREA OVERFLOW",    id: "LG-BD-DHK-GAZ-000007",
      desc: "Sum of active transfers exceeds the parcel area." },
    { name: "MISSING MUTATION", id: "LG-BD-CHI-SAV-000008",
      desc: "A transfer exists with no corresponding mutation record." },
    { name: "DOCUMENT HASH MISMATCH", id: "LG-BD-DHK-SAV-000009",
      desc: "A registered deed's stored hash disagrees with the recomputed SHA-256." },
  ];

  function statusFor(parcelId, results) {
    const r = results[parcelId];
    if (!r) return null;
    return r.overall_status;
  }

  async function boot() {
    let parcels;
    try {
      parcels = await api.listParcels();
    } catch (e) {
      const isNetwork = !e.status;
      setHTML(
        "metrics",
        `<div class="section">
          <b>Could not reach the backend API.</b><br>
          <span class="muted">${esc(e.message)}</span><br><br>
          Run this command from the <code>landguard/</code> directory and open
          <a href="http://127.0.0.1:8000/frontend/dashboard.html">
          http://127.0.0.1:8000/frontend/dashboard.html</a>:<br>
          <pre>python -m uvicorn serve_frontend:app --port 8000</pre>
          ${isNetwork
            ? "If you opened the HTML file directly, the browser cannot reach localhost from a file:// URL."
            : "If you opened the page from a different server, the API and the page must be on the same host."}
        </div>`
      );
      return;
    }

    // Get latest verification for each parcel (don't error out if some have no result).
    const results = {};
    await Promise.all(
      parcels.map(async (p) => {
        try {
          results[p.parcel_id] = await api.getVerification(p.parcel_id);
        } catch (e) {
          if (e.status !== 404) console.warn("verification load failed", p.parcel_id, e);
        }
      })
    );

    // Metrics.
    const total = parcels.length;
    let verified = 0, review = 0, conflict = 0;
    parcels.forEach((p) => {
      const s = results[p.parcel_id]?.overall_status;
      if (s === "VERIFIED") verified++;
      else if (s === "REVIEW_REQUIRED") review++;
      else if (s === "CONFLICT_DETECTED") conflict++;
    });
    setText("m-total", total);
    setText("m-verified", verified);
    setText("m-review", review);
    setText("m-conflict", conflict);

    // Scenarios.
    setHTML(
      "scenarios",
      SCENARIOS.map((s) =>
        scenarioCard(
          s.name,
          s.id,
          s.desc +
            (results[s.id]?.overall_status
              ? ` &mdash; latest: ${statusPill(results[s.id].overall_status)}`
              : "")
        )
      ).join("")
    );

    // Audit chain status.
    try {
      const chain = await api.getAuditVerify();
      setHTML("chainPanel", chainCard(chain));
    } catch (e) {
      setHTML("chainPanel", banner("warn", "!", "Audit chain unreachable", esc(e.message)));
    }

    // Recent audit events.
    try {
      const events = await api.getAudit();
      const recent = events.slice(-8).reverse();
      if (!recent.length) {
        setHTML("recentAudit", empty("No audit events yet. Run a verification to populate the chain."));
      } else {
        setHTML("recentAudit", recent.map(auditRow).join(""));
      }
    } catch (e) {
      setHTML("recentAudit", empty("Failed to load audit log."));
    }

    // Parcel list.
    const enriched = parcels.map((p) => ({
      ...p,
      _verificationStatus: statusFor(p.parcel_id, results),
      _verificationScore: results[p.parcel_id]?.risk_score,
    }));
    const rowsHtml = enriched
      .map((p) => {
        const status = p._verificationStatus
          ? statusPill(p._verificationStatus)
          : `<span class="pill neutral"><span class="dot"></span>NOT VERIFIED</span>`;
        return `
          <div class="result-card" data-id="${esc(p.parcel_id)}" onclick="window.location='parcel.html?id=${encodeURIComponent(p.parcel_id)}'">
            <div>
              <div class="id">${esc(p.parcel_id)}</div>
              <div class="meta">${esc(p.district || "")}${p.upazila ? " · " + esc(p.upazila) : ""}${p.mouza ? " · " + esc(p.mouza) : ""}</div>
            </div>
            <div class="right">
              <div class="area">${p.area_decimal} decimal</div>
              ${status}
            </div>
          </div>
        `;
      })
      .join("");
    setHTML("parcelList", `<div class="result-list">${rowsHtml}</div>`);

    // Map.
    if (typeof LandGuardMap !== "undefined") {
      LandGuardMap.renderParcels("map", enriched);
    }
  }

  return { boot };
})();

window.LandGuardDashboard = LandGuardDashboard;