/**
 * Kapan petunjuk "Geser tabel ke samping" perlu tampil.
 *
 * Dipisah dari komponen supaya keputusannya bisa diuji tanpa DOM: yang menentukan
 * adalah LUAPAN NYATA (`scrollWidth` vs `clientWidth`), bukan lebar layar. Ambang
 * lebar (dulu `max-width: 640px`, sempat 900px) terbukti bocor — tabel "Daftar
 * pemasok" butuh wadah >= 879 px, sehingga pada 901–1150 px tabel masih bisa digeser
 * tanpa petunjuk apa pun.
 */

/** Wadah yang bisa diukur peramban (elemen apa pun dengan dua properti ini). */
export type WadahTerukur = {
  clientWidth: number;
  scrollWidth: number;
};

/**
 * Toleransi 1 px: peramban sering melaporkan selisih sub-piksel walau tabel sudah pas,
 * dan petunjuk yang muncul tanpa tabel yang bisa digeser justru bising.
 */
export const TOLERANSI_PX = 1;

export function perluGeser(wadah: WadahTerukur | null | undefined): boolean {
  if (!wadah) return false;
  return wadah.scrollWidth - wadah.clientWidth > TOLERANSI_PX;
}
