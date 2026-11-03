import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak CSS triase "Perlu diperhatikan".
 *
 * Kenapa ada: bentuk pertamanya tiga bar selebar halaman (909 px) dengan teks
 * pendek, sehingga separuh kanan tiap bar kosong dan bloknya setinggi 216 px
 * untuk tiga temuan. Bentuk yang diinginkan adalah strip tile: satu temuan
 * memakai lebar penuh, tiga temuan tiga kolom — tidak ada sel menganga dan
 * tidak ada bar yang isinya cuma di kiri. Semuanya hanya bisa dijaga lewat
 * deklarasi CSS, jadi diuji di sini.
 */
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

function blok(selector: string): string {
  const cocok = new RegExp(`^${selector}\\s*\\{([^}]*)\\}`, "ms").exec(css);
  if (!cocok) throw new Error(`blok CSS tidak ditemukan: ${selector}`);
  return cocok[1];
}

describe("CSS triase Perlu diperhatikan", () => {
  it("daftar temuan memakai auto-fit sehingga jumlah tile mengikuti jumlah temuan", () => {
    const daftar = blok(".evidence-flags-list");
    expect(daftar).toContain("repeat(auto-fit");
    expect(daftar).toContain("minmax(260px, 1fr)");
    // Kolom tetap 3 membuat satu temuan hanya memakai 1/3 lebar baris.
    expect(daftar).not.toMatch(/repeat\(3,/);
  });

  it("tile boleh menyusut tanpa meluber", () => {
    const tile = blok(".evidence-flag");
    expect(tile).toContain("min-width: 0");
    expect(tile).toContain("border-left-width: 3px");
  });

  it("teks temuan tetap di lantai tipografi proyek (12 px), bukan lebih kecil", () => {
    expect(blok(".evidence-flag-text")).toContain("font-size: var(--fs-1)");
  });

  it("di ponsel tile turun jadi satu kolom", () => {
    expect(css).toMatch(
      /@media \(max-width: 767px\) \{\s*\.evidence-flags-list \{\s*grid-template-columns: minmax\(0, 1fr\);/
    );
  });
});
