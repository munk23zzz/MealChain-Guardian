// Fase 10 (keputusan pemilik 2026-10-16): garis JALUR KIRIMAN di peta.
//
// Modul MURNI (tanpa React, tanpa DOM, tanpa MapLibre) — aturan garis diuji di
// tests/supplier-routes.test.ts tanpa perlu WebGL.
//
// Sumber data: `GET /supplier-routes`. Aturan yang dipegang:
// - Garis digambar HANYA dari geometri jalan yang benar-benar ada di cache
//   (data OSRM). Kiriman yang rutenya belum disinkronkan tetap dilaporkan
//   (titik ujungnya ikut menentukan tampilan peta) tapi TIDAK digambar garis —
//   garis lurus yang menyamar sebagai rute jalan akan menyesatkan.
// - Jarak jalan (OSRM) dan jarak lurus (haversine server) ditampilkan
//   berdampingan, termasuk rasionya: juri berhak tahu jalur jalan biasanya
//   lebih panjang dari jarak udara, bukan angka yang sama.
// - Warna garis mengikuti MUTU kiriman (fail = nada bahaya). Cincin "sedang
//   mengirim" di pin tetap terpisah, jadi dua fakta berbeda tidak saling
//   menutupi (keputusan Fase 9).
// - Alasan rute tidak ada ditulis apa adanya (`MISSING_REASON_LABEL`), bukan
//   disembunyikan jadi "—".

import { formatDate } from "./datetime";
import { formatKg } from "./overview-format";

export type RouteLineTone = "ok" | "fail";

/**
 * Warna garis untuk `paint` MapLibre.
 *
 * WebGL tidak bisa membaca CSS custom property, jadi nilainya literal — dan HARUS
 * sama dengan token di `app/globals.css` (`--status-safe` / `--status-danger`).
 * Kesamaan itu dikunci tes yang membaca berkas CSS-nya, supaya tidak ada dua
 * definisi warna yang bisa menyimpang tanpa ketahuan.
 */
export const ROUTE_LINE_COLORS: Record<RouteLineTone, string> = {
  ok: "#2E7D32",
  fail: "#C62828",
};

export type SupplierRouteRoad = {
  distanceKm: number;
  durationMin: number;
  ratioVsStraight: number | null;
  coordinates: [number, number][];
  source: string;
  fetchedAt: string | null;
};

export type SupplierRoute = {
  id: string;
  batchId: string | null;
  supplierId: string;
  supplierName: string;
  originLatitude: number;
  originLongitude: number;
  destinationId: string | null;
  destinationName: string;
  destinationLatitude: number;
  destinationLongitude: number;
  commodity: string | null;
  quantityKg: number | null;
  usableUntil: string | null;
  safetyStatus: string | null;
  straightKm: number | null;
  road: SupplierRouteRoad | null;
  missingReason: string | null;
};

export type RouteFeature = {
  type: "Feature";
  geometry: { type: "LineString"; coordinates: [number, number][] };
  properties: {
    id: string;
    tone: RouteLineTone;
    label: string;
    supplierName: string;
    destinationName: string;
    commodity: string | null;
    quantityKg: number | null;
    roadKm: number;
    durationMin: number;
    safetyStatus: string | null;
  };
};

export type RouteFeatureCollection = {
  type: "FeatureCollection";
  features: RouteFeature[];
};

export type RouteLayerSummary = {
  routes: number;
  withRoad: number;
  missing: number;
  label: string;
};

/** Nama alasan dari server → kalimat yang bisa dibaca pengguna. */
export const MISSING_REASON_LABEL: Record<string, string> = {
  belum_disinkron: "rute jalan belum disinkronkan dari OSRM",
  layanan_rute_tidak_terjangkau: "layanan rute OSRM tidak terjangkau saat sinkronisasi",
  rute_tidak_ditemukan: "OSRM tidak menemukan jalur jalan",
  respons_rute_tidak_dikenal: "respons rute OSRM tidak dikenali",
};

function text(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  return raw ? raw : null;
}

function number(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

/**
 * Jarak (km) apa adanya dengan satu desimal, gaya id-ID.
 *
 * Sengaja TIDAK memakai `distanceLabel` (lib/supplier-pins.ts): fungsi itu
 * membulatkan jarak ≥ 100 km jadi bilangan bulat, sedangkan di baris jalur
 * beda "110,4 km jalan" vs "76,7 km lurus" itulah buktinya — pembulatan akan
 * menghapus justru hal yang ingin diperlihatkan.
 */
export function roadKmLabel(km: number | null): string {
  if (km === null || !Number.isFinite(km)) return "—";
  return `${(Math.round(km * 10) / 10).toFixed(1).replace(".", ",")} km`;
}

function parseCoordinates(raw: unknown): [number, number][] {
  if (!Array.isArray(raw)) return [];
  const out: [number, number][] = [];
  for (const point of raw) {
    if (!Array.isArray(point) || point.length !== 2) continue;
    const lon = number(point[0]);
    const lat = number(point[1]);
    if (lon === null || lat === null) continue;
    out.push([lon, lat]);
  }
  return out;
}

function parseRoad(raw: unknown): SupplierRouteRoad | null {
  if (raw === null || raw === undefined || typeof raw !== "object") return null;
  const fields = raw as Record<string, unknown>;
  const distanceKm = number(fields.distance_km);
  const durationMin = number(fields.duration_min);
  const geometry = (fields.geometry ?? {}) as Record<string, unknown>;
  const coordinates = parseCoordinates(geometry.coordinates);
  // Tanpa jarak atau tanpa garis, tidak ada yang bisa digambar.
  if (distanceKm === null || coordinates.length < 2) return null;
  return {
    distanceKm,
    durationMin: durationMin ?? 0,
    ratioVsStraight: number(fields.ratio_vs_straight),
    coordinates,
    source: text(fields.source) ?? "osrm",
    fetchedAt: text(fields.fetched_at),
  };
}

function parseRoute(raw: unknown): SupplierRoute | null {
  if (raw === null || raw === undefined || typeof raw !== "object") return null;
  const fields = raw as Record<string, unknown>;
  const origin = (fields.origin ?? {}) as Record<string, unknown>;
  const destination = (fields.destination ?? {}) as Record<string, unknown>;
  const supplierName = text(fields.supplier_name);
  const destinationName = text(fields.destination_name) ?? text(destination.name);
  const originLatitude = number(origin.latitude);
  const originLongitude = number(origin.longitude);
  const destinationLatitude = number(destination.latitude);
  const destinationLongitude = number(destination.longitude);
  // Tanpa dua ujung yang pasti, tidak ada garis yang bisa dipertanggungjawabkan.
  if (
    !supplierName ||
    !destinationName ||
    originLatitude === null ||
    originLongitude === null ||
    destinationLatitude === null ||
    destinationLongitude === null
  ) {
    return null;
  }
  return {
    id: `${text(fields.supplier_id) ?? supplierName}->${text(fields.destination_id) ?? destinationName}`,
    batchId: text(fields.batch_id),
    supplierId: text(fields.supplier_id) ?? supplierName,
    supplierName,
    originLatitude,
    originLongitude,
    destinationId: text(fields.destination_id),
    destinationName,
    destinationLatitude,
    destinationLongitude,
    commodity: text(fields.commodity),
    quantityKg: number(fields.quantity_kg),
    usableUntil: text(fields.usable_until),
    safetyStatus: text(fields.safety_status),
    straightKm: number(fields.straight_km),
    road: parseRoad(fields.road),
    missingReason: text(fields.road_missing_reason),
  };
}

/**
 * Normalisasi payload `GET /supplier-routes` (amplop `{routes}` atau array).
 * Baris tanpa dua ujung berkoordinat dibuang — sama seperti backend yang
 * melaporkannya terpisah di `summary.dilewati_tanpa_koordinat`.
 */
export function supplierRoutes(raw: unknown): SupplierRoute[] {
  const list = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as { routes?: unknown } | null)?.routes)
      ? ((raw as { routes: unknown[] }).routes as unknown[])
      : [];
  const out: SupplierRoute[] = [];
  for (const item of list) {
    const row = parseRoute(item);
    if (row) out.push(row);
  }
  return out;
}

/** Nada garis: kiriman bermutu `fail` memakai nada bahaya. */
export function routeLineTone(row: SupplierRoute): RouteLineTone {
  return row.safetyStatus === "fail" ? "fail" : "ok";
}

/**
 * Kelas DOM untuk contoh garis di legenda/popup.
 *
 * Sengaja BUKAN `route-line`: kelas itu sudah dipakai signature halaman login
 * (`.brand-route .route-line` di app/globals.css, dikunci `tests/login.test.tsx`).
 * Prefiks `ship-route` menghindari tabrakan gaya antar dua hal yang berbeda.
 */
export function routeLineClass(row: SupplierRoute): string {
  return `ship-route ship-route-${routeLineTone(row)}`;
}

/** Kalimat sakelar layer di panel peta. */
export function routeToggleLabel(routes: readonly SupplierRoute[], show: boolean): string {
  return `${show ? "Sembunyikan" : "Tampilkan"} jalur kiriman (${routes.length})`;
}

/** Label pendek: \"Supplier A Cianjur → Jakarta · 110,4 km jalan · 800 kg telur\". */
export function routeLabel(row: SupplierRoute): string {
  const parts = [
    `${row.supplierName} → ${row.destinationName}`,
    row.road ? `${roadKmLabel(row.road.distanceKm)} jalan` : null,
    row.quantityKg !== null ? `${formatKg(row.quantityKg)} ${row.commodity ?? ""}`.trim() : row.commodity,
  ].filter((part): part is string => Boolean(part));
  return parts.join(" · ");
}

/** Baris rincian untuk popup/aria: jarak jalan vs lurus, durasi, sumber, masa layak. */
export function routePopupLines(row: SupplierRoute): string[] {
  const lines: string[] = [];
  if (row.road) {
    lines.push(
      `Jalur jalan (${row.road.source.toUpperCase()}): ${roadKmLabel(row.road.distanceKm)} · ± ${Math.round(
        row.road.durationMin
      )} menit`
    );
  } else {
    const reason = row.missingReason ? MISSING_REASON_LABEL[row.missingReason] ?? row.missingReason : "belum disinkronkan";
    lines.push(`Jalur jalan: belum ada — ${reason}`);
  }
  lines.push(`Jarak lurus: ${roadKmLabel(row.straightKm)}`);
  if (row.road && row.road.ratioVsStraight !== null) {
    lines.push(
      `Jalur jalan ${row.road.ratioVsStraight.toFixed(2).replace(".", ",")}× jarak lurus (jalan berkelok, bukan garis lurus)`
    );
  }
  if (row.usableUntil) {
    lines.push(`Layak dipakai s/d ${formatDate(row.usableUntil)}`);
  }
  if (row.safetyStatus === "fail") {
    lines.push("Mutu kiriman: GAGAL UJI keamanan (dilaporkan apa adanya)");
  }
  return lines;
}

/**
 * GeoJSON untuk layer peta. HANYA kiriman yang punya geometri jalan.
 */
export function routeGeoJson(raw: unknown): RouteFeatureCollection {
  const features: RouteFeature[] = [];
  for (const row of supplierRoutes(raw)) {
    if (!row.road) continue;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: row.road.coordinates },
      properties: {
        id: row.id,
        tone: routeLineTone(row),
        label: routeLabel(row),
        supplierName: row.supplierName,
        destinationName: row.destinationName,
        commodity: row.commodity,
        quantityKg: row.quantityKg,
        roadKm: row.road.distanceKm,
        durationMin: row.road.durationMin,
        safetyStatus: row.safetyStatus,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

/**
 * Titik-titik untuk menentukan batas peta (fitBounds).
 *
 * Termasuk kedua ujung SETIAP kiriman — bahkan yang rutenya belum tersinkron —
 * supaya pengguna melihat dari mana kiriman itu datang; kalau hanya geometri
 * jalan yang dipakai, kiriman yang belum disinkronkan akan tampak seolah tidak
 * ada di peta.
 */
export function routeBoundsPoints(raw: unknown): [number, number][] {
  const points: [number, number][] = [];
  for (const row of supplierRoutes(raw)) {
    points.push([row.originLongitude, row.originLatitude]);
    points.push([row.destinationLongitude, row.destinationLatitude]);
  }
  return points;
}

export function routeLayerSummary(raw: unknown): RouteLayerSummary {
  const rows = supplierRoutes(raw);
  const withRoad = rows.filter((row) => row.road !== null).length;
  const missing = rows.length - withRoad;
  const label = missing
    ? `${rows.length} jalur kiriman · ${missing} belum disinkronkan`
    : `${rows.length} jalur kiriman · semua lewat jalur jalan`;
  return { routes: rows.length, withRoad, missing, label };
}

/** Entri legenda peta untuk layer jalur. */
export function routeLegendEntries(): { tone: RouteLineTone; label: string }[] {
  return [
    { tone: "ok", label: "Jalur kiriman (jalan)" },
    { tone: "fail", label: "Jalur kiriman gagal uji" },
  ];
}


// --- Kolom "Jalur kirim" di tabel Pemasok (lanjutan Fase 10) ----------------
//
// Tabel Pemasok sudah punya kolom Jarak (jarak SPPG → pemasok, garis lurus) dan
// kolom Status (kiriman berjalan). Kolom ini menjawab pertanyaan ketiga yang
// muncul saat demo: "pemasok ini mengirim lewat JALUR mana, dan seberapa jauh
// jalannya?". Angkanya tetap dari server (`GET /supplier-routes`), bukan hitungan
// tabel; yang dihitung di sini hanya cara meringkasnya per pemasok.

export type SupplierRouteSummary = {
  /** Berapa jalur (kiriman aktif) pemasok ini. */
  count: number;
  /** Berapa di antaranya geometri jalannya sudah ada. */
  withRoad: number;
  /** Jalur terpendek yang punya geometri (fallback: baris pertama). */
  primary: SupplierRoute;
  /** Semua jalur, terpendek dulu; yang belum punya geometri di belakang. */
  ordered: SupplierRoute[];
};

/** Jalur tanpa geometri ditaruh paling belakang, bukan dianggap jarak 0. */
function urutanJarak(row: SupplierRoute): number {
  return row.road ? row.road.distanceKm : Number.POSITIVE_INFINITY;
}

/**
 * Kelompokkan jalur per PEMASOK (bukan per batch): satu pemasok bisa mengirim ke
 * beberapa tujuan sekaligus, dan tabel Pemasok hanya punya satu baris untuknya.
 */
export function supplierRouteSummaries(raw: unknown): Map<string, SupplierRouteSummary> {
  const peta = new Map<string, SupplierRouteSummary>();
  for (const row of supplierRoutes(raw)) {
    const ada = peta.get(row.supplierId);
    if (ada) {
      ada.count += 1;
      ada.withRoad += row.road ? 1 : 0;
      ada.ordered.push(row);
    } else {
      peta.set(row.supplierId, {
        count: 1,
        withRoad: row.road ? 1 : 0,
        primary: row,
        ordered: [row],
      });
    }
  }
  // `forEach` (bukan `for...of peta.values()`): target TS repo ini ES5, dan
  // iterasi Map langsung butuh `downlevelIteration`.
  peta.forEach((ringkas) => {
    ringkas.ordered.sort(
      (a: SupplierRoute, b: SupplierRoute) => urutanJarak(a) - urutanJarak(b)
    );
    ringkas.primary = ringkas.ordered[0];
  });
  return peta;
}

function alasanJalur(row: SupplierRoute): string {
  const label = row.missingReason ? MISSING_REASON_LABEL[row.missingReason] : undefined;
  return label ?? "jalur belum tersedia";
}

/**
 * Kalimat sel tabel. `null` = pemasok tanpa kiriman aktif (bukan berarti 0 km).
 * Jarak lurus TIDAK ditulis di sini — itu sudah ada di kolom Jarak, dan
 * mencampur keduanya membuat kolom ini terbaca seperti hitungan ganda.
 */
export function routeCellLabel(ringkas: SupplierRouteSummary | null | undefined): string {
  if (!ringkas || ringkas.count === 0) return "—";
  const utama = ringkas.primary;
  if (!utama.road) {
    // Penyebabnya dibedakan: "belum disinkronkan" hanya benar untuk alasan itu.
    return utama.missingReason === "belum_disinkron" ? "belum disinkronkan" : "jalur tidak tersedia";
  }
  const dasar = `→ ${utama.destinationName} · ${roadKmLabel(utama.road.distanceKm)} jalan`;
  const lain = ringkas.count - 1;
  return lain > 0 ? `${dasar} · +${lain} tujuan` : dasar;
}

/** Daftar lengkap tujuan jalur pemasok ini (untuk atribut `title` sel). */
export function routeCellTitle(ringkas: SupplierRouteSummary | null | undefined): string | null {
  if (!ringkas || ringkas.count === 0) return null;
  const bagian = ringkas.ordered.map((row) =>
    row.road
      ? `${row.destinationName} ${roadKmLabel(row.road.distanceKm)}`
      : `${row.destinationName} — ${alasanJalur(row)}`
  );
  // Sufiks "jarak jalan dari OSRM" hanya masuk akal kalau memang ada jalurnya.
  const sumber = ringkas.withRoad > 0 ? " (jarak jalan dari OSRM)" : "";
  return `${bagian.join(" · ")}${sumber}`;
}
