// Wiring nav "lompat ke bagian" di Overview (20 Okt 2026).
//
// Halaman Overview adalah komponen klien raksasa dengan early-return layar
// login, jadi ia tidak bisa dirender utuh di tes node (tanpa DOM, tanpa token).
// Yang dipaku di sini karena itu batas yang mudah rusak saat halaman disunting:
//
//   1. Halaman memakai komponen bersama + daftar bagian dari lib/section-jump.ts
//      (bukan daftar tautan yang ditulis ulang di JSX).
//   2. Setiap tujuan nav punya tepat satu sasaran ber-id di halaman.
//   3. Sasaran itu memakai kelas `jump-target` (scroll-margin-top supaya tidak
//      mendarat di balik top bar + nav menempel).
//
// Isi daftar (urutan + label per peran) diuji di tests/section-jump.test.tsx.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import { OVERVIEW_SECTION_IDS, overviewSections } from "../lib/section-jump";

const pageSrc = readFileSync("app/page.tsx", "utf8");

describe("Overview — navigasi bagian", () => {
  it("memakai komponen dan daftar bagian bersama", () => {
    expect(pageSrc).toMatch(/import SectionJump from "\.\.\/components\/SectionJump"/);
    expect(pageSrc).toMatch(/overviewSections[^;\n]*from "\.\.\/lib\/section-jump"/);
    expect(pageSrc).toMatch(/<SectionJump[\s\S]{0,160}overviewSections\(/);
  });

  it("tujuan kiriman mengikuti ada-tidaknya kiriman aktif", () => {
    // Kartu kiriman tidak merender apa pun saat daftar kosong; nav tidak boleh
    // menunjuk tempat yang tidak ada.
    expect(pageSrc).toMatch(/hasShipments/);
  });

  it("setiap tujuan punya tepat satu sasaran ber-id", () => {
    for (const { id } of overviewSections({ isApprover: true, hasShipments: true })) {
      expect((pageSrc.match(new RegExp(`id="${id}"`, "g")) ?? []).length).toBe(1);
    }
  });

  it("sasaran nav memakai kelas jump-target", () => {
    for (const { id } of overviewSections({ isApprover: true, hasShipments: true })) {
      expect(pageSrc).toMatch(new RegExp(`className="[^"]*jump-target[^"]*"\\s+id="${id}"`));
    }
  });

  it("jangkar peta tetap yang lama (tautan & uji lain menunjuk id itu)", () => {
    expect(OVERVIEW_SECTION_IDS.peta).toBe("overview-map");
  });
});
