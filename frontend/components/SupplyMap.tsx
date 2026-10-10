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
import {
  formatBalanceGap,
  formatBalanceStatus,
  formatKg,
  type BalanceMapLocation,
} from "../lib/overview-format";

// Kontrak warna design.md §4: danger merah, safe hijau, netral abu.
export function markerColor(status: string): string {
  if (status === "shortage") return "#C62828";
  if (status === "surplus") return "#2E7D32";
  if (status === "balanced") return "#555555";
  return "#92400E";
}

function fitBoundsFor(locations: readonly BalanceMapLocation[]): [[number, number], [number, number]] {
  const points = locations.flatMap((location) => {
    const latitude = Number(location.latitude);
    const longitude = Number(location.longitude);
    return Number.isFinite(latitude) && Number.isFinite(longitude) ? [[latitude, longitude] as const] : [];
  });
  if (!points.length) return [[105, -8], [109, -5]];
  const lats = points.map(([latitude]) => latitude);
  const lons = points.map(([, longitude]) => longitude);
  const pad = 1.6;
  return [[Math.min(...lons) - pad, Math.min(...lats) - pad], [Math.max(...lons) + pad, Math.max(...lats) + pad]];
}

export default function SupplyMap({
  locations,
  commodity,
}: {
  locations: readonly BalanceMapLocation[];
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
      const label = formatBalanceGap(l);
      const el = document.createElement("div");
      el.className = `map-marker map-marker-${l.status}`;
      el.title = `${l.location} — pasokan ${formatKg(l.supply_kg)}, permintaan ${formatKg(l.demand_kg)}, ${label}`;
      new maplibregl.Marker({ color: markerColor(l.status), element: el })
        .setLngLat([Number(l.longitude), Number(l.latitude)])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<strong>${l.location}</strong><br/>pasokan ${formatKg(l.supply_kg)} · permintaan ${formatKg(l.demand_kg)}<br/><em>${label}</em>`
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
      <section className="map-card card" aria-label="Peta kondisi komoditas">
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
          {/* Kepala bagian ala acuan: judul + jumlah lokasi + legenda status
              (kolom tabel lama tidak dipakai lagi karena kartu kini bertumpuk
              dalam grid, bukan baris tabel). */}
          <div className="map-section-head">
            <h3>Status Lokasi</h3>
            <span className="map-section-count">{locations.length} Lokasi</span>
            <span className="map-legend" aria-label="Legenda status">
              <span className="map-legend-item">
                <i className="map-dot map-dot-shortage" aria-hidden="true" /> Shortage
              </span>
              <span className="map-legend-item">
                <i className="map-dot map-dot-surplus" aria-hidden="true" /> Surplus
              </span>
              <span className="map-legend-item">
                <i className="map-dot map-dot-balanced" aria-hidden="true" /> Seimbang
              </span>
            </span>
          </div>
          <ul className="map-list">
            {locations.map((l) => (
              <li key={l.location} className={`map-row map-row-${l.status}`}>
                <i className={`map-dot map-dot-${l.status}`} aria-hidden="true" />
                <span className="map-row-name">{l.location}</span>
                <span className="map-row-status">
                  {formatBalanceStatus(l.status)}
                </span>
                <span className="map-row-supply">Pasokan: {formatKg(l.supply_kg)}</span>
                <span className="map-row-demand">Kebutuhan: {formatKg(l.demand_kg)}</span>
                <span className="map-row-gap">Selisih: {formatBalanceGap(l)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
