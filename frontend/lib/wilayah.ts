/**
 * Kode wilayah untuk TAMPILAN (permintaan pemilik 19 Okt 2026: "nama daerah
 * disingkat, contoh Jakarta → JKT").
 *
 * Kenapa peta kode tinggal di klien, bukan diubah di database:
 * `locations.name` adalah KUNCI IDENTITAS yang dipakai di mana-mana — UUID5
 * seed, matriks jarak `core/logistics.py`, cakupan per peran, filter
 * `?location=`, dan ratusan asersi tes. Mengganti nilainya menjadi "JKT" akan
 * memutus semua itu demi perubahan yang sifatnya kosmetik. Jadi data tetap
 * menyimpan nama resmi, dan YANG DILIHAT operator memakai kode pendek.
 *
 * Aturan: tidak ada tebakan. Nama yang tidak dikenal dikembalikan apa adanya
 * (lebih baik "Kota Baru" daripada kode karangan), dan nilai kosong menjadi "—".
 */

const PETA: Record<string, string> = {
  jakarta: "JKT",
  bogor: "BGR",
  cianjur: "CJR",
  bandung: "BDG",
  semarang: "SMG",
  yogyakarta: "YOG",
  surabaya: "SBY",
  makassar: "MKS",
  palembang: "PLM",
  medan: "MDN",
};

/** Kode pendek satu nama wilayah; nama tak dikenal dikembalikan apa adanya. */
export function kodeWilayah(nama: string | null | undefined): string {
  if (nama === null || nama === undefined) return "—";
  const bersih = String(nama).trim();
  if (!bersih) return "—";
  return PETA[bersih.toLowerCase()] ?? bersih;
}

/** "JKT" + wilayah administratif, dipakai saat ruang cukup (mis. tooltip). */
export function kodeDanWilayah(
  nama: string | null | undefined,
  region: string | null | undefined
): string {
  const kode = kodeWilayah(nama);
  const wilayah = region ? String(region).trim() : "";
  return wilayah ? `${kode} · ${wilayah}` : kode;
}
