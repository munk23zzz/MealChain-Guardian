// Logika modul "Location Network" (dokumen 03 §3, §6.3, 6.5 — 28 Okt 2026).
//
// Semua angka di sini DIBACA dari server (`GET /balance/map`), tidak dihitung
// ulang: backend sudah menjalankan `app/core/gaps.py` untuk surplus/shortage.
// Yang dikerjakan berkas ini hanya hal yang memang tidak dikirim server:
//   - hitungan lokasi per status + total kekurangan/kelebihan (penjumlahan),
//   - satu kalimat yang menyebut selisih keduanya (§6.3),
//   - kelengkapan data tingkat jaringan (§6.5): tanpa catatan & catatan basi,
//   - pengelompokan per wilayah + urutan keparahan.
//
// Koridor sumber→tujuan (§6.2) DIHAPUS 28 Okt 2026 bersama peta: pemilik memilih
// halaman gabungan tanpa peta. Jangan menambahkannya kembali tanpa keputusan baru.
//
// Invarian: angka yang tidak terbaca = `null` dan ditampilkan "—", TIDAK PERNAH
// jatuh menjadi 0. Nol hanya dipakai bila server benar-benar melaporkan nol.

import {
  BALANCE_STATUSES,
  formatKg,
  isBalanceStatus,
  tanpaCatatan,
  type BalanceMapLocation,
  type BalanceStatus,
} from "./overview-format";
import { hoursLeft } from "./food-safety";

export { BALANCE_STATUSES };

// ─────────────────────────────────────────────────────────────────────────────
// Ringkasan jaringan
// ─────────────────────────────────────────────────────────────────────────────

export type NetworkSummary = {
  total: number;
  unmapped: number;
  tally: Record<BalanceStatus, number>;
  /** `null` = ada lokasi shortage yang angkanya tidak terbaca. */
  shortageKg: number | null;
  surplusKg: number | null;
  supplyKg: number | null;
  demandKg: number | null;
};

function toNumber(raw: number | string | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === "string" && !raw.trim()) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export function networkSummary(
  locations: readonly BalanceMapLocation[],
): NetworkSummary {
  const tally: Record<BalanceStatus, number> = {
    shortage: 0,
    surplus: 0,
    balanced: 0,
  };
  let unmapped = 0;
  let shortageKg: number | null = 0;
  let surplusKg: number | null = 0;

  for (const location of locations) {
    if (isBalanceStatus(location.status)) tally[location.status] += 1;
    if (!hasCoordinates(location)) unmapped += 1;

    if (location.status === "shortage") {
      const value = toNumber(location.shortage_kg);
      shortageKg = shortageKg === null || value === null ? null : shortageKg + value;
    }
    if (location.status === "surplus") {
      const value = toNumber(location.surplus_kg);
      surplusKg = surplusKg === null || value === null ? null : surplusKg + value;
    }
  }

  return {
    total: locations.length,
    unmapped,
    tally,
    shortageKg,
    surplusKg,
    supplyKg: sumFinite(locations.map((l) => l.supply_kg)),
    demandKg: sumFinite(locations.map((l) => l.demand_kg)),
  };
}

/** Jumlahkan hanya nilai yang terbaca; semua tak terbaca → `null` (bukan 0). */
function sumFinite(raw: readonly (number | string | null | undefined)[]): number | null {
  let total = 0;
  let ada = false;
  for (const item of raw) {
    const value = toNumber(item);
    if (value === null) continue;
    total += value;
    ada = true;
  }
  return ada ? total : null;
}

// ─────────────────────────────────────────────────────────────────────────────
// §6.3 — satu kalimat yang menjawab "jadi bagaimana?"
// ─────────────────────────────────────────────────────────────────────────────

export type HeadlineTone = "danger" | "safe" | "neutral" | "unknown";
export type NetworkHeadline = { text: string; tone: HeadlineTone };

export function networkHeadline(
  locations: readonly BalanceMapLocation[],
): NetworkHeadline {
  const { tally, shortageKg, surplusKg } = networkSummary(locations);

  if (locations.length === 0) {
    // Tidak ada baris BUKAN berarti "tidak ada kekurangan". Kalimat kabar baik
    // untuk data yang belum masuk adalah angka karangan.
    return {
      text: "Belum ada lokasi yang bisa dibaca untuk komoditas ini; datanya belum masuk.",
      tone: "unknown",
    };
  }

  if (tally.shortage === 0 && tally.surplus === 0) {
    return {
      text: "Tidak ada lokasi kekurangan maupun kelebihan yang terlaporkan untuk komoditas ini.",
      tone: "neutral",
    };
  }

  if (tally.shortage === 0) {
    return surplusKg === null
      ? {
          text: `Tidak ada lokasi kekurangan; ${tally.surplus} lokasi surplus melaporkan kelebihan yang belum terbaca.`,
          tone: "unknown",
        }
      : {
          text: `Tidak ada lokasi kekurangan; kelebihan ${tally.surplus} lokasi (${formatKg(surplusKg)}) bisa dialokasikan.`,
          tone: "safe",
        };
  }

  if (tally.surplus === 0) {
    return shortageKg === null
      ? {
          text: `${tally.shortage} lokasi kekurangan dengan angka yang belum terbaca; belum ada lokasi surplus yang bisa menutup.`,
          tone: "unknown",
        }
      : {
          text: `${tally.shortage} lokasi kekurangan ${formatKg(shortageKg)}; belum ada lokasi surplus yang bisa menutup.`,
          tone: "danger",
        };
  }

  if (shortageKg === null || surplusKg === null) {
    return {
      text: `${tally.shortage} lokasi kekurangan dan ${tally.surplus} lokasi surplus; sebagian angkanya belum terbaca, jadi sisanya tidak bisa disimpulkan.`,
      tone: "unknown",
    };
  }

  const sisa = shortageKg - surplusKg;
  if (sisa > 0) {
    return {
      text: `${tally.shortage} lokasi kekurangan ${formatKg(shortageKg)}; kelebihan ${tally.surplus} lokasi (${formatKg(surplusKg)}) menutup sebagian, ${formatKg(sisa)} belum tertutup.`,
      tone: "danger",
    };
  }
  return {
    text: `${tally.shortage} lokasi kekurangan ${formatKg(shortageKg)}; kelebihan ${tally.surplus} lokasi (${formatKg(surplusKg)}) menutup seluruhnya dan menyisakan ${formatKg(Math.abs(sisa))}.`,
    tone: "safe",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// §6.5 — kelengkapan data tingkat jaringan
//
// Sumber "punya catatan" BUKAN angka 0: `GET /balance/map` sudah mengirim
// `supply_state`/`demand_state` dengan nilai `tidak_ada_baris` untuk sisi yang
// tidak punya baris sama sekali (PLAN-023). Umur catatan memakai
// `supply_recorded_at`/`demand_recorded_at`.
//
// `null` = tidak bisa dinilai (server tidak mengirim waktunya) — bukan 0.
// ─────────────────────────────────────────────────────────────────────────────

export type Completeness = {
  withoutSupply: number;
  withoutDemand: number;
  staleSupply: number | null;
  staleDemand: number | null;
  unmapped: number;
  staleAfterHours: number;
};

function ageHours(stamp: string, nowMs: number): number | null {
  const parsed = Date.parse(stamp);
  if (!Number.isFinite(parsed)) return null;
  return (nowMs - parsed) / 3_600_000;
}

export function dataCompleteness(
  locations: readonly BalanceMapLocation[],
  opts: { now?: number | Date; staleAfterHours?: number } = {},
): Completeness {
  const staleAfterHours = opts.staleAfterHours ?? 24;
  const nowMs =
    opts.now instanceof Date
      ? opts.now.getTime()
      : typeof opts.now === "number"
        ? opts.now
        : Date.now();

  let withoutSupply = 0;
  let withoutDemand = 0;
  let staleSupply: number | null = 0;
  let staleDemand: number | null = 0;

  for (const location of locations) {
    const adaSupply = !tanpaCatatan(location.supply_state);
    const adaDemand = !tanpaCatatan(location.demand_state);
    if (tanpaCatatan(location.supply_state)) withoutSupply += 1;
    if (tanpaCatatan(location.demand_state)) withoutDemand += 1;

    if (staleSupply !== null) {
      const usia =
        adaSupply && typeof location.supply_recorded_at === "string"
          ? ageHours(location.supply_recorded_at, nowMs)
          : adaSupply
            ? null
            : 0;
      if (usia === null) staleSupply = null;
      else if (usia > staleAfterHours) staleSupply += 1;
    }
    if (staleDemand !== null) {
      const usia =
        adaDemand && typeof location.demand_recorded_at === "string"
          ? ageHours(location.demand_recorded_at, nowMs)
          : adaDemand
            ? null
            : 0;
      if (usia === null) staleDemand = null;
      else if (usia > staleAfterHours) staleDemand += 1;
    }
  }

  return {
    withoutSupply,
    withoutDemand,
    staleSupply,
    staleDemand,
    unmapped: locations.filter((location) => !hasCoordinates(location)).length,
    staleAfterHours,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Wilayah & urutan
// ─────────────────────────────────────────────────────────────────────────────

export type RegionRollup = {
  region: string;
  locations: BalanceMapLocation[];
  tally: Record<BalanceStatus, number>;
  shortageKg: number | null;
};

export function rollupByRegion(
  locations: readonly BalanceMapLocation[],
): RegionRollup[] {
  const byRegion = new Map<string, BalanceMapLocation[]>();
  for (const location of locations) {
    const key = location.region?.trim() || "Tanpa wilayah";
    const list = byRegion.get(key) ?? [];
    list.push(location);
    byRegion.set(key, list);
  }

  return Array.from(byRegion.entries())
    .map(([region, rows]) => {
      const tally: Record<BalanceStatus, number> = {
        shortage: 0,
        surplus: 0,
        balanced: 0,
      };
      let shortageKg: number | null = 0;
      for (const row of rows) {
        if (isBalanceStatus(row.status)) tally[row.status] += 1;
        if (row.status === "shortage") {
          const value = toNumber(row.shortage_kg);
          shortageKg =
            shortageKg === null || value === null ? null : shortageKg + value;
        }
      }
      return { region, locations: rows, tally, shortageKg };
    })
    .sort((a, b) => {
      if (b.tally.shortage !== a.tally.shortage) {
        return b.tally.shortage - a.tally.shortage;
      }
      return a.region.localeCompare(b.region);
    });
}

const SEVERITY: Record<string, number> = { shortage: 0, surplus: 1, balanced: 2 };

/** Urutkan dari yang paling kekurangan; selisih terbesar lebih dulu. */
export function sortBySeverity(
  locations: readonly BalanceMapLocation[],
): BalanceMapLocation[] {
  return [...locations].sort((a, b) => {
    const rank = (SEVERITY[a.status] ?? 3) - (SEVERITY[b.status] ?? 3);
    if (rank !== 0) return rank;
    const gapA = Math.abs(toNumber(a.shortage_kg ?? a.surplus_kg) ?? 0);
    const gapB = Math.abs(toNumber(b.shortage_kg ?? b.surplus_kg) ?? 0);
    if (gapB !== gapA) return gapB - gapA;
    return a.location.localeCompare(b.location);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Koordinat
// ─────────────────────────────────────────────────────────────────────────────

function coordinateValue(raw: number | string | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === "string" && !raw.trim()) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/**
 * `Number(null)` adalah 0 — pemeriksaan naif membuat lokasi tanpa koordinat
 * dianggap berada di (0,0) dan penandanya muncul di lepas pantai Afrika.
 * Absen harus dibaca absen, bukan nol.
 */
export function hasCoordinates(location: BalanceMapLocation): boolean {
  return (
    coordinateValue(location.latitude) !== null &&
    coordinateValue(location.longitude) !== null
  );
}

export function formatCoordinates(location: BalanceMapLocation): string {
  const lat = coordinateValue(location.latitude);
  const lng = coordinateValue(location.longitude);
  if (lat === null || lng === null) return "—";
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Legenda & umur catatan
// ─────────────────────────────────────────────────────────────────────────────

/** "baru saja" / "2 jam lalu" / "—". `null` = tidak ada stempel waktu. */
export function ageLabel(
  stamp: string | null | undefined,
  now: number = Date.now(),
): string | null {
  if (!stamp) return null;
  const parsed = Date.parse(stamp);
  if (!Number.isFinite(parsed)) return null;
  const selisihMenit = (now - parsed) / 60_000;
  // Catatan bertanggal di DEPAN jam sistem bukan "baru saja". Data demo pernah
  // memuat baris 4 Nov sementara jam berjalan 28 Okt; memetakan umur negatif ke
  // "baru saja" membuat masa depan terbaca sebagai kondisi sekarang.
  if (selisihMenit < -1) return "waktu catatan di depan jam sistem";
  const menit = Math.max(0, Math.round(selisihMenit));
  if (menit < 2) return "baru saja";
  if (menit < 60) return `${menit} menit lalu`;
  const jam = Math.round(menit / 60);
  if (jam < 48) return `${jam} jam lalu`;
  return `${Math.round(jam / 24)} hari lalu`;
}


/** Status keputusan yang masih menunggu tindakan manusia (bukan hasil akhir). */
export const STATUS_TERBUKA: ReadonlySet<string> = new Set([
  "proposed",
  "pending_approval",
  "approved",
  "verifier_flagged",
  "review_only",
]);

const SATU_HARI_JAM = 24;

function namaLokasi(nilai: unknown): string {
  return nilai === null || nilai === undefined ? "" : String(nilai).trim();
}

function teksKecil(nilai: unknown): string {
  return nilai === null || nilai === undefined ? "" : String(nilai).trim().toLowerCase();
}

/**
 * Jumlah batch per lokasi yang masa layaknya ≤ `hari` lagi DAN boleh dipakai.
 *
 * Kolom ini menjawab "kalau lokasi ini kekurangan, apakah stok yang ada masih
 * bisa dipakai minggu ini?" — karena itu:
 *   * batch ditahan (`quarantine_status = quarantined`) tidak dihitung, seberapa
 *     pun hasil ujinya;
 *   * batch yang gagal uji / belum diverifikasi tidak dihitung;
 *   * tanggal tak terbaca TIDAK dianggap 0 hari — ia tidak dihitung sama sekali,
 *     karena menulis "kedaluwarsa hari ini" dari tanggal rusak adalah karangan;
 *   * batch yang sudah lewat masa layaknya TETAP dihitung: itu yang paling
 *     mendesak, bukan alasan untuk menyembunyikannya.
 *
 * Hasil: `{ [lokasi]: jumlah }`; lokasi dengan 0 tidak muncul (pemanggil memakai
 * `?? 0` dan tidak menulis angka nol).
 */
export function hampirKedaluwarsa(
  batches: readonly unknown[] | null | undefined,
  now: Date = new Date(),
  hari = 7,
): Record<string, number> {
  const hasil: Record<string, number> = {};
  if (!Array.isArray(batches)) return hasil;
  const batasJam = hari * SATU_HARI_JAM;
  for (const baris of batches as {
    location?: unknown;
    usable_until?: unknown;
    safety_status?: unknown;
    quarantine_status?: unknown;
  }[]) {
    const lokasi = namaLokasi(baris?.location);
    if (!lokasi) continue;
    if (teksKecil(baris?.quarantine_status) === "quarantined") continue;
    const status = teksKecil(baris?.safety_status);
    if (status !== "pass") continue;
    const jam = hoursLeft(baris?.usable_until, now);
    if (jam === null || jam > batasJam) continue;
    hasil[lokasi] = (hasil[lokasi] ?? 0) + 1;
  }
  return hasil;
}

/**
 * Jumlah keputusan TERBUKA per lokasi tujuan — "kekurangan ini sudah punya
 * usulan atau belum?". Lokasi tanpa nama dilewati supaya tidak ada kunci
 * `"undefined"` yang lalu tampil sebagai baris.
 */
export function rekomendasiTerbuka(
  decisions: readonly { status?: unknown; target_location_name?: unknown }[] | null | undefined,
): Record<string, number> {
  const hasil: Record<string, number> = {};
  if (!Array.isArray(decisions)) return hasil;
  for (const baris of decisions) {
    const lokasi = namaLokasi(baris?.target_location_name);
    if (!lokasi) continue;
    if (!STATUS_TERBUKA.has(teksKecil(baris?.status))) continue;
    hasil[lokasi] = (hasil[lokasi] ?? 0) + 1;
  }
  return hasil;
}
