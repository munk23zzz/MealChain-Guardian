// Deep link keputusan: `?keputusan=<id>`.
//
// Keputusan yang sedang dibuka dulu hanya hidup di state React — tidak bisa
// dibagikan dan hilang saat muat ulang. Sekarang URL adalah alamatnya:
//   /?keputusan=<id>  → halaman membuka keputusan itu di tab Decision & Evidence.
//
// Semua fungsi murni (tanpa DOM) supaya bisa diuji; halaman yang memegang
// window.location dan history.

export const DECISION_PARAM = "keputusan";

// Id keputusan di repo ini berupa UUID (kadang potongan id pendek). Yang penting:
// tidak ada spasi/slash, dan panjangnya masuk akal. Nilai aneh → null, karena
// membuka "keputusan" hasil tebakan lebih buruk daripada membuka halaman kosong.
const ID_SAH = /^[A-Za-z0-9._:-]{1,64}$/;

/** Baca `?keputusan=` dari query string. Tidak ada / tidak sah → null. */
export function readDecisionLink(search: string | null | undefined): string | null {
  if (!search) return null;
  let params: URLSearchParams;
  try {
    params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  } catch {
    return null;
  }
  const mentah = params.get(DECISION_PARAM);
  if (!mentah) return null;
  const id = mentah.trim();
  return ID_SAH.test(id) ? id : null;
}

/**
 * Query string baru dengan param keputusan diset (atau dihapus bila null).
 * Parameter lain dipertahankan apa adanya.
 */
export function withDecisionLink(
  search: string | null | undefined,
  decisionId: string | null
): string {
  const bersih = search && search.startsWith("?") ? search.slice(1) : (search ?? "");
  const params = new URLSearchParams(bersih);
  if (decisionId) params.set(DECISION_PARAM, decisionId);
  else params.delete(DECISION_PARAM);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}
