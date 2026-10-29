// Kontrak CSS kartu "Riwayat penerimaan" (Dok 05 §8.5).
//
// Dua cacat nyata yang pernah terjadi dan harus tidak kembali:
//   1. tabel melebar melewati kartu di desktop (1.116 px di bungkus 917 px)
//      sehingga kolom Nilai — alasan kartu ini ada — terpotong di tepi kanan;
//   2. di layar sempit tabel dipaksa fixed sehingga kolom menjadi ±40 px.
// Selain itu: radius hanya dari skala token, dan aturan tidak boleh memakai
// `!important` (pola global berkas ini).

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "app", "supplier-receipts.css"), "utf8");

function block(selector: string, from = 0): string {
  const start = css.indexOf(selector, from);
  if (start < 0) throw new Error(`selektor tidak ditemukan: ${selector}`);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  return css.slice(open + 1, close);
}

describe("CSS riwayat penerimaan", () => {
  it("tabel desktop memakai lebar tetap 100% agar muat di kartu", () => {
    const dasar = block(".supplier-receipts .receipt-table {");
    expect(dasar).toContain("table-layout: fixed");
    expect(dasar).toContain("width: 100%");
  });

  it("kolom diberi lima lebar yang jumlahnya 100%", () => {
    const lebar = [...css.matchAll(/th:nth-child\((\d)\) \{\s*width: (\d+)%;/g)].map((m) => ({
      kolom: Number(m[1]),
      persen: Number(m[2]),
    }));
    expect(lebar.map((l) => l.kolom)).toEqual([1, 2, 3, 4, 5]);
    expect(lebar.reduce((n, l) => n + l.persen, 0)).toBe(100);
  });

  it("nama pemasok, alasan, dan asal harga boleh membungkus", () => {
    expect(css).toContain(".supplier-receipts .receipt-table .cell-name");
    expect(css).toContain(".supplier-receipts .receipt-table .cell-meta");
    expect(css).toContain(".supplier-receipts .receipt-origin");
    expect(block(".supplier-receipts .receipt-table .cell-name,")).toContain(
      "white-space: normal"
    );
  });

  // S6 (29 Okt 2026) — dulu di ≤760 px tabel ini dipaksa `min-width: 600px`
  // sehingga layar 360 px harus menggeser ke samping. Sekarang ia jadi kartu
  // berlabel, pola yang sama dengan daftar pemasok dan papan kiriman.
  it("layar sempit: kartu berlabel, tanpa lebar minimum paksa", () => {
    const mobile = css.lastIndexOf("@media (max-width: 760px)");
    expect(mobile).toBeGreaterThan(css.indexOf("table-layout: fixed"));
    const pecahan = css.slice(mobile);
    expect(pecahan).toContain("table-layout: auto");
    expect(pecahan).not.toContain("min-width: 600px");
    expect(pecahan).toMatch(/receipt-table thead \{[^}]*display: none/);
    expect(pecahan).toContain("content: attr(data-label)");
    expect(pecahan).toMatch(/receipt-table td \{[^}]*white-space: normal/);
  });

  it("radius hanya dari skala token (bukan angka mentah)", () => {
    const mentah = [...css.matchAll(/border-radius:\s*([^;]+);/g)]
      .map((m) => m[1].trim())
      .filter((v) => !v.startsWith("var(--radius") && v !== "999px" && v !== "0");
    expect(mentah).toEqual([]);
  });

  it("tidak memakai !important", () => {
    expect(css).not.toContain("!important");
  });
});
