// Kontrak murni: KAPAN petunjuk "Geser tabel ke samping" perlu tampil.
//
// Alasan (16 Okt 2026, lanjutan Fase 12c): ambang lebar layar hanyalah PROKSI dari
// "tabel benar-benar meluap". Bukti ukur — tabel "Daftar pemasok" (7 kolom) butuh
// wadah ≥ 879 px, tetapi pada 1100 px wadahnya cuma 766 px: tabel bisa digeser
// tanpa petunjuk. Karena itu keputusan dipindah ke pengukuran luapan nyata
// (scrollWidth vs clientWidth), bukan angka ambang.
import { describe, expect, it } from "vitest";

import { perluGeser } from "../lib/scroll-hint";

describe("perluGeser — luapan nyata, bukan ambang lebar", () => {
  it("true saat tabel lebih lebar dari wadahnya", () => {
    expect(perluGeser({ clientWidth: 690, scrollWidth: 879 })).toBe(true);
  });

  it("false saat tabel pas di wadahnya", () => {
    expect(perluGeser({ clientWidth: 1106, scrollWidth: 1106 })).toBe(false);
  });

  it("mengabaikan selisih 1 px (pembulatan sub-piksel peramban)", () => {
    expect(perluGeser({ clientWidth: 879, scrollWidth: 880 })).toBe(false);
    expect(perluGeser({ clientWidth: 879, scrollWidth: 881 })).toBe(true);
  });

  it("false saat wadahnya belum ada — bukan menebak perlu", () => {
    expect(perluGeser(null)).toBe(false);
    expect(perluGeser(undefined)).toBe(false);
  });
});
