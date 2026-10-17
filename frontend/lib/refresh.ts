/**
 * Penyegaran terpusat setelah TULIS (permintaan pemilik: "ketika saya melakukan
 * sesuatu pastikan semuanya berjalan sesuai").
 *
 * Masalah yang diselesaikan: setiap komponen dulu me-refetch query-nya SENDIRI
 * sesudah aksi. Akibatnya panel yang tidak disebut di callback itu tetap
 * menampilkan angka lama — terukur pada peta setelah "Segarkan ke hari ini",
 * dan itu hanya satu contoh dari kelas bug yang sama. Tidak ada satu pun
 * `invalidateQueries` di repo sebelum modul ini.
 *
 * Aturannya sekarang satu: SETIAP permintaan tulis yang berhasil menyegarkan
 * SELURUH cache data. Kecil, tidak bisa lupa dipanggil per komponen, dan
 * perilakunya bisa diuji tanpa DOM.
 */

export type Penyegar = () => void;

let penyegar: Penyegar | null = null;

/** Dipanggil sekali oleh provider React Query; `null` = lepaskan. */
export function daftarkanPenyegar(fn: Penyegar | null): void {
  penyegar = fn;
}

/** Segarkan semua data. Aman dipanggil walau belum ada yang mendaftar. */
export function segarkanSetelahTulis(): void {
  penyegar?.();
}

/**
 * Apakah metode HTTP ini MENGUBAH data server?
 *
 * GET/HEAD/OPTIONS tidak — menyegarkan cache sesudahnya hanya membuang kuota.
 * Metode tak dikenal diperlakukan sebagai tulis? TIDAK: lebih baik tidak
 * menyegarkan daripada memicu badai refetch dari permintaan yang tidak jelas.
 */
export function metodeMenulis(method?: string | null): boolean {
  const m = (method ?? "GET").toUpperCase();
  return m === "POST" || m === "PUT" || m === "PATCH" || m === "DELETE";
}
