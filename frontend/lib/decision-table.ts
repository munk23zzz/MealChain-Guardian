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
  // Keputusan yang ditandai verifikator BELUM diverifikasi: ia harus terjangkau
  // lewat chip "Menunggu verifikasi". Sebelumnya ia jatuh ke "lainnya" sehingga
  // tidak muncul di chip mana pun (13 baris, chip 2+6+3 = 11).
  if (
    status === "verifier_flagged" ||
    status === "review_only" ||
    status === "proposed"
  ) {
    return "menunggu";
  }
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
    // Dua status yang dulu lolos sebagai enum Inggris mentah ke kolom Status
    // (terlihat 29 Okt 2026: baris "price_anomaly" bercetak `verifier_flagged`).
    // Istilahnya sama dengan yang dipakai di feed (Fase 25).
    verifier_flagged: "Ditandai verifikator",
    review_only: "Temuan tinjauan",
    proposed: "Diusulkan",
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
    if (commodity === TANPA_KOMODITAS) {
      // Baris tanpa komoditas (3 di data demo) tidak bisa dijangkau penyaring
      // komoditas mana pun. Tanpa opsi ini, "Semua" menghitung 24 tetapi
      // pilihan komoditas hanya menjumlah 21 — selisih yang tak bisa dicari.
      if ((row.commodity_name ?? "").trim()) return false;
    } else if (commodity && (row.commodity_name ?? "").toLowerCase() !== commodity) {
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
/** Nilai penyaring untuk baris yang tidak membawa komoditas. */
export const TANPA_KOMODITAS = "__tanpa_komoditas__";

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
  const tanpa = rows.filter((row) => !(row.commodity_name ?? "").trim()).length;
  if (tanpa > 0) {
    peta.set(TANPA_KOMODITAS, {
      value: TANPA_KOMODITAS,
      label: "Tanpa komoditas",
      count: tanpa,
    });
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

/** Baris per halaman tabel keputusan. 10 = sama dengan daftar lain di aplikasi
 *  ini (Pemasok, Kiriman); pemilik 29 Okt 2026 meminta tabel Agent Log memakai
 *  ukuran halaman yang sama. Pemotongan halaman memakai `paginate` di
 *  `lib/pagination.ts` supaya penomoran & rentang "1–10 dari 14" tidak berbeda
 *  antar panel. */
export const DECISION_PAGE_SIZE = 10;

/**
 * Label kalimat untuk keadaan verifikasi (audit 29 Okt 2026).
 *
 * Dulu komponen mencetak kuncinya apa adanya ("menunggu") di sebelah kolom
 * Status yang berbunyi "Menunggu persetujuan" — dua gaya label di satu baris
 * membuat yang satu terbaca seperti token backend yang bocor.
 */
const LABEL_VERIFIKASI: Record<VerificationKey | "lainnya", string> = {
  all: "—",
  terverifikasi: "Terverifikasi",
  menunggu: "Menunggu verifikasi",
  ditolak: "Ditolak",
  lainnya: "—",
};

export function labelVerifikasi(state: VerificationKey | "lainnya"): string {
  return LABEL_VERIFIKASI[state] ?? "—";
}
