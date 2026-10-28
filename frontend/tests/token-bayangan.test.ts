import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak bayangan (elevasi).
 *
 * Kenapa ada: `box-shadow` ditulis dengan 17 literal `rgba(15, 23, 42, …)` di
 * 10 alpha berbeda untuk tiga peran yang sama — penanda peta, panel melayang,
 * dan kontrol kecil. Akibatnya pin peta punya 4 bayangan berbeda (0,2 / 0,35 /
 * 0,4 / 0,42) yang tidak bisa dibedakan mata, dan popup 0,16 vs 0,18 vs 0,1.
 * Sekarang bayangan hanya boleh datang dari token peran di `:root`.
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

function tanpaKomentar(isi: string): string {
  return isi.replace(/\/\*[\s\S]*?\*\//g, "");
}

const css = readFileSync(join(AKAR, "app", "globals.css"), "utf8");

describe("bayangan memakai token peran", () => {
  it("mendeklarasikan token peran di :root", () => {
    for (const token of [
      "--shadow-pin:",
      "--shadow-pin-hover:",
      "--shadow-pin-soft:",
      "--shadow-pin-core:",
      "--shadow-cluster:",
      "--shadow-pop:",
      "--shadow-float:",
      "--shadow-control:",
      "--shadow-dock:",
      "--ring-hairline:",
    ]) {
      expect(css, `token ${token} tidak dideklarasikan`).toContain(token);
    }
  });

  it("tidak ada lagi literal rgba(15, 23, 42, …) di dalam box-shadow", () => {
    const pelanggaran: string[] = [];
    for (const f of berkasCss()) {
      const isi = tanpaKomentar(readFileSync(f, "utf8"));
      for (const m of Array.from(isi.matchAll(/box-shadow:\s*([^;]+);/g))) {
        if (m[1].includes("rgba(15, 23, 42")) {
          pelanggaran.push(`${f.split(/[\\/]/).pop()}: box-shadow: ${m[1].trim().slice(0, 70)}`);
        }
      }
    }
    expect(pelanggaran).toEqual([]);
  });

  it("dua peran kunci memakai token yang tepat", () => {
    const pin = /^\.map-pin-dot\s*\{([^}]*)\}/m.exec(css);
    expect(pin?.[1]).toContain("box-shadow: var(--shadow-pin)");

    const pop = /^\.top-bar-notif-panel\s*\{([^}]*)\}/m.exec(css);
    expect(pop?.[1]).toContain("box-shadow: var(--shadow-pop)");

    // 29 Okt 2026: bilah pintasan `.evidence-actionbar` (pemakai ketiga
    // `--shadow-dock`) dilepas dari halaman, jadi peran itu tidak diuji lagi.
    // Token `--shadow-dock` tetap ada untuk docs/design.md.
  });

  it("pin pengirim memakai token warna hidup, tanpa bayangan literal", () => {
    // Audit 22 Okt 2026: cincin `0 0 0 2px var(--status-safe)` adalah blok MATI
    // (selektor kembar, kalah cascade). Warna pin pengirim kini isian violet
    // `--status-live` + bayangan inti dari token.
    const ship = /^\.map-pin-supplier-shipping \.map-pin-supplier-dot\s*\{([^}]*)\}/m.exec(css);
    expect(ship?.[1]).toContain("var(--shadow-pin-core)");
    expect(ship?.[1]).not.toContain("var(--status-safe)");
  });
});
