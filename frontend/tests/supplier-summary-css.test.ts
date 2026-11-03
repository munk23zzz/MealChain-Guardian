// Kontrak CSS kartu Ringkasan — KPI strip (29 Okt 2026).
//
// Yang mudah rusak tanpa terlihat: aturan lepas ke seluruh aplikasi, radius
// mentah di luar skala token, dan gaya tombol yang tertinggal dari bentuk lama.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "app", "supplier-summary.css"), "utf8");

function selectorNonMedia(): string[] {
  const tanpaKomentar = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const tanpaMedia = tanpaKomentar.replace(/@media[^{]+\{(?:[^{}]*\{[^}]*\})*[^}]*\}/g, "");
  return [...tanpaMedia.matchAll(/([^{}]+)\{/g)]
    .map((m) => m[1].trim())
    .filter((s) => s && !s.startsWith("@"));
}

describe("CSS ringkasan pemasok (KPI strip)", () => {
  it("setiap selektor di-scope ke .supplier-summary", () => {
    expect(selectorNonMedia().filter((s) => !s.startsWith(".supplier-summary"))).toEqual([]);
  });

  it("tidak memakai !important", () => {
    expect(css).not.toContain("!important");
  });

  it("radius hanya dari skala token (strip tidak memakai pil/radius mentah)", () => {
    const mentah = [...css.matchAll(/border-radius:\s*([^;]+);/g)]
      .map((m) => m[1].trim())
      .filter((v) => !v.startsWith("var(--radius"));
    expect(mentah).toEqual([]);
  });

  it("tidak ada sisa gaya tombol/kontrol dari bentuk lama", () => {
    for (const mati of ["summary-lihat", "summary-sebaran", "summary-status", "summary-tile", "cursor: pointer"]) {
      expect(css).not.toContain(mati);
    }
  });

  it("angka memakai token ukuran metrik, bukan piksel mentah", () => {
    expect(css).toMatch(/\.summary-kpi-value\s*\{[^}]*font-size:\s*var\(--fs-\d\)/);
  });

  it("kolom pertama tanpa garis pemisah kiri", () => {
    expect(css).toContain(".supplier-summary .summary-kpi-item:first-child");
  });

  // S2 (29 Okt 2026): satu angka dipromosikan. Kontraknya: promosi terjadi
  // lewat atribut data-lead, ukurannya memakai token (bukan piksel mentah),
  // dan di layar sempit angka itu mengambil satu baris penuh.
  it("angka yang dipromosikan memakai token hero, bukan piksel", () => {
    expect(css).toMatch(
      /\.summary-kpi-item\[data-lead="true"\] \.summary-kpi-value\s*\{[^}]*font-size:\s*var\(--fs-8\)/
    );
  });

  it("di layar sempit angka yang dipromosikan selebar baris", () => {
    expect(css).toMatch(
      /@media \(max-width: 720px\)[\s\S]*\.summary-kpi-item\[data-lead="true"\][^{]*\{[^}]*flex-basis:\s*100%/
    );
  });
});
