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
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  dataSourceNote,
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
// Kendali tampilan peta (langkah 7b-1): label + ikon tombol "Tampilkan semua".
// Judulnya fungsi murni karena kalimat itu JANJI — lihat lib/map-view.ts.
import {
  MAP_RESET_ICON,
  MAP_RESET_LABEL,
  lokalkanPesanGesture,
  mapCooperativeGestures,
  mapResetTitle,
} from "../lib/map-view";
// Baris legenda ringkas di bawah kanvas (C2, langkah 7b-2): aturan isinya
// (status selalu ada, keterangan ikut sakelar lapisan) hidup di lib murni.
import { compactLegendItems, legendMarkClass } from "../lib/map-legend-compact";
import {
  SUPPLIER_LABEL_MIN_ZOOM,
  SUPPLIER_PIN_LEGEND,
  SUPPLIER_PIN_MIN_ZOOM,
  supplierAccessibleLabel,
  supplierDistanceReference,
  supplierReachMeta,
  supplierLayerSummary,
  supplierLabelsVisible,
  supplierPinClass,
  supplierPinRows,
  supplierPinsForMap,
  supplierPinsVisible,
  supplierPopupLines,
  supplierReachNote,
  supplierReachTag,
  supplierToggleAction,
  supplierToggleLabel,
  suppliersForCommodity,
  type SupplierPinRow,
} from "../lib/supplier-pins";
import {
  ROUTE_LINE_COLORS,
  routeBoundsPoints,
  routeGeoJson,
  routeJourneyRows,
  routeLayerSummary,
  routeLayerTag,
  routeLegendEntries,
  routeLineClass,
  routePopupLines,
  routeToggleAction,
  routeToggleLabel,
  supplierRoutes as supplierRouteRows,
  type SupplierRoute,
} from "../lib/supplier-routes";
import {
  FOCUS_ALL,
  FOCUS_CLEAR_LABEL,
  focusFilterText,
  focusLineFeatures,
  focusOptions,
  focusPick,
} from "../lib/route-focus";
import RouteFocusPicker from "./RouteFocusPicker";

/** Id source/layer MapLibre untuk garis jalur kiriman (Fase 10). */
const ROUTE_SOURCE_ID = "supplier-routes";
const ROUTE_LAYER_ID = "supplier-route-line";
// Garis SOROTAN (Arah C): satu source berisi sampai dua potong — padat = sudah
// ditempuh, putus-putus = belum. Dipisah dari layer dasar supaya aturan warna
// layer dasar tidak perlu diubah sama sekali.
const ROUTE_FOCUS_SOURCE_ID = "supplier-route-focus";
const ROUTE_FOCUS_DONE_LAYER_ID = "supplier-route-focus-done";
const ROUTE_FOCUS_TODO_LAYER_ID = "supplier-route-focus-todo";

/** Id panel rincian lapisan — dipakai `aria-controls` tombol lipatnya. */
/**
 * Pembungkus `matchMedia` yang aman di lingkungan tanpa DOM penuh (uji jsdom
 * tidak menyediakan `matchMedia`). Tanpa jawaban media query, peta memakai
 * perilaku bawaan desktop — bukan menebak "ini ponsel".
 */
function mediaQueryCocok(query: string): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia(query).matches;
}

const LAYER_INFO_PANEL_ID = "map-layer-info-panel";
const LEGEND_PANEL_ID = "map-legend-panel";

const ROUTE_LINE_WIDTH: maplibregl.ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["zoom"],
  5,
  2,
  10,
  4,
];

// Garis sorotan (Arah C) lebih tebal 2 px pada tiap tingkat zoom. Ditulis sebagai
// ekspresi sendiri karena `ROUTE_LINE_WIDTH` adalah ExpressionSpecification —
// menambahkan angka ke ekspresi menghasilkan error tipe (dan peta diam saja).
const ROUTE_FOCUS_WIDTH: maplibregl.ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["zoom"],
  5,
  4,
  10,
  6,
];

function fitBoundsFor(
  locations: readonly BalanceMapLocation[],
  extraPoints: readonly [number, number][] = [],
  pad = 1.6
): [[number, number], [number, number]] {
  const points = locations.flatMap((location) => {
    const latitude = Number(location.latitude);
    const longitude = Number(location.longitude);
    return Number.isFinite(latitude) && Number.isFinite(longitude) ? [[latitude, longitude] as const] : [];
  });
  // Ujung jalur kiriman (dari `routeBoundsPoints`, urutan [lon, lat]) ikut
  // menentukan batas: tanpa itu, pemasok pengirim yang berada di luar cakupan
  // peta SPPG akan tampak "tidak ada", padahal kirimannya sedang jalan.
  const extra = extraPoints
    .filter(([lon, lat]) => Number.isFinite(lon) && Number.isFinite(lat))
    .map(([lon, lat]) => [lat, lon] as const);
  const semua = [...points, ...extra];
  if (!semua.length) return [[105, -8], [109, -5]];
  const lats = semua.map(([latitude]) => latitude);
  const lons = semua.map(([, longitude]) => longitude);
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
  // Asal nilai (PLAN-023) hanya muncul di RINCIAN: lokasi tanpa baris
  // permintaan/pasokan tidak lagi tampak seperti angka terukur.
  const note = dataSourceNote(location);
  if (note) {
    const catatan = document.createElement("span");
    catatan.className = "map-popup-note";
    catatan.textContent = note;
    box.append(catatan);
  }
  return box;
}

/** Membuat penanda satu lokasi (titik + label + popup). Node DOM — nama lokasi
 *  datang dari database, jadi bukan innerHTML. */
function createPin(map: maplibregl.Map, location: BalanceMapLocation, active: boolean): maplibregl.Marker {
  const el = document.createElement("div");
  el.className = `map-pin map-pin-${pinTone(location.status)}${active ? " map-pin-active" : ""}`;
  const accessible = pinAccessibleLabel(location);
  // Titik + label sebagai DUA node: elemen marker tetap seukuran titik supaya
  // koordinat lokasi tepat di tengah titik (label meluber ke kanan).
  const dot = document.createElement("span");
  dot.className = "map-pin-dot";
  dot.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.className = "map-pin-label";
  label.textContent = pinLabel(location);
  el.append(dot, label);
  const marker = new maplibregl.Marker({ element: el })
    .setLngLat([Number(location.longitude), Number(location.latitude)])
    .setPopup(new maplibregl.Popup({ offset: 14 }).setDOMContent(popupNode(location)))
    .addTo(map);
  // Keterangan aksesibilitas dipasang SETELAH marker dibuat: MapLibre 4.7
  // menulis aria-label="Map marker" pada elemen saat konstruksi, menimpa teks
  // yang dipasang sebelumnya — pembaca layar lalu membacakan "Map marker" untuk
  // setiap penanda.
  el.title = accessible;
  el.setAttribute("aria-label", accessible);
  return marker;
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
  const note = dataSourceNote(location);
  const dasar = `${location.location} — pasokan ${formatKg(location.supply_kg)}, permintaan ${formatKg(location.demand_kg)}, ${formatBalanceGap(location)}`;
  return note ? `${dasar}, ${note}` : dasar;
}

/** Isi popup pemasok — NODE DOM, bukan innerHTML (nama pemasok dari DB). */
function supplierPopupNode(row: SupplierPinRow, reachKm: number | null): HTMLElement {
  const { title, lines } = supplierPopupLines(row, reachKm);
  const box = document.createElement("div");
  box.className = "map-popup map-popup-supplier";
  const head = document.createElement("strong");
  head.textContent = title;
  box.append(head);
  lines.forEach((line) => {
    const p = document.createElement("p");
    p.textContent = line;
    box.append(p);
  });
  return box;
}

/** Penanda pemasok: BENTUK berbeda dari pin SPPG (kotak miring, bukan titik
 *  bulat) supaya dua lapisan tidak bisa tertukar di peta yang sama. */
function createSupplierPin(
  map: maplibregl.Map,
  row: SupplierPinRow,
  showLabels: boolean,
  reachKm: number | null
): maplibregl.Marker {
  const el = document.createElement("div");
  el.className = supplierPinClass(row, showLabels, reachKm);
  const accessible = supplierAccessibleLabel(row, reachKm);
  const dot = document.createElement("span");
  dot.className = "map-pin-supplier-dot";
  dot.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.className = "map-pin-label";
  label.textContent = row.name;
  el.append(dot, label);
  const marker = new maplibregl.Marker({ element: el })
    .setLngLat([row.longitude, row.latitude])
    .setPopup(new maplibregl.Popup({ offset: 14 }).setDOMContent(supplierPopupNode(row, reachKm)))
    .addTo(map);
  // Sama seperti pin SPPG: MapLibre menimpa aria-label saat konstruksi.
  el.title = accessible;
  el.setAttribute("aria-label", accessible);
  return marker;
}

/** Segarkan penanda pemasok yang sudah ada (posisi, nada, keterangan, popup). */
function refreshSupplierPin(
  marker: maplibregl.Marker,
  row: SupplierPinRow,
  showLabels: boolean,
  reachKm: number | null
): void {
  const el = marker.getElement();
  el.className = supplierPinClass(row, showLabels, reachKm);
  const accessible = supplierAccessibleLabel(row, reachKm);
  el.title = accessible;
  el.setAttribute("aria-label", accessible);
  const label = el.querySelector(".map-pin-label");
  if (label) label.textContent = row.name;
  marker.setLngLat([row.longitude, row.latitude]);
  marker.setPopup(
    new maplibregl.Popup({ offset: 14 }).setDOMContent(supplierPopupNode(row, reachKm))
  );
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
        {locations.map((l) => {
          const note = dataSourceNote(l);
          return (
            <li key={l.location} className={`map-row map-row-${l.status}`}>
              <i className={`map-dot map-dot-${l.status}`} aria-hidden="true" />
              <span className="map-row-name">{l.location}</span>
              <span className="map-row-status">
                {formatBalanceStatus(l.status)}
              </span>
              <span className="map-row-supply">Pasokan: {formatKg(l.supply_kg)}</span>
              <span className="map-row-demand">Kebutuhan: {formatKg(l.demand_kg)}</span>
              <span className="map-row-gap">Selisih: {formatBalanceGap(l)}</span>
              {note && <span className="map-row-note">{note}</span>}
            </li>
          );
        })}
      </ul>
    </>
  );
}

/** Popup jalur kiriman: identitas jalur, jarak & durasi JALAN (OSRM), perjalanan
 *  (jam berangkat + estimasi tiba dari server), masa layak, dan mutu kiriman.
 *  Jarak lurus/rasio sengaja TIDAK lagi ditulis (arah pemilik 2026-10-16). */
function routePopupNode(row: SupplierRoute): HTMLElement {
  const box = document.createElement("div");
  box.className = "map-popup";
  const title = document.createElement("strong");
  title.textContent = `${row.supplierName} → ${row.destinationName}`;
  box.appendChild(title);
  const swatch = document.createElement("i");
  swatch.className = routeLineClass(row);
  swatch.setAttribute("aria-hidden", "true");
  box.appendChild(swatch);
  for (const baris of routePopupLines(row)) {
    const p = document.createElement("p");
    p.className = "map-popup-line";
    p.textContent = baris;
    box.appendChild(p);
  }
  return box;
}

export default function SupplyMap({
  loading = false,
  locations,
  commodity,
  activeLocation = null,
  showStatusList = true,
  showHeader = true,
  suppliers = null,
  supplierRoutes = null,
  reachKm = null,
  focusedRouteId = null,
  onFocusRoute = null,
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
  /** Payload `GET /suppliers` (amplop atau array) — layer pemasok. Lapisan ini
   *  mati secara bawaan: pemilik proyek memintanya sebagai tambahan, bukan
   *  pengganti pin SPPG, dan 30+ pin kota pada zoom Indonesia akan menutupi
   *  pin SPPG. */
  suppliers?: unknown;
  /** Payload `GET /supplier-routes` (amplop `{routes}` atau array) — garis JALUR
   *  KIRIMAN pemasok → tujuan (Fase 10). Dinyalakan secara bawaan: inilah yang
   *  diminta pemilik proyek (2026-10-16) untuk diperlihatkan di peta. Geometrinya
   *  datang dari cache OSRM di server, jadi peta sendiri tidak memanggil jaringan. */
  supplierRoutes?: unknown;
  /** Ambang jangkauan (km) untuk pin pemasok; `null` = tampilan nasional
   *  (Fase 7b). Peran SPPG memakai 150 km — diputuskan di pemanggil lewat
   *  `supplierReachKmForRole`, bukan di dalam peta, supaya aturannya satu tempat. */
  reachKm?: number | null;
  /** Kiriman yang sedang DISOROT (Arah C). `null` = semua kiriman; id tak dikenal
   *  diperlakukan sama (gagal-tertutup, lihat `lib/route-focus.ts`). */
  focusedRouteId?: string | null;
  /** Pemilih harus dikendalikan pemanggil (peta + kartu kiriman memakai pilihan
   *  yang SAMA). `null` = pemilih tidak dirender — peta tetap bisa dipakai tanpa
   *  Arah C (mis. di tab yang tidak punya kartu kiriman). */
  onFocusRoute?: ((id: string) => void) | null;
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
  /** Tombol "Tampilkan semua" (langkah 7b-1) — elemennya dibuat MapLibre di
   *  dalam grup kontrol kanan-atas; ref ini yang memegang elemennya supaya
   *  judul/aria-label bisa diperbarui saat data berubah. */
  const resetButtonRef = useRef<HTMLButtonElement | null>(null);
  /** Fungsi "kembalikan tampilan" terbaru. Kontrol MapLibre dibuat SEKALI, jadi
   *  klik-nya harus memanggil versi terbaru — bukan salinan saat peta dibangun
   *  (klik setelah lapisan jalur dinyalakan/matikan harus ikut menyesuaikan). */
  const fitAllRef = useRef<() => void>(() => {});

  const hasLocations = Boolean(locations?.length);
  // Pemicu sinkronisasi = tanda tangan ISI data, bukan identitas array.
  const pinSnapshot = useMemo(() => pinSignatures(locations ?? []), [locations]);

  // --- Layer pemasok (Fase 3) ---------------------------------------------
  // Lapisan mati secara bawaan; pengguna menyalakannya sendiri.
  const [showSuppliers, setShowSuppliers] = useState(false);
  // null = belum tahu (SSR / peta belum siap) — pesan "perbesar peta" hanya
  // muncul setelah zoom benar-benar diketahui, bukan dari tebakan.
  const [zoomEnough, setZoomEnough] = useState<boolean | null>(null);
  const supplierRows = useMemo(
    () => suppliersForCommodity(supplierPinRows(suppliers), commodity ?? null),
    [suppliers, commodity]
  );
  // Rujukan jarak dari server (untuk kalimat "…dari SPPG Jakarta"), bukan hitungan UI.
  const supplierReference = useMemo(
    () => supplierDistanceReference(suppliers),
    [suppliers]
  );
  // Kalau server sudah menyaring (`reach.max_distance_km` terisi), jumlah yang
  // dibuang datang dari server — UI tidak menghitung ulang atau menebaknya.
  const supplierReach = useMemo(() => supplierReachMeta(suppliers), [suppliers]);
  const hiddenByServer =
    supplierReach.maxDistanceKm === null ? 0 : supplierReach.excludedOutOfReach;
  // Baris yang benar-benar dipasang: jangkauan hanya berlaku bagi pemanggil yang
  // memberi ambang; `null` = seluruh baris (tampilan nasional).
  const supplierMapRows = useMemo(
    () => supplierPinsForMap(supplierRows, reachKm ?? null),
    [supplierRows, reachKm]
  );
  const supplierSummary = useMemo(
    () => supplierLayerSummary(supplierRows, reachKm ?? null),
    [supplierRows, reachKm]
  );
  const supplierMarkersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  const supplierRowsRef = useRef<readonly SupplierPinRow[]>(supplierMapRows);
  const supplierReachRef = useRef<number | null>(reachKm ?? null);
  const showSuppliersRef = useRef(false);

  // --- Layer jalur kiriman (Fase 10) ---------------------------------------
  // Nyalakan secara bawaan: garis inilah yang diminta pemilik proyek untuk
  // diperlihatkan di peta (keputusan 2026-10-16). Geometri datang dari server
  // (cache OSRM saat sinkronisasi) — peta tidak pernah memanggil OSRM sendiri.
  const [showRoutes, setShowRoutes] = useState(true);
  // Rincian lapisan dilipat secara bawaan (revisi 2026-10-16): angkanya sudah
  // terbaca sebagai tag ringkas di bilah, jadi kalimat penjelas panjang tidak
  // perlu menahan ruang. Isinya tetap ada di DOM (tidak dihapus).
  const [showLayerInfo, setShowLayerInfo] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const routePinRows = useMemo(() => supplierRouteRows(supplierRoutes), [supplierRoutes]);
  const routeFeatures = useMemo(() => routeGeoJson(supplierRoutes), [supplierRoutes]);
  const routeSummary = useMemo(() => routeLayerSummary(supplierRoutes), [supplierRoutes]);
  // Baris perjalanan di kotak "Info map": hanya saat lapisan jalur hidup (kalau
  // lapisannya mati, tidak ada garis yang diterangkan) dan hanya kalau server
  // memang mengirim blok perjalanannya.
  const journeyRows = useMemo(
    () => (showRoutes ? routeJourneyRows(routePinRows) : []),
    [routePinRows, showRoutes]
  );
  // Isi baris legenda ringkas di bawah kanvas (C2, langkah 7b-2). Aturannya ada
  // di lib murni `map-legend-compact.ts`: status lokasi selalu tampil (pin SPPG
  // tidak punya sakelar), sedangkan butir jalur/pemasok hanya muncul saat
  // lapisannya hidup — keterangan warna tanpa lapisan adalah informasi palsu.
  const legendCompact = useMemo(
    () =>
      compactLegendItems({
        jalur: showRoutes ? routeLegendEntries(routePinRows) : [],
        pemasok: showSuppliers ? SUPPLIER_PIN_LEGEND : [],
      }),
    [routePinRows, showRoutes, showSuppliers]
  );
  const routeBounds = useMemo(() => routeBoundsPoints(supplierRoutes), [supplierRoutes]);
  const routeRowsRef = useRef<readonly SupplierRoute[]>(routePinRows);
  const routeFeaturesRef = useRef(routeFeatures);
  const routeBoundsRef = useRef<readonly [number, number][]>(routeBounds);
  const showRoutesRef = useRef(true);
  // --- Sorotan kiriman (Arah C) -------------------------------------------
  const focusOptionRows = useMemo(() => focusOptions(supplierRoutes), [supplierRoutes]);
  const focusRow = useMemo(
    () => focusPick(supplierRoutes, focusedRouteId),
    [supplierRoutes, focusedRouteId]
  );
  const focusLines = useMemo(() => focusLineFeatures(focusRow), [focusRow]);
  const focusLinesRef = useRef(focusLines);
  const onFocusRouteRef = useRef(onFocusRoute);
  // Peta dibuka ulang SEKALI saat jalur pertama tiba: ujung asal (mis. Cianjur)
  // berada di luar cakupan peta SPPG tujuan, jadi tanpa ini garisnya tak terlihat.
  const routeFitDoneRef = useRef(false);

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

  /** Sinkronkan layer jalur kiriman dengan data terbaru.
   *
   *  Bedanya dengan penanda: garis digambar sebagai source/layer MapLibre (GeoJSON),
   *  jadi butuh gaya peta siap (`load`) sebelum source bisa ditambahkan. Saat
   *  data tiba sebelum gaya siap, handler `load` yang memanggil ulang fungsi ini. */
  const syncRouteLayer = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const aktif = showRoutesRef.current && routeFeaturesRef.current.features.length > 0;
    const source = map.getSource(ROUTE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (!aktif) {
      // Dimatikan / tidak ada data: bersihkan sepenuhnya, jangan tinggalkan
      // setengah lapisan yang tampak "masih ada jalur".
      if (map.getLayer(ROUTE_LAYER_ID)) map.removeLayer(ROUTE_LAYER_ID);
      if (source) map.removeSource(ROUTE_SOURCE_ID);
      return;
    }
    if (source) {
      source.setData(routeFeaturesRef.current);
      return;
    }
    if (!map.isStyleLoaded()) return;
    map.addSource(ROUTE_SOURCE_ID, { type: "geojson", data: routeFeaturesRef.current });
    map.addLayer({
      id: ROUTE_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": [
          "match",
          ["get", "tone"],
          "fail",
          ROUTE_LINE_COLORS.fail,
          ROUTE_LINE_COLORS.ok,
        ],
        "line-width": ROUTE_LINE_WIDTH,
        "line-dasharray": [2, 1.2],
        "line-opacity": 0.9,
      },
    });
    map.on("click", ROUTE_LAYER_ID, (event) => {
      const id = (event.features?.[0]?.properties as { id?: string } | undefined)?.id;
      const row = routeRowsRef.current.find((item) => item.id === id);
      if (!row) return;
      // Klik garis = sorot kiriman ini (Arah C). Popup tetap muncul: ia yang
      // dibaca di tempat klik, sedangkan kartu kiriman di bawah peta memuat
      // stepper, rincian, dan riwayatnya.
      onFocusRouteRef.current?.(row.id);
      new maplibregl.Popup({ offset: 10 })
        .setLngLat(event.lngLat)
        .setDOMContent(routePopupNode(row))
        .addTo(map);
    });
  }, []);

  /** Sinkronkan garis SOROTAN (Arah C).
   *
   *  Sama seperti layer dasar: butuh gaya peta siap sebelum source bisa dibuat,
   *  dan saat tidak ada yang disorot seluruh layer + source DIBUANG — tidak boleh
   *  tertinggal garis sorotan untuk kiriman yang sudah dilepas. */
  const syncFocusLayer = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const data = focusLinesRef.current;
    const aktif = showRoutesRef.current && data.features.length > 0;
    const source = map.getSource(ROUTE_FOCUS_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (!aktif) {
      if (map.getLayer(ROUTE_FOCUS_DONE_LAYER_ID)) map.removeLayer(ROUTE_FOCUS_DONE_LAYER_ID);
      if (map.getLayer(ROUTE_FOCUS_TODO_LAYER_ID)) map.removeLayer(ROUTE_FOCUS_TODO_LAYER_ID);
      if (source) map.removeSource(ROUTE_FOCUS_SOURCE_ID);
      return;
    }
    if (source) {
      source.setData(data);
      return;
    }
    if (!map.isStyleLoaded()) return;
    map.addSource(ROUTE_FOCUS_SOURCE_ID, { type: "geojson", data });
    // Sudah ditempuh: padat (pola Oracle "padat = sudah dilalui").
    map.addLayer({
      id: ROUTE_FOCUS_DONE_LAYER_ID,
      type: "line",
      source: ROUTE_FOCUS_SOURCE_ID,
      filter: ["==", ["get", "kind"], "done"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["match", ["get", "tone"], "fail", ROUTE_LINE_COLORS.fail, ROUTE_LINE_COLORS.ok],
        "line-width": ROUTE_FOCUS_WIDTH,
      },
    });
    // Belum ditempuh: putus-putus dengan warna yang sama.
    map.addLayer({
      id: ROUTE_FOCUS_TODO_LAYER_ID,
      type: "line",
      source: ROUTE_FOCUS_SOURCE_ID,
      filter: ["==", ["get", "kind"], "todo"],
      layout: { "line-cap": "butt", "line-join": "round" },
      paint: {
        "line-color": ["match", ["get", "tone"], "fail", ROUTE_LINE_COLORS.fail, ROUTE_LINE_COLORS.ok],
        "line-width": ROUTE_FOCUS_WIDTH,
        "line-dasharray": [2, 1.2],
        "line-opacity": 0.75,
      },
    });
  }, []);

  /** Sinkronkan penanda PEMASOK: hanya saat lapisan dinyalakan DAN zoom cukup
   *  dekat. Semua penanda dibuang saat lapisan dimatikan atau zoom dijauhkan —
   *  tidak ada yang tertinggal setengah aktif. */
  const syncSupplierMarkers = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const markers = supplierMarkersRef.current;
    const visible = showSuppliersRef.current && supplierPinsVisible(map.getZoom());
    const rows = visible ? supplierRowsRef.current : [];
    const showLabels = visible && supplierLabelsVisible(map.getZoom());
    const keep = new Set(rows.map((row) => row.id));
    markers.forEach((marker, id) => {
      if (!keep.has(id)) {
        marker.remove();
        markers.delete(id);
      }
    });
    rows.forEach((row) => {
      const existing = markers.get(row.id);
      if (existing) {
        refreshSupplierPin(existing, row, showLabels, supplierReachRef.current);
        return;
      }
      markers.set(row.id, createSupplierPin(map, row, showLabels, supplierReachRef.current));
    });
  }, []);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current || !locationsRef.current?.length) return;
    // Salinan ref untuk cleanup: nilai `.current` bisa berubah sebelum cleanup
    // dijalankan (aturan react-hooks/exhaustive-deps).
    const markers = markersRef.current;
    const supplierMarkers = supplierMarkersRef.current;
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
      // Gestur kooperatif (celah C9, langkah 7b-2): hanya untuk perangkat sentuh
      // UTAMA. Di ponsel, satu jari menggulir HALAMAN dan dua jari menggeser
      // peta — tanpa itu, geser di atas peta "mencuri" gulir halaman sehingga
      // kartu di bawah peta tidak bisa dicapai. Desktop sengaja TIDAK diikutkan:
      // roda tetikus = zoom tetap seperti sekarang (lihat lib/map-view.ts).
      cooperativeGestures: mapCooperativeGestures(mediaQueryCocok),
    });
    mapRef.current = map;
    // Pesan layar gestur bawaan MapLibre berbahasa Inggris; peta ini berbahasa
    // Indonesia dan pesan itu muncul tepat saat pengguna bingung kenapa peta
    // tidak bergeser. Diganti seketika setelah peta dibuat (elemennya sudah ada).
    if (mapContainer.current) lokalkanPesanGesture(mapContainer.current);
    // Kontrol bawaan: zoom + kompas kanan-atas, atribusi (© OpenStreetMap
    // contributors · MapLibre) kanan-bawah — seperti acuan.
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-right");
    // Kontrol skala jarak (langkah 7b-1 / riset §5 C3): kategori kontrol
    // "Informational" yang sebelumnya tidak ada. Posisinya kiri-bawah — sama
    // dengan bawaan MapLibre dan acuan industri. Sebelumnya ia ditaruh
    // kanan-bawah karena sudut kiri-bawah dipakai panggung legenda; sejak
    // langkah 7b-2 legenda pindah ke bawah kanvas, jadi sudut itu bebas lagi.
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 88, unit: "metric" }), "bottom-left");
    // Tombol "Tampilkan semua" (riset §5 C4): literatur interaksi peta menyebut
    // tombol kembali ke tampilan awal sebagai kebutuhan dasar — tanpa itu,
    // pengguna yang sudah menggeser/zoom harus menebak cara pulang.
    // Elemennya <button> ASLI (bukan DIV bergaya tombol): kontrol peta harus bisa
    // difokus keyboard, aturan yang sama dengan pemilih kiriman Arah C.
    map.addControl(
      {
        onAdd() {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "map-reset-view";
          button.innerHTML = MAP_RESET_ICON;
          button.setAttribute("aria-label", MAP_RESET_LABEL);
          button.title = mapResetTitle(
            locationsRef.current?.length ?? 0,
            showRoutesRef.current && routeBoundsRef.current.length > 0
          );
          button.addEventListener("click", () => fitAllRef.current());
          resetButtonRef.current = button;
          return button;
        },
        onRemove() {
          resetButtonRef.current = null;
        },
      },
      "top-right"
    );
    // Fokus awal (semua lokasi). Efek fokus di bawah yang mengarahkan ke lokasi
    // aktif bila ada. Setelah ini peta TIDAK pernah dibangun ulang lagi.
    map.fitBounds(fitBoundsFor(locationsRef.current, routeBoundsRef.current), {
      padding: 40,
      duration: 0,
    });
    syncMarkers();
    // Zoom menentukan apakah pin pemasok boleh tampil (mereka baru muncul di
    // zoom 8+). Keadaan zoom juga dipakai untuk memberi tahu pengguna kenapa
    // lapisan yang dinyalakan masih kosong.
    setZoomEnough(supplierPinsVisible(map.getZoom()));
    const onZoom = () => {
      setZoomEnough(supplierPinsVisible(map.getZoom()));
      syncSupplierMarkers();
    };
    map.on("zoomend", onZoom);
    syncSupplierMarkers();
    // Source/layer GeoJSON hanya bisa ditambahkan setelah gaya peta siap.
    map.on("load", syncRouteLayer);
    syncRouteLayer();
    map.on("load", syncFocusLayer);
    syncFocusLayer();

    // Kontainer berubah ukuran (jendela, sidebar dilipat, breakpoint tata
    // letak) tanpa MapLibre mengetahuinya — tanpa ini peta tertinggal di
    // ukuran saat dibuat.
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(mapContainer.current);

    return () => {
      observer.disconnect();
      map.off("zoomend", onZoom);
      map.off("load", syncRouteLayer);
      map.off("load", syncFocusLayer);
      map.remove();
      mapRef.current = null;
      markers.clear();
      supplierMarkers.clear();
      pinSignaturesRef.current = {};
      focusRef.current = MAP_FOCUS_INITIAL;
    };
  }, [hasLocations, syncMarkers, syncSupplierMarkers, syncRouteLayer, syncFocusLayer]);

  // Sinkronisasi data (arah Roy 2026-10-11): penanda saja, tanpa fitBounds.
  useEffect(() => {
    syncMarkers();
  }, [pinSnapshot, syncMarkers]);

  // Layer pemasok: tombol + data. Keduanya hanya menyentuh penanda pemasok.
  useEffect(() => {
    showSuppliersRef.current = showSuppliers;
    supplierRowsRef.current = supplierMapRows;
    supplierReachRef.current = reachKm ?? null;
    syncSupplierMarkers();
  }, [showSuppliers, supplierMapRows, reachKm, syncSupplierMarkers]);

  // Layer jalur kiriman: tombol + data (garis, bukan penanda).
  useEffect(() => {
    showRoutesRef.current = showRoutes;
    routeRowsRef.current = routePinRows;
    routeFeaturesRef.current = routeFeatures;
    syncRouteLayer();
  }, [showRoutes, routePinRows, routeFeatures, syncRouteLayer]);

  // Sorotan kiriman (Arah C): pilihan + geometrinya. Tidak menyentuh kamera peta.
  useEffect(() => {
    focusLinesRef.current = focusLines;
    syncFocusLayer();
  }, [focusLines, syncFocusLayer]);

  useEffect(() => {
    onFocusRouteRef.current = onFocusRoute;
  }, [onFocusRoute]);

  useEffect(() => {
    routeBoundsRef.current = routeBounds;
  }, [routeBounds]);

  // Tombol "Tampilkan semua": memakai hitungan batas yang SAMA dengan tampilan
  // awal (`fitBoundsFor`) — bukan rumus kedua. Jalur ikut HANYA kalau lapisannya
  // sedang hidup: mengembalikan pandangan ke jalur yang disembunyikan akan
  // membingungkan (aturan lama: "yang tidak tampil tidak diterangkan").
  const fitAll = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    map.fitBounds(
      fitBoundsFor(locationsRef.current, showRoutesRef.current ? routeBoundsRef.current : []),
      { padding: 40, duration: 600 }
    );
  }, []);

  useEffect(() => {
    fitAllRef.current = fitAll;
  }, [fitAll]);

  // Judul tombol = janji yang harus tetap benar setelah data/lapisan berubah.
  // (`aria-label` cukup dipasang sekali: itu NAMA tombol, bukan keterangan.)
  useEffect(() => {
    const button = resetButtonRef.current;
    if (!button) return;
    button.title = mapResetTitle(
      locations?.length ?? 0,
      showRoutes && routeFeatures.features.length > 0
    );
  }, [locations, showRoutes, routeFeatures]);

  // Buka tampilan SEKALI saat jalur pertama tiba — supaya kedua ujung kiriman
  // terlihat. Sinkronisasi berikutnya tidak pernah menyentuh kamera peta lagi
  // (aturan lama: zoom & geser pengguna tidak boleh tersentak).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || routeFitDoneRef.current) return;
    if (!routeFeatures.features.length) return;
    routeFitDoneRef.current = true;
    map.fitBounds(fitBoundsFor(locationsRef.current, routeBoundsRef.current, 0.5), {
      padding: 40,
      duration: 600,
    });
  }, [routeFeatures]);

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
        </div>
      )}
      <div className="map-body">
        {/* Chip saringan aktif (celah C8, langkah 7b-2; riset §5): begitu satu
            kiriman disorot, peta menyembunyikan kiriman lain — dan itu satu-satunya
            keadaan di mana orang bisa mencari pin yang tidak ada. Keadaan itu harus
            terbaca SEBELUM orang mencarinya, lengkap dengan jalan keluarnya di
            tempat yang sama (bukan hanya di pemilih di bawah kartu). */}
        {focusRow && onFocusRoute && (
          <div className="map-filter">
            <span className="map-filter-text">{focusFilterText(focusRow)}</span>
            <button
              type="button"
              className="map-filter-clear"
              onClick={() => onFocusRoute(FOCUS_ALL)}
            >
              {FOCUS_CLEAR_LABEL}
            </button>
          </div>
        )}

        {/* Container peta — dirender SSR, MapLibre menempel di client */}
        <div className="map-shell">
          <div ref={mapContainer} className="map-gl" />
          {/* Sakelar lapisan — SATU-SATUNYA elemen yang mengapung di kanvas peta.
              Legenda & catatan penjelas pindah ke baris di bawah peta (Opsi 1,
              keputusan pemilik 2026-10-16): sebelumnya panel kendali menutupi 39%
              luas kanvas (terukur 650x262 px dari 947x460 px), tepat di atas Jawa
              Barat tempat pin SPPG dan jalur kiriman berada. */}
          {(Boolean(suppliers) || Boolean(supplierRoutes)) && (
            <div className="map-overlay-toggles">
              {Boolean(suppliers) && (
                <button
                  type="button"
                  className="map-layer-toggle"
                  aria-pressed={showSuppliers}
                  title={supplierToggleAction(supplierMapRows, showSuppliers)}
                  onClick={() => setShowSuppliers((value) => !value)}
                >
                  {supplierToggleLabel(supplierMapRows)}
                </button>
              )}
              {Boolean(supplierRoutes) && (
                <button
                  type="button"
                  className="map-layer-toggle map-route-toggle"
                  aria-pressed={showRoutes}
                  title={routeToggleAction(routePinRows, showRoutes)}
                  onClick={() => setShowRoutes((value) => !value)}
                >
                  {routeToggleLabel(routePinRows)}
                </button>
              )}
              {/* Chip "Info map" masuk PIL yang sama supaya kanvas hanya punya
                  SATU zona kendali yang mengapung (celah C5, langkah 7b-2; riset
                  §5). Isinya dirender DI BAWAH kanvas (`.map-legend-detail`) —
                  jadi membukanya tidak pernah menutupi pin. */}
              <button
                type="button"
                className="map-legend-toggle"
                aria-expanded={showLegend}
                aria-controls={LEGEND_PANEL_ID}
                onClick={() => setShowLegend((value) => !value)}
              >
                <span className="map-legend-chevron" aria-hidden="true" />
                Info map
              </button>
            </div>
          )}
          {/* Rincian "Info map" — DI BAWAH kanvas dan DI DALAM ALUR (bukan
              mengapung di atas peta). Sejak langkah 7b-2 chip pembukanya pindah
              ke pil kendali kiri-atas (satu-satunya elemen yang mengapung, celah
              C5), sedangkan isinya turun ke sini supaya membukanya tidak pernah
              menutupi pin di Jawa Barat (aturan pemilik 2026-10-16).

              Isinya tetap lengkap dan namanya tetap "Info map"; dua aturan
              penyusunannya tidak berubah:
              1. kelompok yang lapisannya sedang MATI tidak ditampilkan —
                 keterangan warna yang tidak ada di peta adalah informasi palsu;
              2. entri "gagal uji" hanya muncul kalau memang ada kiriman bergaris
                 seperti itu (lihat `routeLegendEntries`).

              Yang terbaca TANPA klik adalah baris legenda ringkas di bawah kartu
              (celah C2); kotak ini memuat rincian yang lebih panjang. */}
          <div className="map-legend-detail" data-open={showLegend}>
            <div
              className="map-legend-boxes"
              id={LEGEND_PANEL_ID}
              role="group"
              aria-label="Info map"
            >
              <div className="map-legend-box" role="group" aria-label="Keterangan status lokasi">
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
              {Boolean(supplierRoutes) && showRoutes && (
                <div
                  className="map-legend-box map-legend-box-routes"
                  role="group"
                  aria-label="Keterangan jalur kiriman"
                >
                  <span className="map-legend-box-title">Jalur kiriman:</span>
                  {routeLegendEntries(routePinRows).map((entry) => (
                    <span key={entry.tone} className="map-legend-box-item">
                      <i
                        className={`map-legend-line map-legend-line-${entry.tone}`}
                        aria-hidden="true"
                      />{" "}
                      {entry.label}
                    </span>
                  ))}
                </div>
              )}
              {Boolean(suppliers) && showSuppliers && (
                <div
                  className="map-legend-box map-legend-box-suppliers"
                  role="group"
                  aria-label="Keterangan pemasok"
                >
                  <span className="map-legend-box-title">Pemasok:</span>
                  {SUPPLIER_PIN_LEGEND.map((entry) => (
                    <span key={entry.tone} className="map-legend-box-item">
                      <i
                        className={`map-legend-box-shape map-legend-box-shape-${entry.tone}`}
                        aria-hidden="true"
                      />{" "}
                      {entry.label}
                    </span>
                  ))}
                </div>
              )}
              {Boolean(supplierRoutes) && showRoutes && journeyRows.length > 0 && (
                <div
                  className="map-legend-box map-journey"
                  role="group"
                  aria-label="Perjalanan kiriman"
                >
                  <span className="map-legend-box-title">Perjalanan kiriman:</span>
                  {journeyRows.map((row) => (
                    <span key={row.teks} className={row.kelas}>
                      {row.teks}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Baris legenda ringkas (celah C2, langkah 7b-2): makna titik & garis
            terbaca TANPA satu klik. Sengaja di BAWAH kanvas, bukan mengapung di
            atasnya — panel putih di atas peta pernah menutup 39% kanvas, tepat di
            atas Jawa Barat (keputusan pemilik 2026-10-16). Di sini hanya tanda +
            nama; kalimat panjang (perjalanan & asal geometri) tetap di "Info map",
            dan angka jumlahnya tetap di tag bilah rincian. */}
        <div className="map-legend-compact" role="group" aria-label="Legenda peta">
          <span className="map-legend-compact-title">Legenda:</span>
          {legendCompact.map((butir) => {
            const [kelasDasar, kelasNada] = legendMarkClass(butir);
            return (
              <span key={butir.id} className="map-legend-compact-item">
                <i className={`${kelasDasar} ${kelasNada}`} aria-hidden="true" />{" "}
                {butir.label}
              </span>
            );
          })}
        </div>

        {/* Pemilih kiriman untuk disorot (Arah C). Hanya dirender kalau pemanggil
            mengendalikan pilihannya — di tab yang tidak punya kartu kiriman,
            peta tetap persis seperti sebelumnya. Garis di kanvas tidak bisa
            difokus keyboard, jadi tombol inilah jalur setaranya. */}
        {onFocusRoute && focusOptionRows.length > 0 && (
          <RouteFocusPicker
            options={focusOptionRows}
            focused={focusRow?.id ?? null}
            total={focusOptionRows.length}
            onFocus={onFocusRoute}
          />
        )}

        {/* Bilah rincian lapisan (revisi 2026-10-16, arah pemilik): angkanya
            SELALU terlihat sebagai tag ringkas satu baris; kalimat penjelas
            panjangnya dilipat di balik tombol kecil. Isinya tidak dihapus dari
            DOM — hanya dilipat — jadi angka "yang tidak dipasang" dan asal
            geometri OSRM tetap bisa diperiksa, bukan disembunyikan. */}
        {(Boolean(suppliers) || Boolean(supplierRoutes)) && (
          <div className="map-layer-info">
            <button
              type="button"
              className="map-layer-info-toggle"
              aria-expanded={showLayerInfo}
              aria-controls={LAYER_INFO_PANEL_ID}
              onClick={() => setShowLayerInfo((value) => !value)}
            >
              <span className="map-layer-info-chevron" aria-hidden="true" />
              Rincian lapisan peta
            </button>
            <p className="map-layer-tags" role="status">
              {Boolean(suppliers) && (
                <span className="map-layer-tag">
                  {supplierReachTag(supplierRows, reachKm ?? null, hiddenByServer)}
                </span>
              )}
              {Boolean(suppliers) && Boolean(supplierRoutes) && (
                <span className="map-layer-tag-sep" aria-hidden="true">
                  ·
                </span>
              )}
              {Boolean(supplierRoutes) && (
                <span className="map-layer-tag">
                  {routeLayerTag(routeSummary, showRoutes ? routePinRows : [])}
                </span>
              )}
            </p>
            <div
              id={LAYER_INFO_PANEL_ID}
              className="map-layer-info-panel"
              data-open={showLayerInfo}
            >
              <div className="map-layer-info-inner">
                {Boolean(suppliers) && (
                  <p className="map-supplier-note">
                    {supplierReachNote(
                      supplierRows,
                      reachKm ?? null,
                      supplierReference?.location,
                      hiddenByServer
                    )}
                  </p>
                )}
                {Boolean(supplierRoutes) && (
                  <p className="map-supplier-note">
                    {routeSummary.label} — jalur jalan dari OSRM (diambil saat
                    sinkronisasi, bukan saat peta dibuka).
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Peringatan zoom sengaja DI LUAR panel yang bisa dilipat: saat sakelar
            pemasok dinyalakan pada zoom jauh, alasannya harus muncul seketika —
            bukan menunggu pengguna membuka rincian. */}
        {Boolean(suppliers) && showSuppliers && zoomEnough === false && (
          <p className="map-layer-hint" role="status">
            Perbesar peta untuk melihat {supplierSummary.total} pemasok — pin pemasok
            muncul pada zoom {SUPPLIER_PIN_MIN_ZOOM} ke atas, nama pemasok pada zoom{" "}
            {SUPPLIER_LABEL_MIN_ZOOM} ke atas.
          </p>
        )}
        {showStatusList && (
          <div className="map-side">
            <StatusLocationList locations={locations} />
          </div>
        )}
      </div>
    </section>
  );
}
