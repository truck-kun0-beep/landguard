// LANDGUARD — dashboard.js
// Loads parcels + latest verification results + audit chain status
// and renders the dashboard. Refreshable, with auto-refresh.

const LandGuardDashboard = (() => {
  const {
    esc, statusPill, setHTML, setText, banner, empty, chainCard, auditRow,
    scenarioCard,
  } = LandGuardLayout;
  const api = LandGuard;

  // ---------- Refresh plumbing ----------
  let _refreshTimer = null;
  let _refreshIntervalMs = 0;
  let _statusBadge = null;

  function _setRefreshing(refreshing) {
    const btn = document.getElementById("refreshBtn");
    if (btn) {
      btn.disabled = refreshing;
      const lbl = btn.querySelector(".btn-label");
      if (lbl) lbl.textContent = refreshing ? "Refreshing\u2026" : "\u21bb Refresh";
    }
  }

  function startAutoRefresh(ms) {
    stopAutoRefresh();
    _refreshIntervalMs = ms || 0;
    if (!ms) return;
    _refreshTimer = setInterval(() => {
      run().catch((err) => console.warn("auto-refresh failed", err));
    }, ms);
  }

  function stopAutoRefresh() {
    if (_refreshTimer) {
      clearInterval(_refreshTimer);
      _refreshTimer = null;
    }
  }

  function _markRefreshed(meta) {
    if (!_statusBadge) {
      _statusBadge = document.createElement("div");
      _statusBadge.className = "muted refresh-stamp";
      const header = document.querySelector(".page-header");
      if (header) header.appendChild(_statusBadge);
    }
    _statusBadge.textContent = `Last refreshed ${new Date().toLocaleTimeString()} \u00b7 ${meta}`;
  }

  // ---------- Demo scenarios ----------
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

  // Map seed scenario tags to engine status values so the dashboard
  // shows meaningful counts even when no verification has been run yet.
  const TAG_TO_STATUS = {
    "CLEAN": "VERIFIED",
    "AREA-MISMATCH": "CONFLICT_DETECTED",
    "OWNER-MISMATCH": "CONFLICT_DETECTED",
    "DOUBLE-TRANSFER": "CONFLICT_DETECTED",
    "AREA-OVERFLOW": "CONFLICT_DETECTED",
    "MISSING-MUTATION": "REVIEW_REQUIRED",
    "HASH-MISMATCH": "CONFLICT_DETECTED",
  };

  function effectiveStatus(parcelOrScenario, results) {
    const pid = parcelOrScenario.parcel_id || parcelOrScenario.id;
    const fromEngine = results[pid]?.overall_status;
    if (fromEngine) return fromEngine;
    return TAG_TO_STATUS[parcelOrScenario.scenario_tag] || null;
  }

  // ---------- Main load ----------
  async function _load() {
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
      return null;
    }

    // Latest verification per parcel (404 means "never run" — fine).
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
      const s = effectiveStatus(p, results);
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
            (effectiveStatus(s, results)
              ? ` &mdash; latest: ${statusPill(effectiveStatus(s, results))}`
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
      _verificationStatus: effectiveStatus(p, results),
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

    return { total, verified, review, conflict };
  }

  // run() is the data-loading routine; safe to call any number of times.
  async function run() {
    _setRefreshing(true);
    try {
      const r = await _load();
      const meta = r
        ? `${r.total} parcels · ${r.verified} verified · ${r.review} review · ${r.conflict} conflict`
        : "load failed";
      _markRefreshed(meta);
    } finally {
      _setRefreshing(false);
    }
  }

  async function boot() {
    await run();

    // Manual refresh button.
    const btn = document.getElementById("refreshBtn");
    if (btn) {
      btn.addEventListener("click", async () => {
        try { await run(); }
        catch (err) { console.warn("manual refresh failed", err); }
      });
    }

    // Auto-refresh every 15 seconds so a user running verifications on
    // another tab sees the dashboard update without reloading.
    startAutoRefresh(15_000);

    // Stop auto-refresh when the page is hidden, restart when shown.
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopAutoRefresh();
      else startAutoRefresh(_refreshIntervalMs);
    });
  }

  return { boot, run, startAutoRefresh, stopAutoRefresh };
})();

window.LandGuardDashboard = LandGuardDashboard;