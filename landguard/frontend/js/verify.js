// LANDGUARD — verify.js
// Search & map preview on the verify page.

const LandGuardVerify = (() => {
  const { esc, statusPill, setHTML, setText, empty } = LandGuardLayout;
  const api = LandGuard;

  let allParcels = [];

  function tokenize(s) {
    return (s || "").trim().toLowerCase().split(/\s+/).filter(Boolean);
  }

  function matches(p, tokens) {
    const haystack = [
      p.parcel_id,
      p.district,
      p.upazila,
      p.mouza,
      p.dag_no,
      p.khatian_no,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return tokens.every((t) => haystack.includes(t));
  }

  async function loadAll() {
    if (allParcels.length) return allParcels;
    allParcels = await api.listParcels();
    return allParcels;
  }

  async function fetchVerificationMap(parcels) {
    const out = {};
    await Promise.all(
      parcels.map(async (p) => {
        try { out[p.parcel_id] = await api.getVerification(p.parcel_id); }
        catch (e) {
          if (e.status !== 404) console.warn("verification load failed", p.parcel_id, e);
        }
      })
    );
    return out;
  }

  function renderResults(matchesList, verifications) {
    setText("resultCount", matchesList.length ? `(${matchesList.length})` : "");
    if (!matchesList.length) {
      setHTML("results", empty("No parcels match these filters."));
      return;
    }
    const html = matchesList
      .map((p) => {
        const v = verifications[p.parcel_id];
        const status = v ? statusPill(v.overall_status) : `<span class="pill neutral"><span class="dot"></span>NOT VERIFIED</span>`;
        return `
          <div class="result-card" onclick="window.location='parcel.html?id=${encodeURIComponent(p.parcel_id)}'">
            <div>
              <div class="id">${esc(p.parcel_id)}</div>
              <div class="meta">${esc(p.district || "")}${p.upazila ? " · " + esc(p.upazila) : ""}${p.mouza ? " · " + esc(p.mouza) : ""}${p.dag_no ? " · Dag " + esc(p.dag_no) : ""}${p.khatian_no ? " · Khatian " + esc(p.khatian_no) : ""}</div>
            </div>
            <div class="right">
              <div class="area">${p.area_decimal} decimal</div>
              ${status}
            </div>
          </div>
        `;
      })
      .join("");
    setHTML("results", `<div class="result-list">${html}</div>`);
  }

  function renderMap(matchesList, verifications) {
    if (typeof LandGuardMap === "undefined") return;
    const enriched = matchesList.map((p) => ({
      ...p,
      _verificationStatus: verifications[p.parcel_id]?.overall_status,
    }));
    LandGuardMap.renderParcels("map", enriched);
  }

  async function runSearch() {
    const idQ = tokenize(LandGuardLayout.el("q-id").value);
    const districtQ = tokenize(LandGuardLayout.el("q-district").value);
    const upazilaQ = tokenize(LandGuardLayout.el("q-upazila").value);

    const parcels = await loadAll();
    let filtered = parcels;
    if (idQ.length) filtered = filtered.filter((p) => matches(p, idQ));
    if (districtQ.length) filtered = filtered.filter((p) => matches(p, districtQ));
    if (upazilaQ.length) filtered = filtered.filter((p) => matches(p, upazilaQ));

    // Sort by parcel ID for deterministic ordering.
    filtered.sort((a, b) => (a.parcel_id < b.parcel_id ? -1 : 1));

    const verifications = await fetchVerificationMap(filtered);
    renderResults(filtered, verifications);
    renderMap(filtered, verifications);
  }

  async function boot() {
    const form = LandGuardLayout.el("searchForm");
    form.addEventListener("submit", (e) => { e.preventDefault(); runSearch(); });
    LandGuardLayout.el("clearBtn").addEventListener("click", () => {
      ["q-id", "q-district", "q-upazila"].forEach((id) => { LandGuardLayout.el(id).value = ""; });
      runSearch();
    });
    // Initial: show everything.
    await runSearch();
  }

  return { boot, runSearch };
})();

window.LandGuardVerify = LandGuardVerify;