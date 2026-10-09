"use client";

// SupplyMap (S4-07, arah Roy 2026-10-09) — MapLibre GL sungguhan,
// sesuai docs/design.md §5 (bukan lagi SVG skematik). Tile raster OSM
// gratis TANPA API key — aman untuk demo offline-ish (tile di-cache
// browser). Data REAL dari GET /balance/map (formula gap = panel —
// tanpa rumus kedua). Mount di client via useEffect (WebGL tidak ada
// di SSR); SSR tetap merender container + daftar angka.
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

// Kontrak warna design.md §4: danger merah, safe hijau, netral abu.
export function markerColor(status: string): string {
  if (status === "shortage") return "#C62828";
  if (status === "surplus") return "#2E7D32";
  return "#555555";
}

function fmtKg(v: number): string {
  return `${Number(v).toLocaleString("id-ID")} kg`;
}

// Batas kasar Indonesia dari titik-titik lokasi (dengan padding) —
// fit all markers tanpa hardcode bounding box.
function fitBoundsFor(locations: any[]): [[number, number], [number, number]] {
  const lats = locations.map((l) => Number(l.latitude));
  const lons = locations.map((l) => Number(l.longitude));
  const pad = 1.6;
  return [
    [Math.min(...lons) - pad, Math.min(...lats) - pad],
    [Math.max(...lons) + pad, Math.max(...lats) + pad],
  ];
}

export default function SupplyMap({
  locations,
  commodity,
}: {
  locations: any[];
  commodity?: string;
}) {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current || !locations?.length) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.AttributionControl(), "bottom-right");
    map.fitBounds(fitBoundsFor(locations), { padding: 40, duration: 0 });

    locations.forEach((l) => {
      if (l.latitude == null || l.longitude == null) return;
      const label =
        l.status === "shortage"
          ? `kurang ${fmtKg(l.shortage_kg)}`
          : l.status === "surplus"
            ? `lebih ${fmtKg(l.surplus_kg)}`
            : "seimbang";
      const el = document.createElement("div");
      el.className = `map-marker map-marker-${l.status}`;
      el.title = `${l.location} — pasokan ${fmtKg(l.supply_kg)}, permintaan ${fmtKg(l.demand_kg)}, ${label}`;
      new maplibregl.Marker({ color: markerColor(l.status), element: el })
        .setLngLat([Number(l.longitude), Number(l.latitude)])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<strong>${l.location}</strong><br/>pasokan ${fmtKg(l.supply_kg)} · permintaan ${fmtKg(l.demand_kg)}<br/><em>${label}</em>`
          )
        )
        .addTo(map);
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [locations]);

  if (!locations?.length) {
    return (
      <section className="map-card card" aria-busy="true">
        <h3>Peta Kondisi</h3>
        <p className="map-empty">
          Belum ada data peta — pilih komoditas untuk memuat kondisi semua
          lokasi.
        </p>
      </section>
    );
  }

  return (
    <section className="map-card card" aria-label="Peta kondisi komoditas">
      <div className="card-header">
        <h3>Peta Kondisi{commodity ? ` — ${commodity}` : ""}</h3>
        <span className="map-attrib">MapLibre GL · tile OpenStreetMap · koordinat dari database</span>
      </div>
      <div className="map-body">
        {/* Container peta — dirender SSR, MapLibre menempel di client */}
        <div ref={mapContainer} className="map-gl" />
        <div className="map-side">
          <div className="map-legend" aria-label="Legenda status">
            <span className="map-legend-item">
              <i className="map-dot map-dot-shortage" /> Shortage
            </span>
            <span className="map-legend-item">
              <i className="map-dot map-dot-surplus" /> Surplus
            </span>
            <span className="map-legend-item">
              <i className="map-dot map-dot-balanced" /> Seimbang
            </span>
          </div>
          <ul className="map-list">
            {locations.map((l) => (
              <li key={l.location} className={`map-row map-row-${l.status}`}>
                <i className={`map-dot map-dot-${l.status}`} aria-hidden="true" />
                <span className="map-row-name">{l.location}</span>
                <span className="map-row-numbers">
                  {fmtKg(l.supply_kg)} / {fmtKg(l.demand_kg)}
                </span>
                <span className="map-row-gap">
                  {l.status === "shortage"
                    ? `kurang ${fmtKg(l.shortage_kg)}`
                    : l.status === "surplus"
                      ? `lebih ${fmtKg(l.surplus_kg)}`
                      : "seimbang"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
