// LANDGUARD — minimal API client
// Wraps fetch with auto-detected base.
//
// Pages are normally served by the bundled server at /frontend/*.html
// and the API lives at /api/*. In that case the relative URL "../api"
// resolves to "/api" which is correct.
//
// But sometimes the user opens the HTML file directly (file://) or
// serves the frontend with a plain static server. In those cases the
// auto-detection tries both /api and ../api until it finds one that
// responds. The result is cached after the first success.

const LandGuard = (() => {
  const candidatesFor = () => {
    if (window.LANDGUARD_API_BASE) return [window.LANDGUARD_API_BASE];
    const path = window.location.pathname;
    const htmlPage = path.endsWith(".html");
    const list = [];
    if (htmlPage) list.push("../api");        // /frontend/dashboard.html
    list.push("/api");                        // root-served
    if (!htmlPage) list.push("../api");       // not served by .html (rare)
    return list;
  };

  // Cached winning base. Until we know it, every request tries each
  // candidate in order and remembers the first 2xx.
  let _resolvedBase = null;
  let _resolving = null;

  async function _resolveBase() {
    if (_resolvedBase) return _resolvedBase;
    if (_resolving) return _resolving;
    _resolving = (async () => {
      for (const c of candidatesFor()) {
        try {
          const r = await fetch(`${c}/health`, {
            headers: { Accept: "application/json" },
          });
          if (r.ok) {
            _resolvedBase = c;
            return c;
          }
        } catch (_) { /* try next */ }
      }
      // Fall back to the first candidate so error reporting has a URL.
      _resolvedBase = candidatesFor()[0];
      return _resolvedBase;
    })();
    return _resolving;
  }

  async function request(path, opts = {}) {
    const base = await _resolveBase();
    const url = `${base}${path}`;
    let resp;
    try {
      resp = await fetch(url, {
        headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
        ...opts,
      });
    } catch (networkErr) {
      const err = new Error(
        `Network error contacting the backend (tried ${url}). ` +
        `Is the server running on the same host as this page?`
      );
      err.status = 0;
      err.cause = networkErr;
      throw err;
    }
    if (!resp.ok) {
      let detail;
      try { detail = (await resp.json()).detail; } catch { /* ignore */ }
      const err = new Error(
        detail || `HTTP ${resp.status} from ${url}`
      );
      err.status = resp.status;
      throw err;
    }
    if (resp.status === 204) return null;
    return resp.json();
  }

  return {
    health: () => request("/health"),
    listParcels: () => request("/parcels"),
    getParcel: (id) => request(`/parcels/${encodeURIComponent(id)}`),
    getEvidence: (id) => request(`/parcels/${encodeURIComponent(id)}/evidence`),
    getDocuments: (id) => request(`/parcels/${encodeURIComponent(id)}/documents`),
    getTransactions: (id) => request(`/parcels/${encodeURIComponent(id)}/transactions`),
    getMutations: (id) => request(`/parcels/${encodeURIComponent(id)}/mutations`),
    getTax: (id) => request(`/parcels/${encodeURIComponent(id)}/tax`),
    verify: (id) =>
      request(`/parcels/${encodeURIComponent(id)}/verify`, { method: "POST" }),
    getVerification: (id) =>
      request(`/parcels/${encodeURIComponent(id)}/verification`),
    getVerificationFindings: (id) =>
      request(`/parcels/${encodeURIComponent(id)}/verification/findings`),
    getParcelAudit: (id) =>
      request(`/parcels/${encodeURIComponent(id)}/audit`),
    getAudit: () => request("/audit"),
    getAuditVerify: () => request("/audit/verify"),
    getIntegrity: () => request("/integrity"),
    _resetBase: () => { _resolvedBase = null; _resolving = null; },
  };
})();

window.LandGuard = LandGuard;