// Keseimbangan pasokan per LOKASI untuk BGN Monitor (satu komoditas, banyak
// lokasi). Ini bukan grafik kualitas batch: yang dibandingkan adalah pasokan
// tercatat vs kebutuhan tiap lokasi, dengan satuan kg yang sama.
//
// Aturan kejujuran data (sama dengan grafik SPPG):
// - `demand_state === "tidak_ada_baris"` → kebutuhan TIDAK diketahui, bukan 0.
// - `supply_state === "tidak_ada_baris"` → pasokan TIDAK diketahui, bukan 0.
// - Kebutuhan 0 yang terukur → tidak ada dasar menghitung cakupan; jangan
//   menampilkan 0% atau 100% seolah ada penilaian.
import type { BalanceMapLocation } from "./overview-format";
import {
  formatCoverage,
  formatSignedKg,
  type SupplyTone,
} from "./supply-adequacy";

export type LocationBalanceStatus =
  | "shortage"
  | "surplus"
  | "balanced"
  | "unknown";

export type LocationBalanceState =
  | "terukur"
  | "tanpa_data"
  | "tanpa_kebutuhan";

export type LocationBalanceRow = {
  location: string;
  supplyKg: number | null;
  demandKg: number | null;
  gapKg: number | null;
  coverage: number | null;
  status: LocationBalanceStatus;
  dataState: LocationBalanceState;
  tone: SupplyTone;
};

function angka(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function teks(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function buildLocationBalanceRows(
  locations: readonly BalanceMapLocation[] | null | undefined
): LocationBalanceRow[] {
  const daftar = Array.isArray(locations) ? locations : [];
  return daftar.map((row) => {
    const demandMentah = angka(row.demand_kg);
    const demandState = teks(row.demand_state);
    const demandTerukur =
      demandMentah !== null && demandState !== "tidak_ada_baris";
    const demandKg = demandTerukur ? Math.max(0, demandMentah) : null;

    const supplyMentah = angka(row.supply_kg);
    const supplyState = teks(row.supply_state);
    const supplyTerukur =
      supplyMentah !== null && supplyState !== "tidak_ada_baris";
    const supplyKg = supplyTerukur ? Math.max(0, supplyMentah) : null;

    let coverage: number | null = null;
    let gapKg: number | null = null;
    let status: LocationBalanceStatus = "unknown";
    if (demandKg !== null && demandKg > 0 && supplyKg !== null) {
      coverage = supplyKg / demandKg;
      gapKg = supplyKg - demandKg;
      status = gapKg > 0 ? "surplus" : gapKg === 0 ? "balanced" : "shortage";
    } else if (demandKg !== null && demandKg === 0) {
      status = "balanced";
    }

    const dataState: LocationBalanceState =
      demandKg === null
        ? "tanpa_data"
        : demandKg === 0
          ? "tanpa_kebutuhan"
          : "terukur";

    const tone: SupplyTone =
      coverage === null
        ? "muted"
        : coverage >= 0.999
          ? "safe"
          : coverage >= 0.6
            ? "warning"
            : "danger";

    return {
      location: teks(row.location) || "—",
      supplyKg,
      demandKg,
      gapKg,
      coverage,
      status,
      dataState,
      tone,
    };
  });
}

/**
 * Urutkan dari kekurangan TERBESAR (paling negatif) ke surplus. Lokasi yang
 * tidak bisa dinilai diletakkan di akhir — bukan di atas, karena "belum ada
 * data" bukan masalah terbesar.
 */
export function sortLocationBalanceRows(
  rows: readonly LocationBalanceRow[]
): LocationBalanceRow[] {
  return [...rows].sort((a, b) => {
    if (a.gapKg === null && b.gapKg !== null) return 1;
    if (b.gapKg === null && a.gapKg !== null) return -1;
    if (a.gapKg !== null && b.gapKg !== null && a.gapKg !== b.gapKg) {
      return a.gapKg - b.gapKg;
    }
    return a.location.localeCompare(b.location, "id");
  });
}

export function locationBalanceSummary(
  rows: readonly LocationBalanceRow[]
): {
  measured: number;
  shortage: number;
  worst: LocationBalanceRow | null;
} {
  const measured = rows.filter((row) => row.gapKg !== null);
  const shortage = measured.filter((row) => (row.gapKg as number) < 0);
  const worst =
    [...shortage].sort((a, b) => (a.gapKg as number) - (b.gapKg as number))[0] ??
    null;
  return { measured: measured.length, shortage: shortage.length, worst };
}

export function locationStatusLabel(row: LocationBalanceRow): string {
  if (row.dataState === "tanpa_data") return "kebutuhan belum tercatat";
  if (row.dataState === "tanpa_kebutuhan") return "tidak ada kebutuhan";
  if (row.supplyKg === null) return "pasokan belum tercatat";
  if (row.status === "shortage") return "kekurangan";
  if (row.status === "surplus") return "surplus";
  return "seimbang";
}

// Diekspor ulang supaya komponen hanya perlu satu impor; formatnya identik
// dengan grafik SPPG sehingga tidak ada dua gaya angka di halaman yang sama.
export { formatCoverage, formatSignedKg };
