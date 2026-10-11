// Halaman "Pemasok" — meniru halaman /suppliers di aplikasi acuan
// (E:\hackathon\HackathonBil\MealchainGuardian: daftar + kepercayaan + eksklusi),
// DISESUAIKAN ke endpoint yang ADA di repo ini:
//   GET /supplier-exclusions                       → register eksklusi
//   GET /decisions/{id}/approval-summary           → pemasok + skor keandalan
//
// Backend ini TIDAK punya endpoint daftar pemasok, jadi daftarnya disusun dari
// pemasok yang muncul pada keputusan terakhir dalam cakupan — dan jumlah
// keputusan yang dipindai ditulis apa adanya di halaman (bukan "semua pemasok").

const DASH = "—";

export type SupplierPair = {
  decisionId?: string | null;
  decisionType?: string | null;
  commodity?: string | null;
  supplier?: {
    id?: string | null;
    name?: string | null;
    reliability_score?: number | string | null;
  } | null;
};

export type SupplierRosterRow = {
  id: string;
  name: string;
  reliabilityLabel: string;
  reliability: number | null;
  decisions: number;
  commodities: string[];
};

export function reliabilityLabel(score: unknown): string {
  if (score === null || score === undefined || score === "") return DASH;
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return DASH;
  return `${Math.round(numeric * 100)}%`;
}

export function supplierRoster(pairs: unknown): SupplierRosterRow[] {
  const list = Array.isArray(pairs) ? (pairs as SupplierPair[]) : [];
  const byId = new Map<string, SupplierRosterRow & { commoditySet: Set<string> }>();
  for (const pair of list) {
    const supplier = pair?.supplier;
    const name = supplier?.name ? String(supplier.name).trim() : "";
    const id = supplier?.id ? String(supplier.id) : name;
    if (!name && !id) continue;
    const key = id || name;
    const existing = byId.get(key);
    const score = supplier?.reliability_score;
    const numeric = score === null || score === undefined || score === "" ? null : Number(score);
    const commodity = pair?.commodity ? String(pair.commodity).trim() : "";
    if (existing) {
      existing.decisions += 1;
      if (commodity) existing.commoditySet.add(commodity);
      if (existing.reliability === null && numeric !== null && Number.isFinite(numeric)) {
        existing.reliability = numeric;
        existing.reliabilityLabel = reliabilityLabel(numeric);
      }
      continue;
    }
    byId.set(key, {
      id: key,
      name: name || key,
      reliability: numeric !== null && Number.isFinite(numeric) ? numeric : null,
      reliabilityLabel: reliabilityLabel(score),
      decisions: 1,
      commodities: [],
      commoditySet: commodity ? new Set([commodity]) : new Set(),
    });
  }
  return Array.from(byId.values())
    .map(({ commoditySet, ...row }) => ({ ...row, commodities: Array.from(commoditySet).sort() }))
    .sort((a, b) => b.decisions - a.decisions || a.name.localeCompare(b.name));
}

export type RosterMetrics = {
  suppliers: number;
  avgReliability: number | null;
  avgReliabilityLabel: string;
  totalDecisions: number;
};

export function rosterMetrics(roster: unknown): RosterMetrics {
  const list = Array.isArray(roster) ? (roster as SupplierRosterRow[]) : [];
  const scores = list
    .map((row) => row.reliability)
    .filter((score): score is number => typeof score === "number" && Number.isFinite(score));
  const avg = scores.length ? scores.reduce((total, score) => total + score, 0) / scores.length : null;
  return {
    suppliers: list.length,
    avgReliability: avg,
    avgReliabilityLabel: avg === null ? DASH : reliabilityLabel(avg),
    totalDecisions: list.reduce((total, row) => total + row.decisions, 0),
  };
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
    return {
      id: text(record.id) ?? DASH,
      supplier,
      reason: text(record.reason) ?? DASH,
      at: text(record.excluded_at) ?? text(record.created_at) ?? DASH,
      decisionId: text(record.decision_id) ?? DASH,
      status: text(record.status) ?? "excluded",
    };
  });
}

export const SUPPLIER_SOURCE_NOTE =
  "Daftar pemasok disusun dari pemasok pada keputusan terakhir dalam cakupan Anda (backend ini belum " +
  "punya endpoint daftar pemasok). Skor keandalan dibaca apa adanya dari payung keputusan " +
  "(reliability_score) — tidak dihitung ulang di layar. Register eksklusi dari GET /supplier-exclusions.";

function text(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  return raw ? raw : null;
}
