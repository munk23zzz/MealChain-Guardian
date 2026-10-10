/**
 * Format waktu untuk tampilan — murni (tanpa DOM), supaya bisa diuji vitest.
 *
 * Envelope backend membawa ISO lengkap dengan mikrodetik dan offset UTC
 * ("2026-10-10T18:16:47.844642+00:00"). Menampilkannya apa adanya tidak
 * terbaca; format acuan: "24 Sep 2026 22:08 WIB".
 *
 * Zona waktu dipatok ke Asia/Jakarta supaya hasilnya sama di server (UTC saat
 * build/SSR) maupun di peramban pengguna, dan supaya tes deterministik.
 */

const TZ = "Asia/Jakarta";

/** ISO → "10 Okt 2026 01.16 WIB". Nilai kosong/tidak sah → "—". */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const tanggal = d.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: TZ,
  });
  const jam = d
    .toLocaleTimeString("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: TZ,
    })
    .replace(":", ".");
  return `${tanggal} ${jam} WIB`;
}

/** ISO → "10 Okt 2026" (tanpa jam). Nilai kosong/tidak sah → "—". */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: TZ,
  });
}
