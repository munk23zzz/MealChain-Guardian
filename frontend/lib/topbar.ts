// Logika murni top bar (acuan mockup Stitch overview_map_supply_status:
// header global 64px: brand → dropdown cakupan → status jaringan → chip peran
// → lonceng notifikasi → identitas pemakai → keluar).
//
// Dipisah dari komponen supaya bisa diuji tanpa DOM (pola repo ini).
// Aturan cakupan yang dipegang: HANYA monitor nasional yang boleh memilih
// lokasi; peran SPPG terikat SPPG-nya, dan kalau lokasinya belum diketahui
// dropdown TIDAK menawarkan apa pun (fail-closed — bukan "semua lokasi").

/** Nilai dropdown untuk "seluruh lokasi" (hanya monitor nasional). */
export const ALL_LOCATIONS = "__all__";

export type TopBarLocation = {
  location: string;
  region?: string | null;
  status?: string | null;
  /** Asal nilai pasokan (PLAN-023): `tidak_ada_baris` = 0 hasil pengisian. */
  supply_state?: string | null;
  demand_state?: string | null;
};

export type ScopeOption = { value: string; label: string };

export type ScopeModel = {
  options: ScopeOption[];
  /** true = peran terikat SPPG: cakupan tidak boleh diperluas dari top bar. */
  disabled: boolean;
  placeholder: string;
};

/** Status yang menunggu tindakan manusia (sumber: alur approval backend).
 *
 * `approved` = kuorum dua approval sudah penuh tetapi PO belum terbit; Kepala
 * SPPG masih harus menekan Eksekusi, jadi keputusan itu MASIH menuntut tindakan.
 * `needs_verification` sengaja tidak ada: CHECK constraint `decisions` tidak
 * mengizinkannya, jadi status itu mustahil muncul dan hanya membuat hitungan
 * berbeda dari kenyataan.
 */
export const ACTIONABLE_STATUSES = [
  "PENDING_APPROVAL",
  "APPROVED",
  "VERIFIER_FLAGGED",
] as const;

const ACTIONABLE_SET = new Set<string>(ACTIONABLE_STATUSES);

export function isScopeChooser(role: string | null | undefined): boolean {
  return role === "bgn_monitor";
}

/** Model dropdown cakupan lokasi untuk satu peran. */
export function scopeModel(input: {
  role: string | null | undefined;
  locations: readonly TopBarLocation[];
  ownLocation?: string | null;
}): ScopeModel {
  const locations = input.locations ?? [];
  if (isScopeChooser(input.role)) {
    return {
      options: [
        {
          value: ALL_LOCATIONS,
          label: `Semua lokasi SPPG (${locations.length} lokasi)`,
        },
        ...locations.map((l) => ({ value: l.location, label: l.location })),
      ],
      disabled: false,
      placeholder: "Pilih lokasi",
    };
  }
  if (input.ownLocation) {
    return {
      options: [{ value: input.ownLocation, label: input.ownLocation }],
      disabled: true,
      placeholder: "Lokasi Anda",
    };
  }
  return {
    options: [],
    disabled: true,
    placeholder: input.role ? "Lokasi belum diketahui" : "Cakupan tidak diketahui",
  };
}

/** Cakupan awal setelah login. Data lokasi bisa belum tiba → jangan menebak:
 *  nilai ALL_LOCATIONS berarti "tanpa sorotan", bukan perluasan cakupan. */
export function defaultScope(input: {
  role: string | null | undefined;
  ownLocation?: string | null;
}): string {
  if (isScopeChooser(input.role)) return ALL_LOCATIONS;
  return input.ownLocation ?? ALL_LOCATIONS;
}

/** Baris minimum untuk menilai kedaluwarsa: `valid` dari API + `expires_at`. */
export type ExpiryRow = {
  status?: string | null;
  valid?: boolean | null;
  expires_at?: string | null;
};

/**
 * Apakah keputusan sudah lewat tenggat (tidak bisa ditindak lagi).
 *
 * `valid` dari GET /decisions adalah sumber kebenaran di aplikasi ini — dipakai
 * juga oleh components/RecommendationCard.tsx dan lib/recommendations.ts — jadi
 * ia yang menang bila ada (jangan menghitung ulang keputusan server). Tanpa
 * `valid`, tenggat dihitung dari `expires_at`; tanpa keduanya JANGAN mengklaim
 * kedaluwarsa: lebih baik tidak dihitung daripada mengarang.
 */
export function isExpired(row: ExpiryRow | null | undefined, now?: Date | null): boolean {
  if (typeof row?.valid === "boolean") return !row.valid;
  const tenggat = Date.parse(String(row?.expires_at ?? ""));
  if (!Number.isFinite(tenggat)) return false;
  const nowMs = now instanceof Date ? now.getTime() : Date.now();
  if (!Number.isFinite(nowMs)) return false;
  return tenggat < nowMs;
}

/**
 * Apakah status ini menuntut tindakan PERAN tersebut (audit M7, 18 Okt 2026).
 *
 * `proposed` hanya pekerjaan Kepala SPPG: hanya dia yang boleh menekan
 * "Ajukan" (POST /actions/propose). Ahli Gizi tidak bisa mengajukan, jadi
 * menghitung `proposed` untuknya berarti menampilkan pekerjaan yang mustahil
 * dikerjakan. Tanpa `role` (pemanggil lama) perilaku lama dipertahankan:
 * `proposed` tidak dihitung.
 */
export function isActionableForRole(
  status: string | null | undefined,
  role?: string | null
): boolean {
  const kode = String(status ?? "").toUpperCase();
  if (ACTIONABLE_SET.has(kode)) return true;
  return kode === "PROPOSED" && role === "sppg_head";
}

/** Menunggu tindakan manusia DAN masih bisa ditindak (belum lewat tenggat). */
export function isPendingAction(
  row: ExpiryRow | null | undefined,
  now?: Date | null,
  role?: string | null
): boolean {
  if (!isActionableForRole(row?.status, role)) return false;
  return !isExpired(row, now);
}

/**
 * Menunggu tindakan tetapi JENDELANYA sudah lewat — backend menolak tindakan
 * atasnya (409 "decision expired"), jadi baris seperti ini tidak boleh
 * ditawarkan sebagai pilihan baru. Keputusan yang sudah diputus (ditolak,
 * dieksekusi) TIDAK termasuk: tenggatnya tidak lagi menghalangi pembacaan.
 */
export function isExpiredAction(
  row: ExpiryRow | null | undefined,
  now?: Date | null,
  role?: string | null
): boolean {
  if (!isActionableForRole(row?.status, role)) return false;
  return isExpired(row, now);
}

export type ActionableCounts = {
  /** Menunggu tindakan DAN masih berlaku — yang benar-benar bisa dikerjakan. */
  actionable: number;
  /** Berstatus menunggu tindakan tetapi sudah lewat tenggat. */
  expired: number;
  /** Semua yang berstatus menunggu tindakan (actionable + expired). */
  total: number;
};

/**
 * Pecah hitungan "menunggu tindakan" jadi yang masih hidup dan yang sudah lewat
 * tenggat. Yang lewat TIDAK dihitung sebagai pekerjaan (backend menolak tindakan
 * atasnya dengan 409), tetapi juga tidak disembunyikan: angkanya dilaporkan.
 */
export function countActionableBreakdown(
  decisions: readonly ExpiryRow[] | null | undefined,
  now?: Date | null,
  role?: string | null
): ActionableCounts {
  let actionable = 0;
  let expired = 0;
  for (const decision of decisions ?? []) {
    if (!isActionableForRole(decision?.status, role)) continue;
    if (isExpired(decision, now)) expired += 1;
    else actionable += 1;
  }
  return { actionable, expired, total: actionable + expired };
}

/** Berapa keputusan yang benar-benar menunggu tindakan manusia (masih berlaku). */
export function countActionable(
  decisions: readonly ExpiryRow[] | null | undefined,
  now?: Date | null,
  role?: string | null
): number {
  return countActionableBreakdown(decisions, now, role).actionable;
}

/** Berapa keputusan berstatus menunggu tindakan yang sudah lewat tenggat. */
export function countExpiredActionable(
  decisions: readonly ExpiryRow[] | null | undefined,
  now?: Date | null,
  role?: string | null
): number {
  return countActionableBreakdown(decisions, now, role).expired;
}

/** Jumlah maksimum baris notifikasi yang ditampilkan di popup lonceng. */
export const NOTIF_LIMIT = 5;

/** Keputusan yang dibutuhkan popup notifikasi (subset respons GET /decisions). */
export type NotifDecision = {
  decision_id?: string | null;
  decision_type?: string | null;
  status?: string | null;
  quantity_kg?: number | null;
  created_at?: string | null;
  valid?: boolean | null;
  expires_at?: string | null;
};

export type NotifList = {
  /** Jumlah keputusan yang menunggu tindakan DAN masih bisa ditindak. */
  total: number;
  /** Baris yang ditampilkan, terbaru lebih dulu. */
  shown: NotifDecision[];
  /** Sisa yang tidak ditampilkan karena batas. */
  rest: number;
  /** Menunggu tindakan tetapi sudah lewat tenggat — TIDAK ikut `total`. */
  expired: number;
};

/**
 * Isi popup notifikasi: keputusan yang menunggu tindakan manusia, terbaru lebih
 * dulu, dibatasi `limit` baris. Entri tanpa waktu ditaruh paling akhir, bukan
 * dibuang — supaya jumlahnya tetap cocok dengan lonceng.
 *
 * Keputusan yang sudah lewat tenggat tidak masuk daftar: notifikasi ini
 * menjanjikan tindakan, sementara backend menolak tindakan atasnya (409).
 * Angkanya tetap dilaporkan lewat `expired` supaya tidak hilang diam-diam.
 */
export function notifList(
  decisions: readonly NotifDecision[] | null | undefined,
  limit: number = NOTIF_LIMIT,
  role?: string | null
): NotifList {
  const waktu = (decision: NotifDecision): number => {
    const parsed = decision?.created_at ? Date.parse(decision.created_at) : Number.NaN;
    return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed;
  };

  let expired = 0;
  const menunggu = (decisions ?? []).filter((decision) => {
    if (!isActionableForRole(decision?.status, role)) return false;
    if (isExpired(decision)) {
      expired += 1;
      return false;
    }
    return true;
  });

  const urut = [...menunggu].sort((a, b) => {
    const wa = waktu(a);
    const wb = waktu(b);
    if (wa === wb) return 0; // urutan asli dipertahankan (sort stabil)
    return wa > wb ? -1 : 1;
  });

  const batas = Math.max(0, Math.trunc(limit));
  return {
    total: urut.length,
    shown: urut.slice(0, batas),
    rest: Math.max(0, urut.length - batas),
    expired,
  };
}

/** Inisial untuk avatar (maks 2 huruf, dari nilai pertama yang terisi). */
export function initialsOf(...values: (string | null | undefined)[]): string {
  const source = values.find((value) => value && value.trim());
  if (!source) return "";
  return source
    .trim()
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .map((word) => word[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** Ringkasan jaringan dari data peta (angka REAL, bukan karangan). */
export function networkState(
  locations: readonly TopBarLocation[] | null | undefined
): { tone: "safe" | "warning"; label: string } {
  const rows = locations ?? [];
  // Kekurangan hanya dihitung bila PASOKANNYA tercatat (PLAN-023): tanpa itu,
  // "kekurangan" hanyalah selisih terhadap 0 yang diisi engine.
  const shortage = rows.filter(
    (row) => row?.status === "shortage" && row?.supply_state !== "tidak_ada_baris"
  ).length;
  if (shortage > 0) {
    return { tone: "warning", label: `${shortage} lokasi shortage (${rows.length} terpantau)` };
  }
  return { tone: "safe", label: `Jaringan normal (${rows.length} lokasi)` };
}
