import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak skala radius.
 *
 * Kenapa ada: sebelum 20 Okt 2026 `border-radius` ditulis dengan 12 nilai mentah
 * (1–14 px) tersebar di 142 deklarasi, plus dua token hantu `--r-1` / `--r-2`
 * yang tidak pernah dideklarasikan sehingga `.dc-agent` dan `.dc-steps-fold`
 * tampil bersudut tajam. Skala yang sah sekarang tujuh nilai:
 *   --radius 12 (kartu) · --radius-dock 14 (dock, design.md §2007)
 *   --radius-control 10 (kontrol, §521/§725) · --radius-control-sm 8 (CTA, §2014)
 *   --radius-chip 4 (chip) · 999px (pil) · 50% (bulat)
 * Sisanya yang diizinkan: `0` (netral) dan `1px` (garis rambut 1 px, bukan sudut).
 */
const AKAR = join(__dirname, "..");

function berkasCss(): string[] {
  const hasil: string[] = [];
  for (const dir of ["app", "components"]) {
    for (const nama of readdirSync(join(AKAR, dir))) {
      if (nama.endsWith(".css")) hasil.push(join(AKAR, dir, nama));
    }
  }
  return hasil;
}

const TOKEN_SAH = /^var\(--radius(-dock|-control|-control-sm|-chip)?\)$/;
const NILAI_MENTAH_SAH = /^(999px|50%|0|1px|inherit)$/;

describe("skala radius", () => {
  const css: string = readFileSync(join(AKAR, "app", "globals.css"), "utf8");

  it("mendeklarasikan ketujuh nilai kanonik di :root", () => {
    expect(css).toMatch(/--radius:\s*12px/);
    expect(css).toMatch(/--radius-dock:\s*14px/);
    expect(css).toMatch(/--radius-control:\s*10px/);
    expect(css).toMatch(/--radius-control-sm:\s*8px/);
    expect(css).toMatch(/--radius-chip:\s*4px/);
  });

  it("tidak lagi memakai token hantu --r-1 / --r-2", () => {
    for (const f of berkasCss()) {
      const isi = readFileSync(f, "utf8");
      expect(isi, `token hantu di ${f}`).not.toMatch(/border-radius:\s*var\(--r-[12]\)/);
    }
  });

  it("setiap deklarasi border-radius memakai token atau nilai sah", () => {
    const pelanggaran: string[] = [];
    for (const f of berkasCss()) {
      const isi = readFileSync(f, "utf8");
      for (const m of Array.from(isi.matchAll(/border-radius:\s*([^;]+);/g))) {
        const nilai = m[1].replace(/!important/g, "").trim();
        for (const bagian of nilai.split(/\s+(?=var\(|0|[0-9])/)) {
          const t = bagian.trim();
          if (!t) continue;
          if (!TOKEN_SAH.test(t) && !NILAI_MENTAH_SAH.test(t)) {
            pelanggaran.push(`${f.split(/[\\/]/).pop()}: border-radius: ${nilai}`);
            break;
          }
        }
      }
    }
    expect(pelanggaran).toEqual([]);
  });

  it("komponen Demo Control yang dulu bersudut tajam kini memakai token", () => {
    const dc = /^\.dc-agent\s*\{([^}]*)\}/m.exec(css);
    expect(dc, "blok .dc-agent tidak ditemukan").not.toBeNull();
    expect(dc![1]).toContain("border-radius: var(--radius-control-sm)");
  });
});
