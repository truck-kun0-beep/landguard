// LANDGUARD — minimal API client
// Wraps fetch with a single base URL + JSON error semantics.

const LandGuard = (() => {
  const DEFAULT_BASE = "../api"; // pages live under /frontend/*.html
  const base = () =>
    window.LANDGUARD_API_BASE ||
    (window.location.pathname.endsWith(".html") ? DEFAULT_BASE : "/api");

  async function request(path, opts = {}) {
    const url = `${base()}${path}`;
    const resp = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    if (!resp.ok) {
      let detail;
      try { detail = (await resp.json()).detail; } catch { /* ignore */ }
      const err = new Error(detail || `HTTP ${resp.status}`);
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
  };
})();

window.LandGuard = LandGuard;