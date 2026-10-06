// LANDGUARD — parcel.js (Land Passport page)
// Pulls parcel + verification + evidence + audit and renders the passport.

const LandGuardParcel = (() => {
  const { esc, statusPill, findingPill, fmtDate, shortHash, setHTML, setText, banner, empty, el } =
    LandGuardLayout;
  const api = LandGuard;

  function getParcelIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("id");
  }

  function showNotFound(msg) {
    el("parcelBody").style.display = "none";
    el("parcelNotFound").style.display = "block";
    setText("parcelNotFoundMsg", msg || "The requested parcel does not exist.");
  }

  function renderIdentity(parcel) {
    const items = [
      { label: "Parcel ID", value: parcel.parcel_id },
      { label: "District", value: parcel.district || "—" },
      { label: "Upazila", value: parcel.upazila || "—" },
      { label: "Mouza", value: parcel.mouza || "—" },
      { label: "Sheet", value: parcel.sheet_no || "—" },
      { label: "Dag / Plot", value: parcel.dag_no || "—" },
      { label: "Khatian", value: parcel.khatian_no || "—" },
      { label: "Land Type", value: parcel.land_type || "—" },
      { label: "Area (decimal)", value: parcel.area_decimal },
      { label: "Khatian area", value: parcel.khatian_area_decimal ?? "—" },
      { label: "GIS area", value: parcel.gis_area_decimal ?? "—" },
      { label: "Created", value: parcel.created_at || "—" },
    ];
    const html = items
      .map(
        (it) => `
        <div class="item">
          <div class="label">${esc(it.label)}</div>
          <div class="value">${esc(it.value)}</div>
        </div>`
      )
      .join("");
    setHTML("identityGrid", html);
  }

  function renderOwnership(parcel) {
    const owners = parcel.owner_references || [];
    if (!owners.length) {
      setHTML("ownershipList", empty("No ownership records."));
      return;
    }
    const html = owners
      .map((o) => {
        const pct = Number(o.share_percent || 0);
        return `
          <div class="ownership-row">
            <div style="min-width:160px;">
              <div class="name">${esc(o.name || "Unknown")}</div>
              <div class="id">${esc(o.identifier || "")}</div>
            </div>
            <div class="bar"><div style="width:${Math.min(100, Math.max(0, pct))}%;"></div></div>
            <div class="pct">${pct}%</div>
          </div>
        `;
      })
      .join("");
    setHTML("ownershipList", html);
  }

  function renderMap(parcel, verifications) {
    if (typeof LandGuardMap === "undefined") return;
    const enriched = { ...parcel, _verificationStatus: verifications?.overall_status };
    LandGuardMap.renderOne("map", enriched);
  }

  function renderStatusBanner(parcel, verifications) {
    if (!verifications) {
      setHTML(
        "statusBanner",
        banner(
          "info",
          "ℹ",
          "No verification recorded yet",
          `<div>Click <b>Run Verification</b> to evaluate this parcel against all evidence.</div>`
        )
      );
      return;
    }
    const overall = verifications.overall_status;
    const score = verifications.risk_score;
    const level = verifications.risk_level;
    if (overall === "VERIFIED") {
      setHTML(
        "statusBanner",
        banner(
          "ok",
          "✓",
          "Verified — no material contradictions detected",
          `<div>LANDGUARD VERIFICATION RISK SCORE: <b>${esc(score)}</b> · <b>${esc(level)}</b> · ${esc(
            verifications.finding_count
          )} finding(s). This indicates the available evidence sources are mutually consistent. It is not a legal determination.</div>`
        )
      );
    } else if (overall === "REVIEW_REQUIRED") {
      setHTML(
        "statusBanner",
        banner(
          "warn",
          "!",
          "Review required — evidence is incomplete or contains moderate concerns",
          `<div>LANDGUARD VERIFICATION RISK SCORE: <b>${esc(score)}</b> · <b>${esc(level)}</b> · ${esc(
            verifications.finding_count
          )} finding(s). A human reviewer should examine the relevant records.</div>`
        )
      );
    } else {
      setHTML(
        "statusBanner",
        banner(
          "bad",
          "✕",
          "Conflict detected — strong contradiction between records",
          `<div>LANDGUARD VERIFICATION RISK SCORE: <b>${esc(score)}</b> · <b>${esc(level)}</b> · ${esc(
            verifications.finding_count
          )} finding(s). This does <b>not</b> constitute a legal fraud determination; it indicates the records describing this parcel disagree in a way that warrants investigation.</div>`
        )
      );
    }
  }

  function renderFindings(verifications) {
    if (!verifications || !verifications.findings) {
      setHTML("findings", empty("Run verification to see findings."));
      return;
    }
    const findings = verifications.findings;
    const html = findings
      .map((f) => {
        const cls = f.status === "FAIL" ? "fail" : f.status === "WARNING" ? "warn" : "ok";
        return `
          <div class="finding ${cls}">
            <div class="finding-header">
              <span class="code">${esc(f.rule_code)}</span>
              ${findingPill(f.status, f.severity)}
            </div>
            <div class="message">${esc(f.message)}</div>
          </div>
        `;
      })
      .join("");
    setHTML("findings", html);
  }

  function renderEvidenceBreakdown(parcelId, verifications) {
    if (!verifications || !verifications.findings) {
      setHTML("evidenceBreakdown", empty("Run verification to see evidence."));
      return;
    }
    const interesting = verifications.findings.filter((f) => f.status !== "PASS");
    if (!interesting.length) {
      setHTML(
        "evidenceBreakdown",
        `<div class="notice"><b>✓</b> All rule findings passed — no contradicting evidence to display.</div>`
      );
      return;
    }
    const html = interesting
      .map((f) => {
        const refs = (f.evidence_reference || [])
          .map((r) => {
            const fieldsJson = JSON.stringify(r.fields || {}, null, 2);
            return `
              <div class="evidence-item">
                <div class="source">${esc(r.source)} · ${esc(r.record_type)} · ${esc(r.reference)}</div>
                <pre>${esc(fieldsJson)}</pre>
              </div>
            `;
          })
          .join("");
        return `
          <div class="finding ${f.status === "FAIL" ? "fail" : "warn"}">
            <div class="finding-header">
              <span class="code">${esc(f.rule_code)}</span>
              ${findingPill(f.status, f.severity)}
            </div>
            <div class="message">${esc(f.message)}</div>
            <div class="evidence-list">${refs || `<div class="muted">No evidence attached.</div>`}</div>
          </div>
        `;
      })
      .join("");
    setHTML("evidenceBreakdown", html);
  }

  function renderDocuments(documents) {
    if (!documents || !documents.length) {
      setHTML("documents", empty("No documents recorded."));
      return;
    }
    const html = `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Document</th>
              <th>Type</th>
              <th>Issued</th>
              <th>Authority</th>
              <th>Status</th>
              <th>Hash</th>
            </tr>
          </thead>
          <tbody>
            ${documents
              .map((d) => {
                const shortHash = d.document_hash
                  ? d.document_hash === "0".repeat(64)
                    ? "—"
                    : `${d.document_hash.slice(0, 10)}…${d.document_hash.slice(-10)}`
                  : "—";
                return `
                  <tr>
                    <td class="mono">${esc(d.document_id)}</td>
                    <td>${esc(d.document_type)}</td>
                    <td>${esc(fmtDate(d.issue_date))}</td>
                    <td>${esc(d.issuing_authority || "—")}</td>
                    <td>${esc(d.status || "—")}</td>
                    <td class="mono" style="font-size:11px;">${esc(shortHash)}</td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    `;
    setHTML("documents", html);
  }

  function renderTransactions(transactions) {
    if (!transactions || !transactions.length) {
      setHTML("transactions", empty("No transactions recorded."));
      return;
    }
    const rows = transactions
      .slice()
      .sort((a, b) => (a.transaction_date < b.transaction_date ? -1 : 1))
      .map(
        (t) => `
        <tr>
          <td class="mono">${esc(t.txn_id)}</td>
          <td>${esc(t.transaction_date || "—")}</td>
          <td class="mono">${esc(t.from_owner_reference || "—")}</td>
          <td class="mono">${esc(t.to_owner_reference || "—")}</td>
          <td>${t.transferred_area_decimal ?? "—"}</td>
          <td>${esc(t.status || "—")}</td>
        </tr>
      `
      )
      .join("");
    setHTML(
      "transactions",
      `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Transaction</th>
                <th>Date</th>
                <th>From</th>
                <th>To</th>
                <th>Area (decimal)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `
    );
  }

  function renderMutations(mutations) {
    if (!mutations || !mutations.length) {
      setHTML(
        "mutations",
        empty("No mutation records. A missing mutation is itself a moderate signal — see Verification.")
      );
      return;
    }
    const rows = mutations
      .slice()
      .sort((a, b) => (a.application_date < b.application_date ? -1 : 1))
      .map(
        (m) => `
        <tr>
          <td class="mono">${esc(m.application_number || m.mutation_id || "—")}</td>
          <td>${esc(fmtDate(m.application_date))}</td>
          <td>${esc(fmtDate(m.approval_date))}</td>
          <td class="mono">${esc(m.previous_owner_reference || "—")}</td>
          <td class="mono">${esc(m.new_owner_reference || "—")}</td>
          <td>${m.area_decimal ?? "—"}</td>
          <td>${esc(m.status || "—")}</td>
        </tr>
      `
      )
      .join("");
    setHTML(
      "mutations",
      `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Application</th>
                <th>Filed</th>
                <th>Approved</th>
                <th>Previous owner</th>
                <th>New owner</th>
                <th>Area (decimal)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `
    );
  }

  function renderTax(taxRecords) {
    if (!taxRecords || !taxRecords.length) {
      setHTML("tax", empty("No tax records."));
      return;
    }
    const rows = taxRecords
      .slice()
      .sort((a, b) => (a.tax_year < b.tax_year ? -1 : 1))
      .map(
        (t) => `
        <tr>
          <td>${esc(String(t.tax_year || "—"))}</td>
          <td class="mono">${esc(t.recorded_owner_reference || "—")}</td>
          <td>${t.area_decimal ?? "—"}</td>
          <td>${t.amount_due ?? "—"}</td>
          <td>${t.amount_paid ?? "—"}</td>
          <td>${esc(fmtDate(t.payment_date))}</td>
          <td>${esc(t.status || "—")}</td>
        </tr>
      `
      )
      .join("");
    setHTML(
      "tax",
      `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Year</th>
                <th>Recorded owner</th>
                <th>Area (decimal)</th>
                <th>Due (BDT)</th>
                <th>Paid (BDT)</th>
                <th>Payment date</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `
    );
  }

  async function renderAuditTrail(parcelId) {
    let chain, events;
    try {
      [chain, events] = await Promise.all([
        api.getAuditVerify(),
        api.getParcelAudit(parcelId),
      ]);
    } catch (e) {
      setHTML("auditTrail", empty("Failed to load audit log."));
      return;
    }

    setHTML(
      "auditChainBadge",
      chain.valid
        ? `<span class="pill ok"><span class="dot"></span>AUDIT CHAIN VALID</span>`
        : `<span class="pill bad"><span class="dot"></span>AUDIT CHAIN INVALID</span>`
    );

    if (!events.length) {
      setHTML("auditTrail", empty("No audit events for this parcel yet."));
      return;
    }

    const html = events
      .slice()
      .reverse()
      .map(
        (ev) => `
        <div class="audit-row">
          <div class="seq">#${ev.sequence_number ?? ev.seq ?? "?"}</div>
          <div>
            <div><b>${esc(ev.event_type)}</b> <span class="muted">·</span> <span class="muted">${esc(
              ev.timestamp
            )}</span></div>
            <div class="muted" style="font-size:12px; margin-top:2px;">Actor: ${esc(
              ev.actor || ev.actor_reference || "—"
            )}</div>
            <div class="hash">
              <div><b>previous:</b> <span>${esc(shortHash(ev.previous_event_hash))}</span></div>
              <div><b>current:</b> <span>${esc(shortHash(ev.current_event_hash))}</span></div>
            </div>
          </div>
        </div>
      `
      )
      .join("");
    setHTML("auditTrail", html);
  }

  async function refreshAll(parcelId) {
    let parcel, verifications;
    try {
      parcel = await api.getParcel(parcelId);
    } catch (e) {
      if (e.status === 404) return showNotFound(`No parcel with ID "${parcelId}".`);
      return showNotFound(e.message);
    }
    try {
      verifications = await api.getVerification(parcelId);
    } catch (e) {
      verifications = null;
      if (e.status !== 404) console.warn("verification load failed", e);
    }

    setText("parcelId", parcel.parcel_id);
    const subtitleParts = [];
    if (parcel.district) subtitleParts.push(parcel.district);
    if (parcel.upazila) subtitleParts.push(parcel.upazila);
    if (parcel.mouza) subtitleParts.push("Mouza " + parcel.mouza);
    subtitleParts.push(`${parcel.area_decimal} decimal`);
    setText("parcelSubtitle", subtitleParts.join(" · "));

    renderIdentity(parcel);
    renderOwnership(parcel);
    renderStatusBanner(parcel, verifications);
    renderMap(parcel, verifications);
    renderFindings(verifications);
    renderEvidenceBreakdown(parcelId, verifications);

    try {
      const [documents, transactions, mutations] = await Promise.all([
        api.getDocuments(parcelId),
        api.getTransactions(parcelId),
        api.getMutations(parcelId),
      ]);
      renderDocuments(documents);
      renderTransactions(transactions);
      renderMutations(mutations);
    } catch (e) {
      setHTML("documents", empty("Failed to load supporting records."));
      setHTML("transactions", empty(""));
      setHTML("mutations", empty(""));
    }

    try {
      const tax = await api.getTax(parcelId);
      renderTax(tax);
    } catch (e) {
      setHTML("tax", empty("Failed to load tax records."));
    }

    await renderAuditTrail(parcelId);
  }

  async function runVerification(parcelId) {
    const btn = el("runVerifyBtn");
    btn.disabled = true;
    btn.querySelector(".btn-label").textContent = "Running…";
    try {
      const result = await api.verify(parcelId);
      btn.querySelector(".btn-label").textContent = "▶ Run Verification";
      btn.disabled = false;
      await refreshAll(parcelId);
      return result;
    } catch (e) {
      btn.querySelector(".btn-label").textContent = "▶ Run Verification";
      btn.disabled = false;
      throw e;
    }
  }

  async function boot() {
    const parcelId = getParcelIdFromUrl();
    if (!parcelId) return showNotFound("Open this page with a parcel ID, e.g. parcel.html?id=LG-BD-DHK-SAV-000001");
    el("parcelBody").style.display = "block";
    el("parcelNotFound").style.display = "none";

    await refreshAll(parcelId);

    el("runVerifyBtn").addEventListener("click", async () => {
      try { await runVerification(parcelId); }
      catch (err) {
        setHTML(
          "statusBanner",
          banner("bad", "✕", "Verification failed", esc(err.message || "Unknown error"))
        );
      }
    });
  }

  return { boot, refreshAll };
})();

window.LandGuardParcel = LandGuardParcel;