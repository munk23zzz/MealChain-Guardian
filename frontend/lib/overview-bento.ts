// Fase 2 redesign (Overview bento) — logika murni tile hero & ringkasan jaringan.
//
// Prinsip yang dipegang modul ini (aturan proyek "tanpa angka karangan"):
//   * nilai yang tidak tersedia → `null`, BUKAN 0;
//   * satu nilai hilang membuat TOTAL menjadi `null` (fail-closed), bukan
//     jumlah sebagian yang terlihat seperti angka lengkap;
//   * status yang tidak dikenal tidak pernah dianggap "seimbang" (0).
//
// Modul ini murni: tanpa DOM, tanpa fetch — diuji di tests/overview-bento.test.ts.
import type { BalanceMapLocation } from "./overview-format";

export type HeroScope = "location" | "network";
export type HeroTone = "shortage" | "surplus" | "balanced" | "unknown";

export type HeroGap = {
  /** "location" = lokasi yang dipilih di top bar; "network" = seluruh jaringan. */
  scope: HeroScope;
  /** Nama lokasi (hanya saat scope "location"). */
  name: string | null;
  /** Selisih pasokan−kebutuhan: negatif = kurang, positif = lebih. null = tak terhitung. */
  gapKg: number | null;
  supplyKg: number | null;
  demandKg: number | null;
  tone: HeroTone;
};

/** Angka dari nilai mentah API; string kosong/spasi = tidak tersedia. */
function finite(value: number | string | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "string" && !value.trim()) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

/** Jumlah fail-closed: daftar kosong → null, satu nilai hilang → null. */
function totalOf(values: readonly (number | null)[]): number | null {
  if (!values.length) return null;
  let total = 0;
  for (const value of values) {
    if (value === null) return null;
    total += value;
  }
  return total;
}

/** Selisih satu baris. Status tak dikenal → null (tidak dianggap 0). */
function gapOfRow(row: BalanceMapLocation): number | null {
  if (row.status === "shortage") {
    const value = finite(row.shortage_kg);
    return value === null ? null : -value;
  }
  if (row.status === "surplus") return finite(row.surplus_kg);
  if (row.status === "balanced") return 0;
  return null;
}

function toneOfGap(gapKg: number | null, fallbackStatus?: string): HeroTone {
  if (gapKg !== null) {
    if (gapKg < 0) return "shortage";
    if (gapKg > 0) return "surplus";
    return "balanced";
  }
  // Selisih tidak bisa dihitung: pakai status yang dikenal supaya arah masalah
  // tetap terbaca, dan jangan menebak bila statusnya pun tidak dikenal.
  if (fallbackStatus === "shortage" || fallbackStatus === "surplus" || fallbackStatus === "balanced") {
    return fallbackStatus;
  }
  return "unknown";
}

/**
 * Selisih pasokan untuk tile hero.
 *
 * Lokasi aktif dipakai bila ada di data; kalau tidak (atau belum dipilih),
 * hero menampilkan selisih JARINGAN = Σsurplus − Σshortage. Lokasi aktif yang
 * tidak ada di data TIDAK dikarang: jatuh ke jaringan.
 */
export function heroGap(
  locations: readonly BalanceMapLocation[] | null | undefined,
  activeLocation?: string | null,
): HeroGap {
  const rows = locations ?? [];
  const picked = activeLocation
    ? rows.find((row) => row.location === activeLocation)
    : undefined;

  if (picked) {
    const gapKg = gapOfRow(picked);
    return {
      scope: "location",
      name: picked.location,
      gapKg,
      supplyKg: finite(picked.supply_kg),
      demandKg: finite(picked.demand_kg),
      tone: toneOfGap(gapKg, String(picked.status)),
    };
  }

  const gapKg = totalOf(rows.map(gapOfRow));
  const totals = networkTotals(rows);
  return {
    scope: "network",
    name: null,
    gapKg,
    supplyKg: totals.supplyKg,
    demandKg: totals.demandKg,
    tone: toneOfGap(gapKg),
  };
}

/** Total pasokan & kebutuhan seluruh lokasi (fail-closed seperti totalOf). */
export function networkTotals(
  locations: readonly BalanceMapLocation[] | null | undefined,
): { supplyKg: number | null; demandKg: number | null } {
  const rows = locations ?? [];
  return {
    supplyKg: totalOf(rows.map((row) => finite(row.supply_kg))),
    demandKg: totalOf(rows.map((row) => finite(row.demand_kg))),
  };
}

/**
 * Pangsa selisih terhadap kebutuhan dalam persen bulat (0–100).
 * null bila selisih tidak diketahui atau kebutuhan tidak diketahui/nol —
 * "0%" akan terbaca seperti "tidak ada masalah", padahal datanya tidak ada.
 */
export function gapShareOfDemand(
  gapKg: number | null,
  demandKg: number | null,
): number | null {
  if (gapKg === null || demandKg === null) return null;
  if (demandKg <= 0) return null;
  return Math.round((Math.abs(gapKg) / demandKg) * 100);
}

/**
 * Pangsa pasokan terhadap kebutuhan dalam persen bulat — mis. 300/1.080 = 28%.
 * Sengaja TIDAK dibatasi 100%: 162% adalah informasi nyata (surplus jaringan),
 * yang dibatasi hanya lebar bar-nya di CSS.
 * null bila salah satu nilai tidak diketahui atau kebutuhan ≤ 0.
 */
export function demandCoveragePct(
  supplyKg: number | null,
  demandKg: number | null,
): number | null {
  if (supplyKg === null || demandKg === null) return null;
  if (demandKg <= 0) return null;
  return Math.round((supplyKg / demandKg) * 100);
}

/**
 * Angka selisih bertanda untuk ditampilkan: "−780 kg", "+1.400 kg", "0 kg".
 * Tanda minus memakai karakter tipografis U+2212 (−), bukan hyphen, supaya
 * tidak terbaca sebagai pemisah.
 */
export function formatSignedKg(gapKg: number | null): string {
  if (gapKg === null) return "—";
  if (gapKg === 0) return "0 kg";
  const magnitude = Math.abs(gapKg).toLocaleString("id-ID");
  return `${gapKg < 0 ? "−" : "+"}${magnitude} kg`;
}
