/**
 * Berapa baris yang dipakai daftar pil "Pilih kiriman".
 *
 * Dipisah dari komponen supaya bisa diuji tanpa tata letak sungguhan: yang
 * dihitung hanya `offsetTop` anak-anak — anak dengan `offsetTop` sama berada di
 * baris yang sama.
 */
export function jumlahBaris(offsetTops: readonly number[]): number {
  if (offsetTops.length === 0) return 0;
  return new Set(offsetTops).size;
}

/**
 * Tombol buka-tutup hanya perlu bila daftar memakai LEBIH DARI SATU baris
 * (permintaan pemilik 20 Okt 2026). Daftar satu baris tidak butuh segitiga:
 * tombol yang tidak mengubah apa pun hanya menambah keramaian.
 */
export function perluTombolTutup(offsetTops: readonly number[]): boolean {
  return jumlahBaris(offsetTops) > 1;
}
