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

  return {
    render, esc, statusPill, findingPill, fmtDate, shortHash, banner, empty, el, setHTML, setText,
  };
})();

window.LandGuardLayout = LandGuardLayout;