// Halaman "Pemasok" — daftar + kepercayaan + eksklusi.
//
// Sumber daftar (Fase 3, 2026-10-14): `GET /suppliers` — endpoint daftar pemasok
// yang BARU ada di Fase 2. Sebelumnya halaman ini menyusun daftarnya dari
// pemasok yang kebetulan muncul pada sampel keputusan terakhir (dan menuliskan
// keterbatasan itu di layar) karena backend belum punya endpoint daftar.
//
// Aturan tampilan:
// - Nilai yang tidak ada ditulis "—" (bukan 0, bukan string kosong).
// - Enum internal ('none'/'hygiene'/'haccp') TIDAK pernah tampil; labelnya dari
//   `certificationLabel` di lib/supplier-pins.ts supaya tidak ada dua kamus.
// - Urutan = risiko dulu: dikecualikan → skor terendah → terbaik → tanpa skor.

import { formatClockWib, formatDate } from "./datetime";
import {
  LOW_RELIABILITY,
  certificationLabel,
  distanceLabel as formatDistance,
  distanceReachLabel,
  shippingLabel,
  supplierShipping,
  withinReachKm,
  type SupplierShipping,
} from "./supplier-pins";

const DASH = "—";

export type SupplierDirectoryRow = {
  id: string;
  name: string;
  hub: string;
  commodity: string;
  reliability: number | null;
  reliabilityLabel: string;
  /** Bar mini kolom Keandalan (Fase 5); null = tanpa bar, dan labelnya "—". */
  reliabilityMeter: ReliabilityMeter | null;
  certification: string;
  coordinates: string;
  /** Jarak dari rujukan server (`distance_reference`), atau null bila tidak ada rujukan. */
  distanceKm: number | null;
  distanceLabel: string;
  excluded: boolean;
  excludedScopes: string[];
  /** Kiriman yang sedang berjalan (dari server), atau null bila tidak ada. */
  shipping: SupplierShipping | null;
  /** Kalimat status kiriman; "—" bila tidak sedang mengirim. */
  shippingLabel: string;
};

export function reliabilityLabel(score: unknown): string {
  if (score === null || score === undefined || score === "") return DASH;
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return DASH;
  return `${Math.round(numeric * 100)}%`;
}

export type ReliabilityMeter = { pct: number; tone: "ok" | "warn" | "danger" };

/**
 * Lebar bar mini kolom Keandalan (0–100) + nadanya — Fase 5 redesign.
 *
 * Ambangnya MEMAKAI `LOW_RELIABILITY` yang sudah dipakai halaman ini, bukan
 * angka baru: >= 0,80 "ok", >= 0,60 (LOW_RELIABILITY) "warn", di bawah itu
 * "danger" (kelas yang di ringkasan sudah disebut "keandalan rendah").
 * Skor yang tidak ada → null: kolomnya tetap "—" TANPA bar, karena bar kosong
 * terbaca "keandalan 0%" — dua hal yang berbeda. Skor di luar 0..1 dijepit agar
 * bar tidak melewati jalurnya; angkanya sendiri tetap ditulis apa adanya.
 */
export function reliabilityMeter(score: unknown): ReliabilityMeter | null {
  if (score === null || score === undefined || score === "") return null;
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return null;
  const pct = Math.min(100, Math.max(0, Math.round(numeric * 100)));
  const tone: ReliabilityMeter["tone"] =
    numeric >= 0.8 ? "ok" : numeric >= LOW_RELIABILITY ? "warn" : "danger";
  return { pct, tone };
}

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

/** Koordinat 4 desimal dengan pemisah desimal koma (gaya id-ID), tanpa ICU. */
function coordinate(value: number): string {
  return value.toFixed(4).replace(".", ",");
}

function coordinatesLabel(latitude: number | null, longitude: number | null): string {
  if (latitude === null || longitude === null) return DASH;
  return `${coordinate(latitude)} / ${coordinate(longitude)}`;
}

/**
 * Baris tabel daftar pemasok dari payload `GET /suppliers`
 * (amplop `{items: [...]}` atau array langsung).
 */
export function supplierDirectory(raw: unknown): SupplierDirectoryRow[] {
  const list = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as { items?: unknown } | null)?.items)
      ? ((raw as { items: unknown[] }).items as unknown[])
      : [];
  const rows: SupplierDirectoryRow[] = [];
  for (const item of list) {
    const record = (item ?? {}) as Record<string, unknown>;
    const name = text(record.name);
    if (!name) continue;
    const reliability = number(record.reliability_score);
    const latitude = number(record.latitude);
    const longitude = number(record.longitude);
    const scopes = Array.isArray(record.excluded_scope_locations)
      ? record.excluded_scope_locations
          .map((s) => text(s))
          .filter((s): s is string => Boolean(s))
      : [];
    const distanceKm = number(record.distance_km);
    const shipping = supplierShipping(record.shipping);
    rows.push({
      id: text(record.id) ?? name,
      name,
      hub: text(record.location) ?? DASH,
      commodity: text(record.commodity) ?? DASH,
      reliability,
      reliabilityLabel: reliabilityLabel(reliability),
      reliabilityMeter: reliabilityMeter(reliability),
      certification: certificationLabel(text(record.certification_status)),
      coordinates: coordinatesLabel(latitude, longitude),
      distanceKm,
      distanceLabel: formatDistance(distanceKm),
      excluded: record.excluded_at_hub === true || scopes.includes(text(record.location) ?? ""),
      excludedScopes: scopes,
      shipping,
      shippingLabel: shippingLabel(shipping),
    });
  }
  return rows.sort(compareByRisk);
}

/**
 * Baris kedua sel "Pemasok": hub · koordinat (Fase 12c, 16 Okt 2026).
 *
 * Dua kolom terpisah ("Hub" dan "Koordinat") memakan 178 px dari 913 px tabel
 * sehingga sembilan kolom berdesakan dan setiap sel membungkus 3–4 baris
 * (terukur: tinggi baris 74 px, tabel 1025 px di dalam wadah 913 px → wajib
 * digeser ke samping). Sebagai baris sekunder di bawah NAMA, keduanya tetap
 * terbaca penuh dan kolomnya bisa bernapas. Bagian yang tidak ada TIDAK ditulis
 * "—": "Cianjur · —" terbaca seperti data rusak.
 */
export function supplierMetaLine(row: SupplierDirectoryRow): string {
  const bagian = [row.hub !== DASH ? row.hub : null, row.coordinates !== DASH ? row.coordinates : null];
  const ada = bagian.filter((item): item is string => Boolean(item));
  return ada.length ? ada.join(" · ") : DASH;
}

/** Risiko dulu: dikecualikan → skor terendah → terbaik → tanpa skor → nama. */
function compareByRisk(a: SupplierDirectoryRow, b: SupplierDirectoryRow): number {
  if (a.excluded !== b.excluded) return a.excluded ? -1 : 1;
  const unknownRank = (row: SupplierDirectoryRow) => (row.reliability === null ? 1 : 0);
  const byRank = unknownRank(a) - unknownRank(b);
  if (byRank !== 0) return byRank;
  if (a.reliability !== null && b.reliability !== null && a.reliability !== b.reliability) {
    return a.reliability - b.reliability;
  }
  return a.name.localeCompare(b.name);
}

export type DirectoryMetrics = {
  suppliers: number;
  avgReliability: number | null;
  avgReliabilityLabel: string;
  lowReliability: number;
  excluded: number;
  withCoordinates: number;
  /** Jumlah pemasok di luar jangkauan (0 bila tidak ada ambang / jarak tak diketahui). */
  outOfReach: number;
  /** Jumlah pemasok yang jaraknya tidak dilaporkan server. */
  unknownDistance: number;
  /** Berapa pemasok yang sedang mengirim barang hari ini. */
  shipping: number;
};

export function directoryMetrics(
  rows: unknown,
  reachKm?: number | null
): DirectoryMetrics {
  const list = Array.isArray(rows) ? (rows as SupplierDirectoryRow[]) : [];
  const scores = list
    .map((row) => row.reliability)
    .filter((score): score is number => typeof score === "number" && Number.isFinite(score));
  const avg = scores.length
    ? scores.reduce((total, score) => total + score, 0) / scores.length
    : null;
  const known = list.filter(
    (row) => typeof row.distanceKm === "number" && Number.isFinite(row.distanceKm)
  );
  return {
    suppliers: list.length,
    avgReliability: avg,
    avgReliabilityLabel: avg === null ? DASH : reliabilityLabel(avg),
    lowReliability: scores.filter((score) => score < LOW_RELIABILITY).length,
    excluded: list.filter((row) => row.excluded).length,
    withCoordinates: list.filter((row) => row.coordinates !== DASH).length,
    outOfReach:
      reachKm === null || reachKm === undefined
        ? 0
        : known.filter((row) => !withinReachKm(row.distanceKm, reachKm)).length,
    unknownDistance: list.length - known.length,
    shipping: list.filter((row) => row.shipping !== null).length,
  };
}

/**
 * Saring daftar pemasok berdasarkan jangkauan (Fase 7b).
 *
 * `reachKm` null/undefined = daftar apa adanya (perilaku lama, dan perilaku
 * `bgn_monitor`). Baris tanpa jarak TIDAK ikut saat penyaringan aktif: tidak bisa
 * dibuktikan dekat, jadi tidak diklaim dekat — sama dengan aturan di peta dan di
 * endpoint `GET /suppliers?max_distance_km=`.
 */
export function filterDirectoryByReach(
  rows: readonly SupplierDirectoryRow[],
  reachKm?: number | null
): SupplierDirectoryRow[] {
  if (reachKm === null || reachKm === undefined || !Number.isFinite(reachKm)) {
    return [...rows];
  }
  return rows.filter((row) => withinReachKm(row.distanceKm, reachKm));
}

/** Nada baris tabel untuk kolom jarak: dalam / luar jangkauan / tidak diketahui. */
export function directoryReachLabel(
  row: SupplierDirectoryRow,
  reachKm?: number | null
): string {
  return distanceReachLabel(row.distanceKm, reachKm);
}

/**
 * Label RINGKAS pil jangkauan di sel Status tabel Pemasok (Fase 12c, 16 Okt 2026).
 *
 * Jarak km sudah tertulis di kolom Jarak — persis di sebelah sel Status — jadi pil
 * cukup menyebut KEADAANNYA. Mengulang angka itu di dalam pil membuat pilnya
 * 171 px dan mendorong tabel 7 kolom meluap dari wadahnya (terukur 960 px di dalam
 * 913 px). Kalimat penuhnya tetap dipakai sebagai `title`. Kasus "jarak tidak
 * diketahui" TIDAK disamarkan menjadi "di luar jangkauan": dua keadaan berbeda,
 * sama seperti aturan `distanceReachLabel`.
 */
export function directoryReachTagLabel(
  row: SupplierDirectoryRow,
  reachKm?: number | null
): string {
  if (row.distanceKm === null || !Number.isFinite(row.distanceKm)) return "jarak tidak diketahui";
  return withinReachKm(row.distanceKm, reachKm) ? "dalam jangkauan" : "di luar jangkauan";
}

/** Ringkasan jujur di atas tabel: berapa yang tampil dari berapa, dari rujukan mana. */
export function directoryReachSummary(
  rows: readonly SupplierDirectoryRow[],
  reachKm?: number | null,
  reference?: string | null
): string {
  if (reachKm === null || reachKm === undefined || !Number.isFinite(reachKm)) {
    const unknown = rows.filter((row) => row.distanceKm === null).length;
    const ekor = unknown > 0 ? ` · ${unknown} tanpa jarak` : "";
    return `${rows.length} pemasok ditampilkan (semua, tanpa ambang jarak)${ekor}`;
  }
  const within = rows.filter((row) => withinReachKm(row.distanceKm, reachKm)).length;
  const dari = reference ? ` dari ${reference}` : "";
  return `${within} dari ${rows.length} pemasok dalam jangkauan ${reachKm} km${dari}`;
}

export type ExclusionRow = {
  id: string;
  supplier: string;
  reason: string;
  at: string;
  decisionId: string;
  status: string;
};

export function exclusionRows(items: unknown): ExclusionRow[] {
  const list = Array.isArray(items) ? items : [];
  return list.map((item) => {
    const record = (item ?? {}) as Record<string, unknown>;
    const supplier =
      text(record.supplier_name) ??
      text((record.supplier as { name?: unknown } | undefined)?.name) ??
      text(record.supplier) ??
      DASH;
    // Waktu ditulis dalam WIB dan tanpa mikrodetik (audit 26 Okt 2026): dulu
    // string ISO mentah dari `created_at` tampil apa adanya
    // ("2026-10-25T20:43:30.217503+00:00") — satu-satunya tempat di UI yang
    // memakai UTC mentah, sementara kolom waktu lain memakai "26 Okt 03.43".
    const waktu = text(record.excluded_at) ?? text(record.created_at) ?? null;
    return {
      id: text(record.id) ?? DASH,
      supplier,
      reason: text(record.reason) ?? DASH,
      at: waktu ? `${formatDate(waktu)} ${formatClockWib(waktu)}` : DASH,
      // Endpoint mengirim `source_decision_id`; `decision_id` hanya ada di
      // fixture tes lama, jadi dibaca sebagai cadangan.
      decisionId:
        text(record.source_decision_id) ?? text(record.decision_id) ?? DASH,
      status: text(record.status) ?? "excluded",
    };
  });
}

/** Label status satu entri register eksklusi (audit 26 Okt 2026).
 *
 * Sebelumnya tabel tidak punya kolom status, sehingga "Pemasok dieksklusi: 2"
 * terbaca seolah dua pemasok sedang dikecualikan — padahal satu `active` dan
 * satu masih `proposed` (menunggu keputusan manusia).
 */
export function exclusionStatusLabel(status: string | null | undefined): string {
  switch ((status ?? "").toLowerCase()) {
    case "active":
      return "Aktif";
    case "proposed":
      return "Menunggu keputusan";
    case "rejected":
      return "Usulan ditolak";
    case "revoked":
      return "Dicabut";
    default:
      return "—";
  }
}

/** Hitung entri register per status — dipakai ringkasan "aktif · menunggu". */
export function exclusionCounts(items: unknown): { active: number; proposed: number; total: number } {
  const rows = exclusionRows(items);
  return {
    active: rows.filter((row) => row.status.toLowerCase() === "active").length,
    proposed: rows.filter((row) => row.status.toLowerCase() === "proposed").length,
    total: rows.length,
  };
}
