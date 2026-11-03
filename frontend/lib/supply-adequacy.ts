// Kecukupan pasokan per komoditas untuk SATU SPPG (peran kepala SPPG & ahli gizi).
//
// Sumber angka:
// - kebutuhan  : `demand_kg` dari GET /balance/map (SupplyRecord/DemandRecord),
// - kualitas   : GET /batches (safety_status, quarantine_status, usable_until).
//
// Batang TIDAK memakai `supply_kg` dari /balance/map karena angka itu agregat
// catatan pasokan, bukan stok yang benar-benar layak dipakai. Yang digambar
// adalah batch yang aman, tidak ditahan, dan belum kedaluwarsa; `supply_kg`
// tetap dibawa sebagai konteks "tercatat" supaya selisihnya tidak disembunyikan.
//
// Semua fungsi di sini murni (tanpa React) supaya aturan sortir/klasifikasi bisa
// diuji tanpa DOM dan tidak bisa berbeda antara kepala SPPG dan ahli gizi.

import { hoursLeft, quarantineStatus } from "./food-safety";
import type { BalanceMapLocation } from "./overview-format";

export type AdequacyLens = "quantity" | "freshness";

export type SupplyTone = "safe" | "warning" | "danger" | "muted";

export type AdequacyBatch = {
  location?: string | null;
  commodity?: string | null;
  quantity_kg?: number | string | null;
  safety_status?: string | null;
  quarantine_status?: string | null;
  receipt_status?: string | null;
  usable_until?: string | null;
  freshness_score?: number | string | null;
};

export type BatchBuckets = {
  /** Aman + sisa masa layak > 48 jam. */
  freshKg: number;
  /** Aman + sisa masa layak 0..48 jam (masih boleh dipakai, mendesak). */
  nearKg: number;
  /** Gagal uji, ditahan, ditolak saat terima, atau sudah lewat masa layak. */
  unsafeKg: number;
  /** Ada kg-nya, tetapi status/umur tidak cukup untuk disebut layak. */
  unverifiedKg: number;
  /** freshKg + nearKg — satu-satunya angka yang dipakai menghitung cakupan. */
  usableKg: number;
  /** Semua kg batch, termasuk yang tidak layak (konteks stok fisik). */
  totalKg: number;
  batchCount: number;
  nearCount: number;
};

export type CommodityAdequacy = {
  commodity: string;
  demandKg: number | null;
  supplyRecordKg: number | null;
  buckets: BatchBuckets;
  /** usableKg / demandKg; null saat kebutuhan tidak terukur/0. */
  coverage: number | null;
  /** freshKg / demandKg; null saat kebutuhan tidak terukur/0. */
  freshCoverage: number | null;
  /** usableKg - demandKg; negatif = kurang. */
  gapKg: number | null;
  /** freshKg - demandKg; negatif = kebutuhan belum tertutup stok segar. */
  freshGapKg: number | null;
  status: "shortage" | "surplus" | "balanced" | "unknown";
  dataState: "terukur" | "tanpa_kebutuhan" | "tanpa_data";
  tone: SupplyTone;
  freshTone: SupplyTone;
};

export type AdequacySummary = {
  measured: number;
  short: number;
  worst: CommodityAdequacy | null;
};

function angka(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function teks(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function bucketsKosong(): BatchBuckets {
  return {
    freshKg: 0,
    nearKg: 0,
    unsafeKg: 0,
    unverifiedKg: 0,
    usableKg: 0,
    totalKg: 0,
    batchCount: 0,
    nearCount: 0,
  };
}

/**
 * Kelompokkan batch satu (lokasi, komoditas) menjadi empat keranjang kualitas.
 * Aturan sengaja konservatif: batch yang tidak punya `usable_until` tidak
 * dianggap segar (masuk "belum terverifikasi"), bukan diisi 0 lalu tampak aman.
 */
export function bucketBatches(
  batches: unknown,
  location: string,
  commodity: string,
  now: Date
): BatchBuckets {
  const hasil = bucketsKosong();
  const lokasi = teks(location).toLowerCase();
  const komoditas = teks(commodity).toLowerCase();
  if (!lokasi || !komoditas) return hasil;

  const daftar = Array.isArray(batches) ? (batches as AdequacyBatch[]) : [];
  for (const batch of daftar) {
    if (teks(batch?.location).toLowerCase() !== lokasi) continue;
    if (teks(batch?.commodity).toLowerCase() !== komoditas) continue;

    hasil.batchCount += 1;
    const kg = angka(batch?.quantity_kg);
    if (kg === null || kg <= 0) continue;
    hasil.totalKg += kg;

    const status = teks(batch?.safety_status).toLowerCase();
    const karantina = quarantineStatus(batch?.quarantine_status);
    const terima = teks(batch?.receipt_status).toLowerCase();
    const sisaJam = hoursLeft(batch?.usable_until, now);
    const ditolak = terima === "rejected" || terima === "ditolak";

    if (
      status === "fail" ||
      karantina === "quarantined" ||
      karantina === "failed" ||
      ditolak ||
      (sisaJam !== null && sisaJam <= 0)
    ) {
      hasil.unsafeKg += kg;
    } else if (status !== "pass" || sisaJam === null) {
      hasil.unverifiedKg += kg;
    } else if (sisaJam <= 48) {
      hasil.nearKg += kg;
      hasil.nearCount += 1;
    } else {
      hasil.freshKg += kg;
    }
  }

  hasil.usableKg = hasil.freshKg + hasil.nearKg;
  return hasil;
}

export function toneForCoverage(coverage: number | null): SupplyTone {
  if (coverage === null) return "muted";
  if (coverage >= 0.999) return "safe";
  if (coverage >= 0.6) return "warning";
  return "danger";
}

export function buildCommodityAdequacy(
  commodity: string,
  locations: readonly BalanceMapLocation[] | null | undefined,
  batches: unknown,
  location: string,
  now: Date
): CommodityAdequacy {
  const namaLokasi = teks(location).toLowerCase();
  const baris = (locations ?? []).find(
    (row) => teks(row.location).toLowerCase() === namaLokasi
  );
  const demandMentah = baris ? angka(baris.demand_kg) : null;
  const demandState = teks(baris?.demand_state).toLowerCase();
  const demandTerukur =
    Boolean(baris) && demandState !== "tidak_ada_baris" && demandMentah !== null;
  const demandKg = demandTerukur ? Math.max(0, demandMentah as number) : null;
  const supplyRecordKg = baris ? angka(baris.supply_kg) : null;
  const buckets = bucketBatches(batches, location, commodity, now);
  // Pagar sumber data: `supply_records` adalah pasokan yang sudah masuk
  // pembukuan. Batch demo/siap-kirim bisa lebih besar dari angka itu; tanpa
  // pagar, peta menulis "shortage" sementara grafik menulis "surplus" untuk
  // komoditas yang sama. Stok layak tidak boleh mengklaim lebih dari tercatat.
  // Proporsi kualitas batch tetap dipakai supaya lensa kesegaran tidak hilang.
  if (supplyRecordKg !== null && buckets.totalKg > 0) {
    const batas = Math.max(0, supplyRecordKg);
    if (buckets.usableKg > batas) {
      const faktor = batas / buckets.usableKg;
      buckets.freshKg *= faktor;
      buckets.nearKg *= faktor;
      buckets.usableKg = batas;
    }
  }

  const coverage =
    demandKg !== null && demandKg > 0 ? buckets.usableKg / demandKg : null;
  const freshCoverage =
    demandKg !== null && demandKg > 0 ? buckets.freshKg / demandKg : null;
  const gapKg = demandKg !== null ? buckets.usableKg - demandKg : null;
  const freshGapKg = demandKg !== null ? buckets.freshKg - demandKg : null;

  let status: CommodityAdequacy["status"] = "unknown";
  if (demandKg !== null && demandKg > 0) {
    status = buckets.usableKg >= demandKg ? "surplus" : "shortage";
  } else if (demandKg === 0) {
    status = "balanced";
  }

  const dataState: CommodityAdequacy["dataState"] =
    demandKg === null ? "tanpa_data" : demandKg === 0 ? "tanpa_kebutuhan" : "terukur";

  return {
    commodity,
    demandKg,
    supplyRecordKg,
    buckets,
    coverage,
    freshCoverage,
    gapKg,
    freshGapKg,
    status,
    dataState,
    tone: toneForCoverage(coverage),
    freshTone: toneForCoverage(freshCoverage),
  };
}

export function buildAdequacyRows(args: {
  commodities: readonly string[];
  byCommodity: Record<string, readonly BalanceMapLocation[] | null | undefined>;
  batches: unknown;
  location: string;
  now: Date;
}): CommodityAdequacy[] {
  return args.commodities.map((commodity) =>
    buildCommodityAdequacy(
      commodity,
      args.byCommodity[commodity],
      args.batches,
      args.location,
      args.now
    )
  );
}

export function metricFor(row: CommodityAdequacy, lens: AdequacyLens): number | null {
  return lens === "freshness" ? row.freshCoverage : row.coverage;
}

export function gapFor(row: CommodityAdequacy, lens: AdequacyLens): number | null {
  return lens === "freshness" ? row.freshGapKg : row.gapKg;
}

/**
 * Kepala SPPG: cakupan total terendah lebih dulu.
 * Ahli gizi: cakupan stok SEGAR terendah lebih dulu.
 * Baris tanpa kebutuhan terukur selalu di belakang — bukan dianggap 0%.
 */
export function sortAdequacyRows(
  rows: readonly CommodityAdequacy[],
  lens: AdequacyLens
): CommodityAdequacy[] {
  return [...rows].sort((a, b) => {
    const ma = metricFor(a, lens);
    const mb = metricFor(b, lens);
    if (ma === null && mb !== null) return 1;
    if (mb === null && ma !== null) return -1;
    if (ma !== null && mb !== null && ma !== mb) return ma - mb;
    return (gapFor(a, lens) ?? 0) - (gapFor(b, lens) ?? 0);
  });
}

export function adequacySummary(
  rows: readonly CommodityAdequacy[],
  lens: AdequacyLens
): AdequacySummary {
  const measured = rows.filter((row) => metricFor(row, lens) !== null);
  const short = measured.filter((row) => (metricFor(row, lens) ?? 0) < 0.999);
  const worst =
    [...short].sort(
      (a, b) => (metricFor(a, lens) ?? 0) - (metricFor(b, lens) ?? 0)
    )[0] ?? null;
  return { measured: measured.length, short: short.length, worst };
}

export function formatSignedKg(kg: number | null | undefined): string {
  if (kg === null || kg === undefined || !Number.isFinite(Number(kg))) return "—";
  const bulat = Math.round(Number(kg));
  if (bulat === 0) return "0 kg";
  const abs = Math.abs(bulat).toLocaleString("id-ID");
  return bulat > 0 ? `+${abs} kg` : `−${abs} kg`;
}

export function formatCoverage(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "—";
  }
  return `${Math.round(Number(value) * 100)}%`;
}
