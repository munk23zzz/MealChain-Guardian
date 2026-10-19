import { describe, expect, it } from "vitest";

import { searchSuppliers, tokens } from "../lib/supplier-search";
import type { SupplierDirectoryRow } from "../lib/suppliers-board";

function baris(isi: Partial<SupplierDirectoryRow> & { name: string }): SupplierDirectoryRow {
  return {
    id: isi.name,
    hub: "Cianjur",
    commodity: "wortel",
    reliability: 0.9,
    reliabilityLabel: "90%",
    reliabilityMeter: null,
    certification: "HACCP",
    coordinates: "-6,8240 / 107,1636",
    distanceKm: 12,
    distanceLabel: "12 km",
    excluded: false,
    excludedScopes: [],
    shipping: null,
    shippingLabel: "—",
    ...isi,
  };
}

const DAFTAR = [
  baris({ name: "Prima Ayam Sejahtera Tangerang", hub: "Tangerang", commodity: "ayam" }),
  baris({ name: "CV Telur Ciamur Bandung", hub: "Bandung", commodity: "telur" }),
  baris({ name: "Sayur Segar Puncak", hub: "Cianjur", commodity: "wortel", certification: "Tidak bersertifikat" }),
  baris({ name: "UD Beras Johar Semarang", hub: "Semarang", commodity: "beras" }),
];

describe("tokens", () => {
  it("memecah kueri menjadi kata, huruf kecil, tanpa aksen", () => {
    expect(tokens("  Ayam   PRIMA ")).toEqual(["ayam", "prima"]);
    expect(tokens("Café Résumé")).toEqual(["cafe", "resume"]);
    expect(tokens("")).toEqual([]);
    expect(tokens("   ")).toEqual([]);
  });
});

describe("searchSuppliers", () => {
  it("kueri kosong mengembalikan daftar apa adanya (referensi sama)", () => {
    expect(searchSuppliers(DAFTAR, "")).toBe(DAFTAR);
    expect(searchSuppliers(DAFTAR, "   ")).toBe(DAFTAR);
  });

  it("mencari pada nama tanpa peduli huruf besar/kecil", () => {
    expect(searchSuppliers(DAFTAR, "prima").map((r) => r.name)).toEqual([
      "Prima Ayam Sejahtera Tangerang",
    ]);
    expect(searchSuppliers(DAFTAR, "SEGAR").map((r) => r.name)).toEqual(["Sayur Segar Puncak"]);
  });

  it("mencari juga pada hub, komoditas, dan sertifikasi", () => {
    expect(searchSuppliers(DAFTAR, "bandung").map((r) => r.name)).toEqual(["CV Telur Ciamur Bandung"]);
    expect(searchSuppliers(DAFTAR, "beras").map((r) => r.name)).toEqual(["UD Beras Johar Semarang"]);
    expect(searchSuppliers(DAFTAR, "haccp").map((r) => r.name)).toEqual([
      "Prima Ayam Sejahtera Tangerang",
      "CV Telur Ciamur Bandung",
      "UD Beras Johar Semarang",
    ]);
  });

  it("banyak kata = DAN, bukan ATAU", () => {
    expect(searchSuppliers(DAFTAR, "ayam prima").map((r) => r.name)).toEqual([
      "Prima Ayam Sejahtera Tangerang",
    ]);
    expect(searchSuppliers(DAFTAR, "ayam bandung")).toEqual([]);
  });

  it("tanpa hasil mengembalikan array kosong, bukan seluruh daftar", () => {
    expect(searchSuppliers(DAFTAR, "zzzz")).toEqual([]);
  });

  it("urutan asli dipertahankan dan masukan tidak diubah", () => {
    const hasil = searchSuppliers(DAFTAR, "a");
    expect(hasil.map((r) => r.name)).toEqual(
      DAFTAR.filter((r) => hasil.includes(r)).map((r) => r.name)
    );
    expect(DAFTAR).toHaveLength(4);
  });

  it("tahan terhadap nilai kosong pada kolom yang dicari", () => {
    const ganjil = [baris({ name: "Tanpa Sertifikat", certification: "", commodity: "" })];
    expect(searchSuppliers(ganjil, "sertifikat")).toHaveLength(1);
    expect(searchSuppliers(ganjil, "wortel")).toEqual([]);
  });
});
