/**
 * Cakupan lokasi di panel chaos (Ruling 2026-10-14).
 *
 * Yang dikunci ruling adalah LOKASI TUJUAN keputusan ("SPPG siapa yang
 * menerima"), bukan lokasi batch. Karena itu panel ini:
 *  - mengirim `target_location_id` = lokasi SPPG pemakai (dari /auth/me),
 *    bukan lokasi batch seperti sebelumnya;
 *  - tetap menampilkan batch dari lokasi lain — batch adalah data sisi SUMBER
 *    (lokasi asal pasokan) dan justru skenarionya: pasokan dari luar gagal,
 *    SPPG bereaksi.
 *
 * Dulu panel mengirim lokasi batch sebagai target; setelah cakupan ditegakkan
 * server, itu akan dibalas 403 untuk batch luar dan keputusannya pun bukan
 * milik SPPG pemakai. Logika murni di modul ini supaya bisa diuji tanpa DOM.
 */

import { safetyLabel } from "./bahasa";

export const MISSING_LOCATION_REASON =
  "Lokasi SPPG Anda belum terbaca dari identitas server (/auth/me). " +
  "Muat ulang halaman setelah login — Event 3 butuh lokasi tujuan yang jelas.";

export type BatchLike = {
  id?: string;
  commodity?: string;
  location?: string;
  location_id?: string | null;
  quantity_kg?: number | string;
  safety_status?: string;
};

/** Lokasi tujuan event = SPPG pemakai. String kosong bila belum diketahui. */
export function resolveEventTarget(ownLocationId?: string | null): string {
  return ownLocationId ? String(ownLocationId) : "";
}

/** Alasan tombol picu tidak tersedia; null = boleh dipicu. */
export function blockedReason(ownLocationId?: string | null): string | null {
  return resolveEventTarget(ownLocationId) ? null : MISSING_LOCATION_REASON;
}

/**
 * Label batch. Lokasi batch ditulis apa adanya (sisi sumber) — batch dari
 * SPPG lain tetap boleh dipilih, jadi TIDAK ada penanda "tidak bisa dipicu".
 */
export function batchLabel(batch: BatchLike): string {
  return [
    batch.commodity,
    batch.location,
    `${batch.quantity_kg} kg`,
    // Status keamanan batch dulu tampil "pass"/"fail" (enum Inggris) di opsi
    // pilihan skenario. safetyLabel = modul terjemahan yang sama dengan halaman
    // keamanan pangan, jadi satu status tidak punya dua nama.
    safetyLabel(batch.safety_status),
  ]
    .filter((part) => part !== undefined && part !== null && part !== "")
    .join(" · ");
}

/** Keterangan tujuan keputusan, supaya operator tahu ke mana hasilnya masuk. */
export function eventTargetNote(
  ownLocationId?: string | null,
  ownLocationName?: string | null
): string {
  if (!resolveEventTarget(ownLocationId)) {
    return "Lokasi tujuan belum diketahui — event tidak bisa dijalankan.";
  }
  return `Keputusan dari event ini menyasar SPPG Anda${
    ownLocationName ? ` (${ownLocationName})` : ""
  }. Batch boleh berasal dari lokasi sumber mana pun.`;
}
