/**
 * Kontrak CSS: panel pemilih keputusan WAJIB benar-benar hilang saat tertutup.
 *
 * Bug yang dijaga (19 Okt 2026, laporan pemilik: "masa kebuka terus"): komponen
 * `DecisionPicker` sudah menulis `hidden={!terbuka}` dan tes unit jsdom lulus —
 * tetapi `.dpick-panel { display: flex }` di globals.css MENGALAHKAN aturan
 * bawaan peramban `[hidden] { display: none }`. Akibatnya panel daftar 83
 * keputusan selalu tergambar, menutupi kartu ringkasan di halaman Decision &
 * Evidence. jsdom tidak memuat stylesheet, jadi hanya tes yang membaca CSS ini
 * yang bisa menangkapnya.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

/** Ambil isi blok aturan pertama yang cocok (selektor persis). */
function blok(selektor: string): string | null {
  const polos = selektor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const cocok = css.match(new RegExp(`(?:^|\\n)\\s*${polos}\\s*\\{([^}]*)\\}`, "i"));
  return cocok ? cocok[1] : null;
}

describe("panel pemilih keputusan benar-benar tertutup", () => {
  it("memberi aturan eksplisit `.dpick-panel[hidden] { display: none }`", () => {
    const isi = blok(".dpick-panel[hidden]");
    expect(isi, "tidak ada aturan `.dpick-panel[hidden]` di globals.css").not.toBeNull();
    expect(isi!).toMatch(/display\s*:\s*none/);
  });

  it("aturan itu berada setelah `.dpick-panel` sehingga menang urutan", () => {
    const dasar = css.indexOf(".dpick-panel {");
    const tertutup = css.indexOf(".dpick-panel[hidden]");
    expect(dasar).toBeGreaterThan(-1);
    expect(tertutup).toBeGreaterThan(dasar);
  });

  it("panel tetap overlay absolut saat terbuka (tidak mendorong tata letak)", () => {
    const isi = blok(".dpick-panel");
    expect(isi).not.toBeNull();
    expect(isi!).toMatch(/position\s*:\s*absolute/);
  });
});
