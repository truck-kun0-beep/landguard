// LANDGUARD — Leaflet map helper
// Renders parcel polygons from the existing JSON geometry_geojson.
// Labeled clearly as synthetic demo data.

const LandGuardMap = (() => {
  let mapInstance = null;
  let polygonsLayer = null;

  function colorFor(parcel) {
    // Pick a color by status if available, otherwise neutral.
    const status = parcel._verificationStatus;
    if (status === "CONFLICT_DETECTED") return { color: "#a3261f", fillColor: "#fbe3e1" };
    if (status === "REVIEW_REQUIRED") return { color: "#8a5a00", fillColor: "#fbf0d6" };
    if (status === "VERIFIED") return { color: "#1d6f42", fillColor: "#e0f1e7" };
    return { color: "#0f4c81", fillColor: "#e7eef7" };
  }

  function popupHtml(parcel) {
    const area = parcel.area_decimal;
    const district = parcel.district || "";
    const upazila = parcel.upazila || "";
    const status = parcel._verificationStatus
      ? `<div class="map-popup-meta">Verification: <b>${parcel._verificationStatus}</b></div>`
      : "";
    return `
      <div>
        <div class="map-popup-title">${parcel.parcel_id}</div>
        <div class="map-popup-meta">${district}${upazila ? " · " + upazila : ""}</div>
        <div class="map-popup-meta">Area: <b>${area}</b> decimal</div>
        ${status}
        <a class="map-popup-link" href="parcel.html?id=${encodeURIComponent(parcel.parcel_id)}">
          Open Land Passport →
        </a>
      </div>
    `;
  }

  function fitToGeometry(map, geojson) {
    if (!geojson || !geojson.coordinates) return;
    const coords = geojson.coordinates[0] || [];
    if (!coords.length) return;
    const lats = coords.map((c) => c[1]);
    const lngs = coords.map((c) => c[0]);
    const bounds = [
      [Math.min(...lats), Math.min(...lngs)],
      [Math.max(...lats), Math.max(...lngs)],
    ];
    map.fitBounds(bounds, { padding: [20, 20] });
  }

  function ensureMap(containerId) {
    if (mapInstance) return mapInstance;
    const c = document.getElementById(containerId);
    if (!c) return null;
    mapInstance = L.map(containerId, {
      zoomControl: true,
      attributionControl: true,
    }).setView([23.78, 90.41], 7); // Bangladesh-ish default
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · Synthetic demo data',
    }).addTo(mapInstance);
    polygonsLayer = L.layerGroup().addTo(mapInstance);
    return mapInstance;
  }

  function renderParcels(containerId, parcels, opts = {}) {
    const map = ensureMap(containerId);
    if (!map) return;
    polygonsLayer.clearLayers();

    const focusGeometry = opts.focusedGeometry || null;
    const focusParcelId = opts.focusedParcelId || null;

    parcels.forEach((p) => {
      if (!p.geometry_geojson) return;
      const { color, fillColor } = colorFor(p);
      const isFocus = p.parcel_id === focusParcelId;
      const poly = L.geoJSON(p.geometry_geojson, {
        style: () => ({
          color,
          weight: isFocus ? 3 : 2,
          fillColor,
          fillOpacity: isFocus ? 0.55 : 0.35,
          dashArray: isFocus ? null : "4 4",
        }),
      });
      poly.bindPopup(popupHtml(p));
      poly.on("click", () => {
        if (opts.onSelect) opts.onSelect(p);
      });
      poly.addTo(polygonsLayer);
    });

    if (focusGeometry) {
      fitToGeometry(map, focusGeometry);
    } else if (parcels.length) {
      const all = L.featureGroup(parcels.map((p) => L.geoJSON(p.geometry_geojson)));
      map.fitBounds(all.getBounds(), { padding: [24, 24] });
    }
  }

  function renderOne(containerId, parcel, opts = {}) {
    return renderParcels(containerId, [parcel], {
      focusedGeometry: parcel.geometry_geojson,
      focusedParcelId: parcel.parcel_id,
      onSelect: opts.onSelect,
    });
  }

  return { renderParcels, renderOne, ensureMap };
})();

window.LandGuardMap = LandGuardMap;