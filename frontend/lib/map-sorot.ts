/** Jembatan antara peta dan daftar lokasi yang dirender DI LUAR peta.
 *
 *  Halaman Overview merender peta dan daftar "Status Lokasi" sebagai dua elemen
 *  bersaudara (daftarnya selebar halaman), sehingga daftar tidak bisa menerima
 *  callback lewat props. Modul kecil ini yang menyambungkannya: peta mendaftarkan
 *  penangan saat dipasang, daftar memanggilnya saat baris diketuk.
 *
 *  Tanpa pendaftaran (mis. halaman lain yang memakai daftar tanpa peta) daftar
 *  tetap dirender statis — bukan tombol yang tidak melakukan apa-apa.
 */

export type PenanganSorot = (nama: string) => void;

let penangan: PenanganSorot | null = null;
const pelanggan = new Set<() => void>();

function beriTahu(): void {
  pelanggan.forEach((dengar) => dengar());
}

/** Daftarkan penangan peta. Mengembalikan fungsi pembatal (dipanggil saat unmount). */
export function daftarkanSorot(fn: PenanganSorot): () => void {
  penangan = fn;
  beriTahu();
  return () => {
    if (penangan === fn) penangan = null;
    beriTahu();
  };
}

/** Apakah ada peta yang siap menerima permintaan sorot. */
export function sorotTersedia(): boolean {
  return penangan !== null;
}

/** Sorot lokasi. Mengembalikan false bila tidak ada peta terdaftar. */
export function sorotLokasiTerenregistrasi(nama: string): boolean {
  if (!penangan) return false;
  penangan(nama);
  return true;
}

/** Berlangganan perubahan ketersediaan (dipakai hook di komponen daftar). */
export function langgananSorot(dengar: () => void): () => void {
  pelanggan.add(dengar);
  return () => {
    pelanggan.delete(dengar);
  };
}

/** Hanya untuk tes: kembalikan modul ke keadaan awal. */
export function resetSorotUntukTes(): void {
  penangan = null;
  pelanggan.clear();
}
