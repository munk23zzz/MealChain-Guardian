// Aturan kapan register eksklusi diambil. Dulu pengambilan itu menumpang efek
// sampel yang ber-penjaga `evaluatedKey`, sehingga membuka tab Pemasok setelah
// tab Kualitas Agen membuat /supplier-exclusions tidak pernah dipanggil dan
// kartu register mengklaim "tidak ada eksklusi" padahal datanya belum dimuat.
import { describe, expect, it } from "vitest";

import { shouldLoadExclusions } from "../lib/supplier-exclusions";

describe("shouldLoadExclusions", () => {
  it("tab Pemasok + token → diambil", () => {
    expect(shouldLoadExclusions("suppliers", "tok")).toBe(true);
  });

  it("tab lain → tidak diambil (walau token ada)", () => {
    expect(shouldLoadExclusions("quality", "tok")).toBe(false);
    expect(shouldLoadExclusions("today", "tok")).toBe(false);
  });

  it("tanpa token → tidak diambil", () => {
    expect(shouldLoadExclusions("suppliers", null)).toBe(false);
  });
});
