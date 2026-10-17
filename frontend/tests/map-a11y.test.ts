/**
 * K3 (riset 7b-3): padanan TEKS untuk isi peta.
 *
 * Alasan: penanda peta tidak masuk urutan Tab, sedangkan daftar teks lokasi
 * dimatikan di Overview (`showStatusList={false}`). Tanpa padanan teks, pembaca
 * layar tidak punya satu pun cara mengetahui isi peta.
 *
 * Batas yang dijaga (dari memo 7b-3): daftar ini TIDAK boleh berubah menjadi
 * tabel "Pasokan / Kebutuhan" — tabel itu sudah dihapus atas permintaan pemilik.
 * Karena itu bentuknya satu baris ringkas + daftar sr-only dari data yang sama.
 */
import { describe, expect, it } from "vitest";

import { penandaPeta, ringkasPenanda } from "../lib/map-a11y";

const LOKASI = [
  {
    location: "Jakarta",
    status: "shortage",
    supply_kg: 314.2,
    demand_kg: 1080,
    shortage_kg: 765.8,
    surplus_kg: 0,
  },
  { location: "Medan", status: "shortage", shortage_kg: 80, supply_kg: 100, demand_kg: 180 },
  { location: "Bandung", status: "surplus", surplus_kg: 120, shortage_kg: 0, supply_kg: 220, demand_kg: 100 },
  { location: "Bogor", status: "balanced", surplus_kg: 0, shortage_kg: 0 },
];

describe("penandaPeta", () => {
  it("memberi satu baris ringkas per lokasi, memakai bahasa pengguna", () => {
    const hasil = penandaPeta(LOKASI);
    expect(hasil.map((p) => p.nama)).toEqual(["Jakarta", "Medan", "Bandung", "Bogor"]);
    expect(hasil[0].ringkas).toBe("kurang 765,8 kg");
    expect(hasil[2].ringkas).toBe("lebih 120 kg");
    expect(hasil[3].ringkas).toBe("seimbang");
  });

  it("mengurutkan menurut kepentingan: shortage terbesar dulu, seimbang terakhir", () => {
    const hasil = penandaPeta(LOKASI);
    expect(hasil.map((p) => p.status)).toEqual([
      "shortage",
      "shortage",
      "surplus",
      "balanced",
    ]);
    expect(hasil[0].nama).toBe("Jakarta"); // 765,8 > 80
  });

  it("membaca untuk pembaca layar dengan status dan selisih, bukan warna", () => {
    const hasil = penandaPeta(LOKASI);
    expect(hasil[0].aria).toBe("Jakarta — Shortage, kurang 765,8 kg");
  });

  it("mengabaikan baris tanpa nama dan tidak melempar untuk masukan kosong", () => {
    expect(penandaPeta(null)).toEqual([]);
    expect(
      penandaPeta([{ location: "  ", status: "shortage" }, { location: "Bogor", status: "balanced" }])
        .map((p) => p.nama)
    ).toEqual(["Bogor"]);
  });
});

describe("ringkasPenanda", () => {
  it("menampilkan maksimal N penanda lalu menyebut sisaannya", () => {
    expect(ringkasPenanda(penandaPeta(LOKASI), 3)).toBe(
      "Jakarta kurang 765,8 kg · Medan kurang 80 kg · Bandung lebih 120 kg · +1 lokasi lain"
    );
  });

  it("tidak menambah sisaan bila semuanya sudah tampil", () => {
    const dua = penandaPeta(LOKASI).slice(0, 2);
    expect(ringkasPenanda(dua, 3)).toBe("Jakarta kurang 765,8 kg · Medan kurang 80 kg");
  });

  it("mengembalikan teks kosong untuk daftar kosong", () => {
    expect(ringkasPenanda([], 3)).toBe("");
  });
});
