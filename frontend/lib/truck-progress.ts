/**
 * Posisi mobil kiriman ANTAR denyut data (audit 24 Okt 2026).
 *
 * Server mengirim `progress` = fraksi perjalanan PADA SAAT data dibuat. Selama
 * selang menuju polling berikutnya mobil harus terus maju, jadi `progress` itu
 * dijadikan JANGKAR lalu ditambah waktu berjalan dibagi durasi tempuh.
 *
 * Kenapa berjangkar, bukan dihitung dari `etaAt`: kalau jam server dan jam
 * peramban berbeda (atau data contoh bertanggal lain), hitungan dari `etaAt`
 * bisa melompat ke awal/ujung jalur dan bertentangan dengan angka server.
 * Berjangkar selalu mulai dari kebenaran server, lalu bergerak maju; setiap
 * polling menambatkan ulang.
 */
import type { RouteJourney } from "./supplier-routes";

/** Titik tambat: `progress` server + kapan data itu diterima peramban. */
export type JangkarTruk = { progress: number; at: number };

/** Batasi ke [0, 1]; nilai aneh (NaN) dianggap tidak bergerak. */
function jepit(nilai: number): number {
  if (!Number.isFinite(nilai)) return 0;
  return Math.min(1, Math.max(0, nilai));
}

export function fraksiBerjalan(
  journey: RouteJourney | null | undefined,
  jangkar: JangkarTruk | null | undefined,
  nowMs: number
): number {
  const dariServer = jepit(journey?.progress ?? jangkar?.progress ?? 0);
  if (!jangkar) return dariServer;
  const durasiMenit = journey?.travelMin ?? null;
  if (!durasiMenit || durasiMenit <= 0) return jepit(jangkar.progress);
  const lewatMs = nowMs - jangkar.at;
  if (!Number.isFinite(lewatMs) || lewatMs <= 0) return jepit(jangkar.progress);
  return jepit(jangkar.progress + lewatMs / (durasiMenit * 60_000));
}

/**
 * Durasi ANIMASI satu perjalanan di peta (demo jaman sekarang).
 *
 * Kenapa ada: `fraksiBerjalan` memajukan mobil pada laju NYATA. Untuk rute
 * 70 menit itu 1/4200 per detik — di layar mobil tampak diam, dan juri tidak
 * melihat ada yang sedang berjalan. Angka estimasi (waktu tempuh, ETA) tetap
 * apa adanya; hanya POSISI ikon di peta yang dipentaskan lebih cepat, dan
 * setiap kiriman menuntaskan jalurnya dalam ≤ 45 detik nyata.
 */
export const DURASI_ANIMASI_MS = 45_000;

/**
 * Fraksi posisi ikon versi ANIMASI: maju dari titik tambat menuju ujung jalur
 * dan tiba di sana tepat setelah `durasiMs`.
 *
 * Kontrak:
 * - mulai dari `progress` server (tidak pernah menghitung dari jam dinding);
 * - monoton — angka server yang menyusul tidak memundurkan ikon;
 * - tidak pernah melewati 1;
 * - tanpa jangkar/durasi aneh: pakai angka server apa adanya.
 */
export function fraksiAnimasi(
  journey: RouteJourney | null | undefined,
  awal: JangkarTruk | null | undefined,
  nowMs: number,
  durasiMs: number = DURASI_ANIMASI_MS
): number {
  const server = jepit(journey?.progress ?? awal?.progress ?? 0);
  if (!awal) return server;
  const dasar = jepit(awal.progress);
  const lewatMs = nowMs - awal.at;
  if (!Number.isFinite(lewatMs) || lewatMs <= 0) return Math.max(dasar, server);
  if (!Number.isFinite(durasiMs) || durasiMs <= 0) return Math.max(dasar, server);
  // Laju animasi dihitung dari titik tambat, TIDAK ditambahkan lagi ke angka
  // server — kalau ditambahkan, satu pembaruan polling membuat ikon melompat
  // dua kali lebih jauh. Angka server hanya dipakai sebagai LANTAI, supaya
  // ikon tidak pernah tertinggal di belakang kenyataan.
  const animasi = dasar + (lewatMs / durasiMs) * (1 - dasar);
  return jepit(Math.max(animasi, server));
}
