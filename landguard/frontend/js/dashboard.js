// LANDGUARD — dashboard.js
// Loads parcels + latest verification results + audit chain status
// and renders the dashboard.

const LandGuardDashboard = (() => {
  const { esc, statusPill, shortHash, fmtDate, setHTML, setText, banner, empty } =
    LandGuardLayout;
  const api = LandGuard;

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
      setHTML("metrics",
        `<div class="section">Failed to load parcels: ${esc(e.message)}</div>`);
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

    // Audit chain status.
    try {
      const chain = await api.getAuditVerify();
      setHTML(
        "chainBadge",
        chain.valid
          ? `<span class="pill ok"><span class="dot"></span>AUDIT CHAIN VALID</span>`
          : `<span class="pill bad"><span class="dot"></span>AUDIT CHAIN INVALID</span>`
      );
      setHTML(
        "chainPanel",
        chain.valid
          ? banner(
              "ok",
              "✓",
              "Audit chain valid",
              `<div>${chain.event_count} event(s). Every hash independently recomputed and linked.</div>`
            )
          : banner(
              "bad",
              "✕",
              "Audit chain invalid",
              `<div>${esc(chain.error || "Unknown")}. First invalid sequence: <code>${esc(
                chain.first_invalid_sequence ?? "?"
              )}</code>.</div>`
            )
      );
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
        const html = recent
          .map((ev) => {
            const parcel = ev.parcel_id
              ? `<a href="parcel.html?id=${encodeURIComponent(ev.parcel_id)}">${esc(ev.parcel_id)}</a>`
              : `<span class="muted">—</span>`;
            return `
              <div class="audit-row">
                <div class="seq">#${ev.sequence_number ?? ev.seq ?? "?"}</div>
                <div>
                  <div><b>${esc(ev.event_type)}</b> · ${parcel}</div>
                  <div class="muted" style="font-size:12px;">${esc(ev.timestamp)} · actor: ${esc(ev.actor || ev.actor_reference || "—")}</div>
                </div>
              </div>
            `;
          })
          .join("");
        setHTML("recentAudit", `<div>${html}</div>`);
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