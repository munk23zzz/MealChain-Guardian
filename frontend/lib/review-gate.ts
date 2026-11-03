// review-gate — aturan "review boleh dikirim?" sebagai fungsi murni.
//
// Kenapa dipisah dari komponen: aturan ini pernah hanya hidup di dalam handler
// tombol, sehingga tidak bisa diuji tanpa DOM dan mudah menyimpang dari yang
// ditegakkan server (`POST /decisions/{id}/review` menolak 422 tanpa alasan
// ≥10 karakter dan tanpa rujukan bukti). Sekarang satu fungsi dipakai komponen
// DAN tes; server tetap penentu akhir.

export const REASON_MIN = 10;

//: Peran yang boleh meninjau bukti batch. Sama dengan `MUTATING_ROLES`
//: (`backend/app/api/auth.py`); bgn_monitor read-only.
export const REVIEW_ROLES = ["sppg_head", "sppg_nutritionist"] as const;

export type ReviewDraft = {
  role: string | null;
  batchId: string | null;
  reason: string;
  evidenceRefs: string[];
};

export type ReviewReadiness = {
  /** Boleh mengirim sekarang? */
  ok: boolean;
  /** Alasan penolakan dalam bahasa manusia, kosong bila `ok`. */
  blockers: string[];
};

export function reviewReadiness(draft: ReviewDraft): ReviewReadiness {
  const blockers: string[] = [];
  const role = String(draft.role ?? "");
  if (!(REVIEW_ROLES as readonly string[]).includes(role)) {
    blockers.push("peran ini tidak berwenang meninjau bukti batch");
  }
  if (!draft.batchId) {
    blockers.push("pilih batch yang ditinjau");
  }
  if (draft.reason.trim().length < REASON_MIN) {
    blockers.push(`alasan review minimal ${REASON_MIN} karakter`);
  }
  const refs = (draft.evidenceRefs ?? []).map((r) => r.trim()).filter(Boolean);
  if (refs.length === 0) {
    blockers.push("minimal satu rujukan bukti");
  }
  return { ok: blockers.length === 0, blockers };
}
