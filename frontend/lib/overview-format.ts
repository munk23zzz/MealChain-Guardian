export const BALANCE_STATUSES = ["shortage", "surplus", "balanced"] as const;
export type BalanceStatus = (typeof BALANCE_STATUSES)[number];

/**
 * Asal nilai per sisi (PLAN-023, 2026-10-17). Backend mengisi supply/demand yang
 * TIDAK ADA dengan `0` supaya peta tetap lengkap, jadi angka saja tidak cukup:
 * `tidak_ada_baris` berarti angka 0 itu hasil pengisian, bukan hasil pengukuran.
 */
export type DataState = "terukur" | "sebagian" | "tidak_ada_baris";

/** The exact read model returned by GET /balance/map. Values may be absent on partial/stale data. */
export type BalanceMapLocation = {
  location: string;
  status: BalanceStatus | string;
  supply_kg?: number | string | null;
  demand_kg?: number | string | null;
  shortage_kg?: number | string | null;
  surplus_kg?: number | string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  region?: string | null;
  /** Asal nilai per sisi + ringkasannya (opsional: respons lama tidak punya). */
  supply_state?: DataState | string | null;
  demand_state?: DataState | string | null;
  data_state?: DataState | string | null;
  supply_recorded_at?: string | null;
  demand_recorded_at?: string | null;
};

/** Sisi tanpa baris = angka 0-nya hasil pengisian, bukan fakta terukur. */
export function tanpaCatatan(state?: string | null): boolean {
  return state === "tidak_ada_baris";
}

/**
 * Catatan asal nilai untuk RINCIAN/tooltip — `null` bila semua sisi terukur,
 * sehingga tidak ada label tambahan di keadaan normal. Angka `0` yang terukur
 * tetap ditampilkan `0 kg`; catatan ini hanya menerangkan yang tidak tercatat.
 */
export function dataSourceNote(
  location: Partial<BalanceMapLocation> | null | undefined
): string | null {
  const sisi: string[] = [];
  if (tanpaCatatan(location?.supply_state)) sisi.push("pasokan");
  if (tanpaCatatan(location?.demand_state)) sisi.push("permintaan");
  if (sisi.length === 0) return null;
  return `${sisi.join(" & ")} tanpa catatan`;
}

export function isBalanceStatus(status: string): status is BalanceStatus {
  return (BALANCE_STATUSES as readonly string[]).includes(status);
}

export function formatKg(value: number | string | null | undefined): string {
  if (value == null || value === "") return "—";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toLocaleString("id-ID")} kg` : "—";
}

export function formatBalanceGap(location: BalanceMapLocation): string {
  if (location.status === "shortage") return `kurang ${formatKg(location.shortage_kg)}`;
  if (location.status === "surplus") return `lebih ${formatKg(location.surplus_kg)}`;
  if (location.status === "balanced") return "seimbang";
  return "status belum tersedia";
}

export function formatBalanceStatus(status: string): string {
  if (status === "shortage") return "Shortage";
  if (status === "surplus") return "Surplus";
  if (status === "balanced") return "Seimbang";
  return "Status belum tersedia";
}

export function sumFiniteKg(locations: readonly Pick<BalanceMapLocation, "supply_kg">[]): number | null {
  if (!locations.length) return null;
  let total = 0;
  for (const { supply_kg } of locations) {
    if (supply_kg == null || (typeof supply_kg === "string" && !supply_kg.trim())) return null;
    const value = Number(supply_kg);
    if (!Number.isFinite(value)) return null;
    total += value;
  }
  return total;
}

export function summarizeBalanceStatus(locations: readonly BalanceMapLocation[]): string {
  const counts = locations.reduce(
    (summary, location) => {
      if (isBalanceStatus(location.status)) summary[location.status] += 1;
      return summary;
    },
    { surplus: 0, shortage: 0, balanced: 0 } as Record<BalanceStatus, number>,
  );
  return `${counts.surplus} surplus · ${counts.shortage} shortage · ${counts.balanced} seimbang`;
}
