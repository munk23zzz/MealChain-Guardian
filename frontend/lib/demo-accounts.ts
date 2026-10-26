// Akun demo untuk layar login.
//
// Kenapa TIDAK lewat API lagi (26 Okt 2026): `GET /auth/demo-accounts` kini
// menuntut Bearer token ber-peran admin (`bgn_monitor` — satu-satunya peran
// admin di skema; lihat `backend/app/core/admin_rules.py`). Halaman login
// bersifat publik dan tidak punya token, jadi memanggil endpoint itu dari sini
// hanya menghasilkan 401 lalu pesan error. Daftar di bawah cukup untuk mengisi
// email; kata sandi diketik operator dan TIDAK pernah ditanam di bundel klien.

export type AkunDemo = {
  label: string;
  email: string;
  role: string;
  grup?: "utama" | "kota";
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
