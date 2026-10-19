/**
 * Pencarian "Daftar pemasok" (permintaan pemilik 19 Okt 2026).
 *
 * Menyaring DAFTAR YANG SUDAH DIMUAT (klien) — bukan memanggil server: payload
 * `GET /suppliers` sudah memuat seluruh pemasok dalam cakupan peran, jadi
 * pencarian tidak boleh menambah permintaan jaringan atau mengubah angka di
 * kartu Ringkasan (angka itu tetap dihitung dari daftar penuh).
 *
 * Aturan yang dipakai (dipaku tests/supplier-search.test.ts):
 *   1. kueri kosong / hanya spasi → daftar asli dikembalikan apa adanya
 *      (referensi sama, supaya tidak memicu render ulang);
 *   2. pencarian tanpa peduli huruf besar-kecil dan tanpa peduli aksen;
 *   3. beberapa kata = DAN: setiap kata harus cocok di salah satu kolom;
 *   4. kolom yang dicari: nama, hub, komoditas, sertifikasi;
 *   5. urutan asli dipertahankan — pencarian menyaring, tidak mengurutkan ulang.
 */

import type { SupplierDirectoryRow } from "./suppliers-board";

/** Buang aksen & huruf besar supaya "Café" cocok dengan "cafe". */
function normalisasi(teks: string): string {
  return teks
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

/** Kata-kata pencarian yang sudah dinormalisasi. */
export function tokens(kueri: string): string[] {
  return normalisasi(kueri).split(/\s+/).filter(Boolean);
}

function kolomTercari(row: SupplierDirectoryRow): string {
  return normalisasi(
    [row.name, row.hub, row.commodity, row.certification].filter(Boolean).join(" · ")
  );
}

/** Saring daftar pemasok dengan kueri bebas. */
export function searchSuppliers(
  rows: SupplierDirectoryRow[],
  kueri: string
): SupplierDirectoryRow[] {
  const kata = tokens(kueri);
  if (kata.length === 0) return rows;
  return rows.filter((row) => {
    const kolom = kolomTercari(row);
    return kata.every((k) => kolom.includes(k));
  });
}
