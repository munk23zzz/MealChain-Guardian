// Panel "Surplus wilayah lain" di samping grafik kecukupan (28 Okt 2026).
//
// Aturan yang dipaku di sini:
// 1. Angka hanya dari server (`GET /surplus/regions`); klien TIDAK menghitung
//    ulang surplus dari peta — peta akun SPPG hanya memuat satu lokasi.
// 2. Tanpa angka = null → dirender "—", BUKAN 0 kg yang seolah terukur.
// 3. Baris rusak (tanpa nama wilayah, kg negatif/bukan angka) dibuang; tidak
//    boleh ada NaN di lebar batang.
// 4. `reason` diterjemahkan menjadi sebab yang bisa dibaca, bukan "kosong".
import { describe, expect, it } from "vitest";

import {
  komoditasKeluarga,
  komoditasTone,
  regionSharePct,
  regionSurplus,
  regionSurplusReason,
  sumberRingkas,
  type RegionSurplusView,
} from "../lib/surplus-regions";

const PAYLOAD = {
  as_of: "2026-10-28T03:00:00+00:00",
  commodities: ["ayam", "beras", "telur", "wortel"],
  excluded_location: "Bandung",
  min_surplus_kg: 150,
  available: true,
  reason: null,
  totals: {
    surplus_kg: 3782.74,
    layak_kg: 3547.89,
    source_locations: 3,
    regions: 2,
    excluded_surplus_kg: 184.81,
    surplus_unmeasured_locations: 0,
  },
  regions: [
    {
      region: "Jawa Barat",
      surplus_kg: 3547.89,
      layak_kg: 3547.89,
      locations: 2,
      by_commodity: [
        { commodity: "beras", surplus_kg: 1572.41 },
        { commodity: "telur", surplus_kg: 1261.09 },
        { commodity: "wortel", surplus_kg: 488.44 },
        { commodity: "ayam", surplus_kg: 225.95 },
      ],
      sources: [
        { location: "Cianjur", surplus_kg: 2689.16, by_commodity: [] },
        { location: "Bogor", surplus_kg: 858.73, by_commodity: [] },
      ],
    },
    {
      region: "DKI Jakarta",
      surplus_kg: 215.4,
      layak_kg: 215.4,
      locations: 1,
      by_commodity: [{ commodity: "wortel", surplus_kg: 215.4 }],
      sources: [{ location: "Jakarta", surplus_kg: 215.4, by_commodity: [] }],
    },
  ],
};

describe("regionSurplus", () => {
  it("membaca agregat wilayah apa adanya dari server", () => {
    const v = regionSurplus(PAYLOAD);
    expect(v.tersedia).toBe(true);
    expect(v.regions.map((r) => r.region)).toEqual(["Jawa Barat", "DKI Jakarta"]);
    expect(v.regions[0].surplusKg).toBeCloseTo(3547.89, 2);
    expect(v.totalKg).toBeCloseTo(3782.74, 2);
    expect(v.layakKg).toBeCloseTo(3547.89, 2);
    expect(v.sourceLocations).toBe(3);
    expect(v.excludedLocation).toBe("Bandung");
    expect(v.excludedKg).toBeCloseTo(184.81, 2);
    expect(v.unmeasured).toBe(0);
    expect(v.minKg).toBe(150);
    expect(v.komoditas).toEqual(["ayam", "beras", "telur", "wortel"]);
    expect(v.kosong).toBe(false);
  });

  it("urutan wilayah dipertahankan menurun (yang terbesar tetap di atas)", () => {
    const v = regionSurplus({
      ...PAYLOAD,
      regions: [PAYLOAD.regions[1], PAYLOAD.regions[0]],
    });
    expect(v.regions.map((r) => r.region)).toEqual(["Jawa Barat", "DKI Jakarta"]);
  });

  it("tanpa angka sama sekali → null (—), bukan 0 kg", () => {
    const v = regionSurplus({
      available: false,
      reason: "tidak_ada_surplus_terukur",
      commodities: ["telur"],
      regions: [],
      totals: { surplus_kg: 0, layak_kg: 0, source_locations: 0, regions: 0 },
    });
    expect(v.tersedia).toBe(false);
    expect(v.totalKg).toBeNull();
    expect(v.layakKg).toBeNull();
    expect(v.sourceLocations).toBeNull();
    expect(v.kosong).toBe(true);
    expect(v.reason).toBe("tidak_ada_surplus_terukur");
  });

  it("payload rusak/kosong tidak pernah menghasilkan NaN", () => {
    for (const rusak of [null, undefined, {}, { regions: "bukan array" }]) {
      const v = regionSurplus(rusak);
      expect(v.regions).toEqual([]);
      expect(v.totalKg).toBeNull();
    }
  });

  it("baris tanpa nama wilayah atau kg tak terpakai dibuang", () => {
    const v = regionSurplus({
      available: true,
      regions: [
        { region: "", surplus_kg: 100 },
        { region: "Sumatera Utara", surplus_kg: "150.5" },
        { region: "Jawa Tengah", surplus_kg: -8 },
        { region: "Jawa Timur", surplus_kg: "bukan angka" },
      ],
      totals: { surplus_kg: 150.5 },
    });
    expect(v.regions.map((r) => r.region)).toEqual(["Sumatera Utara"]);
    expect(v.regions[0].surplusKg).toBeCloseTo(150.5, 2);
  });

  it("wilayah tanpa pecahan komoditas tetap sah (bar satu warna)", () => {
    const v = regionSurplus({
      available: true,
      regions: [{ region: "Bali", surplus_kg: 90, locations: 1 }],
      totals: { surplus_kg: 90 },
    });
    expect(v.regions[0].byCommodity).toEqual([]);
    expect(v.regions[0].locations).toBe(1);
  });
});

describe("pemisahan layak vs kecil", () => {
  it("wilayah tanpa sumber ≥ ambang masuk daftar 'kecil', bukan hilang", () => {
    const v = regionSurplus({
      available: true,
      min_surplus_kg: 150,
      regions: [
        { region: "Jawa Barat", surplus_kg: 3547.89, layak_kg: 3547.89, locations: 2 },
        { region: "Bali", surplus_kg: 90, layak_kg: 0, locations: 1 },
        { region: "Lombok", surplus_kg: 10, layak_kg: 0, locations: 1 },
      ],
      totals: { surplus_kg: 3647.89, layak_kg: 3547.89, source_locations: 4, regions: 3 },
    });
    expect(v.layak.map((r) => r.region)).toEqual(["Jawa Barat"]);
    expect(v.kecil.map((r) => r.region)).toEqual(["Bali", "Lombok"]);
    expect(v.kecilKg).toBeCloseTo(100, 2);
    // Total tetap memuat yang kecil — tidak ada kg yang menguap dari header.
    expect(v.totalKg).toBeCloseTo(3647.89, 2);
  });

  it("tanpa ambang dari server, semua wilayah tampil sebagai baris", () => {
    const v = regionSurplus({
      available: true,
      regions: [
        { region: "Bali", surplus_kg: 90, locations: 1 },
        { region: "Lombok", surplus_kg: 10, locations: 1 },
      ],
      totals: { surplus_kg: 100 },
    });
    expect(v.layak).toHaveLength(2);
    expect(v.kecil).toEqual([]);
    expect(v.kecilKg).toBeNull();
  });
});

describe("regionSharePct", () => {
  it("relatif terhadap wilayah terbesar, dibatasi 100", () => {
    expect(regionSharePct(3547.89, 3547.89)).toBe(100);
    expect(regionSharePct(215.4, 3547.89)).toBeCloseTo(6.07, 1);
    expect(regionSharePct(10_000, 3547.89)).toBe(100);
  });

  it("pembagi nol/bukan angka → 0, bukan NaN", () => {
    expect(regionSharePct(100, 0)).toBe(0);
    expect(regionSharePct(10, Number.NaN)).toBe(0);
  });
});

describe("komoditasTone", () => {
  it("indeks warna stabil mengikuti daftar komoditas dan berputar", () => {
    const daftar = ["ayam", "beras", "telur", "wortel"];
    expect(komoditasTone(daftar, "ayam")).toBe(0);
    expect(komoditasTone(daftar, "telur")).toBe(2);
    expect(komoditasTone(daftar, "wortel")).toBe(3);
    // Nama di luar daftar tetap dapat warna deterministik (tidak acak).
    expect(komoditasTone(daftar, "kacang")).toBe(komoditasTone(daftar, "kacang"));
    expect(komoditasTone([], "kacang")).toBe(0);
  });
});

describe("komoditasKeluarga", () => {
  it("memakai palet identitas yang sama dengan pil komoditas di peta", () => {
    // docs/design.md: telur amber, ayam rose, beras biru, wortel violet.
    expect(komoditasKeluarga("telur")).toBe("amber");
    expect(komoditasKeluarga("ayam")).toBe("rose");
    expect(komoditasKeluarga("beras")).toBe("blue");
    expect(komoditasKeluarga("wortel")).toBe("violet");
  });

  it("tidak peka huruf besar/kecil dan spasi tepi", () => {
    expect(komoditasKeluarga(" Telur ")).toBe("amber");
    expect(komoditasKeluarga("BERAS")).toBe("blue");
  });

  it("mengembalikan null untuk komoditas di luar empat kanonik", () => {
    // Pemanggil lalu jatuh ke indeks urutan (komoditasTone), bukan warna acak.
    expect(komoditasKeluarga("kacang")).toBeNull();
    expect(komoditasKeluarga("")).toBeNull();
  });
});

describe("sumberRingkas", () => {
  it("menyebut lokasi sumber teratas dan sisanya sebagai jumlah", () => {
    const v: RegionSurplusView = regionSurplus(PAYLOAD);
    expect(sumberRingkas(v.regions[0], 2)).toBe("Cianjur, Bogor");
    expect(
      sumberRingkas(
        {
          ...v.regions[0],
          sources: [
            { location: "Cianjur", surplusKg: 10, byCommodity: [] },
            { location: "Bogor", surplusKg: 9, byCommodity: [] },
            { location: "Depok", surplusKg: 8, byCommodity: [] },
          ],
        },
        2
      )
    ).toBe("Cianjur, Bogor +1");
    expect(sumberRingkas({ ...v.regions[0], sources: [] }, 2)).toBe("tanpa nama sumber");
  });
});

describe("regionSurplusReason", () => {
  it("setiap alasan server punya kalimat sebab", () => {
    expect(regionSurplusReason("tidak_ada_surplus_terukur")).toContain("Belum ada lokasi");
    expect(regionSurplusReason("surplus_hanya_di_lokasi_ini")).toContain("lokasi Anda");
    expect(regionSurplusReason("surplus_tanpa_permintaan_tercatat")).toContain(
      "permintaannya belum tercatat"
    );
    expect(regionSurplusReason(null)).toContain("Belum ada surplus");
    expect(regionSurplusReason("kode_baru")).toContain("Belum ada surplus");
  });
});
