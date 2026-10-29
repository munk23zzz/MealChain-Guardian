// Ringkasan eksekusi untuk tab Agent Log (UI-1, 29 Okt 2026).
//
// Batas yang dijaga modul ini — sama seperti `agent-activity.ts`:
//
// - Skema TIDAK menyimpan status eksekusi per agent (`running`/`failed`).
//   Yang dicatat: keputusan, statusnya, dan jejak langkahnya. Karena itu fungsi
//   di bawah hanya menghitung keadaan yang benar-benar ada di baris keputusan.
//   Menambah angka "berjalan" atau "gagal" di sini berarti mengarang.
// - "Lewat tenggat" hanya berlaku untuk keputusan yang MASIH menunggu tindakan.
//   Keputusan yang sudah disetujui/dieksekusi/ditolak tidak menjadi tunggakan
//   hanya karena `expires_at`-nya lewat.
// - Tanggal kosong atau rusak tidak pernah dibaca sebagai "lewat" (null ≠ 0).

import { verificationState, type AuditDecision } from "./decision-table";

/** Status yang berarti verifikator menandai keputusan ini perlu diperiksa. */
export const FLAGGED_STATUS = "verifier_flagged";

export type ExecutionOverview = {
  /** Seluruh keputusan pada periode terpilih. */
  total: number;
  /** Keputusan yang sudah punya jejak penilaian agent (`has_agent_review`). */
  reviewed: number;
  /** Masih menunggu verifikasi/persetujuan. */
  waiting: number;
  /** Ditolak verifikator. */
  rejected: number;
  /** Ditandai verifikator (`verifier_flagged`). */
  flagged: number;
  /** Masih menunggu tindakan DAN `expires_at` sudah lewat. */
  overdue: number;
  /** flagged ∪ overdue — satu keputusan dihitung sekali. */
  attention: number;
};

export function isFlagged(row: Pick<AuditDecision, "status">): boolean {
  return (row.status ?? "").trim().toLowerCase() === FLAGGED_STATUS;
}

function waktu(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** `true` bila keputusan masih menunggu tindakan tetapi tenggatnya sudah lewat. */
export function isOverdue(
  row: Pick<AuditDecision, "status" | "expires_at" | "valid">,
  now: Date
): boolean {
  if (verificationState(row) !== "menunggu") return false;
  const tenggat = waktu(row.expires_at);
  const acuan = now.getTime();
  if (tenggat === null || !Number.isFinite(acuan)) return false;
  return tenggat < acuan;
}

export function needsAttention(
  row: Pick<AuditDecision, "status" | "expires_at" | "valid">,
  now: Date
): boolean {
  return isFlagged(row) || isOverdue(row, now);
}

export function executionOverview(
  rows: ReadonlyArray<AuditDecision>,
  now: Date
): ExecutionOverview {
  const hasil: ExecutionOverview = {
    total: 0,
    reviewed: 0,
    waiting: 0,
    rejected: 0,
    flagged: 0,
    overdue: 0,
    attention: 0,
  };

  for (const row of rows) {
    hasil.total += 1;
    if (row.has_agent_review === true) hasil.reviewed += 1;

    const verifikasi = verificationState(row);
    if (verifikasi === "menunggu") hasil.waiting += 1;
    if (verifikasi === "ditolak") hasil.rejected += 1;
    if (isFlagged(row)) hasil.flagged += 1;
    if (isOverdue(row, now)) hasil.overdue += 1;
    if (needsAttention(row, now)) hasil.attention += 1;
  }

  return hasil;
}
