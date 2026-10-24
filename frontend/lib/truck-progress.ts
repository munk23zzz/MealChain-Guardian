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
