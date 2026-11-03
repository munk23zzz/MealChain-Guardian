import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Dua sisa audit desain (20 Okt 2026).
 *
 * 1. Kontrol peta MapLibre: aturan proyek `.map-card .maplibregl-ctrl-group`
 *    (spesifisitas 0,2,0) KALAH dari stylesheet MapLibre, sehingga bayangan
 *    terukur tetap `rgba(0, 0, 0, 0.1) 0 0 0 2px` — bukan `--shadow-control`.
 *    Perbaikan tanpa `!important`: naikkan spesifisitas lewat leluhur `.map-gl`
 *    (0,3,0), sekalian tokenkan radiusnya (--radius-chip).
 * 2. `<code>` tidak punya font-family di mana pun, jadi angka/kode jatuh ke
 *    `monospace` bawaan peramban (terukur pada `GET /agenda` di tab Hari Ini)
 *    alih-alih `--font-data` (Fira Code) seperti angka lain.
 */
const AKAR = join(__dirname, "..");
const mapConsole = readFileSync(join(AKAR, "app", "map-console.css"), "utf8");
const globals = readFileSync(join(AKAR, "app", "globals.css"), "utf8");

describe("kontrol peta MapLibre", () => {
  it("memakai selektor ber-spesifisitas lebih tinggi (0,3,0) tanpa !important", () => {
    expect(mapConsole).toContain(".map-card .map-gl .maplibregl-ctrl-group {");
    expect(mapConsole).not.toMatch(/maplibregl-ctrl-group[^{]*\{[^}]*!important/);
  });

  it("bayangan dan radius kontrol memakai token", () => {
    const blok = /^\.map-card \.map-gl \.maplibregl-ctrl-group \{([^}]*)\}/m.exec(mapConsole);
    expect(blok, "blok kontrol peta tidak ditemukan").not.toBeNull();
    expect(blok![1]).toContain("box-shadow: var(--shadow-control)");
    // 27 Okt 2026: klaster kontrol peta jadi PIL (`999px`) mengikuti permintaan
    // pemilik "semua tombol oval". Radius chip 4 px dipertahankan sebagai token
    // untuk chip/lencana, bukan untuk klaster tombol ini.
    expect(blok![1]).toContain("border-radius: 999px");
  });
});

describe("tipografi kode", () => {
  it("code/kbd/samp/pre memakai huruf data, bukan monospace bawaan", () => {
    const blok = /^code,[\s,]*kbd,[\s,]*samp,[\s,]*pre\s*\{([^}]*)\}/m.exec(globals);
    expect(blok, "aturan font kode tidak ditemukan").not.toBeNull();
    expect(blok![1]).toContain("font-family: var(--font-data)");
  });
});
