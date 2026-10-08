// LANDGUARD — parcel.js (Land Passport page)
// Pulls parcel + verification + evidence + audit and renders the passport.

const LandGuardParcel = (() => {
  const {
    esc, statusPill, findingPill, fmtDate, shortHash, setHTML, setText,
    banner, empty, el, chainCard, auditRow,
  } = LandGuardLayout;
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
      { label: "Parcel ID",     value: parcel.parcel_id },
      { label: "District",      value: parcel.district || "—" },
      { label: "Upazila",       value: parcel.upazila || "—" },
      { label: "Mouza",         value: parcel.mouza || "—" },
      { label: "Sheet",         value: parcel.sheet_no || "—" },
      { label: "Dag / Plot",    value: parcel.dag_no || "—" },
      { label: "Khatian",       value: parcel.khatian_no || "—" },
      { label: "Land Type",     value: parcel.land_type || "—" },
      { label: "Area (decimal)", value: parcel.area_decimal },
      { label: "Khatian area",  value: parcel.khatian_area_decimal ?? "—" },
      { label: "GIS area",      value: parcel.gis_area_decimal ?? "—" },
      { label: "Created",       value: parcel.created_at || "—" },
    ];
    setHTML(
      "identityGrid",
      items
        .map(
          (it) => `
        <div class="item">
          <div class="label">${esc(it.label)}</div>
          <div class="value">${esc(it.value)}</div>
        </div>`
        )
        .join("")
    );
  }

  function renderOwnership(parcel) {
    const owners = parcel.owner_references || [];
    if (!owners.length) {
      setHTML("ownershipList", empty("No ownership records."));
      return;
    }
    setHTML(
      "ownershipList",
      owners
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
        .join("")
    );
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
          "i",
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
          "\u2713",
          "VERIFIED",
          `<div>No inconsistencies detected across configured evidence checks. Risk score: <b>${esc(score)}</b> &middot; level: <b>${esc(level)}</b>. This is a screening result &mdash; not a legal determination.</div>`
        )
      );
    } else if (overall === "REVIEW_REQUIRED") {
      setHTML(
        "statusBanner",
        banner(
          "warn",
          "!",
          "REVIEW REQUIRED",
          `<div>Evidence is incomplete or contains moderate concerns. Risk score: <b>${esc(score)}</b> &middot; level: <b>${esc(level)}</b>. A human reviewer should examine the relevant records.</div>`
        )
      );
    } else {
      setHTML(
        "statusBanner",
        banner(
          "bad",
          "\u2715",
          "CONFLICT DETECTED",
          `<div>Strong contradiction between records describing this parcel. Risk score: <b>${esc(score)}</b> &middot; level: <b>${esc(level)}</b>. This indicates the records disagree in a way that warrants investigation; it does not constitute a legal fraud determination.</div>`
        )
      );
    }
  }

  function renderVerificationHeadline(parcel, verifications) {
    if (!verifications) {
      setHTML("verificationHeadline", empty("Run verification to see the headline result."));
      setHTML("verificationMeta", "");
      return;
    }
    const score = verifications.risk_score;
    const level = verifications.risk_level;
    const findings = verifications.finding_count;
    const pass = verifications.findings.filter((f) => f.status === "PASS").length;
    const warn = verifications.findings.filter((f) => f.status === "WARNING").length;
    const fail = verifications.findings.filter((f) => f.status === "FAIL").length;
    setHTML(
      "verificationMeta",
      `<span class="pill ${verifications.overall_status === "VERIFIED" ? "ok" : verifications.overall_status === "REVIEW_REQUIRED" ? "warn" : "bad"}"><span class="dot"></span>${esc(verifications.overall_status.replace("_", " "))}</span>`
    );
    setHTML(
      "verificationHeadline",
      `
        <div class="grid cols-3">
          <div class="metric neutral">
            <div class="label">LANDGUARD Risk Score</div>
            <div class="value">${esc(score)}</div>
            <div class="meta">${esc(verifications.risk_label || "LANDGUARD VERIFICATION RISK SCORE")}</div>
          </div>
          <div class="metric ${verifications.overall_status === "VERIFIED" ? "ok" : verifications.overall_status === "REVIEW_REQUIRED" ? "warn" : "bad"}">
            <div class="label">Risk Level</div>
            <div class="value">${esc(level)}</div>
            <div class="meta">${esc(findings)} rule(s) evaluated</div>
          </div>
          <div class="metric neutral">
            <div class="label">Findings</div>
            <div class="value">${esc(pass)} / ${esc(warn)} / ${esc(fail)}</div>
            <div class="meta">PASS &middot; WARNING &middot; FAIL</div>
          </div>
        </div>
      `
    );
  }

  function renderFindings(verifications) {
    if (!verifications || !verifications.findings) {
      setHTML("findings", empty("Run verification to see findings."));
      return;
    }
    const findings = verifications.findings;
    setHTML(
      "findings",
      findings
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
        .join("")
    );
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
        `<div class="notice"><b>\u2713</b> All rule findings passed &mdash; no contradicting evidence to display.</div>`
      );
      return;
    }
    setHTML(
      "evidenceBreakdown",
      interesting
        .map((f) => {
          const refs = (f.evidence_reference || [])
            .map((r) => {
              const fieldsJson = JSON.stringify(r.fields || {}, null, 2);
              return `
              <div class="evidence-item">
                <div class="source">${esc(r.source)} &middot; ${esc(r.record_type)} &middot; ${esc(r.reference)}</div>
                <pre>${esc(fieldsJson)}</pre>
              </div>
            `;
            })
            .join("");
          const cls = f.status === "FAIL" ? "fail" : "warn";
          return `
          <div class="finding ${cls}">
            <div class="finding-header">
              <span class="code">${esc(f.rule_code)}</span>
              ${findingPill(f.status, f.severity)}
            </div>
            <div class="message">${esc(f.message)}</div>
            <div class="evidence-list">${refs || `<div class="muted">No evidence attached.</div>`}</div>
          </div>
        `;
        })
        .join("")
    );
  }

  function renderDocuments(documents) {
    if (!documents || !documents.length) {
      setHTML("documents", empty("No documents recorded."));
      return;
    }
    setHTML(
      "documents",
      `
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
                    : `${d.document_hash.slice(0, 10)}\u2026${d.document_hash.slice(-10)}`
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
    `
    );
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

    setHTML("auditChainCard", chainCard(chain));

    if (!events.length) {
      setHTML("auditTrail", empty("No audit events for this parcel yet."));
      return;
    }
    setHTML(
      "auditTrail",
      events
        .slice()
        .reverse()
        .map(auditRow)
        .join("")
    );
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
    renderVerificationHeadline(parcel, verifications);
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