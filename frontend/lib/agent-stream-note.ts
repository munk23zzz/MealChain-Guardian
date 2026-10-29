// Satu kalimat untuk kanal log yang tertutup sebelum putaran selesai.
//
// Kenapa dipisah dari komponen: keputusannya kecil tapi mudah salah — kalau
// terlalu rajin, setiap putaran yang BERHASIL pun diberi peringatan; kalau
// terlalu malas, terminal berhenti diam-diam dan operator mengira putaran masih
// berjalan. Fungsi murni = keputusan ini bisa diuji tanpa memasang DOM.
//
// Keadaan yang TIDAK perlu catatan:
// - `dibatalkan`: pemanggil sendiri menutup kanal setelah POST selesai — normal.
// - `galatTercatat`: pesan galatnya sudah tampil; menambah kalimat kedua hanya
//   mengubur yang pertama.

export function catatanAliranPutus(opsi: {
  dibatalkan: boolean;
  galatTercatat: boolean;
}): string | null {
  if (opsi.dibatalkan || opsi.galatTercatat) return null;
  return "kanal log ditutup sebelum putaran selesai — langkah berikutnya tidak tersiar";
}
