// Bahasa warna halaman Recommendations — logika murni supaya pemetaan status →
// warna tepi kartu bisa diuji tanpa DOM dan tidak mudah berubah tanpa sengaja.
//
// Alasannya: di halaman ini ada puluhan kartu sekaligus. Tepi berwarna adalah
// isyarat "lihat saya" terkuat, jadi warna itu hanya boleh dipakai untuk kartu
// yang memang menuntut tindakan. Kartu kedaluwarsa diberi tepi netral.

export type CardEdge =
  | "edge-primary"
  | "edge-warning"
  | "edge-danger"
  | "edge-expired"
  | "edge-neutral";

/** Status yang butuh perhatian manusia atau sudah gagal → warnanya lebih kuat. */
const EDGE_BY_STATUS: Record<string, CardEdge> = {
  // "Menunggu persetujuan" adalah keadaan PALING UMUM di feed (14 dari 16
  // kartu pada demo 29 Okt 2026). Tepi amber di hampir semua kartu berhenti
  // menjadi isyarat — pemilik meminta warnanya abu netral saja, sehingga amber
  // kembali berarti "perlu diperiksa".
  PENDING_APPROVAL: "edge-neutral",
  VERIFIER_FLAGGED: "edge-warning",
  NEEDS_VERIFICATION: "edge-warning",
  REJECTED: "edge-danger",
  FAIL: "edge-danger",
  SHORTAGE: "edge-danger",
};

/**
 * Tepi kartu rekomendasi.
 * - bahaya (ditolak/gagal) SELALU menang, termasuk saat kedaluwarsa;
 * - kedaluwarsa → netral (bukan biru/amber) supaya kartu yang masih hidup
 *   menonjol;
 * - sisanya → tepi utama (biru).
 */
export function cardEdge(
  decision: { status?: string | null; valid?: boolean | null } | null | undefined
): CardEdge {
  const status = String(decision?.status ?? "").toUpperCase();
  const dariStatus = EDGE_BY_STATUS[status] ?? "edge-primary";
  if (decision?.valid === false && dariStatus !== "edge-danger") return "edge-expired";
  return dariStatus;
}
