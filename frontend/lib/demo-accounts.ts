// Akun demo untuk layar login.
//
// Kenapa lewat API, bukan ditulis di sini: kata sandi tidak boleh ikut ke bundel
// klien. Backend hanya mengirimkannya ketika instalasi menyatakan `DEMO_MODE`
// aktif (`GET /auth/demo-accounts`); di mode lain daftar kosong dan tombol demo
// tetap bisa mengisi email saja.

import { request } from "./api";

export type AkunDemo = {
  label: string;
  email: string;
  role: string;
  grup?: "utama" | "kota";
  password?: string;
};

/** Cadangan tanpa sandi: dipakai bila endpoint demo tidak tersedia/mati. */
export const AKUN_DEMO_CADANGAN: AkunDemo[] = [
  { label: "SPPG Head", email: "sppg.head@demo.local", role: "sppg_head", grup: "utama" },
  { label: "Nutritionist", email: "sppg.nutritionist@demo.local", role: "sppg_nutritionist", grup: "utama" },
  { label: "BGN Monitor", email: "bgn.monitor@demo.local", role: "bgn_monitor", grup: "utama" },
  { label: "Kepala Bandung", email: "sppg.head.bandung@demo.local", role: "sppg_head", grup: "kota" },
  { label: "Gizi Bandung", email: "sppg.nutritionist.bandung@demo.local", role: "sppg_nutritionist", grup: "kota" },
  { label: "Kepala Surabaya", email: "sppg.head.surabaya@demo.local", role: "sppg_head", grup: "kota" },
  { label: "Gizi Surabaya", email: "sppg.nutritionist.surabaya@demo.local", role: "sppg_nutritionist", grup: "kota" },
];

/** Pisahkan tombol demo utama dan approver kota (dua baris di layar login). */
export function kelompokkanAkun(akun: AkunDemo[]): { utama: AkunDemo[]; kota: AkunDemo[] } {
  const utama: AkunDemo[] = [];
  const kota: AkunDemo[] = [];
  for (const satu of akun) {
    (satu.grup === "kota" ? kota : utama).push(satu);
  }
  return { utama, kota };
}

/**
 * Ambil daftar akun demo (lengkap dengan sandi bila `DEMO_MODE` aktif).
 * Tidak pernah melempar: kegagalan jaringan/mode non-demo → daftar cadangan
 * tanpa sandi, supaya layar login tetap bisa dipakai.
 */
export async function muatAkunDemo(): Promise<AkunDemo[]> {
  try {
    const data = await request("/auth/demo-accounts", { method: "GET" });
    const akun = Array.isArray(data?.accounts) ? (data.accounts as AkunDemo[]) : [];
    if (data?.enabled === true && akun.length > 0) return akun;
  } catch {
    // Mode non-demo atau backend belum siap: jatuh ke cadangan.
  }
  return AKUN_DEMO_CADANGAN;
}
