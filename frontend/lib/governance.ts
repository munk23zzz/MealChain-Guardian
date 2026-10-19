import { blockingReasons } from "./bahasa";
import { roleLabel } from "./settings";

/**
 * Turunan tampilan "Governance & persetujuan" dari read model server.
 *
 * Aturan yang dijaga:
 *  - angka HANYA dari `approval_requirement` + `approval_state`; UI tidak
 *    pernah menghitung sendiri siapa yang wajib menyetujui (design.md §1.3);
 *  - `missing` dari server menentukan grup mana yang belum terpenuhi — bukan
 *    perbandingan himpunan di sini. Yang dihitung hanya `total - missing`,
 *    karena `total` = jumlah grup syarat dan `missing` = grup yang belum;
 *  - `rejected` menang atas hitungan peran: satu penolakan menggugurkan;
 *  - data aneh (missing lebih banyak dari total) tidak boleh menghasilkan
 *    angka negatif atau melempar.
 */

export type GovernanceState =
  | "menunggu"
  | "sebagian"
  /** Semua peran syarat sudah setuju, tetapi eksekusi masih tertahan
      (mis. pemasok belum terikat, verifikasi, atau jendela waktu). */
  | "lengkap"
  | "siap"
  | "ditolak"
  | "selesai";

export type GovernanceGroup = {
  /** Label manusia untuk satu grup syarat ("Kepala SPPG atau Ahli Gizi SPPG"). */
  label: string;
  /** Role mentah dalam grup, sudah dirapikan. */
  roles: string[];
  /** Sudah ada satu approval dari grup ini. */
  done: boolean;
};

export type GovernanceView = {
  state: GovernanceState;
  label: string;
  /** Grup syarat yang sudah terpenuhi. */
  done: number;
  /** Jumlah grup syarat. */
  total: number;
  groups: GovernanceGroup[];
  /** Label grup yang masih kurang (untuk kalimat "menunggu …"). */
  missingLabels: string[];
  /** Alasan tertahan dari server, apa adanya. */
  blocker: string[];
  canApprove: boolean;
  canExecute: boolean;
  approvedRoles: string[];
};

const LABEL: Record<GovernanceState, string> = {
  menunggu: "Menunggu persetujuan",
  sebagian: "Sebagian disetujui",
  lengkap: "Persetujuan lengkap",
  siap: "Siap dieksekusi",
  ditolak: "Ditolak",
  selesai: "Selesai",
};

function daftar(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function grupDari(value: unknown): string[][] {
  return daftar(value)
    .map((grup) => (Array.isArray(grup) ? grup : [grup]))
    .map((grup) => grup.map((r) => String(r)).filter(Boolean))
    .filter((grup) => grup.length > 0);
}

function labelGrup(roles: string[]): string {
  return roles.map((r) => roleLabel(r)).join(" atau ");
}

function samaGrup(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const set = new Set(b);
  return a.every((r) => set.has(r));
}

export function governanceView(summary: unknown): GovernanceView {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const requirement = (payload?.approval_requirement ?? null) as Record<string, unknown> | null;
  const state = (payload?.approval_state ?? null) as Record<string, unknown> | null;

  const syarat = grupDari(requirement?.required_roles);
  const kurang = grupDari(state?.missing);
  const total = syarat.length;
  const done = Math.max(0, Math.min(total, total - Math.min(kurang.length, total)));

  const approvedRoles = daftar(state?.approved_roles).map((r) => String(r));
  const groups: GovernanceGroup[] = syarat.map((roles) => ({
    roles,
    label: labelGrup(roles),
    done: roles.some((r) => approvedRoles.includes(r)),
  }));
  // Server adalah sumber kebenaran: kalau grup tercantum di `missing`,
  // tandai belum selesai walau `approved_roles` memuat salah satu role-nya
  // (mis. approval dibatalkan).
  const missingLabels = kurang.map((roles) => labelGrup(roles));

  const rejected = state?.rejected === true || payload?.status === "rejected";
  const satisfied = state?.satisfied === true || payload?.status === "approved";
  const executed = payload?.status === "executed";

  // "Siap dieksekusi" HANYA kalau server menyatakan `can_execute`. Tanpa itu,
  // syarat peran boleh lengkap tetapi eksekusi masih tertahan (pemasok belum
  // terikat, belum diverifikasi, jendela lewat) — chip tidak boleh menjanjikan
  // lebih dari yang server izinkan (terukur: kartu pernah menulis
  // "Siap dieksekusi" berdampingan dengan "Boleh dieksekusi: Belum").
  let status: GovernanceState;
  if (rejected) status = "ditolak";
  else if (executed) status = "selesai";
  else if (satisfied && payload?.can_execute === true) status = "siap";
  else if (satisfied) status = "lengkap";
  else if (done > 0) status = "sebagian";
  else status = "menunggu";

  return {
    state: status,
    label: LABEL[status],
    done,
    total,
    groups,
    missingLabels,
    blocker: blockingReasons(payload),
    canApprove: payload?.can_approve === true,
    canExecute: payload?.can_execute === true,
    approvedRoles,
  };
}
