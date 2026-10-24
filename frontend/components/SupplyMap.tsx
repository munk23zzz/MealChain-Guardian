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
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { kodeWilayah } from "../lib/wilayah";
import { posisiDanArah, siapkanJalur, wakeLine } from "../lib/route-flow";
import { fraksiBerjalan, type JangkarTruk } from "../lib/truck-progress";
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
import { compactLegendItems, legendBreakIndexes, legendMarkClass } from "../lib/map-legend-compact";
import {
  KLASTER_JARAK_PIKSEL,
  KLASTER_ZOOM_MAKS,
  gabungKlasterBerdekatan,
  kelompokkanBertumpuk,
  klasterPerluGelembung,
  labelKlaster,
  offsetSpider,
  pusatKlaster,
} from "../lib/map-cluster";
import { penandaPeta, ringkasPenanda } from "../lib/map-a11y";
// Kelas pin digabung, bukan ditimpa — kelas `maplibregl-marker` milik pustaka
// membawa position:absolute; menghapusnya membuat pin bergeser dari koordinat.
import { gabungKelasPin } from "../lib/map-pin-class";
// Ikon sakelar lapisan (19 Okt 2026): pil kendali kini ikon saja — teks
// "Pemasok (6)"/"Jalur kiriman (12)" memakan lebar tepat di atas Jawa Barat,
// padahal artinya sudah dibawa legenda di bawah kanvas dan jumlahnya di tag.
import {
  daftarkanSorot,
  langgananSorot,
  sorotLokasiTerenregistrasi,
  sorotTersedia,
} from "../lib/map-sorot";
// Ikon di dalam penanda (bukan emoji/teks): siluet bangunan untuk SPPG dan
// truk untuk pemasok — dua lapisan penanda jadi bisa dibedakan dari bentuknya.
import { buildPinGlyph } from "../lib/map-pin-glyphs";
import {
  routePopupView,
  sppgPopupView,
  supplierPopupView,
  truckPopupView,
  type MapPopupView,
} from "../lib/map-popup";
import {
  SUPPLIER_LABEL_MIN_ZOOM,
  SUPPLIER_PIN_LEGEND,
  supplierAccessibleLabel,
  supplierDistanceReference,
  supplierReachMeta,
  supplierLayerSummary,
  supplierLabelsVisible,
  supplierPinClass,
  supplierPinRows,
  supplierPinsForMap,
  supplierReachNote,
  supplierReachTag,
  suppliersForCommodity,
  type SupplierPinRow,
} from "../lib/supplier-pins";
import {
  ROUTE_LINE_COLORS,
  ROUTE_TODO_COLORS,
  routeBoundsPoints,
  routeGeoJson,
  routeJourneyRows,
  routeLayerSummary,
  routeLayerTag,
  routeLegendEntries,
  routeLineClass,
  shipmentKey,
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
// K1 (7b-3): satu source, DUA layer — padat = sudah ditempuh, putus-putus =
// sisa perjalanan atau perkiraan. `line-dasharray` tidak bisa data-driven di
// MapLibre, jadi bentuk garis dipisah lewat filter `kind` per fitur.
const ROUTE_DONE_LAYER_ID = "supplier-route-line-done";
const ROUTE_TODO_LAYER_ID = "supplier-route-line-todo";
// Kiriman yang SUDAH TIBA (21 Okt 2026): redup, tanpa animasi, tanpa ikon.
// Dibedakan dari garis terang supaya "terang = ada yang bergerak" tetap benar.
const ROUTE_QUIET_LAYER_ID = "supplier-route-line-tiba";
// Alas putih (casing) di bawah garis jalur. Basemap OSM terang + banyak hijau
// membuat garis hijau 2-4 px sulit ditemukan mata; alas ini hanya alat
// keterbacaan, bukan informasi baru — karena itu tidak masuk legenda.
/**
 * Lapisan "menyala" untuk kiriman yang SEDANG berjalan (permintaan pemilik
 * 20 Okt 2026: ikon & jalur pemasok yang sedang mengirim menyala).
 *
 * Ini lapisan tambahan DI BAWAH garis biasa: lebar + blur, tanpa mengganti warna
 * atau kepadatan garis. Jadi "menyala" menambah penekanan, tidak menghapus arti
 * garis yang sudah ada (padat = ditempuh, putus-putus = sisa).
 */
const ROUTE_HALO_DONE_LAYER_ID = "supplier-route-halo-done";
const ROUTE_HALO_TODO_LAYER_ID = "supplier-route-halo-todo";
/** Kilau tipis di atas bagian yang sudah ditempuh (bukan data baru: hanya
 *  pantulan putih supaya garis terbaca sebagai pita yang menyala). */
const ROUTE_GLINT_LAYER_ID = "supplier-route-glint";
/** Ekor cahaya di belakang kendaraan yang sedang berjalan. */
const WAKE_SOURCE_ID = "supplier-truck-wake";
const WAKE_LAYER_ID = "supplier-truck-wake-line";
const ROUTE_CASING_DONE_LAYER_ID = "supplier-route-casing-done";
const ROUTE_CASING_TODO_LAYER_ID = "supplier-route-casing-todo";
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
// Id panel rincian; dulu ada juga LEGEND_PANEL_ID untuk chip "Info map", tetapi
// panel itu sudah dilebur ke sini (19 Okt 2026) supaya legenda hanya dibaca di
// SATU tempat: baris legenda di bawah kanvas, dengan rincian di panel ini.

// Lebar dinaikkan 20 Okt 2026: peta sekarang hanya menggambar kiriman yang
// sedang berjalan (1–3 jalur, bukan 20), jadi garis boleh lebih tegas tanpa
// membuat peta padat.
const ROUTE_LINE_WIDTH: maplibregl.ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["zoom"],
  5,
  6,
  10,
  7.8,
];

/** Alas: +2,2 px dari garis di setiap tingkat zoom (cukup untuk halo tipis). */
const ROUTE_CASING_WIDTH: maplibregl.ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["zoom"],
  5,
  8.4,
  10,
  10.6,
];

/** Sisa perjalanan digambar LEBIH TIPIS: itu estimasi, bukan fakta terkirim. */
const ROUTE_TODO_WIDTH: maplibregl.ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["zoom"],
  5,
  5.4,
  10,
  6.8,
];

/** Kilau: putih tipis, ikut zoom, selalu di dalam garis (tidak menambah lebar). */
const ROUTE_GLINT_WIDTH: maplibregl.ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["zoom"],
  5,
  1.1,
  10,
  1.9,
];

/** Alas potongan "belum ditempuh" — selalu +2 px dari garisnya. */
const ROUTE_TODO_CASING_WIDTH: maplibregl.ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["zoom"],
  5,
  5.4,
  10,
  7,
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

/**
 * Satu popup pada satu waktu + jaminan popup tidak terpotong tepi peta.
 *
 * Latar (21 Okt 2026): tiap marker memasang popup sendiri, jadi mengklik
 * pemasok kedua meninggalkan popup pertama terbuka — peta penuh gelembung.
 * MapLibre juga menjalankan autoPan SETELAH popup terbuka; kalau kita
 * menggeser peta terlalu awal, autoPan menimpa koreksi itu. Karena itu
 * koreksi dijalankan pada setiap `moveend` selama popup terbuka, dengan
 * batas aman agar peta tidak melompat jauh.
 */
let popupTerbuka: maplibregl.Popup | null = null;
/** Waktu klik truk terakhir; dipakai handler garis jalur untuk tidak menimpa
 *  popup truk saat klik yang sama juga terdeteksi sebagai klik layer garis. */
let trukKlikTerakhir = 0;

function jagaPopup(popup: maplibregl.Popup, map: maplibregl.Map): maplibregl.Popup {
  let sedangMenyesuaikan = false;

  const rapikan = () => {
    if (!popup.isOpen() || sedangMenyesuaikan) return;
    const el = popup.getElement();
    if (!el) return;
    const kotak = el.getBoundingClientRect();
    const peta = map.getContainer().getBoundingClientRect();
    // Popup yang seluruhnya di luar peta berarti penandanya di luar viewport
    // (mis. dibuka lewat keyboard/otomasi): jangan pan — dulu pernah
    // menggeser peta ribuan piksel sampai terlihat seperti laut.
    if (kotak.bottom < peta.top || kotak.top > peta.bottom) return;
    // Popup yang lebih tinggi dari peta tidak akan muat; jangan pan berulang.
    if (kotak.height > peta.height - 24) return;
    // Sisakan ruang di atas untuk bar tab lengket di ponsel dan kontrol peta.
    const sempit = window.matchMedia("(max-width: 480px)").matches;
    const insetAtas = sempit ? 82 : 24;
    const insetSamping = sempit ? 6 : 12;
    const bawah = kotak.bottom - peta.bottom + 12;
    const atas = peta.top + insetAtas - kotak.top;
    // Arah panBy: offset POSITIF menggeser pusat peta ke selatan, sehingga
    // isi peta (termasuk popup) bergerak KE ATAS. Jadi popup yang terlalu
    // rendah perlu offset positif, dan popup yang terlalu tinggi negatif.
    const perluY = bawah > 0 ? bawah : atas > 0 ? -atas : 0;
    // Peta ponsel sempit: penanda di tepi membuat popup terpotong KIRI/KANAN
    // kalau hanya sumbu Y yang dikoreksi.
    const kanan = kotak.right - peta.right + insetSamping;
    const kiri = peta.left + insetSamping - kotak.left;
    const perluX = kanan > 0 ? kanan : kiri > 0 ? -kiri : 0;
    if (Math.abs(perluX) < 4 && Math.abs(perluY) < 4) return;
    const batasY = Math.max(160, peta.height);
    const batasX = Math.max(160, peta.width);
    const geserX = Math.max(-batasX, Math.min(batasX, perluX));
    const geserY = Math.max(-batasY, Math.min(batasY, perluY));
    sedangMenyesuaikan = true;
    map.panBy([geserX, geserY], { duration: 240 });
    window.setTimeout(() => {
      sedangMenyesuaikan = false;
    }, 300);
  };

  popup.on("open", () => {
    if (popupTerbuka && popupTerbuka !== popup) popupTerbuka.remove();
    popupTerbuka = popup;
    // MapLibre menulis tombol tutup berbahasa Inggris ("Close popup");
    // antarmuka ini berbahasa Indonesia. Ganti tanpa mengubah glyph ×.
    const tutup = popup.getElement()?.querySelector<HTMLButtonElement>(".maplibregl-popup-close-button");
    if (tutup) {
      tutup.setAttribute("aria-label", "Tutup informasi");
      tutup.title = "Tutup informasi";
    }
    map.on("moveend", rapikan);
    // Koreksi pertama setelah layout/font siap; moveend menangani sisa autoPan.
    window.setTimeout(rapikan, 350);
  });
  popup.on("close", () => {
    if (popupTerbuka === popup) popupTerbuka = null;
    map.off("moveend", rapikan);
  });
  return popup;
}

/**
 * Popup peta yang SERAGAM untuk empat jenis penanda (SPPG, pemasok, truk,
 * garis jalur): satu kartu, satu hierarki (kicker → judul → angka utama →
 * metrik → fakta). Warna aksen mengikuti jenis/nada, tetapi chip selalu
 * menuliskan artinya dengan kata — warna bukan satu-satunya penanda.
 *
 * Dibangun sebagai NODE, bukan HTML string: nama lokasi/pemasok datang dari DB.
 */
function renderPopup(view: MapPopupView): HTMLElement {
  const box = document.createElement("div");
  box.className = `map-popup map-popup-${view.kind}`;
  box.dataset.kind = view.kind;
  box.dataset.tone = view.tone;
  box.setAttribute("role", "group");
  box.setAttribute("aria-label", view.aria);

  const head = document.createElement("div");
  head.className = "map-popup-head";
  const icon = document.createElement("span");
  icon.className = "map-popup-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.append(view.kind === "supplier" ? buildPinGlyph("supplier") : view.kind === "sppg" ? buildPinGlyph("sppg") : buildTruckGlyph());
  const heading = document.createElement("span");
  heading.className = "map-popup-heading";
  const kicker = document.createElement("span");
  kicker.className = "map-popup-kicker";
  kicker.textContent = view.kicker;
  const title = document.createElement("strong");
  title.className = "map-popup-title";
  title.textContent = view.title;
  const chip = document.createElement("span");
  chip.className = "map-popup-chip";
  chip.textContent = view.chip;
  heading.append(kicker, title, chip);
  head.append(icon, heading);

  const hero = document.createElement("div");
  hero.className = "map-popup-hero";
  const heroLabel = document.createElement("span");
  heroLabel.className = "map-popup-hero-label";
  heroLabel.textContent = view.hero.label;
  const heroValue = document.createElement("strong");
  heroValue.className = "map-popup-hero-value";
  heroValue.textContent = view.hero.value;
  hero.append(heroLabel, heroValue);

  box.append(head, hero);

  if (view.meter) {
    const meter = document.createElement("div");
    meter.className = "map-popup-meter";
    const track = document.createElement("span");
    track.className = "map-popup-meter-track";
    const fill = document.createElement("i");
    fill.className = "map-popup-meter-fill";
    fill.style.width = `${view.meter.pct}%`;
    track.append(fill);
    const text = document.createElement("span");
    text.className = "map-popup-meter-text";
    text.textContent = view.meter.text;
    meter.append(track, text);
    box.append(meter);
  }

  if (view.metrics.length) {
    const metrics = document.createElement("dl");
    metrics.className = "map-popup-metrics";
    view.metrics.forEach((metric) => {
      const item = document.createElement("div");
      item.className = "map-popup-metric";
      const label = document.createElement("dt");
      label.textContent = metric.label;
      const value = document.createElement("dd");
      value.textContent = metric.value;
      item.append(label, value);
      metrics.append(item);
    });
    box.append(metrics);
  }

  if (view.callout) {
    const callout = document.createElement("p");
    callout.className = "map-popup-callout";
    callout.dataset.tone = view.callout.tone;
    callout.textContent = view.callout.text;
    box.append(callout);
  }

  view.facts.forEach((fact) => {
    const line = document.createElement("p");
    line.className = "map-popup-line";
    line.textContent = fact;
    box.append(line);
  });

  if (view.note) {
    const note = document.createElement("span");
    note.className = "map-popup-note";
    note.textContent = view.note;
    box.append(note);
  }
  return box;
}

/** Konten popup SPPG (dibangun dari view murni di `lib/map-popup.ts`). */
function popupNode(location: BalanceMapLocation): HTMLElement {
  return renderPopup(sppgPopupView(location));
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
  dot.append(buildPinGlyph("sppg"));
  // Ekor penunjuk: koordinat lokasi jatuh di UJUNG ekor (anchor "bottom"),
  // bukan di tengah kepala — supaya pin tidak menutupi titik aslinya.
  const tip = document.createElement("span");
  tip.className = "map-pin-tip";
  tip.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.className = "map-pin-label";
  label.textContent = pinLabel(location);
  el.append(dot, tip, label);
  const marker = new maplibregl.Marker({ element: el, anchor: "bottom" })
    .setLngLat([Number(location.longitude), Number(location.latitude)])
    .setPopup(jagaPopup(new maplibregl.Popup({ offset: 32, maxWidth: "320px" }).setDOMContent(popupNode(location)), map))
    .addTo(map);
  // Keterangan aksesibilitas dipasang SETELAH marker dibuat: MapLibre 4.7
  // menulis aria-label="Map marker" pada elemen saat konstruksi, menimpa teks
  // yang dipasang sebelumnya — pembaca layar lalu membacakan "Map marker" untuk
  // setiap penanda.
  pasangAksesPin(el, marker, accessible);
  return marker;
}

/** Pasang identitas aksesibilitas pada elemen penanda peta.
 *
 *  MapLibre 4.7 menimpa `aria-label` saat marker dibuat, jadi atribut dipasang
 *  setelahnya. `aria-label` pada `<div>` tanpa peran dilaporkan axe sebagai
 *  "aria-prohibited-attr", maka elemen diberi `role="button"` + `tabindex="0"`
 *  dan tombol Enter/Spasi membuka popup yang sama seperti klik tetikus. */
function pasangAksesPin(el: HTMLElement, marker: maplibregl.Marker, accessible: string): void {
  el.title = accessible;
  el.setAttribute("aria-label", accessible);
  el.setAttribute("role", "button");
  el.setAttribute("tabindex", "0");
  if (el.dataset.pinA11y === "1") return;
  el.dataset.pinA11y = "1";
  el.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    marker.togglePopup();
  });
}

/** Geser kontrol kanan-atas peta ke bawah pil lapisan.
 *
 *  Di 375 px pil ("Pemasok", "Jalur kiriman", "Info map") memakai hampir seluruh
 *  lebar kanvas, sehingga tombol zoom dan "Tampilkan semua" tertutup pil —
 *  axe melaporkannya sebagai target yang terhalang (44x10 px terlihat). Karena
 *  tinggi pil berubah saat isinya berganti, offsetnya dihitung dari elemennya,
 *  bukan angka mati. */
function aturOffsetKontrol(container: HTMLElement): void {
  // Pil lapisan adalah SAUDARA kanvas (di dalam .map-shell), bukan anak kontainer
  // MapLibre — jadi pencariannya dari shell, bukan dari kontainer peta.
  const shell = container.closest<HTMLElement>(".map-shell") ?? container;
  const pil = shell.querySelector<HTMLElement>(".map-overlay-toggles");
  const sudut = container.querySelector<HTMLElement>(".maplibregl-ctrl-top-right");
  if (!sudut) return;
  const tinggi = pil ? pil.getBoundingClientRect().height : 0;
  // Hanya geser bila pil benar-benar menabrak sudut kontrol (terjadi di ponsel);
  // di desktop pil berhenti jauh sebelum kolom kontrol, dan menggeser kontrol
  // hanya akan mengubah tata letak tanpa alasan.
  const bertabrakan = pil ? pil.getBoundingClientRect().right > sudut.getBoundingClientRect().left : false;
  const nilai = bertabrakan ? `${Math.round(tinggi + 16)}px` : "0px";
  // Bandingkan dulu: MutationObserver di bawah memantau atribut style, dan
  // penulisan berulang dengan nilai sama akan memicu lingkaran tak berujung.
  if (sudut.style.top !== nilai) sudut.style.top = nilai;
}

/** Tampilkan kembali penanda yang tadi diganti gelembung klaster. */
function tampilkanPin(markers: Map<string, maplibregl.Marker>): void {
  markers.forEach((marker) => {
    const el = marker.getElement();
    if (!el) return;
    el.style.visibility = "";
    el.removeAttribute("aria-hidden");
    el.setAttribute("tabindex", "0");
  });
}

/** Sembunyikan penanda anggota klaster dari pandangan DAN dari tab order:
 *  target yang tak terlihat tapi masih bisa difokus adalah jebakan keyboard. */
function sembunyikanPin(marker: maplibregl.Marker): void {
  const el = marker.getElement();
  if (!el) return;
  el.style.visibility = "hidden";
  el.setAttribute("aria-hidden", "true");
  el.setAttribute("tabindex", "-1");
}

/** Segarkan isi penanda yang sudah ada (posisi, label, keterangan, popup) —
 *  tanpa menyentuh kamera peta. Dipakai saat sinkronisasi data. */
function refreshPin(
  marker: maplibregl.Marker,
  location: BalanceMapLocation,
  map: maplibregl.Map
): void {
  const el = marker.getElement();
  const wasActive = el.classList.contains("map-pin-active");
  // Kelas digabung, BUKAN ditimpa: `className = ...` ikut menghapus
  // `maplibregl-marker` (pembawa position:absolute) yang dipasang MapLibre,
  // sehingga penanda jatuh ke alur normal dan bergeser dari koordinatnya
  // setiap kali penanda lain ditambah/dibuang. Lihat lib/map-pin-class.ts.
  el.className = gabungKelasPin(
    el.className,
    `map-pin map-pin-${pinTone(location.status)}${wasActive ? " map-pin-active" : ""}`
  );
  const accessible = pinAccessibleLabel(location);
  pasangAksesPin(el, marker, accessible);
  const label = el.querySelector(".map-pin-label");
  if (label) label.textContent = pinLabel(location);
  marker.setLngLat([Number(location.longitude), Number(location.latitude)]);
  marker.setPopup(jagaPopup(new maplibregl.Popup({ offset: 14, maxWidth: "320px" }).setDOMContent(popupNode(location)), map));
}

/** Keterangan penanda untuk pembaca layar (MapLibre menandai tiap penanda
 *  "Map marker"; sepuluh penanda tanpa keterangan tidak berguna). */
function pinAccessibleLabel(location: BalanceMapLocation): string {
  const note = dataSourceNote(location);
  const dasar = `pasokan ${formatKg(location.supply_kg)}, permintaan ${formatKg(location.demand_kg)}, ${formatBalanceGap(location)}`;
  // Nama aksesibel WAJIB diawali teks yang terlihat di penanda (WCAG 2.5.3
  // "Label in Name"): teks pin = "Bandung +380 kg", bukan "Bandung — pasokan …".
  const awal = pinLabel(location);
  return note ? `${awal}: ${dasar}, ${note}` : `${awal}: ${dasar}`;
}

/** Isi popup pemasok — NODE DOM, bukan innerHTML. */
function supplierPopupNode(row: SupplierPinRow, reachKm: number | null): HTMLElement {
  return renderPopup(supplierPopupView(row, reachKm));
}

/**
 * Ikon mobil kiriman (permintaan pemilik 20 Okt 2026): posisi kendaraan saat ini
 * di sepanjang jalur, menghadap arah perjalanan.
 *
 * Kenapa SVG dan bukan emoji: emoji digambar font sistem (beda bentuk per OS,
 * tidak bisa diwarnai token) dan dilarang pedoman ikon aplikasi ini. Ikon ini
 * tampak DARI ATAS supaya rotasi arah masuk akal — bukan siluet depan.
 */
const SVG_TRUK_NS = "http://www.w3.org/2000/svg";

/**
 * Ikon MOBIL TRUK (permintaan pemilik 20 Okt 2026) — bak + kabin, digambar DARI
 * ATAS supaya rotasi arah perjalanan masuk akal.
 *
 * Kaca depan dan garis pemisah kabin/bak dibentuk sebagai LUBANG (`fill-rule:
 * evenodd`) sehingga warna puck terlihat menembus; tanpa lubang, truk dari atas
 * hanya terbaca sebagai kotak putih.
 *
 * Tetap SVG, bukan emoji: emoji digambar font sistem (beda bentuk per OS, tidak
 * bisa diwarnai token) dan dilarang pedoman ikon aplikasi ini.
 */
function buildTruckGlyph(): SVGSVGElement {
  const svg = document.createElementNS(SVG_TRUK_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const badan = document.createElementNS(SVG_TRUK_NS, "path");
  badan.setAttribute(
    "d",
    [
      // kabin: sempit dan membulat, di depan (arah maju)
      "M8.6 3.4h6.8a2.2 2.2 0 0 1 2.2 2.2v2.6H6.4V5.6a2.2 2.2 0 0 1 2.2-2.2Z",
      // kaca depan (lubang)
      "M9.6 4.9h4.8v1.7H9.6Z",
      // bak: lebih lebar daripada kabin, dengan celah 0,9 px → siluet "mobil box"
      "M6.9 9.9h10.2a1.5 1.5 0 0 1 1.5 1.5v7.1a2.3 2.3 0 0 1-2.3 2.3H7.7a2.3 2.3 0 0 1-2.3-2.3v-7.1a1.5 1.5 0 0 1 1.5-1.5Z",
    ].join(" ")
  );
  badan.setAttribute("fill", "currentColor");
  badan.setAttribute("fill-rule", "evenodd");
  svg.append(badan);
  return svg;
}

function createTruckMarker(
  map: maplibregl.Map,
  row: SupplierRoute,
  posisi: [number, number],
  arah: number
): maplibregl.Marker {
  const el = document.createElement("div");
  el.className = "map-truck";
  el.style.setProperty("--truk-arah", `${Math.round(arah)}deg`);
  el.append(buildTruckGlyph());
  const view = truckPopupView(row);
  const marker = new maplibregl.Marker({ element: el, anchor: "center" })
    .setLngLat(posisi)
    .setPopup(jagaPopup(new maplibregl.Popup({ offset: 18, maxWidth: "320px" }).setDOMContent(renderPopup(view)), map))
    .addTo(map);
  // Keterangan dipasang SESUDAH marker dibuat: MapLibre menulis
  // aria-label="Map marker" pada konstruktor dan menimpa teks sebelumnya
  // (jebakan yang sama dengan pin SPPG dan pin pemasok). Sekarang truk juga
  // bisa dibuka dengan keyboard seperti penanda lain.
  pasangAksesPin(el, marker, view.aria);
  // Klik truk TIDAK boleh tembus ke garis jalur di bawahnya: tanpa ini,
  // handler klik layer jalur ikut membuka popup jalur dan menimpa popup truk
  // (pengguna mengklik mobil, yang muncul malah "Jalur kiriman").
  el.addEventListener("click", (event) => {
    trukKlikTerakhir = Date.now();
    event.stopPropagation();
    // Jaring pengaman: MapLibre kadang tidak membuka popup saat klik jatuh
    // pada <path> di dalam SVG ikon. Kalau klik belum membuka apa pun,
    // buka sendiri; kalau MapLibre sudah menutup popup yang tadi terbuka,
    // jangan membukanya lagi.
    const popup = marker.getPopup();
    if (!popup) return;
    const sebelumnyaTerbuka = popup.isOpen();
    window.requestAnimationFrame(() => {
      if (!sebelumnyaTerbuka && !popup.isOpen()) marker.togglePopup();
    });
  });
  return marker;
}

/** Penanda pemasok: BENTUK berbeda dari pin SPPG (kotak miring, bukan titik
 *  bulat) supaya dua lapisan tidak bisa tertukar di peta yang sama. */
function createSupplierPin(
  map: maplibregl.Map,
  row: SupplierPinRow,
  showLabels: boolean,
  reachKm: number | null,
  sedangJalan: boolean
): maplibregl.Marker {
  const el = document.createElement("div");
  el.className = supplierPinClass(row, showLabels, reachKm, sedangJalan);
  const accessible = supplierAccessibleLabel(row, reachKm);
  const dot = document.createElement("span");
  dot.className = "map-pin-supplier-dot";
  dot.setAttribute("aria-hidden", "true");
  dot.append(buildPinGlyph("supplier"));
  const label = document.createElement("span");
  label.className = "map-pin-label";
  label.textContent = row.name;
  el.append(dot, label);
  const marker = new maplibregl.Marker({ element: el })
    .setLngLat([row.longitude, row.latitude])
    .setPopup(jagaPopup(new maplibregl.Popup({ offset: 18, maxWidth: "320px" }).setDOMContent(supplierPopupNode(row, reachKm)), map))
    .addTo(map);
  // Sama seperti pin SPPG: MapLibre menimpa aria-label saat konstruksi.
  pasangAksesPin(el, marker, accessible);
  return marker;
}

/** Segarkan penanda pemasok yang sudah ada (posisi, nada, keterangan, popup). */
function refreshSupplierPin(
  marker: maplibregl.Marker,
  row: SupplierPinRow,
  showLabels: boolean,
  reachKm: number | null,
  sedangJalan: boolean,
  map: maplibregl.Map
): void {
  const el = marker.getElement();
  // Sama seperti pin lokasi: jangan menimpa seluruh className — kelas
  // `maplibregl-marker` milik pustaka harus bertahan supaya penanda tetap
  // `position: absolute` dan menempel di koordinatnya saat zoom in/out.
  el.className = gabungKelasPin(
    el.className,
    supplierPinClass(row, showLabels, reachKm, sedangJalan)
  );
  const accessible = supplierAccessibleLabel(row, reachKm);
  pasangAksesPin(el, marker, accessible);
  const label = el.querySelector(".map-pin-label");
  if (label) label.textContent = row.name;
  marker.setLngLat([row.longitude, row.latitude]);
  marker.setPopup(
    jagaPopup(new maplibregl.Popup({ offset: 14, maxWidth: "320px" }).setDOMContent(supplierPopupNode(row, reachKm)), map)
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
  onSorot,
}: {
  locations: readonly BalanceMapLocation[];
  /** Bila diberikan, tiap baris menjadi TOMBOL yang menyorot lokasi di peta.
   *  Tanpa prop ini, daftar memakai jembatan `lib/map-sorot` (peta yang
   *  dirender sebagai elemen bersaudara mendaftarkan dirinya di sana); bila
   *  tidak ada peta terdaftar, baris tetap statis — bukan tombol mati. */
  onSorot?: (nama: string) => void;
}) {
  const [petaSiap, setPetaSiap] = useState(() => sorotTersedia());
  useEffect(() => langgananSorot(() => setPetaSiap(sorotTersedia())), []);
  const sorot = onSorot ?? (petaSiap ? sorotLokasiTerenregistrasi : undefined);
  if (!locations.length) return null;

  return (
    <>
      <div className="map-section-head">
        <h3>Status Lokasi</h3>
        <span className="map-section-count">{locations.length} Lokasi</span>
        <span className="map-legend" role="group" aria-label="Legenda status">
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
          const isiBaris = (
            <>
              <i className={`map-dot map-dot-${l.status}`} aria-hidden="true" />
              <span className="map-row-name">{kodeWilayah(l.location)}</span>
              <span className="map-row-status">{formatBalanceStatus(l.status)}</span>
              <span className="map-row-supply">Pasokan: {formatKg(l.supply_kg)}</span>
              <span className="map-row-demand">Kebutuhan: {formatKg(l.demand_kg)}</span>
              <span className="map-row-gap">Selisih: {formatBalanceGap(l)}</span>
              {note && <span className="map-row-note">{note}</span>}
            </>
          );
          return (
            <li key={l.location} className={`map-row map-row-${l.status}`}>
              {/* Baris ini Tombol, bukan teks mati: mengetuknya menyorot lokasi
                  di peta (terbang ke titiknya + cincin aktif). Sebelumnya daftar
                  hanya bisa dibaca, sehingga satu-satunya jalan ke penanda adalah
                  peta itu sendiri — termasuk penanda yang tertutup kontrol peta. */}
              {sorot ? (
                <button
                  type="button"
                  className="map-row-btn"
                  title={`Sorot ${kodeWilayah(l.location)} di peta`}
                  onClick={() => sorot(l.location)}
                >
                  {isiBaris}
                </button>
              ) : (
                <div className="map-row-btn map-row-btn-statis">{isiBaris}</div>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}

/** Popup jalur kiriman — fakta yang sama, dibingkai seperti kartu truk. */
function routePopupNode(row: SupplierRoute): HTMLElement {
  return renderPopup(routePopupView(row));
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
  /** Gelembung klaster yang sedang tampil — dibuang lalu dibuat ulang setiap
   *  sinkronisasi supaya jumlahnya selalu sesuai data terbaru. */
  const clusterMarkersRef = useRef<maplibregl.Marker[]>([]);
  /** Koordinat asli penanda yang sempat disebar (spiderfy) di zoom maksimum;
   *  dipulihkan begitu peta digeser/diperbesar lagi agar posisi tetap jujur. */
  const sebarRef = useRef<Map<string, maplibregl.LngLat>>(new Map());
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
  // SELALU hidup (permintaan 20 Okt 2026: tombol lapisan dihapus dari peta).
  // Tidak ada state/penyetel lagi — peta tidak boleh punya keadaan "lapisan
  // mati" yang tidak bisa dinyalakan kembali, dan legenda tidak perlu
  // menerangkan lapisan yang bisa disembunyikan.
  const showSuppliers = true;
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
  /** Ikon mobil per id kiriman — hanya untuk kiriman yang SEDANG berjalan. */
  const trukMarkersRef = useRef<Map<string, maplibregl.Marker>>(new Map());
  /** Bingkai animasi geser per kiriman (dibatalkan saat posisi baru datang). */
  const trukFrameRef = useRef<Map<string, number>>(new Map());
  // Jangkar posisi mobil: `progress` server + kapan angka itu diterima. Dipakai
  // untuk memajukan mobil di antara dua polling (audit 24 Okt 2026).
  const trukJangkarRef = useRef<Map<string, JangkarTruk>>(new Map());
  const supplierRowsRef = useRef<readonly SupplierPinRow[]>(supplierMapRows);
  const supplierReachRef = useRef<number | null>(reachKm ?? null);
  // Selalu hidup — ref ikut nilai tetapnya, bukan keadaan yang bisa berubah.
  const showSuppliersRef = useRef(true);

  // --- Layer jalur kiriman (Fase 10) ---------------------------------------
  // SELALU hidup (keputusan 2026-10-16, tombolnya dihapus 20 Okt 2026):
  // garis inilah yang diminta pemilik proyek untuk diperlihatkan di peta.
  // Geometri datang dari server (cache OSRM saat sinkronisasi) — peta tidak
  // pernah memanggil OSRM sendiri.
  const showRoutes = true;
  // Rincian lapisan dilipat secara bawaan (revisi 2026-10-16): angkanya sudah
  // terbaca sebagai tag ringkas di bilah, jadi kalimat penjelas panjang tidak
  // perlu menahan ruang. Isinya tetap ada di DOM (tidak dihapus).
  const [showLayerInfo, setShowLayerInfo] = useState(false);

  const routePinRows = useMemo(() => supplierRouteRows(supplierRoutes), [supplierRoutes]);
  /** Kiriman yang sedang berjalan — satu-satunya yang punya garis + ikon mobil. */
  const jumlahJalan = useMemo(
    () => routePinRows.filter((row) => row.journey?.state === "di_jalan").length,
    [routePinRows]
  );
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
        // Butir "Sedang mengirim" hanya disebut bila ADA pin yang memakai
        // nadanya — lebih baik dari sekadar jumlah pin > 0: legenda yang
        // menjanjikan warna yang tak terlihat membuat pembaca mencari-cari.
        pemasok: showSuppliers
          ? SUPPLIER_PIN_LEGEND.filter(
              (butir) => butir.tone !== "shipping" || jumlahJalan > 0
            )
          : [],
      }),
    [routePinRows, showRoutes, showSuppliers, jumlahJalan]
  );
  // Pemenggalan baris ditentukan MAKNA, bukan lebar layar: kelompok pemasok
  // selalu mulai di baris 2 (permintaan pemilik 2026-10-19). Tanpa ini, di lebar
  // ~925 px "Pemasok · Keandalan rendah · Dikecualikan" menempel di ujung baris 1
  // dan sisanya menggantung di baris 2.
  const legendBreaks = useMemo(
    () => new Set(legendBreakIndexes(legendCompact)),
    [legendCompact]
  );
  // K3: padanan teks penanda — dihitung dari data yang SAMA dengan pin peta.
  const penanda = useMemo(() => penandaPeta(locations), [locations]);
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
  // Apakah satu kiriman sedang disorot — dipakai saat layer dasar DIBANGUN ULANG
  // (ganti komoditas) supaya opasitas redup tidak hilang begitu saja.
  const routeFokusRef = useRef(false);
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
      if (diff.changed.includes(row.location)) refreshPin(existing, row, map);
    });
    pinSignaturesRef.current = next;
  }, []);

  /** Sorot satu lokasi dari daftar "Status Lokasi": peta terbang ke titiknya dan
   *  penandanya diberi cincin aktif. Ini juga jalur menjangkau penanda yang
   *  tertutup kolom kontrol peta (SC 2.5.8, pengecualian "Equivalent"). */
  const sorotLokasi = useCallback((nama: string) => {
    const map = mapRef.current;
    const lokasi = (locationsRef.current ?? []).find((l) => l.location === nama);
    if (!map || !lokasi) return;
    markersRef.current.forEach((marker, id) => {
      marker.getElement()?.classList.toggle("map-pin-active", id === nama);
    });
    map.flyTo({
      center: [Number(lokasi.longitude), Number(lokasi.latitude)],
      // Zoom 9 cukup untuk memisahkan penanda kota yang tadinya berklaster.
      zoom: Math.max(map.getZoom(), 9),
      duration: 700,
    });
  }, []);

  // Halaman Overview merender daftar "Status Lokasi" di LUAR komponen peta, jadi
  // baris daftar tidak bisa memakai props. Peta mendaftarkan penangannya di sini.
  useEffect(() => daftarkanSorot(sorotLokasi), [sorotLokasi]);

  /** Ganti penanda yang BERTUMPUK dengan satu gelembung berisi jumlah lokasi.
   *
   *  Alasan: dua target yang pusatnya kurang dari 24 px saling berpotongan
   *  (WCAG 2.5.8 "Target Size" minimal 24×24 px + pengecualian jarak), dan di
   *  ponsel ketukan jari mengenai penanda yang salah. Koordinat penanda tidak
   *  diubah — hanya tampilannya yang digabung; gelembung diketuk akan
   *  memperbesar peta sampai penanda terpisah sendiri. */
  const syncClusters = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    clusterMarkersRef.current.forEach((marker) => marker.remove());
    clusterMarkersRef.current = [];
    const pin = markersRef.current;
    // Pulihkan posisi asli bila sebelumnya sempat disebar (spiderfy) di zoom
    // maksimum, lalu tampilkan semua penanda lagi sebelum dikelompokkan ulang.
    sebarRef.current.forEach((asli, id) => pin.get(id)?.setLngLat(asli));
    sebarRef.current.clear();
    tampilkanPin(pin);
    if (!pin.size || map.getZoom() > KLASTER_ZOOM_MAKS) return;

    const titik: { id: string; x: number; y: number }[] = [];
    pin.forEach((marker, id) => {
      const s = map.project(marker.getLngLat());
      titik.push({ id, x: s.x, y: s.y });
    });
    const grup = klasterPerluGelembung(gabungKlasterBerdekatan(kelompokkanBertumpuk(titik)));
    if (!grup.length) return;

    grup.forEach((anggota) => {
      anggota.forEach((t) => {
        const marker = pin.get(t.id);
        if (marker) sembunyikanPin(marker);
      });
      const pusat = pusatKlaster(anggota);
      const nama = anggota.map((t) => t.id);
      const gelembung = document.createElement("button");
      gelembung.type = "button";
      gelembung.className = "map-cluster";
      gelembung.textContent = String(anggota.length);
      gelembung.title = nama.join(", ");
      let gelembungMarker: maplibregl.Marker | null = null;
      gelembung.addEventListener("click", () => {
        const lngLat = map.unproject([pusat.x, pusat.y]);
        if (map.getZoom() < KLASTER_ZOOM_MAKS) {
          // Berapa level zoom yang benar-benar dibutuhkan? Cari jarak terdekat
          // antar-anggota, lalu hitung faktor pembesaran agar jaraknya melewati
          // ambang klaster (24 px). Satu klik harus cukup — kalau tidak, pengguna
          // hanya melihat gelembung yang sama berpindah tempat.
          let terdekat = Infinity;
          for (let i = 0; i < anggota.length; i += 1) {
            for (let j = i + 1; j < anggota.length; j += 1) {
              const jarak = Math.hypot(anggota[i].x - anggota[j].x, anggota[i].y - anggota[j].y);
              if (jarak < terdekat) terdekat = jarak;
            }
          }
          const faktor = (KLASTER_JARAK_PIKSEL * 1.4) / Math.max(terdekat, 1);
          const langkah = Math.min(Math.max(Math.log2(faktor), 1.5), 5);
          map.easeTo({
            center: lngLat,
            zoom: Math.min(map.getZoom() + langkah, KLASTER_ZOOM_MAKS),
          });
          return;
        }
        // Sudah di zoom maksimum (koordinat benar-benar berimpit): sebar
        // penanda pada lingkaran supaya masing-masing bisa diketuk.
        gelembungMarker?.remove();
        tampilkanPin(pin);
        const offset = offsetSpider(anggota.length, 30);
        anggota.forEach((t, i) => {
          const marker = pin.get(t.id);
          if (!marker) return;
          const asli = marker.getLngLat();
          if (!sebarRef.current.has(t.id)) sebarRef.current.set(t.id, asli);
          const p = map.project(asli);
          marker.setLngLat(map.unproject([p.x + offset[i].dx, p.y + offset[i].dy]));
        });
      });
      gelembungMarker = new maplibregl.Marker({ element: gelembung })
        .setLngLat(map.unproject([pusat.x, pusat.y]))
        .addTo(map);
      // MapLibre menulis aria-label="Map marker" saat marker dibuat (sama
      // seperti penanda SPPG), jadi nama yang benar dipasang SETELAHnya.
      gelembung.setAttribute("aria-label", labelKlaster(nama));
      clusterMarkersRef.current.push(gelembungMarker);
    });
  }, []);

  /** Sinkronkan layer jalur kiriman dengan data terbaru.
   *
   *  Bedanya dengan penanda: garis digambar sebagai source/layer MapLibre (GeoJSON),
   *  jadi butuh gaya peta siap (`load`) sebelum source bisa ditambahkan. Saat
   *  data tiba sebelum gaya siap, handler `load` yang memanggil ulang fungsi ini. */
  /**
   * Geser ikon mobil ke posisi baru dengan halus.
   *
   * Data kiriman diperbarui tiap 5 detik (Live Sync); tanpa animasi, ikon
   * MELOMPAT di sepanjang garis dan terbaca seperti kesalahan render. Satu
   * transisi 700 ms dengan easing keluar membuat geraknya terbaca sebagai
   * kendaraan yang maju — satu-satunya gerak di peta, dan ia membawa arti
   * (posisi kendaraan), bukan hiasan.
   */
  const geserTruk = useCallback(
    (id: string, marker: maplibregl.Marker, ke: [number, number], arahKe: number) => {
      const bingkaiLama = trukFrameRef.current.get(id);
      if (bingkaiLama !== undefined && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(bingkaiLama);
      }
      const el = marker.getElement();
      const dari = marker.getLngLat();
      const arahDari = Number(el.style.getPropertyValue("--truk-arah").replace("deg", "")) || 0;
      const setArah = (derajat: number) =>
        el.style.setProperty("--truk-arah", `${Math.round(derajat)}deg`);
      const tanpaGerak =
        typeof requestAnimationFrame !== "function" ||
        typeof performance === "undefined" ||
        mediaQueryCocok("(prefers-reduced-motion: reduce)");
      if (tanpaGerak) {
        marker.setLngLat(ke);
        setArah(arahKe);
        return;
      }
      // Arah terpendek: 350° → 10° harus lewat 360°, bukan berputar balik.
      const selisih = ((arahKe - arahDari + 540) % 360) - 180;
      const diam =
        Math.abs(ke[0] - dari.lng) < 1e-9 &&
        Math.abs(ke[1] - dari.lat) < 1e-9 &&
        Math.abs(selisih) < 0.5;
      if (diam) return;
      const mulai = performance.now();
      const LAMA_MS = 700;
      const langkah = (kini: number) => {
        const t = Math.min(1, (kini - mulai) / LAMA_MS);
        const e = 1 - Math.pow(1 - t, 3); // ease-out cubic
        marker.setLngLat([
          dari.lng + (ke[0] - dari.lng) * e,
          dari.lat + (ke[1] - dari.lat) * e,
        ]);
        setArah(arahDari + selisih * e);
        if (t < 1) trukFrameRef.current.set(id, requestAnimationFrame(langkah));
        else trukFrameRef.current.delete(id);
      };
      trukFrameRef.current.set(id, requestAnimationFrame(langkah));
    },
    []
  );

  /**
   * Jangkar posisi mobil untuk satu kiriman.
   *
   * Server hanya mengirim `progress` tiap polling; di antaranya mobil harus
   * tetap maju. Jangkar diganti HANYA saat angka server berubah, supaya gerak
   * lokal tidak "mundur" hanya karena satu kiriman belum berubah angkanya.
   */
  const jangkarTruk = useCallback((row: SupplierRoute): JangkarTruk => {
    const peta = trukJangkarRef.current;
    const angka = Math.min(1, Math.max(0, row.journey?.progress ?? 0));
    const lama = peta.get(row.id);
    if (lama && Math.abs(lama.progress - angka) < 1e-9) return lama;
    const baru: JangkarTruk = { progress: angka, at: Date.now() };
    peta.set(row.id, baru);
    return baru;
  }, []);

  /**
   * Pasang/pindahkan ikon mobil ke posisi kendaraan SEKARANG.
   *
   * Hanya kiriman `di_jalan` yang punya ikon: yang sudah tiba atau belum
   * berangkat tidak sedang mengirim, jadi tidak perlu indikator di peta.
   * Posisi dihitung dari `journey.progress` pada geometri jalan, arah dari
   * segmen di titik itu (lihat lib/route-flow.ts).
   */
  const syncTruk = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const hidup = new Set<string>();
    const wakes: GeoJSON.Feature[] = [];
    for (const row of routeRowsRef.current) {
      if (row.journey?.state !== "di_jalan") continue;
      const koordinat = row.road?.coordinates;
      if (!koordinat || koordinat.length < 2) continue;
      const jalur = siapkanJalur(koordinat as [number, number][]);
      if (!jalur) continue;
      // Posisi dihitung dari waktu, bukan dari angka beku: `progress` server
      // menjadi jangkar, lalu fraksi dimajukan per detik sehingga mobil benar-
      // benar berjalan (audit 24 Okt 2026).
      const frac = fraksiBerjalan(row.journey, jangkarTruk(row), Date.now());
      const { posisi, arah } = posisiDanArah(jalur, frac);
      hidup.add(row.id);
      // Ekor: jejak beberapa kilometer terakhir. Ini yang membuat kendaraan
      // terbaca "sedang bergerak ke arah sana", bukan titik yang melompat.
      const ekor = wakeLine(jalur, frac);
      if (ekor.length > 1) {
        wakes.push({
          type: "Feature",
          properties: { id: row.id },
          geometry: { type: "LineString", coordinates: ekor },
        });
      }
      const derajat = Math.round(arah);
      const ada = trukMarkersRef.current.get(row.id);
      if (ada) {
        // Jejak untuk audit: fraksi yang benar-benar dipakai tiap detak.
        // Terbaca di DOM (`data-frac`) tanpa perlu console.log di produksi.
        ada.getElement().dataset.frac = frac.toFixed(5);
        geserTruk(row.id, ada, posisi, derajat);
        continue;
      }
      const baru = createTruckMarker(map, row, posisi, derajat);
      baru.getElement().dataset.frac = frac.toFixed(5);
      trukMarkersRef.current.set(row.id, baru);
    }
    // Kiriman yang selesai/berhenti: ikonnya dicabut, bukan dibiarkan menua.
    for (const [id, marker] of Array.from(trukMarkersRef.current.entries())) {
      if (hidup.has(id)) continue;
      marker.remove();
      trukMarkersRef.current.delete(id);
      // Jangkar ikut dibuang: kiriman yang tiba tidak boleh menyisakan entri.
      trukJangkarRef.current.delete(id);
    }
    // Ekor digambar sebagai SATU layer (bukan satu per kiriman): menggambar 1–3
    // garis lewat satu source jauh lebih murah daripada menambah layer dinamis.
    const data: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: wakes };
    const sumber = map.getSource(WAKE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (wakes.length === 0) {
      if (map.getLayer(WAKE_LAYER_ID)) map.removeLayer(WAKE_LAYER_ID);
      if (sumber) map.removeSource(WAKE_SOURCE_ID);
      return;
    }
    if (!map.isStyleLoaded()) {
      // Gaya peta bisa belum siap saat data tiba lebih dulu (race). Tanpa
      // penjaga ini MapLibre melempar "Style is not done loading", error
      // boundary menangkapnya, dan SELURUH layar jadi kosong — terukur pada
      // peran BGN Monitor saat membuka Overview. Layer ekor truk kosmetik:
      // lewati dulu, dipasang lagi pada pemanggilan berikutnya / event load.
      return;
    }
    if (sumber) {
      sumber.setData(data);
      return;
    }
    map.addSource(WAKE_SOURCE_ID, { type: "geojson", data });
    map.addLayer({
      id: WAKE_LAYER_ID,
      type: "line",
      source: WAKE_SOURCE_ID,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#8B5CF6",
        "line-width": ["interpolate", ["linear"], ["zoom"], 5, 8, 10, 13],
        "line-blur": 5,
        "line-opacity": 0.55,
      },
    });
  }, [geserTruk, jangkarTruk]);

  const syncRouteLayer = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const aktif = showRoutesRef.current && routeFeaturesRef.current.features.length > 0;
    const source = map.getSource(ROUTE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (!aktif) {
      // Dimatikan / tidak ada data: bersihkan sepenuhnya, jangan tinggalkan
      // setengah lapisan yang tampak "masih ada jalur".
      if (map.getLayer(ROUTE_HALO_DONE_LAYER_ID)) map.removeLayer(ROUTE_HALO_DONE_LAYER_ID);
      if (map.getLayer(ROUTE_HALO_TODO_LAYER_ID)) map.removeLayer(ROUTE_HALO_TODO_LAYER_ID);
      if (map.getLayer(ROUTE_DONE_LAYER_ID)) map.removeLayer(ROUTE_DONE_LAYER_ID);
      if (map.getLayer(ROUTE_TODO_LAYER_ID)) map.removeLayer(ROUTE_TODO_LAYER_ID);
      if (map.getLayer(ROUTE_CASING_DONE_LAYER_ID)) map.removeLayer(ROUTE_CASING_DONE_LAYER_ID);
      if (map.getLayer(ROUTE_CASING_TODO_LAYER_ID)) map.removeLayer(ROUTE_CASING_TODO_LAYER_ID);
      if (map.getLayer(ROUTE_GLINT_LAYER_ID)) map.removeLayer(ROUTE_GLINT_LAYER_ID);
      if (source) map.removeSource(ROUTE_SOURCE_ID);
      return;
    }
    if (source) {
      source.setData(routeFeaturesRef.current);
      return;
    }
    if (!map.isStyleLoaded()) return;
    map.addSource(ROUTE_SOURCE_ID, { type: "geojson", data: routeFeaturesRef.current });
    const warnaGaris = [
      "match",
      ["get", "tone"],
      "fail",
      ROUTE_LINE_COLORS.fail,
      ROUTE_LINE_COLORS.ok,
    ] as maplibregl.ExpressionSpecification;
    const warnaSisa = [
      "match",
      ["get", "tone"],
      "fail",
      ROUTE_TODO_COLORS.fail,
      ROUTE_TODO_COLORS.ok,
    ] as maplibregl.ExpressionSpecification;
    // HANYA lapisan dasar + SATU halo tenang (redesign 20 Okt 2026).
    //
    // Versi sebelumnya menumpuk tiga efek sekaligus — halo lebar, inti neon
    // violet, denyut 1,2 dtk, plus tiga titik mengalir — pada warna di luar
    // palet status. Hasilnya ramai: mata mengejar gerak yang tidak membawa
    // informasi tambahan. Aturan yang dipakai sekarang: SATU elemen bergerak
    // (ikon mobil, karena posisinya memang data), garis hanya memberi penekanan.
    //
    // Garis tetap membawa arti lamanya (peta-patterns: putus = belum ditempuh):
    // padat hijau = sudah ditempuh, putus biru = sisa perjalanan.
    const sedangJalan: maplibregl.FilterSpecification = ["==", ["get", "state"], "di_jalan"];
    // Halo sewarna nadanya, bukan warna baru: menaikkan bobot visual tanpa
    // menambah arti kedua yang harus dipelajari pembaca.
    map.addLayer({
      id: ROUTE_HALO_DONE_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["all", ["==", ["get", "kind"], "done"], sedangJalan],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": warnaGaris,
        "line-width": 20,
        "line-blur": 12,
        "line-opacity": 0.26,
      },
    });
    map.addLayer({
      id: ROUTE_HALO_TODO_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["all", ["==", ["get", "kind"], "todo"], sedangJalan],
      layout: { "line-cap": "butt", "line-join": "round" },
      paint: {
        "line-color": warnaSisa,
        "line-width": 18,
        "line-blur": 12,
        "line-opacity": 0.22,
      },
    });

    // Alas putih lalu garis di atasnya. Urutan ini yang membuat garis terbaca di
    // basemap terang; halo tadi paling bawah supaya tidak menutupi pin.
    map.addLayer({
      id: ROUTE_CASING_DONE_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["all", ["==", ["get", "kind"], "done"], ["!=", ["get", "quiet"], true]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#FFFFFF",
        "line-width": ROUTE_CASING_WIDTH,
        "line-opacity": routeFokusRef.current ? 0.15 : 0.85,
      },
    });
    map.addLayer({
      id: ROUTE_CASING_TODO_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["all", ["==", ["get", "kind"], "todo"], ["!=", ["get", "quiet"], true]],
      layout: { "line-cap": "butt", "line-join": "round" },
      paint: {
        "line-color": "#FFFFFF",
        "line-width": ROUTE_TODO_CASING_WIDTH,
        // Alas ikut putus dengan pola yang sama, supaya sisa perjalanan tidak
        // terbaca sebagai jalan solid.
        "line-dasharray": [4, 3],
        "line-opacity": routeFokusRef.current ? 0.15 : 0.5,
      },
    });
    map.addLayer({
      id: ROUTE_DONE_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["all", ["==", ["get", "kind"], "done"], ["!=", ["get", "quiet"], true]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": warnaGaris,
        "line-width": ROUTE_LINE_WIDTH,
        "line-opacity": routeFokusRef.current ? 0.22 : 0.9,
      },
    });
    map.addLayer({
      id: ROUTE_TODO_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["all", ["==", ["get", "kind"], "todo"], ["!=", ["get", "quiet"], true]],
      layout: { "line-cap": "butt", "line-join": "round" },
      paint: {
        "line-color": warnaSisa,
        "line-width": ROUTE_TODO_WIDTH,
        // Celah lebih lebar dari garis (4 vs 3): pola putus harus terbaca
        // sebagai "belum", bukan garis padat yang terputus-putus.
        "line-dasharray": [4, 3],
        "line-opacity": routeFokusRef.current ? 0.26 : 0.62,
      },
    });

    // Kiriman yang sudah tiba: satu garis utuh, abu-abu, putus-putus, tipis.
    // Tidak diberi halo/glint/ikon — peta tetap tenang, tetapi jalur yang sudah
    // ditempuh masih terbaca sebagai konteks.
    // Jalur yang sudah tiba: alas putih + garis nada (hijau/merah) yang diredupkan.
    // Versi pertama memakai abu-abu 2,5px @0,32 — terukur saat audit 21 Okt 2026:
    // nyaris tak terlihat di basemap terang. Sekarang warnanya tetap dari palet
    // status (bukan warna baru, supaya legenda tidak berbohong), tetapi lebih
    // tebal dan diberi alas supaya terbaca.
    map.addLayer({
      id: `${ROUTE_QUIET_LAYER_ID}-casing`,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["==", ["get", "quiet"], true],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#FFFFFF",
        "line-width": 7.6,
        "line-opacity": 0.75,
      },
    });
    map.addLayer({
      id: ROUTE_QUIET_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["==", ["get", "quiet"], true],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#475569",
        "line-width": 4.4,
        "line-dasharray": [7, 5],
        "line-opacity": 0.75,
      },
    });

    // Kilau di atas bagian yang SUDAH ditempuh. Putih, sangat tipis, dan hanya
    // di potongan padat — jadi ia mempertegas "yang benar-benar sudah jalan",
    // bukan menambah kode warna baru yang harus dipelajari pembaca.
    map.addLayer({
      id: ROUTE_GLINT_LAYER_ID,
      type: "line",
      source: ROUTE_SOURCE_ID,
      filter: ["all", ["==", ["get", "kind"], "done"], sedangJalan],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#FFFFFF",
        "line-width": ROUTE_GLINT_WIDTH,
        "line-opacity": routeFokusRef.current ? 0.15 : 0.62,
      },
    });

    // Klik berlaku di KEDUA lapisan: kalau hanya lapisan putus-putus yang bisa
    // diklik, kiriman yang sudah tiba (garisnya padat semua) kehilangan popup.
    const bukaPopupJalur = (event: maplibregl.MapLayerMouseEvent) => {
      const id = (event.features?.[0]?.properties as { id?: string } | undefined)?.id;
      const row = routeRowsRef.current.find((item) => shipmentKey(item) === id);
      if (!row) return;
      // Klik garis = sorot kiriman ini (Arah C). Popup tetap muncul: ia yang
      // dibaca di tempat klik, sedangkan kartu kiriman di bawah peta memuat
      // stepper, rincian, dan riwayatnya.
      // Klik pada ikon truk juga sampai ke layer garis di bawahnya; jangan
      // ganti popup truk dengan popup jalur untuk klik yang sama.
      if (Date.now() - trukKlikTerakhir < 600) return;
      onFocusRouteRef.current?.(row.id);
      jagaPopup(
        new maplibregl.Popup({ offset: 10, maxWidth: "320px" })
          .setLngLat(event.lngLat)
          .setDOMContent(routePopupNode(row)),
        map
      ).addTo(map);
    };
    map.on("click", ROUTE_GLINT_LAYER_ID, bukaPopupJalur);
    map.on("click", ROUTE_DONE_LAYER_ID, bukaPopupJalur);
    map.on("click", ROUTE_TODO_LAYER_ID, bukaPopupJalur);
    // Kiriman yang SUDAH TIBA punya layer sendiri (garis redup). Tanpa
    // pendaftaran ini, garis yang paling banyak terlihat di sore hari justru
    // satu-satunya yang tidak bisa diklik — ditemukan saat audit 22 Okt 2026.
    map.on("click", ROUTE_QUIET_LAYER_ID, bukaPopupJalur);

    // Urutan pasang layer mengikuti urutan data tiba, jadi ekor kendaraan bisa
    // tertimbun alas putih/garis jalur. Naikkan eksplisit: jejak truk harus
    // selalu terbaca di atas jalur.
    if (map.getLayer(WAKE_LAYER_ID)) map.moveLayer(WAKE_LAYER_ID);
  }, []);

  /** Redupkan garis jalur dasar saat satu kiriman disorot.
   *
   *  Tanpa ini, tiga (atau 21, di tampilan BGN) garis dengan koridor yang sama
   *  menumpuk dan sorotan tetap tenggelam di keramaian. Garis yang tidak dipilih
   *  tidak dihapus — hanya diturunkan opasitasnya — supaya konteks jaringan tetap
   *  terlihat dan tidak ada informasi yang hilang. */
  const dimBaseRoutes = useCallback((redup: boolean) => {
    const map = mapRef.current;
    routeFokusRef.current = redup;
    if (!map) return;
    const atur = (id: string, nilai: number) => {
      if (!map.getLayer(id)) return;
      try {
        map.setPaintProperty(id, "line-opacity", nilai);
      } catch {
        // Gaya peta sedang dimuat ulang: lewati, bukan melempar ke error boundary.
      }
    };
    atur(ROUTE_DONE_LAYER_ID, redup ? 0.22 : 0.9);
    atur(ROUTE_TODO_LAYER_ID, redup ? 0.26 : 0.62);
    atur(ROUTE_CASING_DONE_LAYER_ID, redup ? 0.15 : 0.85);
    atur(ROUTE_CASING_TODO_LAYER_ID, redup ? 0.12 : 0.5);
    atur(ROUTE_GLINT_LAYER_ID, redup ? 0.15 : 0.5);
  }, []);

  /** Sinkronkan garis SOROTAN (Arah C).
   *
   *  Sama seperti layer dasar: butuh gaya peta siap sebelum source bisa dibuat,
   *  dan saat tidak ada yang disorot seluruh layer + source DIBUANG — tidak boleh
   *  tertinggal garis sorotan untuk kiriman yang sudah dilepas. */
  const syncFocusLayer = useCallback(() => {
    const warnaSisa = [
      "match",
      ["get", "tone"],
      "fail",
      ROUTE_TODO_COLORS.fail,
      ROUTE_TODO_COLORS.ok,
    ] as maplibregl.ExpressionSpecification;
    const map = mapRef.current;
    if (!map) return;
    const data = focusLinesRef.current;
    const aktif = showRoutesRef.current && data.features.length > 0;
    // Sorotan hidup → garis dasar diredupkan; sorotan dilepas → warna normal.
    dimBaseRoutes(aktif);
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
        "line-color": warnaSisa,
        "line-width": ROUTE_FOCUS_WIDTH,
        "line-dasharray": [4, 3],
        "line-opacity": 0.95,
      },
    });
  }, [dimBaseRoutes]);

  /** Pemasok yang punya kiriman `di_jalan` saat ini. Pin-nya diberi isian warna
   *  aktif + denyut; sisanya tetap lingkaran bergaris. Diisi dari data jalur,
   *  bukan dari blok `shipping` pemasok (blok itu menghitung kiriman yang sudah
   *  tiba juga). */
  const jalanRef = useRef<Set<string>>(new Set());

  /** Sinkronkan penanda PEMASOK: hanya saat lapisan dinyalakan DAN zoom cukup
   *  dekat. Semua penanda dibuang saat lapisan dimatikan atau zoom dijauhkan —
   *  tidak ada yang tertinggal setengah aktif. */
  const syncSupplierMarkers = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const markers = supplierMarkersRef.current;
    // Lapisan pemasok selalu hidup dan TIDAK digerbang zoom: titiknya digambar
    // di semua tingkat perbesaran (lihat catatan di lib/supplier-pins.ts).
    const visible = showSuppliersRef.current;
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
        refreshSupplierPin(
          existing,
          row,
          showLabels,
          supplierReachRef.current,
          jalanRef.current.has(row.id),
          map
        );
        return;
      }
      markers.set(
        row.id,
        createSupplierPin(map, row, showLabels, supplierReachRef.current, jalanRef.current.has(row.id))
      );
    });
  }, []);

  // Data jalur datang setelah peta hidup: perbarui himpunan pemasok aktif lalu
  // segarkan penanda, supaya warna pin tidak bergantung pada urutan permintaan.
  useEffect(() => {
    jalanRef.current = new Set(
      routePinRows
        .filter((row) => row.journey?.state === "di_jalan")
        .map((row) => row.supplierId)
    );
    syncSupplierMarkers();
  }, [routePinRows, syncSupplierMarkers]);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current || !locationsRef.current?.length) return;
    // Salinan ref untuk cleanup: nilai `.current` bisa berubah sebelum cleanup
    // dijalankan (aturan react-hooks/exhaustive-deps).
    const markers = markersRef.current;
    const supplierMarkers = supplierMarkersRef.current;
    const trukMarkers = trukMarkersRef.current;
    const sebar = sebarRef.current;
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
    // Bilah skala ("50 km") DIHAPUS atas permintaan pemilik 19 Okt 2026: ia
    // duduk di kiri-bawah, tempat yang sekarang dipakai pil sakelar lapisan,
    // dan skalanya jarang dibaca saat memeriksa pin/jalur. Konsekuensi yang
    // disengaja: jarak tidak lagi bisa diukur langsung dari peta — angka km
    // tetap ada di popup jalur dan kartu kiriman.
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
    syncClusters();
    // Zoom hanya menentukan apakah NAMA pemasok ikut ditulis di samping titik.
    // Keadaan ini juga dipakai memberi tahu pengguna kenapa pin tampil tanpa nama.
    setZoomEnough(supplierLabelsVisible(map.getZoom()));
    const onZoom = () => {
      setZoomEnough(supplierLabelsVisible(map.getZoom()));
      syncSupplierMarkers();
      syncClusters();
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
    const wadah = mapContainer.current;
    const observer = new ResizeObserver(() => {
      map.resize();
      if (wadah) aturOffsetKontrol(wadah);
    });
    observer.observe(wadah);
    // Pil lapisan muncul BELAKANGAN (setelah data pemasok tiba), jadi tinggi
    // awalnya 0. MutationObserver memantau DOM kanvas: begitu pil (atau isinya)
    // berubah, offset kontrol kanan-atas dihitung ulang.
    let raf = 0;
    const pemantau = new MutationObserver(() => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        aturOffsetKontrol(wadah);
      });
    });
    pemantau.observe(wadah.closest(".map-shell") ?? wadah, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "style"],
    });
    aturOffsetKontrol(wadah);

    return () => {
      observer.disconnect();
      pemantau.disconnect();
      if (raf) cancelAnimationFrame(raf);
      map.off("zoomend", onZoom);
      map.off("load", syncRouteLayer);
      map.off("load", syncFocusLayer);
      map.remove();
      mapRef.current = null;
      markers.clear();
      supplierMarkers.clear();
      trukMarkers.forEach((marker) => marker.remove());
      trukMarkers.clear();
      clusterMarkersRef.current = [];
      sebar.clear();
      pinSignaturesRef.current = {};
      focusRef.current = MAP_FOCUS_INITIAL;
    };
  }, [hasLocations, syncMarkers, syncClusters, syncSupplierMarkers, syncRouteLayer, syncFocusLayer]);

  // Sinkronisasi data (arah Roy 2026-10-11): penanda saja, tanpa fitBounds.
  useEffect(() => {
    syncMarkers();
    syncClusters();
  }, [pinSnapshot, syncMarkers, syncClusters]);

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
    // Hanya berdenyut kalau memang ada kiriman yang sedang berjalan: lapisan
    // glow tanpa isi tidak perlu animasi.
    const adaJalan = routeFeatures.features.some(
      (f) => (f.properties as { state?: string | null }).state === "di_jalan"
    );
    syncTruk();
    // Kalau sinkronisasi di atas terlewat karena gaya peta belum siap, ulangi
    // tepat saat gaya selesai dimuat.
    const peta = mapRef.current;
    if (peta) peta.on("load", syncTruk);
    // Audit 24 Okt 2026: mobil harus tetap berjalan DI ANTARA dua polling.
    // Satu langkah per detik, dihaluskan ease 700 ms di `geserTruk`; tanpa ini
    // posisi hanya berubah tiap 15 detik dan di layar tampak diam.
    if (!adaJalan || mediaQueryCocok("(prefers-reduced-motion: reduce)")) return;
    const detak = window.setInterval(syncTruk, 1000);
    return () => window.clearInterval(detak);
  }, [
    showRoutes,
    routePinRows,
    routeFeatures,
    syncRouteLayer,
    syncTruk,
  ]);

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
          {/* Tombol lapisan peta DIHAPUS (permintaan 20 Okt 2026): pin pemasok
              dan jalur kiriman selalu tampil, jadi sakelar "tampilkan/sembunyikan"
              tidak punya keadaan yang bisa dipilih lagi. Legenda di bawah kanvas
              tetap menerangkan warna garis dan bentuk penanda. */}
          {/* Sematan "Info map" dilebur ke panel "Rincian lapisan peta" di
              bawah (19 Okt 2026). Alasannya bukan ruang: isi panel itu memang
              legenda yang SAMA dengan baris legenda di bawah kanvas (status,
              jalur, pemasok) — satu fakta dibaca dua tempat, yang kedua lewat
              klik. Satu-satunya isi yang tidak duplikat, daftar perjalanan
              kiriman, ikut pindah ke panel itu. */}
        </div>

        {/* Baris legenda ringkas (celah C2, langkah 7b-2): makna titik & garis
            terbaca TANPA satu klik. Sengaja di BAWAH kanvas, bukan mengapung di
            atasnya — panel putih di atas peta pernah menutup 39% kanvas, tepat di
            atas Jawa Barat (keputusan pemilik 2026-10-16). Di sini hanya tanda +
            nama; kalimat panjang (perjalanan & asal geometri) tetap di "Info map",
            dan angka jumlahnya tetap di tag bilah rincian. */}
        <div className="map-legend-compact" role="group" aria-label="Legenda peta">
          <span className="map-legend-compact-title">Legenda:</span>
          {legendCompact.map((butir, urutan) => {
            // SEMUA kelas dipakai: nada (warna) + gaya (padat/putus) untuk garis.
            const kelas = legendMarkClass(butir).join(" ");
            return (
              <Fragment key={butir.id}>
                {/* Pemenggal baris: elemen dekoratif setinggi 0 selebar baris,
                    jadi tidak menambah makna apa pun untuk pembaca layar. */}
                {legendBreaks.has(urutan) && (
                  <span className="map-legend-compact-break" aria-hidden="true" />
                )}
                <span className="map-legend-compact-item">
                  <i className={kelas} aria-hidden="true" />{" "}
                  {butir.label}
                </span>
              </Fragment>
            );
          })}
        </div>

        {/* K3 — padanan TEKS untuk isi peta. Selalu dirender, termasuk saat daftar
            status lokasi dimatikan di Overview: penanda peta tidak masuk urutan
            Tab, jadi tanpa baris ini pembaca layar tidak punya jalan masuk.
            Bentuknya satu baris (nama + selisih) — BUKAN tabel pasokan/kebutuhan
            yang sudah dihapus pemilik. Kalimat penuh ada di daftar sr-only. */}
        {penanda.length > 0 && (
          <p
            className="map-marker-line"
            title={penanda.map((butir) => butir.aria).join(" · ")}
          >
            <span className="map-marker-line-title">Penanda:</span>{" "}
            {ringkasPenanda(penanda)}
          </p>
        )}
        {penanda.length > 0 && (
          <ul className="sr-only" aria-label="Daftar penanda peta">
            {penanda.map((butir) => (
              <li key={butir.nama}>{butir.aria}</li>
            ))}
          </ul>
        )}

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
                {/* Perjalanan kiriman: satu-satunya isi "Info map" yang tidak
                    duplikat legenda, jadi ia ikut pindah ke sini. Hanya saat
                    lapisan jalur hidup — keterangan garis yang tidak ada di
                    peta adalah informasi palsu (aturan yang sama seperti
                    legenda ringkas). */}
                {journeyRows.length > 0 && (
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
        {/* Pin pemasok tidak lagi digerbang zoom (20 Okt 2026): yang perlu
            diterangkan tinggal NAMA-nya. Kalimatnya di luar panel lipat supaya
            langsung terbaca. */}
        {Boolean(suppliers) && showSuppliers && zoomEnough === false && (
          <p className="map-layer-hint" role="status">
            {supplierSummary.total} pemasok tampil sebagai titik; nama pemasok muncul
            pada zoom {SUPPLIER_LABEL_MIN_ZOOM} ke atas.
          </p>
        )}
        {Boolean(supplierRoutes) && jumlahJalan > 0 && (
          <p className="map-layer-hint" role="status">
            Ikon mobil menandai posisi kiriman yang sedang berjalan sekarang.
          </p>
        )}
        {showStatusList && (
          <div className="map-side">
            <StatusLocationList locations={locations} onSorot={sorotLokasi} />
          </div>
        )}
      </div>
    </section>
  );
}
