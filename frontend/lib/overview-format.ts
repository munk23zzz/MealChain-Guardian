export const BALANCE_STATUSES = ["shortage", "surplus", "balanced"] as const;
export type BalanceStatus = (typeof BALANCE_STATUSES)[number];

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
};

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
