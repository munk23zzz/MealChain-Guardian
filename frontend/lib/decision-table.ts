// Tabel keputusan untuk tab Agent Log (dokumen `06-agent-log.md` §2.5).
//
// Satu tempat untuk: kolom tabel, keadaan verifikasi, penyaring (teks /
// komoditas / status verifikasi), dan paginasi. Komponen tabel tidak menghitung
// apa pun sendiri — sama seperti modul lain di repo ini, logika tampilan ada di
// lib murni dan bisa diuji tanpa React.

export interface AuditDecision {
  decision_id: string;
  decision_type: string;
  status: string;
  quantity_kg?: number | null;
  safe_delivered_cost?: number | null;
  expires_at?: string | null;
  created_at?: string | null;
  valid?: boolean;
  commodity_name?: string | null;
  target_location_name?: string | null;
  supplier_name?: string | null;
  has_agent_review?: boolean;
}

export type VerificationKey = "all" | "terverifikasi" | "menunggu" | "ditolak";

export const VERIFICATION_OPTIONS: ReadonlyArray<{
  key: VerificationKey;
  label: string;
}> = [
  { key: "all", label: "Semua status" },
  { key: "terverifikasi", label: "Sudah diverifikasi" },
  { key: "menunggu", label: "Menunggu verifikasi" },
  { key: "ditolak", label: "Ditolak" },
];

/**
 * Keadaan verifikasi satu keputusan.
 *
 * `rejected` = ditolak. `approved`/`executed` hanya bisa dicapai setelah ada
 * verifikasi, jadi keduanya "terverifikasi". `pending_approval` = menunggu.
 * Status lain tidak dikarang menjadi salah satu dari tiga: hasilnya "lainnya".
 */
export function verificationState(
  row: Pick<AuditDecision, "status" | "expires_at" | "valid">
): VerificationKey | "lainnya" {
  const status = (row.status ?? "").toLowerCase();
  if (status === "rejected") return "ditolak";
  if (status === "approved" || status === "executed") return "terverifikasi";
  if (status === "pending_approval" || status === "pending") return "menunggu";
  return "lainnya";
}

/** Label manusia untuk jenis keputusan mentah dari backend. */
const TYPE_LABEL: Record<string, string> = {
  supplier_procurement: "Pengadaan dari pemasok",
  supplier_exclusion: "Ganti sumber pasokan",
  regional_balance: "Penyeimbangan pasokan regional",
  surplus_redistribution: "Redistribusi surplus",
  price_adjustment: "Penyesuaian harga",
};

export function decisionTypeLabel(type: string | null | undefined): string {
  const raw = (type ?? "").trim();
  if (!raw) return "—";
  return TYPE_LABEL[raw] ?? raw;
}

export function statusLabel(status: string | null | undefined): string {
  const map: Record<string, string> = {
    pending_approval: "Menunggu persetujuan",
    approved: "Disetujui",
    executed: "Dieksekusi",
    rejected: "Ditolak",
    expired: "Kedaluwarsa",
    draft: "Draf",
  };
  const raw = (status ?? "").trim();
  if (!raw) return "—";
  return map[raw] ?? raw;
}

export interface DecisionFilter {
  query?: string;
  commodity?: string | null;
  verification?: VerificationKey;
}

/** Penyaring dipakai bersama oleh pencarian, chip komoditas, dan pilihan status. */
export function filterDecisions<T extends AuditDecision>(
  rows: ReadonlyArray<T>,
  filter: DecisionFilter = {}
): T[] {
  const query = (filter.query ?? "").trim().toLowerCase();
  const commodity = (filter.commodity ?? "").trim().toLowerCase();
  const verification = filter.verification ?? "all";

  return rows.filter((row) => {
    if (commodity && (row.commodity_name ?? "").toLowerCase() !== commodity) {
      return false;
    }
    if (verification !== "all" && verificationState(row) !== verification) {
      return false;
    }
    if (!query) return true;
    // Yang bisa dicari: jenis (kode & label), status (kode & label), id,
    // komoditas, pemasok, tujuan. Tidak ada field karangan.
    const haystack = [
      row.decision_id,
      row.decision_id?.slice(0, 8),
      row.decision_type,
      decisionTypeLabel(row.decision_type),
      row.status,
      statusLabel(row.status),
      row.commodity_name,
      row.supplier_name,
      row.target_location_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

/** Daftar komoditas yang benar-benar ada di feed (bukan daftar tetap). */
export function commodityOptions(
  rows: ReadonlyArray<AuditDecision>
): { value: string; label: string; count: number }[] {
  const peta = new Map<string, { value: string; label: string; count: number }>();
  for (const row of rows) {
    const nama = (row.commodity_name ?? "").trim();
    if (!nama) continue;
    const key = nama.toLowerCase();
    const ada = peta.get(key);
    if (ada) ada.count += 1;
    else peta.set(key, { value: nama, label: nama, count: 1 });
  }
  return Array.from(peta.values()).sort((a, b) =>
    a.label.localeCompare(b.label, "id")
  );
}

export function verificationCounts(
  rows: ReadonlyArray<AuditDecision>
): Record<VerificationKey, number> {
  const hasil: Record<VerificationKey, number> = {
    all: rows.length,
    terverifikasi: 0,
    menunggu: 0,
    ditolak: 0,
  };
  for (const row of rows) {
    const state = verificationState(row);
    if (state === "terverifikasi" || state === "menunggu" || state === "ditolak") {
      hasil[state] += 1;
    }
  }
  return hasil;
}

/** Kalimat status di atas tabel — menyebut sebab, bukan hanya angka. */
export function tableSummary({
  shown,
  total,
  query = "",
  commodity = null,
  verification = "all",
}: {
  shown: number;
  total: number;
  query?: string;
  commodity?: string | null;
  verification?: VerificationKey;
}): string {
  if (total === 0) return "Belum ada keputusan pada periode ini.";
  const bagian: string[] = [`${shown} dari ${total} keputusan`];
  if (query.trim()) bagian.push(`cocok "${query.trim()}"`);
  if (commodity) bagian.push(`komoditas ${commodity}`);
  if (verification !== "all") {
    const label = VERIFICATION_OPTIONS.find((o) => o.key === verification)?.label;
    if (label) bagian.push(label.toLowerCase());
  }
  return bagian.join(" · ");
}

export const DECISION_PAGE_SIZE = 6;

export function pageSlice<T>(rows: ReadonlyArray<T>, page: number): T[] {
  const aman = Math.max(1, Math.trunc(page) || 1);
  const mulai = (aman - 1) * DECISION_PAGE_SIZE;
  return rows.slice(mulai, mulai + DECISION_PAGE_SIZE);
}

export function pageCount(total: number): number {
  return Math.max(1, Math.ceil(total / DECISION_PAGE_SIZE));
}
