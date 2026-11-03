// Akun demo untuk layar login.
//
// Sejarah singkat (supaya tidak bolak-balik lagi):
// 1. Awalnya kata sandi ditanam di bundel klien → ditutup (SEC-02).
// 2. Lalu diambil dari `GET /auth/demo-accounts` → endpoint itu kini menuntut
//    Bearer token `bgn_monitor`, sedangkan halaman login publik tidak punya token.
// 3. Sekarang (27 Okt 2026): pintu khusus `GET /auth/demo-login`, TANPA token,
//    tetapi hanya terbuka bila `DEMO_MODE` DAN `DEMO_LOGIN_AUTOFILL` aktif.
//    Di instalasi nyata keduanya mati → `{enabled:false}`, tombol hanya mengisi
//    email. Kata sandi tetap tidak pernah ditanam di bundel.

import { request } from "./api";

export type AkunDemo = {
  label: string;
  email: string;
  role: string;
  grup?: "utama" | "kota";
  password?: string;
};

/** Daftar akun demo tanpa sandi — satu-satunya sumber tombol di layar login. */
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
 * Ambil daftar akun demo (lengkap dengan sandi bila server mengizinkan).
 * Tidak pernah melempar: autofill mati atau backend tak terjangkau → daftar
 * cadangan tanpa sandi, supaya layar login tetap bisa dipakai (email saja).
 */
export async function muatAkunDemo(): Promise<AkunDemo[]> {
  try {
    const data = await request("/auth/demo-login", { method: "GET" });
    const akun = Array.isArray(data?.accounts) ? (data.accounts as AkunDemo[]) : [];
    if (data?.enabled === true && akun.length > 0) return akun;
  } catch {
    // Token tidak ada / autofill mati / backend belum siap: pakai cadangan.
  }
  return AKUN_DEMO_CADANGAN;
}

/**
 * Sandi untuk satu email demo, bila server memberikannya.
 *
 * `null` = sandi belum/tidak tersedia (autofill mati, permintaan belum selesai,
 * atau email tidak ada di daftar). Dipakai layar login untuk mengisi kolom sandi
 * begitu daftar bersandi tiba — operator yang menekan tombol demo lebih dulu
 * tidak lagi berakhir dengan kolom kosong dan galat 401.
 */
export function passwordDemoUntuk(akun: AkunDemo[], email: string): string | null {
  return akun.find((satu) => satu.email === email)?.password ?? null;
}

/**
 * Apakah server mengirim sandi demo sama sekali.
 *
 * `false` berarti tombol demo hanya mengisi email; layar login WAJIB
 * mengatakannya (bukan membiarkan kolom sandi kosong tanpa penjelasan).
 */
export function sandiDemoTersedia(akun: AkunDemo[]): boolean {
  return akun.some((satu) => Boolean(satu.password));
}
