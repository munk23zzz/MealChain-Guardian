// Logika murni peta gaya acuan (arah Roy 2026-10-11): nada & label pin, dan
// proporsi bar telemetri node. Dipisah dari komponen supaya bisa diuji tanpa
// DOM — dan supaya tidak ada angka/label yang dikarang di dalam JSX.
import { formatKg, type BalanceMapLocation } from "./overview-format";

export type PinTone = "surplus" | "balanced" | "shortage" | "unknown";

export function pinTone(status?: string | null): PinTone {
  if (status === "surplus" || status === "balanced" || status === "shortage") return status;
  return "unknown";
}

function finiteOrNull(value: number | string | null | undefined): number | null {
  if (value == null || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

/** Label pin: nama lokasi + selisih yang benar-benar ada di data. */
export function pinLabel(row: BalanceMapLocation): string {
  const tone = pinTone(row.status);
  if (tone === "balanced") return `${row.location} seimbang`;
  const value =
    tone === "shortage" ? finiteOrNull(row.shortage_kg) : tone === "surplus" ? finiteOrNull(row.surplus_kg) : null;
  if (value === null) return row.location;
  return tone === "shortage" ? `${row.location} −${formatKg(value)}` : `${row.location} +${formatKg(value)}`;
}

export type Gauge = { value: number | null; share: number };

/** Dua bar telemetri node (pasokan & kebutuhan). `share` = proporsi terhadap
 *  nilai terbesar di antara keduanya (0–100) — perbandingan NYATA dari dua
 *  angka yang ada, bukan skala karangan. Angka tak tersedia → null & 0. */
export function nodeGauges(row: BalanceMapLocation): { supply: Gauge; demand: Gauge } {
  const supply = finiteOrNull(row.supply_kg);
  const demand = finiteOrNull(row.demand_kg);
  const values = [supply, demand].filter((value): value is number => value !== null);
  const max = values.length ? Math.max(...values) : 0;
  const share = (value: number | null) =>
    value === null || max <= 0 ? 0 : Math.round((value / max) * 100);
  return {
    supply: { value: supply, share: share(supply) },
    demand: { value: demand, share: share(demand) },
  };
}
