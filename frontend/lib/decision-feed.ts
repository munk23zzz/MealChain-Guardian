// Logika murni halaman Recommendation Feed: chip filter, pencarian, urutan,
// dan ringkasan hasil. Dipisah dari page.tsx supaya bisa diuji tanpa DOM dan
// supaya tidak ada selisih antara yang ditulis di layar dan yang benar-benar
// dilakukan kode.
//
// Aturan yang dipegang:
//   - istilah datang dari satu sumber, tidak dikarang di sini: jenis keputusan
//     dari typeWord()/DECISION_TYPE_LABELS, status dari statusWord()
//     (lib/decision-picker), dan "perlu tindakan" dari ACTIONABLE_STATUSES
//     (lib/topbar) — definisi yang sama dengan lonceng notifikasi top bar dan
//     angka di sidebar;
//   - angka chip = jumlah baris yang benar-benar ada, bukan taksiran;
//   - urutan bawaan ("urgency") bisa dipertanggungjawabkan dari data yang ada:
//     keputusan yang menunggu tindakan manusia DAN masih berlaku di paling
//     atas, lalu yang menunggu tindakan tetapi sudah lewat tenggat, lalu isu
//     keamanan, ketidakseimbangan, terakhir harga. Sebelum 16 Okt tier teratas
//     justru yang PALING LAMA lewat tenggat, sehingga kartu yang sudah tidak
//     bisa ditindak menutupi kartu yang masih hidup (temuan QA F1);
//   - "menunggu tindakan" berarti masih BISA ditindak: keputusan yang lewat
//     tenggat (`valid: false` dari API) tidak ikut dihitung di chip maupun di
//     cakupan "action", karena backend menolak tindakan atasnya (409);
//   - tanggal yang tidak terbaca diletakkan di akhir tanpa diacak;
//   - pencarian mencocokkan kata yang benar-benar tercetak di kartu (termasuk
//     istilah manusia), bukan hanya enum backend, supaya "harga" menemukan
//     price_anomaly dan "ditolak" menemukan rejected.

import { statusWord, typeWord } from "./decision-picker";
import { ACTIONABLE_STATUSES, isExpired, isPendingAction } from "./topbar";

export type FeedSort = "urgency" | "due" | "newest";

export type FeedFilter = {
  /** "all" = semua; "action" = yang menunggu tindakan; selain itu nama status. */
  scope?: string;
  /** Kata kunci bebas; "" = tidak menyaring. */
  query?: string;
};

export type FeedChip = { id: string; label: string; count: number };

export type FeedRow = Record<string, any> & {
  decision_id?: string | null;
  status?: string | null;
  decision_type?: string | null;
};

export const FEED_SCOPE_ALL = "all";
export const FEED_SCOPE_ACTION = "action";

/** Label kontrol urutan (dipakai <select> di feed). */
export const FEED_SORT_LABELS: Record<FeedSort, string> = {
  urgency: "Urgensi (bawaan)",
  due: "Tenggat terdekat",
  newest: "Terbaru",
};

/** Urutan chip status: yang menuntut tindakan lebih dulu, sisanya mengikuti alur. */
const STATUS_ORDER = [
  "pending_approval",
  "needs_verification",
  "verifier_flagged",
  "proposed",
  "approved",
  "executed",
  "rejected",
];

/** Prioritas jenis keputusan untuk urutan "urgency" (kecil = lebih dulu). */
const TYPE_ORDER: Record<string, number> = {
  safety_disruption: 0,
  regional_balance: 1,
  surplus_redistribution: 1,
  price_anomaly: 2,
  supplier_exclusion: 3,
};

const ACTIONABLE_SET = new Set<string>(ACTIONABLE_STATUSES);

const norm = (value: unknown): string => String(value ?? "").trim().toLowerCase();

const statusList = (decisions: unknown): FeedRow[] =>
  (Array.isArray(decisions) ? decisions : []).filter(
    (row): row is FeedRow => Boolean(row) && typeof row === "object"
  );

const timeOf = (value: unknown): number | null => {
  if (value === null || value === undefined || value === "") return null;
  const ms = Date.parse(String(value));
  return Number.isFinite(ms) ? ms : null;
};

export function isActionable(status: unknown): boolean {
  return ACTIONABLE_SET.has(norm(status).toUpperCase());
}

/** Status → label manusia; "action" jadi "perlu tindakan". */
export function scopeLabel(scope: unknown): string {
  const key = norm(scope);
  if (!key || key === FEED_SCOPE_ALL) return "";
  if (key === FEED_SCOPE_ACTION) return "perlu tindakan";
  return statusWord(key);
}

/**
 * Chip filter: "Perlu tindakan" lebih dulu, lalu satu chip per status yang
 * memang ada di data (label bahasa manusia). Daftar kosong → tanpa chip.
 */
export function feedChips(decisions: unknown): FeedChip[] {
  const withStatus = statusList(decisions).filter((row) => Boolean(norm(row.status)));
  if (!withStatus.length) return [];

  const counts = new Map<string, number>();
  for (const row of withStatus) {
    const key = norm(row.status);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  const rank = (status: string): number => {
    const index = STATUS_ORDER.indexOf(status);
    return index === -1 ? STATUS_ORDER.length : index;
  };

  // Array.from (bukan spread) — tsconfig repo ini di bawah es2015, jadi
  // iterator Map tidak bisa langsung disebar.
  const ids = Array.from(counts.keys()).sort((a, b) => rank(a) - rank(b) || (a < b ? -1 : 1));

  return [
    {
      id: FEED_SCOPE_ACTION,
      label: "Perlu tindakan",
      // Hanya yang masih bisa ditindak — chip ini menjanjikan tindakan, dan
      // keputusan lewat tenggat ditolak backend (409). Angka ini harus sama
      // dengan isi daftar saat chip diklik (lihat feedVisible).
      count: withStatus.filter((row) => isPendingAction(row)).length,
    },
    ...ids.map((id) => ({ id, label: statusWord(id), count: counts.get(id) ?? 0 })),
  ];
}

/** Kata yang dicari: apa yang benar-benar tercetak di kartu + nilai mentahnya. */
function haystack(row: FeedRow): string {
  return [
    typeWord(row.decision_type),
    row.decision_type,
    statusWord(row.status),
    row.status,
    row.decision_id,
    String(row.demo_case ?? "").replace(/-/g, " "),
    row.rejection_reason,
    row.verifier_note,
    row.valid ? "berlaku" : "kedaluwarsa",
  ]
    .filter((part) => part !== null && part !== undefined && part !== "")
    .join(" ")
    .toLowerCase();
}

/** Saring per cakupan + kata kunci. Urutan masukan dibiarkan apa adanya. */
export function feedVisible(decisions: unknown, filter: FeedFilter = {}): FeedRow[] {
  const scope = norm(filter.scope) || FEED_SCOPE_ALL;
  const query = norm(filter.query).replace(/\s+/g, " ");

  // Hanya baris yang benar-benar bisa dibuka (punya decision_id) yang masuk
  // feed: kartu tanpa id akan jadi tombol yang tidak menuju apa pun.
  return statusList(decisions)
    .filter((row) => typeof row.decision_id === "string" && row.decision_id !== "")
    .filter((row) => {
      if (scope !== FEED_SCOPE_ALL) {
        if (scope === FEED_SCOPE_ACTION) {
          if (!isPendingAction(row)) return false;
        } else if (norm(row.status) !== scope) {
          return false;
        }
      }
      if (!query) return true;
      return haystack(row).includes(query);
    });
}

/** Urutkan tanpa mengubah data; `now` null = tidak ada klaim waktu. */
export function sortFeed(decisions: unknown, mode: FeedSort, now: Date | null): FeedRow[] {
  const rows = statusList(decisions).map((row, index) => ({ row, index }));

  /**
   * Kunci urutan "urgency": tier dulu, lalu tenggat/jenis, lalu waktu buat.
   * Tier 0 = menunggu tindakan DAN masih berlaku (yang benar-benar bisa
   * dikerjakan sekarang), tier 1 = menunggu tindakan tetapi sudah lewat
   * tenggat, tier 2 = sisanya. Dulu tier 0 justru yang PALING LAMA lewat
   * tenggat, sehingga kartu mati menutupi kartu hidup (temuan QA F1).
   */
  const urgencyOf = (row: FeedRow): { tier: number; type: number; due: number | null } => {
    const due = timeOf(row.expires_at);
    if (isActionable(row.status)) {
      return { tier: isExpired(row, now) ? 1 : 0, type: 0, due };
    }
    return { tier: 2, type: TYPE_ORDER[norm(row.decision_type)] ?? 9, due };
  };

  /** Penanda "sudah lewat tenggat" untuk mengelompokkannya di akhir. */
  const expiredKey = (row: FeedRow): number => (isExpired(row, now) ? 1 : 0);

  const byTime = (
    a: number | null,
    b: number | null,
    direction: 1 | -1,
    indexA: number,
    indexB: number
  ): number => {
    if (a === null && b === null) return indexA - indexB;
    if (a === null) return 1;
    if (b === null) return -1;
    if (a === b) return indexA - indexB;
    return (a - b) * direction;
  };

  rows.sort((left, right) => {
    if (mode === "newest") {
      return byTime(timeOf(left.row.created_at), timeOf(right.row.created_at), -1, left.index, right.index);
    }
    if (mode === "due") {
      // Yang masih berlaku berurut tenggat terdekat; yang sudah lewat menutup
      // daftar (juga berurut tenggat, bukan diacak) — sesuai nama tesnya.
      const lewat = expiredKey(left.row) - expiredKey(right.row);
      if (lewat !== 0) return lewat;
      return byTime(timeOf(left.row.expires_at), timeOf(right.row.expires_at), 1, left.index, right.index);
    }
    const a = urgencyOf(left.row);
    const b = urgencyOf(right.row);
    if (a.tier !== b.tier) return a.tier - b.tier;
    if (a.tier <= 1) return byTime(a.due, b.due, 1, left.index, right.index);
    if (a.type !== b.type) return a.type - b.type;
    return byTime(timeOf(left.row.created_at), timeOf(right.row.created_at), -1, left.index, right.index);
  });

  return rows.map((entry) => entry.row);
}

/** Satu kalimat jujur tentang hasil yang sedang dilihat (untuk role="status"). */
export function feedSummary(input: {
  shown: number;
  total: number;
  scope?: string;
  query?: string;
}): string {
  const parts = [`Menampilkan ${input.shown} dari ${input.total} rekomendasi`];
  const label = scopeLabel(input.scope);
  if (label) parts.push(`filter: ${label}`);
  const query = String(input.query ?? "").trim();
  if (query) parts.push(`pencarian: "${query}"`);
  return parts.join(" · ");
}

/** Benar kalau pengguna sedang menyaring (untuk tombol "Kosongkan filter"). */
export function hasActiveFilter(filter: FeedFilter = {}): boolean {
  const scope = norm(filter.scope) || FEED_SCOPE_ALL;
  return scope !== FEED_SCOPE_ALL || norm(filter.query) !== "";
}
