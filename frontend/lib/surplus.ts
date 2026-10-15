// Halaman "Surplus & Limbah" — meniru halaman /surplus di aplikasi acuan
// (E:\hackathon\HackathonBil\MealchainGuardian), DISESUAIKAN: sumber angka =
// GET /balance/map?commodity=... (surplus_kg, shortage_kg, koordinat, region).
//
// Di acuan ada panel "rencana alokasi surplus" + pembahasan limbah (Peraturan
// BGN No. 1/2026). Di repo ini tidak ada tabel limbah/disposal, jadi bagian
// limbah ditulis "—" dengan alasan yang jujur, dan alokasi dihitung dari
// surplus nyata (greedy: kebutuhan terbesar diisi surplus terbesar).

const DASH = "—";

export type BalanceNode = {
  location?: string | null;
  region?: string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  surplus_kg?: number | string | null;
  shortage_kg?: number | string | null;
  status?: string | null;
};

export type SurplusSummary = {
  surplusKg: number | null;
  surplusCount: number;
  shortageKg: number | null;
  shortageCount: number;
  balancedCount: number;
};

export function surplusSummary(locations: unknown): SurplusSummary {
  const list = nodes(locations);
  const surplus = list.filter((node) => number(node.surplus_kg) > 0);
  const shortage = list.filter((node) => number(node.shortage_kg) > 0);
  const surplusKg = sumOrNull(surplus.map((node) => number(node.surplus_kg)).filter((n) => n > 0));
  const shortageKg = sumOrNull(shortage.map((node) => number(node.shortage_kg)).filter((n) => n > 0));
  return {
    surplusKg,
    surplusCount: surplus.length,
    shortageKg,
    shortageCount: shortage.length,
    balancedCount: list.filter((node) => String(node.status ?? "") === "balanced").length,
  };
}

/** Jarak lingkaran besar (km) — dipakai untuk mengurutkan pasangan alokasi. */
export function haversineKm(
  a: { latitude?: unknown; longitude?: unknown },
  b: { latitude?: unknown; longitude?: unknown }
): number | null {
  const lat1 = Number(a?.latitude);
  const lon1 = Number(a?.longitude);
  const lat2 = Number(b?.latitude);
  const lon2 = Number(b?.longitude);
  if (![lat1, lon1, lat2, lon2].every((n) => Number.isFinite(n))) return null;
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return Math.round(2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h))));
}

export type Allocation = {
  from: string;
  to: string;
  kg: number;
  distanceKm: number | null;
  region: string | null;
};

/**
 * Rencana alokasi: kebutuhan terbesar diisi dari surplus terbesar, sampai salah
 * satu sisi habis. Urutan tujuan = kekurangan terbesar lebih dulu.
 */
export function allocationPlan(locations: unknown, limit = 5): Allocation[] {
  const list = nodes(locations);
  const pools = list
    .map((node) => ({ node, left: number(node.surplus_kg) }))
    .filter((pool) => pool.left > 0)
    .sort((a, b) => b.left - a.left);
  const needs = list
    .map((node) => ({ node, left: number(node.shortage_kg) }))
    .filter((need) => need.left > 0)
    .sort((a, b) => b.left - a.left);

  const rows: Allocation[] = [];
  for (const need of needs) {
    for (const pool of pools) {
      if (need.left <= 0) break;
      if (pool.left <= 0) continue;
      const kg = Math.min(pool.left, need.left);
      if (kg <= 0) continue;
      pool.left -= kg;
      need.left -= kg;
      rows.push({
        from: name(pool.node),
        to: name(need.node),
        kg,
        distanceKm: haversineKm(pool.node, need.node),
        region: region(need.node),
      });
      if (rows.length >= limit) return rows;
    }
  }
  return rows;
}

export type SurplusFact = { label: string; value: string; hint?: string | null };

/** Bagian limbah/sisa pangan yang sumbernya belum ada di repo ini. */
export function wasteFacts(): SurplusFact[] {
  return [
    { label: "Sisa pangan dicatat", value: DASH, hint: "pencatatan limbah/sisa pangan belum tersedia" },
    { label: "Limbah dialihkan", value: DASH, hint: "pengalihan limbah belum tercatat" },
    { label: "Komposter / bank pangan", value: DASH, hint: "belum ada data mitra pengolahan" },
  ];
}

function nodes(locations: unknown): BalanceNode[] {
  return Array.isArray(locations) ? (locations as BalanceNode[]) : [];
}

function number(value: unknown): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function name(node: BalanceNode): string {
  const raw = node?.location ? String(node.location).trim() : "";
  return raw || DASH;
}

function region(node: BalanceNode): string | null {
  const raw = node?.region ? String(node.region).trim() : "";
  return raw || null;
}

function sumOrNull(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((total, value) => total + value, 0);
}
