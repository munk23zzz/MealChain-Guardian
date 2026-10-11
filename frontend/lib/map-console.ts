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

// --- Sinkronisasi peta tanpa menyentuh zoom (arah Roy 2026-10-11) -----------
// Keluhan: tiap polling (5 detik) membuat peta "nge-zoom" sendiri — peta
// dibangun ulang tiap kali array `locations` berganti identitas, lalu
// fitBounds dijalankan lagi, sehingga zoom/geser pengguna hilang.
// Dua penjaga murni di bawah ini yang menjaga perilakunya:
//   1. `pinSignature`/`pinDiff` — tahu penanda MANA yang isinya berubah,
//      supaya penanda diperbarui di tempat (tanpa membangun ulang peta).
//   2. `nextMapFocus` — kapan peta BOLEH di-dekatkan: hanya saat pertama
//      tampil atau saat lokasi aktif BERGANTI.

/** Tanda tangan isi satu penanda: berubah hanya bila nada/label/posisi/angka
 *  lokasi benar-benar berubah — bukan karena objeknya baru. */
export function pinSignature(row: BalanceMapLocation): string {
  return [
    pinTone(row.status),
    finiteOrNull(row.latitude) ?? "",
    finiteOrNull(row.longitude) ?? "",
    pinLabel(row),
    finiteOrNull(row.supply_kg) ?? "",
    finiteOrNull(row.demand_kg) ?? "",
  ].join("|");
}

/** Peta tanda tangan per nama lokasi (hanya lokasi berkoordinat yang punya
 *  penanda — sama dengan aturan pembuatan penanda). */
export function pinSignatures(locations: readonly BalanceMapLocation[]): Record<string, string> {
  const out: Record<string, string> = {};
  locations.forEach((row) => {
    if (finiteOrNull(row.latitude) === null || finiteOrNull(row.longitude) === null) return;
    out[row.location] = pinSignature(row);
  });
  return out;
}

/** Penanda yang perlu ditambah / diperbarui / dibuang antara dua snapshot. */
export function pinDiff(
  previous: Readonly<Record<string, string>>,
  current: Readonly<Record<string, string>>
): { added: string[]; changed: string[]; removed: string[] } {
  const added: string[] = [];
  const changed: string[] = [];
  const removed: string[] = [];
  Object.keys(current).forEach((name) => {
    if (!(name in previous)) added.push(name);
    else if (previous[name] !== current[name]) changed.push(name);
  });
  Object.keys(previous).forEach((name) => {
    if (!(name in current)) removed.push(name);
  });
  return { added, changed, removed };
}

/** Keadaan fokus peta: sudah pernah di-dekatkan, dan untuk lokasi apa. */
export type MapFocus = { fitted: boolean; active: string | null };

export const MAP_FOCUS_INITIAL: MapFocus = { fitted: false, active: null };

/**
 * Keputusan fokus peta. `fit: true` hanya saat belum pernah fokus atau saat
 * lokasi aktif BERGANTI; sinkronisasi data (isi sama, atau angka/status
 * berubah pada lokasi yang sama) TIDAK pernah menghasilkan `fit: true` —
 * itulah sebabnya zoom & geser pengguna bertahan saat sync.
 */
export function nextMapFocus(previous: MapFocus, active: string | null): { focus: MapFocus; fit: boolean } {
  const target = active ?? null;
  if (!previous.fitted) return { focus: { fitted: true, active: target }, fit: true };
  if (previous.active === target) return { focus: previous, fit: false };
  return { focus: { fitted: true, active: target }, fit: true };
}

