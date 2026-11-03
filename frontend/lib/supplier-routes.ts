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
// - Jarak jalan (OSRM) yang ditulis di popup; jarak lurus & rasionya TIDAK lagi
//   dipampang (arah pemilik 2026-10-16) — pembaca peta membaca rute yang tergambar,
//   dan angka haversine 1,41× hanya memancing "kok beda?" tanpa mengubah keputusan.
//   Angkanya tetap ada di payload/kolom tabel lain kalau perlu diaudit.
// - Warna garis mengikuti MUTU kiriman (fail = nada bahaya). Cincin "sedang
//   mengirim" di pin tetap terpisah, jadi dua fakta berbeda tidak saling
//   menutupi (keputusan Fase 9).
// - Alasan rute tidak ada ditulis apa adanya (`MISSING_REASON_LABEL`), bukan
//   disembunyikan jadi "—".

import { formatClockWib, formatDate, formatDateTime } from "./datetime";
import { journeyLineParts } from "./route-line-split";
import { formatKg } from "./overview-format";

export type RouteLineTone = "ok" | "fail";

/** Keadaan perjalanan kiriman — kosakata SAMA dengan server (app/core/journey.py). */
export type RouteJourneyState =
  | "belum_berangkat"
  | "di_jalan"
  | "sudah_tiba"
  | "tidak_diketahui";

/** Nada visual perjalanan (kelas CSS), bukan klaim keadaan baru. */
export type RouteJourneyTone = "moving" | "done" | "pending" | "unknown";

export type RouteJourney = {
  dispatchedAt: string | null;
  etaAt: string | null;
  state: RouteJourneyState;
  stateLabel: string;
  travelMin: number | null;
  elapsedMin: number | null;
  remainingMin: number | null;
  progress: number | null;
  usableUntil: string | null;
  arrivesBeforeUsableUntil: boolean | null;
};

/**
 * Warna garis untuk `paint` MapLibre.
 *
 * WebGL tidak bisa membaca CSS custom property, jadi nilainya literal — dan HARUS
 * sama dengan token di `app/globals.css` (`--status-safe` / `--status-danger`).
 * Kesamaan itu dikunci tes yang membaca berkas CSS-nya, supaya tidak ada dua
 * definisi warna yang bisa menyimpang tanpa ketahuan.
 */
export const ROUTE_LINE_COLORS: Record<RouteLineTone, string> = {
  // Bagian yang SUDAH ditempuh memakai biru-600 (--route-live-strong).
  // Sisa perjalanan memakai biru lebih terang (--route-live-soft) di
  // ROUTE_TODO_COLORS, jadi dua bagian satu kiriman tetap satu keluarga warna
  // tetapi bisa dibedakan lewat pola garis. Nilai ini WAJIB sama dengan
  // --route-live-strong; tes supplier-routes mengunci pasangan CSS ↔ konstanta.
  ok: "#2563EB",
  fail: "#C62828",
};



/**
 * Warna untuk potongan yang BELUM ditempuh (masih perkiraan).
 *
 * Bukan hijau yang sama dengan bagian yang sudah ditempuh: kalau warnanya sama,
 * mata membaca "dua garis hijau" dan pengguna tidak bisa tahu mana yang fakta
 * terkirim dan mana yang estimasi. Dipakai warna AKSI aplikasi
 * (`--accent-strong` #2563EB, tombol/tautan) — biru juga konvensi peta untuk
 * "rute berjalan", dan ia tidak menabrak merah (gagal uji) maupun hijau (tiba).
 */
export const ROUTE_TODO_COLORS: Record<RouteLineTone, string> = {
  // Sisa perjalanan = biru-700 (--route-live-soft): satu kiriman tetap satu
  // keluarga warna, dibedakan dari bagian yang sudah ditempuh lewat pola
  // putus-putus.
  ok: "#1D4ED8",
  fail: "#C62828",
};

/** Nada legenda jalur: nada garis + satu nada tampilan untuk "sisa perjalanan". */
/**
 * Nada legenda garis.
 *
 * Tanpa nada "menyala" lagi (redesign 20 Okt 2026): garis kiriman berjalan tidak
 * memakai warna kelima — penekanannya halo sewarna, dan penanda bergeraknya
 * ikon mobil. Legenda yang menyebut warna yang tidak ada hanya menambah beban.
 */
export type RouteLegendTone = RouteLineTone | "sisa" | "tiba";

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
  routeKey: string | null;
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
  harvestedAt: string | null;
  usableUntil: string | null;
  safetyStatus: string | null;
  straightKm: number | null;
  road: SupplierRouteRoad | null;
  missingReason: string | null;
  journey: RouteJourney | null;
};

/** Dua bagian garis jalur (K1). Dipakai sebagai filter layer di peta. */
export type RouteLineKind = "done" | "todo";

export type RouteFeature = {
  type: "Feature";
  /** Id unik per FITUR (`lajur#batch#kind`): satu kiriman = dua fitur. */
  id: string;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  properties: {
    id: string;
    /** Bagian garis (K1): `done` = sudah ditempuh (padat), `todo` = sisa (putus-putus). */
    kind: RouteLineKind;
    tone: RouteLineTone;
    label: string;
    supplierName: string;
    destinationName: string;
    commodity: string | null;
    quantityKg: number | null;
    roadKm: number;
    durationMin: number;
    safetyStatus: string | null;
    /**
     * `true` = kiriman yang sudah tiba: digambar redup tanpa animasi/ikon.
     * Dipakai filter layer peta supaya garis terang tetap berarti "bergerak".
     */
    quiet: boolean;
    /**
     * Keadaan perjalanan kiriman (`di_jalan`, `tiba`, …) atau `null` bila
     * server belum mengirim blok perjalanan. Peta memakainya untuk menyalakan
     * garis kiriman yang SEDANG berjalan — bukan untuk menyembunyikan yang lain.
     */
    state: string | null;
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

const JOURNEY_STATES: readonly RouteJourneyState[] = [
  "belum_berangkat",
  "di_jalan",
  "sudah_tiba",
  "tidak_diketahui",
];

/**
 * Blok `journey` dari server → bentuk yang dipakai UI.
 *
 * Dua aturan penting: keadaan diambil APA ADANYA (tidak diterjemahkan ulang di
 * klien, supaya peta dan server tidak bisa berbeda cerita), dan estimasi tiba
 * hanya ada kalau server memang mengirimnya — jam tiba tidak pernah dihitung di
 * peramban, karena peramban tidak tahu jam berangkat barang.
 */
function parseJourney(raw: unknown): RouteJourney | null {
  if (raw === null || raw === undefined || typeof raw !== "object") return null;
  const fields = raw as Record<string, unknown>;
  const state = text(fields.state);
  if (!state || !JOURNEY_STATES.includes(state as RouteJourneyState)) return null;
  return {
    dispatchedAt: text(fields.dispatched_at),
    etaAt: text(fields.eta_at),
    state: state as RouteJourneyState,
    stateLabel: text(fields.state_label) ?? state,
    travelMin: number(fields.travel_min),
    elapsedMin: number(fields.elapsed_min),
    remainingMin: number(fields.remaining_min),
    progress: number(fields.progress),
    usableUntil: text(fields.usable_until),
    arrivesBeforeUsableUntil:
      typeof fields.arrives_before_usable_until === "boolean"
        ? fields.arrives_before_usable_until
        : null,
  };
}

/** Nada visual keadaan perjalanan (kelas CSS `.map-journey-<nada>`). */
export function journeyTone(state: RouteJourneyState | null): RouteJourneyTone {
  switch (state) {
    case "di_jalan":
      return "moving";
    case "sudah_tiba":
      return "done";
    case "belum_berangkat":
      return "pending";
    default:
      return "unknown";
  }
}

/** Menit → "24 menit" / "2 jam 15 menit" (dipakai untuk sisa perjalanan). */
export function durationLabel(minutes: number | null): string {
  if (minutes === null || !Number.isFinite(minutes)) return "—";
  const total = Math.round(Math.abs(minutes));
  if (total < 60) return `${total} menit`;
  const jam = Math.floor(total / 60);
  const sisa = total % 60;
  return sisa === 0 ? `${jam} jam` : `${jam} jam ${sisa} menit`;
}

/**
 * Kalimat keadaan perjalanan satu kiriman (baris Info map).
 *
 * "Belum berangkat" TIDAK diberi jam tiba: jam itu tidak ada di DB, dan menulis
 * perkiraan di sana akan terbaca seolah barangnya sudah di jalan.
 */
export function routeJourneyLine(row: SupplierRoute, denganTujuan = true): string {
  const awal = denganTujuan ? `${row.destinationName} · ` : "";
  const journey = row.journey;
  if (!journey) return `${awal}perjalanan belum dilaporkan server`;
  if (journey.state === "di_jalan" && journey.etaAt) {
    const sisa = journey.remainingMin !== null ? ` (${durationLabel(journey.remainingMin)} lagi)` : "";
    return `${awal}di jalan · tiba ± ${formatClockWib(journey.etaAt)}${sisa}`;
  }
  if (journey.state === "sudah_tiba" && journey.etaAt) {
    return `${awal}sudah tiba ${formatClockWib(journey.etaAt)}`;
  }
  if (journey.state === "belum_berangkat") {
    return `${awal}belum berangkat · estimasi tiba belum ada`;
  }
  return `${awal}sudah berangkat · estimasi tiba belum ada`;
}

/** Kelas DOM baris perjalanan (nada dari keadaan, bukan warna bebas). */
export function routeJourneyRowClass(row: SupplierRoute): string {
  return `map-journey-item map-journey-${journeyTone(row.journey?.state ?? null)}`;
}

/**
 * Baris perjalanan untuk kotak "Info map".
 *
 * Dibatasi `maks` baris supaya kotaknya tetap kecil (arah pemilik 2026-10-16);
 * sisanya diringkas jadi "+N kiriman lain" — tidak dihapus diam-diam.
 */
export function routeJourneyRows(
  rows: readonly SupplierRoute[],
  maks = 3
): { teks: string; kelas: string }[] {
  const hasil = rows
    .filter((row) => row.journey !== null)
    .slice(0, maks)
    .map((row) => ({ teks: routeJourneyLine(row), kelas: routeJourneyRowClass(row) }));
  const sisa = rows.filter((row) => row.journey !== null).length - hasil.length;
  if (sisa > 0) {
    hasil.push({ teks: `+${sisa} kiriman lain`, kelas: "map-journey-item map-journey-more" });
  }
  return hasil;
}

/** Estimasi tiba paling awal di antara baris yang punya `eta_at`. */
export function nearestEta(rows: readonly SupplierRoute[]): string | null {
  let terdekat: string | null = null;
  for (const row of rows) {
    const eta = row.journey?.etaAt;
    if (!eta) continue;
    if (terdekat === null || eta < terdekat) terdekat = eta;
  }
  return terdekat;
}

/**
 * Baris tambahan popup garis: jam berangkat, estimasi tiba, dan batas layak.
 *
 * Semuanya dari server (`journey`), jadi peta dan halaman lain menyebut angka
 * yang sama; yang dihitung di klien hanya cara menuliskannya.
 */
export function routeEtaLines(row: SupplierRoute): string[] {
  const journey = row.journey;
  if (!journey) return [];
  // K4 (17 Okt 2026): jam berangkat + estimasi tiba digabung jadi SATU baris.
  // Popup terukur 240×176 px berisi 5 baris; dua di antaranya hanya jam, untuk
  // satu fakta yang sama ("kapan berangkat → kapan sampai"). Digabung, popup
  // tetap memuat semua fakta tanpa memangkas apa pun.
  const berangkat = journey.dispatchedAt
    ? `Berangkat ${formatDateTime(journey.dispatchedAt)}`
    : "Belum berangkat (barang masih di pemasok)";
  let tiba: string;
  if (journey.etaAt) {
    const sisa =
      journey.state === "di_jalan" && journey.remainingMin !== null
        ? ` · ${durationLabel(journey.remainingMin)} lagi`
        : "";
    tiba = `tiba ± ${formatClockWib(journey.etaAt)} WIB${sisa}`;
  } else if (journey.state === "tidak_diketahui") {
    tiba = "tiba belum ada — jalur jalan belum disinkronkan";
  } else {
    tiba = "tiba belum ada — barang belum berangkat";
  }
  const lines: string[] = [`${berangkat} → ${tiba}`];
  if (journey.travelMin !== null && journey.etaAt === null) {
    // Waktu tempuh hanya diulang di sini kalau tidak ada estimasi tiba: kalau ada,
    // baris jalur jalan di popup sudah menyebut durasinya (tidak dihitung ganda).
    lines.push(`Waktu tempuh jalur: ± ${durationLabel(journey.travelMin)} (OSRM)`);
  }
  if (journey.arrivesBeforeUsableUntil === false) {
    lines.push("Estimasi tiba melewati batas layak pakai (dilaporkan apa adanya)");
  }
  // Catatan: keadaan "tiba sebelum batas layak" sengaja TIDAK ditulis sebagai
  // kalimat (arah pemilik 2026-10-16: "Tiba sebelum batas layak (...) hapus saja").
  // Tanggalnya tetap terlihat sekali di baris "Layak dipakai s/d ..." — mengulangnya
  // sebagai kalimat penghibur hanya memanjangkan popup. Peringatan di atas tetap ada
  // karena itu menandai masalah nyata, bukan menenangkan pembaca.
  return lines;
}

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
    routeKey: text(fields.route_key),
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
    harvestedAt: text(fields.harvested_at),
    usableUntil: text(fields.usable_until),
    safetyStatus: text(fields.safety_status),
    straightKm: number(fields.straight_km),
    road: parseRoad(fields.road),
    missingReason: text(fields.road_missing_reason),
    journey: parseJourney(fields.journey),
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


/**
 * Kunci React untuk SATU baris kiriman.
 *
 * `id` sengaja per PASANGAN pemasok-tujuan (dipakai memilih/menyorot jalur),
 * sehingga dua batch dari pemasok yang sama ke SPPG yang sama berbagi id.
 * Kunci React harus per KIRIMAN: memakai `id` apa adanya memunculkan
 * "Encountered two children with the same key" dan satu baris bisa hilang
 * dari layar (kasus nyata: beras 900 kg + kiriman demo 800 kg, 18 Okt 2026).
 */
export function shipmentKey(row: Pick<SupplierRoute, "id" | "batchId">): string {
  return row.batchId ? `${row.id}#${row.batchId}` : row.id;
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

/** Label pendek: \"Supplier A Cianjur → Jakarta · 110,4 km jalan · 800 kg telur\". */
export function routeLabel(row: SupplierRoute): string {
  const parts = [
    `${row.supplierName} → ${row.destinationName}`,
    row.road ? `${roadKmLabel(row.road.distanceKm)} jalan` : null,
    row.quantityKg !== null ? `${formatKg(row.quantityKg)} ${row.commodity ?? ""}`.trim() : row.commodity,
  ].filter((part): part is string => Boolean(part));
  return parts.join(" · ");
}

/** Baris rincian untuk popup/aria: jalur jalan, durasi, perjalanan, masa layak. */
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
  // Perjalanan (jam berangkat + estimasi tiba) datang dari server, bukan dari
  // hitungan peramban — lihat `routeEtaLines`.
  lines.push(...routeEtaLines(row));
  // "Jarak lurus: 78,4 km" dan "Jalur jalan 1,41× jarak lurus (jalan berkelok, bukan
  // garis lurus)" DIHAPUS atas permintaan pemilik 2026-10-16. `row.straightKm` dan
  // `road.ratioVsStraight` tetap dikirim server (dipakai kolom/tabel lain) — hanya
  // tidak lagi dipampang di popup peta.
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
    // Sejak 21 Okt 2026 kiriman yang SUDAH TIBA juga digambar, tetapi redup
    // (permintaan pemilik: "dimasukkan ke peta juga tidak apa-apa"). Sebelumnya
    // peta hanya menampilkan yang sedang berjalan, sehingga sore hari tinggal
    // satu-dua garis dan terlihat seperti data hilang.
    //
    // Tetap dibedakan supaya arti "garis terang = ada yang bergerak" tidak
    // rusak: kiriman yang sudah tiba menghasilkan SATU fitur utuh dengan
    // `quiet: true` (tanpa animasi, tanpa ikon mobil), sedangkan yang berjalan
    // tetap dipecah "done" + "todo" dan mendapat ikon.
    const berjalan = row.journey?.state === "di_jalan";
    if (row.journey === null) continue;
    if (!berjalan && row.journey.state !== "sudah_tiba") continue;
    const bagian = berjalan
      ? journeyLineParts(row.road.coordinates, row.journey)
      : { done: row.road.coordinates, todo: [] as [number, number][] };
    if (!bagian) continue;
    const kunci = shipmentKey(row);
    const properti = {
      // Id per KIRIMAN (`lajur#batch`), bukan per lajur: dua batch di lajur yang
      // sama (dua kiriman telur sehari) tadinya berbagi id sehingga klik/popup
      // dan sorotan menunjuk kiriman yang salah (audit 22 Okt 2026).
      id: kunci,
      tone: routeLineTone(row),
      label: routeLabel(row),
      supplierName: row.supplierName,
      destinationName: row.destinationName,
      commodity: row.commodity,
      quantityKg: row.quantityKg,
      roadKm: row.road.distanceKm,
      durationMin: row.road.durationMin,
      safetyStatus: row.safetyStatus,
      state: row.journey?.state ?? null,
      quiet: !berjalan,
    };
    // Satu kiriman bisa menyumbang DUA fitur (ditempuh + sisa). Geometri < 2 titik
    // tidak digambar — bagian kosong dilewati, bukan dibuat jadi garis nol panjang.
    for (const [kind, coords] of [
      ["done", bagian.done],
      ["todo", bagian.todo],
    ] as const) {
      if (coords.length < 2) continue;
      features.push({
        type: "Feature",
        // Id tingkat-FITUR harus unik: satu kiriman menghasilkan dua fitur
        // (ditempuh + sisa) dan MapLibre memakai id ini untuk feature-state.
        id: `${kunci}#${kind}`,
        geometry: { type: "LineString", coordinates: coords },
        properties: { ...properti, kind },
      });
    }
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

/**
 * Tag SANGAT pendek untuk bilah rincian lapisan: jumlah jalur + keadaan
 * perjalanannya (arah pemilik 2026-10-16: saat jalur kiriman dinyalakan, waktu
 * estimasi sampai ikut terlihat tanpa perlu membuka apa pun).
 *
 * Estimasi tiba yang ditulis di sini datang dari server (`journey.eta_at`);
 * kalau belum ada kiriman yang berjalan, tag menyebut asal geometrinya seperti
 * sebelumnya — bukan mengarang jam.
 */
export function routeLayerTag(
  summary: RouteLayerSummary,
  rows: readonly SupplierRoute[] = []
): string {
  if (rows.length === 0) return "belum ada jalur kiriman";
  const diJalan = rows.filter((row) => row.journey?.state === "di_jalan");
  // Peta hanya menggambar jalur yang SEDANG berjalan (keputusan pemilik
  // 20 Okt 2026). Kalau tidak ada, tag tidak boleh mengklaim "N jalur" —
  // angka itu akan membuat orang mencari garis yang memang tidak ada.
  const tiba = rows.filter((row) => row.journey?.state === "sudah_tiba");
  if (diJalan.length === 0) {
    return tiba.length > 0 ? `${tiba.length} kiriman sudah tiba` : "tidak ada kiriman berjalan";
  }
  const bagian = [`${diJalan.length} kiriman berjalan`];
  const terdekat = nearestEta(diJalan);
  if (terdekat) bagian.push(`tiba terdekat ± ${formatClockWib(terdekat)}`);
  else if (summary.missing) bagian.push(`${summary.missing} belum disinkronkan`);
  if (tiba.length > 0) bagian.push(`${tiba.length} sudah tiba`);
  return bagian.join(" · ");
}

/**
 * Entri legenda peta untuk layer jalur.
 *
 * Entri "gagal uji" hanya ditulis bila ADA kiriman bergaris seperti itu —
 * legenda yang menyebut warna yang tidak dipakai membuat pembaca mencari-cari
 * sesuatu yang tidak ada di peta.
 */
export function routeLegendEntries(
  rows: readonly SupplierRoute[] = []
): { tone: RouteLegendTone; label: string; gaya: "padat" | "putus" }[] {
  // K1 (7b-3): legenda tidak lagi menulis "Jalur kiriman (jalan)" untuk semua
  // garis. Satu arti: padat = sudah ditempuh, putus-putus = sisa atau perkiraan.
  // Sebelum ini legenda menulis "Sisa perjalanan" putus-putus sementara LAYER
  // menggambar semua kiriman putus-putus — termasuk yang sudah tiba.
  // Nada "sisa" = warna amber di legenda, SAMA dengan warna layer `todo` di peta;
  // legenda yang memakai hijau untuk estimasi akan menyesatkan.
  // Sejak 20 Okt 2026 lapisan dasar hanya menggambar kiriman yang sedang
  // berjalan, jadi legenda pun hanya boleh menyebut nada dari baris itu.
  const bergerak = rows.filter((row) => row.journey?.state === "di_jalan");
  const entries: { tone: RouteLegendTone; label: string; gaya: "padat" | "putus" }[] = [];
  if (bergerak.length > 0) {
    entries.push(
      { tone: "ok", label: "Sudah ditempuh", gaya: "padat" },
      { tone: "sisa", label: "Sisa perjalanan (perkiraan)", gaya: "putus" }
    );
  }
  const tibaEntries = rows.filter((row) => row.journey?.state === "sudah_tiba");
  if (tibaEntries.length > 0) {
    // Nada "tiba": kanvas menggambar kiriman yang sudah tiba dengan SLATE
    // #475569 (--route-arrived), bukan violet. Dulu entri ini memakai "ok"
    // sehingga legenda menjanjikan violet untuk garis yang tampak abu-abu.
    // Gaya legenda harus sama dengan kanvas: jalur yang sudah tiba digambar
    // putus-putus tipis, jadi legenda menyebut "putus" — bukan "padat".
    entries.push({ tone: "tiba", label: "Sudah tiba (redup)", gaya: "putus" });
  }
  if (bergerak.some((row) => routeLineTone(row) === "fail")) {
    entries.push({ tone: "fail", label: "Jalur kiriman gagal uji", gaya: "putus" });
  }
  return entries;
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
 * Sejak Fase 12c kata "jalan" juga tidak diulang: nama kolomnya sudah
 * "Jalur kirim", dan asalnya (OSRM = jarak jalan) tetap tertulis di atribut
 * `title` sel — menghapusnya memberi 35 px untuk kolom Status sehingga pil
 * status tidak lagi terpaksa membungkus ke baris kedua.
 */
export function routeCellLabel(ringkas: SupplierRouteSummary | null | undefined): string {
  if (!ringkas || ringkas.count === 0) return "—";
  const utama = ringkas.primary;
  if (!utama.road) {
    // Penyebabnya dibedakan: "belum disinkronkan" hanya benar untuk alasan itu.
    return utama.missingReason === "belum_disinkron" ? "belum disinkronkan" : "jalur tidak tersedia";
  }
  const dasar = `→ ${utama.destinationName} · ${roadKmLabel(utama.road.distanceKm)}`;
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
