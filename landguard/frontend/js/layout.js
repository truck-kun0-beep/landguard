// LANDGUARD — shared layout + small DOM helpers
// Each page calls LandGuardLayout.mount({ active: "dashboard", title, breadcrumb, pageHtml })
// which renders the top nav and wraps the page body.

const LandGuardLayout = (() => {
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  const NAV = [
    { id: "home", label: "Home", href: "index.html" },
    { id: "dashboard", label: "Dashboard", href: "dashboard.html" },
    { id: "verify", label: "Verify", href: "verify.html" },
  ];

  function render(active, breadcrumb) {
    const navHtml = NAV.map((n) => {
      const cls = n.id === active ? "active" : "";
      return `<a class="${cls}" href="${esc(n.href)}">${esc(n.label)}</a>`;
    }).join("");

    const breadcrumbHtml = breadcrumb
      ? `<div class="breadcrumb">${breadcrumb
          .map((b, i) => {
            const sep = i === breadcrumb.length - 1 ? "" : " &nbsp;›&nbsp; ";
            if (b.href) {
              return `<a href="${esc(b.href)}">${esc(b.label)}</a>${sep}`;
            }
            return `${esc(b.label)}${sep}`;
          })
          .join("")}</div>`
      : "";

    return `
      <header class="topnav">
        <div class="topnav-inner">
          <div class="brand">
            <span class="mark">LG</span>
            <span>
              LANDGUARD
              <small>Cryptographic Land Verification &amp; Fraud Detection — Bangladesh</small>
            </span>
          </div>
          <nav class="navlinks">${navHtml}</nav>
          <button class="theme-toggle" type="button" id="themeToggle"
                  aria-label="Toggle dark mode" title="Toggle dark mode">
            <span class="ico" aria-hidden="true">◐</span>
            <span class="lbl">Theme</span>
          </button>
        </div>
      </header>
    `;
  }

  function statusPill(overall) {
    switch (overall) {
      case "VERIFIED":
        return `<span class="pill ok"><span class="dot"></span>VERIFIED</span>`;
      case "REVIEW_REQUIRED":
        return `<span class="pill warn"><span class="dot"></span>REVIEW REQUIRED</span>`;
      case "CONFLICT_DETECTED":
        return `<span class="pill bad"><span class="dot"></span>CONFLICT DETECTED</span>`;
      default:
        return `<span class="pill neutral"><span class="dot"></span>${esc(overall || "UNKNOWN")}</span>`;
    }
  }

  function findingPill(status, severity) {
    const cls = status === "FAIL" ? "bad" : status === "WARNING" ? "warn" : "ok";
    return `<span class="pill ${cls}">${esc(status)}${severity ? ` · ${esc(severity)}` : ""}</span>`;
  }

  function fmtDate(s) {
    if (!s) return "—";
    return s;
  }

  function shortHash(h, n = 10) {
    if (!h) return "—";
    if (h === "0".repeat(64)) return "GENESIS (0000…)";
    if (h.length <= n * 2 + 3) return h;
    return `${h.slice(0, n)}…${h.slice(-n)}`;
  }

  function banner(kind, glyph, title, body) {
    return `
      <div class="banner ${esc(kind)}">
        <div class="glyph">${esc(glyph)}</div>
        <div>
          <strong>${esc(title)}</strong>
          ${body ? `<div>${body}</div>` : ""}
        </div>
      </div>
    `;
  }

  function empty(text) {
    return `<div class="empty-state">${esc(text)}</div>`;
  }

  function el(id) { return document.getElementById(id); }

  function setHTML(id, html) { const n = el(id); if (n) n.innerHTML = html; }
  function setText(id, text) { const n = el(id); if (n) n.textContent = text; }

  function chainCard(result) {
    const ok = !!result.valid;
    const glyph = ok ? "\u2713" : "\u2715";
    const headTitle = ok ? "CHAIN VALID" : "CHAIN INVALID";
    return `
      <div class="audit-chain-card ${ok ? "ok" : "bad"}">
        <div>
          <div class="label">Cryptographic audit chain</div>
          <div class="value">${glyph} ${headTitle}</div>
          <div class="desc">
            ${esc(result.event_count)} event(s) verified.
            ${ok
              ? "Every stored hash independently recomputed from the chain and matches."
              : `First invalid sequence: <code>${esc(result.first_invalid_sequence ?? "?")}</code>. ${esc(result.error || "")}`}
          </div>
        </div>
        <div>
          <a class="btn secondary" href="verify.html">Inspect Parcels</a>
        </div>
      </div>
      <div class="notice">
        <b>Note</b>
        Each event carries a SHA-256 hash linked to the previous one.
        Changing an earlier event invalidates every subsequent hash.
      </div>
    `;
  }

  function auditRow(ev) {
    const seq = ev.sequence_number ?? ev.seq ?? "?";
    const eventType = ev.event_type || "UNKNOWN";
    const ts = ev.timestamp || "-";
    const actor = ev.actor || ev.actor_reference || "-";
    const prev = ev.previous_event_hash || "";
    const cur = ev.current_event_hash || "";
    const prevFull = prev || "(none)";
    const curFull = cur || "(none)";
    const prevShort = shortHash(prev);
    const curShort = shortHash(cur);
    return `
      <div class="audit-row">
        <div class="seq">#${esc(String(seq))}</div>
        <div>
          <div><b>${esc(eventType)}</b>
            <span class="muted">&middot;</span>
            <span class="muted">${esc(ts)}</span>
          </div>
          <div class="muted" style="font-size:12px; margin-top:2px;">Actor: ${esc(actor)}</div>
          <div class="hash">
            <div><b>previous:</b> <span class="mono">${esc(prevShort)}</span></div>
            <div><b>current:</b> <span class="mono">${esc(curShort)}</span></div>
            <details class="hash-details">
              <summary>Show full hashes</summary>
              <pre>previous: ${esc(prevFull)}\ncurrent:  ${esc(curFull)}</pre>
            </details>
          </div>
        </div>
      </div>
    `;
  }

  function scenarioCard(name, parcelId, descriptionHtml) {
    // name + parcelId are user-controlled text, always escape them.
    // descriptionHtml is a short HTML fragment built by the dashboard
    // (e.g. an inline status pill) and is rendered as trusted HTML.
    return `
      <div class="scenario-card" onclick="window.location='parcel.html?id=${encodeURIComponent(parcelId)}'">
        <div class="name">${esc(name)}</div>
        <div class="desc">${descriptionHtml}</div>
        <div class="id mono">${esc(parcelId)}</div>
      </div>
    `;
  }

  // ---------- Theme (light / dark / system) ----------

  const _THEME_KEY = "landguard:theme"; // "light" | "dark" | "auto"

  function _applyTheme(mode) {
    const root = document.documentElement;
    if (mode === "dark") {
      root.setAttribute("data-theme", "dark");
    } else if (mode === "light") {
      root.setAttribute("data-theme", "light");
    } else {
      // Auto / system: clear explicit theme so media query takes over.
      root.removeAttribute("data-theme");
    }
    // Reflect in the toggle button if it's mounted.
    const btn = document.getElementById("themeToggle");
    if (btn) {
      const next = mode === "light" ? "dark" : mode === "dark" ? "auto" : "light";
      btn.setAttribute("data-next", next);
      const lbl = btn.querySelector(".lbl");
      if (lbl) {
        lbl.textContent = `Theme: ${mode === "auto" ? "auto" : mode}`;
      }
    }
  }

  function _initTheme() {
    let stored = null;
    try { stored = localStorage.getItem(_THEME_KEY); } catch (_) { /* private mode */ }
    if (stored !== "light" && stored !== "dark" && stored !== "auto") stored = "auto";
    _applyTheme(stored);
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("#themeToggle");
      if (!btn) return;
      const next = btn.getAttribute("data-next") || "dark";
      try { localStorage.setItem(_THEME_KEY, next); } catch (_) { /* ignore */ }
      _applyTheme(next);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _initTheme);
  } else {
    _initTheme();
  }

  return {
    render, esc, statusPill, findingPill, fmtDate, shortHash, banner, empty, el, setHTML, setText,
    chainCard, auditRow, scenarioCard,
  };
})();

window.LandGuardLayout = LandGuardLayout;