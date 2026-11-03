/**
 * Menggabungkan kelas pin peta TANPA menghapus kelas milik MapLibre.
 *
 * Kenapa modul ini ada (bug zoom 2026-10-18): `refreshPin` dan
 * `refreshSupplierPin` dulu menulis `el.className = ...` secara utuh. Itu
 * menghapus kelas yang dipasang MapLibre sendiri saat marker dibuat
 * (`maplibregl-marker`, `maplibregl-marker-anchor-*`) — dan `maplibregl-marker`
 * itulah yang memberi `position: absolute`. Tanpa kelas itu, `.map-pin` dengan
 * `position: relative` menang, penanda masuk alur normal di dalam wadah kanvas,
 * lalu posisinya menjadi "transform + offset alur". Offset alur berubah setiap
 * kali penanda lain ditambah/dibuang (pin pemasok muncul di zoom 6, nama di
 * zoom 8, gelembung klaster di tampilan jaringan) — hasilnya pin terlihat
 * bergeser dari koordinatnya saat zoom in/out (terukur sampai ±192 px di
 * aplikasi hidup).
 *
 * Aturannya: kelas milik aplikasi selalu berawalan `map-pin` (map-pin,
 * map-pin-surplus, map-pin-active, map-pin-supplier, map-pin-supplier-low,
 * map-pin-supplier-compact, dst). Kelas di luar awalan itu milik pustaka dan
 * WAJIB dipertahankan apa adanya.
 */

/** Awalan kelas yang dimiliki aplikasi (boleh diganti saat pin disegarkan). */
export const AWALAN_KELAS_PIN = "map-pin";

/**
 * Hasil = kelas "asing" (mis. maplibregl-marker) yang sudah ada, diikuti kelas
 * pin yang baru. Kelas pin lama yang tidak ada lagi di `baru` dibuang supaya
 * nada lama tidak menumpuk dengan nada baru.
 */
export function gabungKelasPin(lama: string, baru: string): string {
  const kelasBaru = baru.split(/\s+/).filter(Boolean);
  const kelasAsing = lama
    .split(/\s+/)
    .filter((kelas) => kelas && !kelas.startsWith(AWALAN_KELAS_PIN));
  return Array.from(new Set([...kelasAsing, ...kelasBaru])).join(" ");
}
