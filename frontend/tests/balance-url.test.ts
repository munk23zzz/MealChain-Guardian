// Path/URL pemanggilan detail saldo — satu tempat supaya `as_of` tidak bisa
// lupa dikirim oleh satu pemanggil saja.
//
// Alasan: peta dan panel detail dulu mengambil snapshot pada waktu BERBEDA,
// sehingga angka pasokan/kebutuhan di panel bisa berbeda dari peta untuk
// komoditas dan lokasi yang sama. Sekarang panel detail memakai `as_of` dari
// respons peta (satu snapshot), jadi semua angka yang terlihat di layar
// merujuk ke satu instant data.
import { describe, expect, it } from "vitest";

import { balancePath } from "../lib/balance-url";

describe("balancePath — satu snapshot untuk detail dan peta", () => {
  it("tanpa as_of: path lama tetap dipakai", () => {
    expect(balancePath("Jakarta", "telur")).toBe("/balance/Jakarta/telur");
    expect(balancePath("Jakarta", "telur", null)).toBe("/balance/Jakarta/telur");
    expect(balancePath("Jakarta", "telur", "")).toBe("/balance/Jakarta/telur");
  });

  it("dengan as_of: parameter di-encode, bukan ditempel mentah", () => {
    expect(balancePath("Jakarta", "telur", "2026-10-18T08:00:00Z")).toBe(
      "/balance/Jakarta/telur?as_of=2026-10-18T08%3A00%3A00Z",
    );
  });

  it("nama lokasi/komoditas di-encode", () => {
    expect(balancePath("Jakarta Pusat", "telur")).toBe(
      "/balance/Jakarta%20Pusat/telur",
    );
  });
});
