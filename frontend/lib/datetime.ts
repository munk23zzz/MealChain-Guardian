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

/** ISO → "18:16:47" (jam UTC, dipakai jejak agen agar lintas hop bisa dibandingkan).
 *  Nilai kosong/tidak sah → "—" — pemanggil TIDAK boleh memanggil toISOString
 *  sendiri, karena new Date(undefined).toISOString() melempar RangeError dan
 *  menjatuhkan seluruh render. */
export function formatClockUtc(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(11, 19);
}

/**
 * ISO → jam WIB ringkas "22.54" (tanpa tanggal, tanpa detik).
 *
 * Dipakai untuk estimasi tiba perjalanan kiriman: yang dibutuhkan pembaca adalah
 * "kapan", bukan tanggal lengkap. Tanggalnya tetap ditulis di baris popup lewat
 * `formatDateTime` supaya kiriman yang tiba besok tidak terbaca sebagai hari ini.
 * Nilai kosong/tidak sah → "—".
 */
export function formatClockWib(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d
    .toLocaleTimeString("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: TZ,
    })
    .replace(":", ".");
}

/** Kunci hari WIB (YYYY-MM-DD) untuk membandingkan "hari ini" tanpa jam. */
function kunciHari(d: Date): string {
  return d.toLocaleDateString("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: TZ,
  });
}

/**
 * ISO → "14.20" bila masih hari ini, atau "8 Okt 2026 16.01" bila bukan.
 *
 * Dipakai pil/verdict kiriman: jam saja membuat perjalanan 13 hari lalu
 * terbaca sebagai perjalanan hari ini. Perbandingan memakai tanggal WIB,
 * bukan UTC, supaya pergantian hari di Jakarta tidak salah.
 */
export function formatMomentWib(
  iso: string | null | undefined,
  sekarang: Date = new Date()
): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  if (Number.isNaN(sekarang.getTime())) return formatClockWib(iso);
  if (kunciHari(d) === kunciHari(sekarang)) return formatClockWib(iso);
  return `${formatDate(iso)} ${formatClockWib(iso)}`;
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
