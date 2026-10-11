"use client";

// SupplyMap (S4-07, arah Roy 2026-10-09) — MapLibre GL sungguhan, sesuai
// docs/design.md §5 (bukan SVG skematik). Tile raster OSM gratis TANPA API key;
// data REAL dari GET /balance/map (formula gap = panel, tanpa rumus kedua).
// Mount di client via useEffect (WebGL tidak ada di SSR); SSR tetap merender
// container + daftar angka.
//
// Gaya peta (arah Roy 2026-10-11, setelah revisi): PETA TERANG seperti acuan —
// kanvas OSM apa adanya (tanpa penggelapan), legenda putih "Status lokasi"
// kiri-bawah, kontrol bawaan MapLibre (zoom + kompas) kanan-atas, dan atribusi
// kanan-bawah. Tanpa kepala panel mengapung dan tanpa kaki panel.
// Warna pin & legenda memakai token status aplikasi (`--status-*`), sama dengan
// badge di permukaan terang; tidak ada hex di komponen ini.
import { useCallback, useEffect, useMemo, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  formatBalanceGap,
  formatBalanceStatus,
  formatKg,
  type BalanceMapLocation,
} from "../lib/overview-format";
import {
  MAP_FOCUS_INITIAL,
  nextMapFocus,
  pinDiff,
  pinLabel,
  pinSignatures,
  pinTone,
  type MapFocus,
} from "../lib/map-console";

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

/** Konten popup dibangun sebagai NODE (bukan HTML string): nama lokasi datang
 *  dari database, jadi jangan ditempel ke innerHTML. */
function popupNode(location: BalanceMapLocation): HTMLElement {
  const box = document.createElement("div");
  box.className = "map-popup";
  const title = document.createElement("strong");
  title.textContent = location.location;
  const numbers = document.createElement("p");
  numbers.textContent = `pasokan ${formatKg(location.supply_kg)} · permintaan ${formatKg(location.demand_kg)}`;
  const gap = document.createElement("em");
  gap.textContent = formatBalanceGap(location);
  box.append(title, numbers, gap);
  return box;
}

/** Membuat penanda satu lokasi (titik + label + popup). Node DOM — nama lokasi
 *  datang dari database, jadi bukan innerHTML. */
function createPin(map: maplibregl.Map, location: BalanceMapLocation, active: boolean): maplibregl.Marker {
  const el = document.createElement("div");
  el.className = `map-pin map-pin-${pinTone(location.status)}${active ? " map-pin-active" : ""}`;
  const accessible = pinAccessibleLabel(location);
  el.title = accessible;
  el.setAttribute("aria-label", accessible);
  // Titik + label sebagai DUA node: elemen marker tetap seukuran titik supaya
  // koordinat lokasi tepat di tengah titik (label meluber ke kanan).
  const dot = document.createElement("span");
  dot.className = "map-pin-dot";
  dot.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.className = "map-pin-label";
  label.textContent = pinLabel(location);
  el.append(dot, label);
  return new maplibregl.Marker({ element: el })
    .setLngLat([Number(location.longitude), Number(location.latitude)])
    .setPopup(new maplibregl.Popup({ offset: 14 }).setDOMContent(popupNode(location)))
    .addTo(map);
}

/** Segarkan isi penanda yang sudah ada (posisi, label, keterangan, popup) —
 *  tanpa menyentuh kamera peta. Dipakai saat sinkronisasi data. */
function refreshPin(marker: maplibregl.Marker, location: BalanceMapLocation): void {
  const el = marker.getElement();
  const wasActive = el.classList.contains("map-pin-active");
  el.className = `map-pin map-pin-${pinTone(location.status)}${wasActive ? " map-pin-active" : ""}`;
  const accessible = pinAccessibleLabel(location);
  el.title = accessible;
  el.setAttribute("aria-label", accessible);
  const label = el.querySelector(".map-pin-label");
  if (label) label.textContent = pinLabel(location);
  marker.setLngLat([Number(location.longitude), Number(location.latitude)]);
  marker.setPopup(new maplibregl.Popup({ offset: 14 }).setDOMContent(popupNode(location)));
}

/** Keterangan penanda untuk pembaca layar (MapLibre menandai tiap penanda
 *  "Map marker"; sepuluh penanda tanpa keterangan tidak berguna). */
function pinAccessibleLabel(location: BalanceMapLocation): string {
  return `${location.location} — pasokan ${formatKg(location.supply_kg)}, permintaan ${formatKg(location.demand_kg)}, ${formatBalanceGap(location)}`;
}

/**
 * Daftar status per lokasi (kartu bertumpuk dalam grid).
 *
 * Dipisah dari peta supaya bisa dirender sebagai bagian tersendiri selebar
 * halaman — tata letak dashboard acuan: peta + grafik berdampingan, daftar
 * lokasi di bawahnya. `SupplyMap` tetap merendernya secara bawaan supaya
 * kontrak render lama (dan tesnya) tidak berubah.
 */
export function StatusLocationList({
  locations,
}: {
  locations: readonly BalanceMapLocation[];
}) {
  if (!locations.length) return null;

  return (
    <>
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
    </>
  );
}

export default function SupplyMap({
  loading = false,
  locations,
  commodity,
  activeLocation = null,
  showStatusList = true,
  showHeader = true,
}: {
  locations: readonly BalanceMapLocation[];
  commodity?: string;
  /** Lokasi yang sedang disorot (dipilih dari dropdown cakupan di top bar).
   *  Nilai tak dikenal / "__all__" = tampilan semua lokasi (gagal-tertutup,
   *  tidak ada tebakan). */
  activeLocation?: string | null;
  /** Data peta belum tiba: tampilkan skeleton, bukan pesan "belum ada data". */
  loading?: boolean;
  /** false = daftar status dirender pemanggil sendiri (mis. selebar halaman). */
  showStatusList?: boolean;
  /** false = pembungkus halaman sudah menulis judul kartunya sendiri. */
  showHeader?: boolean;
}) {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  // Marker per lokasi — dipakai efek sinkronisasi di bawah (tanpa membangun
  // ulang peta).
  const markersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  // Data terbaru dibaca lewat ref: peta dibangun SEKALI, sedangkan sinkronisasi
  // (polling 5 detik) hanya memperbarui isi penanda. Kalau efek pembangunan peta
  // bergantung pada array `locations` — yang identitasnya berganti tiap polling —
  // peta dibongkar-pasang tiap 5 detik dan zoom/geser pengguna ikut tersentak.
  const locationsRef = useRef<readonly BalanceMapLocation[]>(locations);
  const activeLocationRef = useRef<string | null>(activeLocation ?? null);
  // Isi penanda terakhir (tanda tangan, bukan identitas objek) + keadaan fokus
  // peta. Keduanya murni & diuji di lib/map-console.ts.
  const pinSignaturesRef = useRef<Record<string, string>>({});
  const focusRef = useRef<MapFocus>(MAP_FOCUS_INITIAL);

  const hasLocations = Boolean(locations?.length);
  // Pemicu sinkronisasi = tanda tangan ISI data, bukan identitas array.
  const pinSnapshot = useMemo(() => pinSignatures(locations ?? []), [locations]);

  // Ref data terbaru (efek ini tidak menyentuh kamera peta sama sekali).
  useEffect(() => {
    locationsRef.current = locations;
    activeLocationRef.current = activeLocation ?? null;
  }, [locations, activeLocation]);

  /** Sinkronkan penanda dengan data terbaru: tambah / ubah isi / buang.
   *  Tidak ada fitBounds di sini — zoom & geser pengguna tidak disentuh. */
  const syncMarkers = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const rows = (locationsRef.current ?? []).filter(
      (l) => Number.isFinite(Number(l.latitude)) && Number.isFinite(Number(l.longitude))
    );
    const next = pinSignatures(rows);
    const diff = pinDiff(pinSignaturesRef.current, next);
    diff.removed.forEach((name) => {
      markersRef.current.get(name)?.remove();
      markersRef.current.delete(name);
    });
    rows.forEach((row) => {
      const existing = markersRef.current.get(row.location);
      if (!existing) {
        markersRef.current.set(
          row.location,
          createPin(map, row, row.location === activeLocationRef.current)
        );
        return;
      }
      // Hanya penanda yang isinya benar-benar berubah yang disentuh.
      if (diff.changed.includes(row.location)) refreshPin(existing, row);
    });
    pinSignaturesRef.current = next;
  }, []);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current || !locationsRef.current?.length) return;
    // Salinan ref untuk cleanup: nilai `.current` bisa berubah sebelum cleanup
    // dijalankan (aturan react-hooks/exhaustive-deps).
    const markers = markersRef.current;
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
    // Kontrol bawaan: zoom + kompas kanan-atas, atribusi (© OpenStreetMap
    // contributors · MapLibre) kanan-bawah — seperti acuan.
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-right");
    // Fokus awal (semua lokasi). Efek fokus di bawah yang mengarahkan ke lokasi
    // aktif bila ada. Setelah ini peta TIDAK pernah dibangun ulang lagi.
    map.fitBounds(fitBoundsFor(locationsRef.current), { padding: 40, duration: 0 });
    syncMarkers();

    // Kontainer berubah ukuran (jendela, sidebar dilipat, breakpoint tata
    // letak) tanpa MapLibre mengetahuinya — tanpa ini peta tertinggal di
    // ukuran saat dibuat.
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(mapContainer.current);

    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
      markers.clear();
      pinSignaturesRef.current = {};
      focusRef.current = MAP_FOCUS_INITIAL;
    };
  }, [hasLocations, syncMarkers]);

  // Sinkronisasi data (arah Roy 2026-10-11): penanda saja, tanpa fitBounds.
  useEffect(() => {
    syncMarkers();
  }, [pinSnapshot, syncMarkers]);

  // Sorotan lokasi aktif. Peta hanya di-dekatkan saat PILIHAN lokasi berubah
  // (sinkronisasi tidak boleh menarik kembali peta yang baru digeser).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((marker, name) => {
      marker.getElement().classList.toggle("map-pin-active", name === activeLocation);
    });
    const decision = nextMapFocus(focusRef.current, activeLocation ?? null);
    focusRef.current = decision.focus;
    if (!decision.fit) return;
    const target = (locationsRef.current ?? []).find((l) => l.location === activeLocation);
    const latitude = Number(target?.latitude);
    const longitude = Number(target?.longitude);
    if (target && Number.isFinite(latitude) && Number.isFinite(longitude)) {
      const pad = 0.12;
      map.fitBounds(
        [
          [longitude - pad, latitude - pad],
          [longitude + pad, latitude + pad],
        ],
        { padding: 40, duration: 600 }
      );
      return;
    }
    map.fitBounds(fitBoundsFor(locationsRef.current), { padding: 40, duration: 600 });
  }, [activeLocation, pinSnapshot]);

  if (!locations?.length) {
    return (
      <section
        className={showHeader ? "map-card card" : "map-card"}
        aria-label="Peta kondisi komoditas"
        aria-busy={loading || undefined}
      >
        {showHeader && <h3>Peta Kondisi</h3>}
        {loading ? (
          <>
            <p className="sr-only" aria-live="polite">
              Memuat peta kondisi semua lokasi…
            </p>
            <div className="skeleton skeleton-map" aria-hidden="true" />
          </>
        ) : (
          <p className="map-empty">
            Belum ada data peta — pilih komoditas untuk memuat kondisi semua
            lokasi.
          </p>
        )}
      </section>
    );
  }

  return (
    <section
      className={showHeader ? "map-card card" : "map-card"}
      aria-label="Peta kondisi komoditas"
    >
      {showHeader && (
        <div className="card-header">
          <h3>Peta Kondisi{commodity ? ` — ${commodity}` : ""}</h3>
          <span className="map-attrib">MapLibre GL · tile OpenStreetMap · koordinat dari database</span>
        </div>
      )}
      <div className="map-body">
        {/* Container peta — dirender SSR, MapLibre menempel di client */}
        <div className="map-shell">
          <div ref={mapContainer} className="map-gl" />
          <div className="map-legend-box" role="group" aria-label="Legenda status lokasi">
            <span className="map-legend-box-title">Status lokasi:</span>
            <span className="map-legend-box-item">
              <i className="map-legend-box-dot map-legend-box-dot-surplus" aria-hidden="true" /> Surplus
            </span>
            <span className="map-legend-box-item">
              <i className="map-legend-box-dot map-legend-box-dot-balanced" aria-hidden="true" /> Seimbang
            </span>
            <span className="map-legend-box-item">
              <i className="map-legend-box-dot map-legend-box-dot-shortage" aria-hidden="true" /> Shortage
            </span>
          </div>
        </div>
        {showStatusList && (
          <div className="map-side">
            <StatusLocationList locations={locations} />
          </div>
        )}
      </div>
    </section>
  );
}
