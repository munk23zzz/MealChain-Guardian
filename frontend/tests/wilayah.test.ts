import { describe, expect, it } from "vitest";

import { kodeDanWilayah, kodeWilayah } from "../lib/wilayah";

describe("kodeWilayah", () => {
  it("memetakan sepuluh kota demo ke kode pendek", () => {
    expect(kodeWilayah("Jakarta")).toBe("JKT");
    expect(kodeWilayah("Bogor")).toBe("BGR");
    expect(kodeWilayah("Cianjur")).toBe("CJR");
    expect(kodeWilayah("Bandung")).toBe("BDG");
    expect(kodeWilayah("Semarang")).toBe("SMG");
    expect(kodeWilayah("Yogyakarta")).toBe("YOG");
    expect(kodeWilayah("Surabaya")).toBe("SBY");
    expect(kodeWilayah("Makassar")).toBe("MKS");
    expect(kodeWilayah("Palembang")).toBe("PLM");
    expect(kodeWilayah("Medan")).toBe("MDN");
  });

  it("menerima huruf besar/kecil dan spasi di tepi", () => {
    expect(kodeWilayah("  jAkArTa ")).toBe("JKT");
  });

  it("tidak mengarang kode untuk nama tak dikenal", () => {
    expect(kodeWilayah("Kota Baru")).toBe("Kota Baru");
    expect(kodeWilayah(null)).toBe("—");
    expect(kodeWilayah("   ")).toBe("—");
  });
});

describe("kodeDanWilayah", () => {
  it("menyertakan wilayah administratif bila ada", () => {
    expect(kodeDanWilayah("Jakarta", "DKI Jakarta")).toBe("JKT · DKI Jakarta");
    expect(kodeDanWilayah("Cianjur", null)).toBe("CJR");
  });
});
