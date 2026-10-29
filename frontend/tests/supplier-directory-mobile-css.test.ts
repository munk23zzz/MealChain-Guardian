// Kontrak CSS "Daftar pemasok" setelah S4 (29 Okt 2026).
//
// Sebabnya: enam kolom dengan `white-space: nowrap` tidak bisa muat di ponsel.
// Kalau tetap dipaksa tabel, pembaca harus menggeser ke samping untuk melihat
// kolom Status — persis yang dilarang aturan layout (tanpa scroll horizontal).
// Karena itu di bawah 760 px tiap pemasok menjadi kartu berlabel `data-label`,
// polanya sama dengan papan kiriman (S3). Tes ini mengunci keberadaannya, bukan
// membuktikannya di browser.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");

/** Blok media yang memuat penanda tertentu (bukan sekadar blok media pertama). */
function blokMedia(ambang: string, penanda: string): string {
  const kepala = `@media (max-width: ${ambang})`;
  let dari = 0;
  while (dari < css.length) {
    const mulai = css.indexOf(kepala, dari);
    if (mulai < 0) break;
    // Hitung kurung kurawal untuk mengambil SELURUH blok media (ia memuat aturan
    // bersarang, jadi indeks "}\n" pertama bukan akhir blok).
    let dalam = 0;
    let akhir = -1;
    for (let i = css.indexOf("{", mulai); i < css.length; i += 1) {
      if (css[i] === "{") dalam += 1;
      else if (css[i] === "}") {
        dalam -= 1;
        if (dalam === 0) {
          akhir = i + 1;
          break;
        }
      }
    }
    const blok = css.slice(mulai, akhir < 0 ? css.length : akhir);
    if (blok.includes(penanda)) return blok;
    dari = mulai + kepala.length;
  }
  throw new Error(`blok @media ${ambang} yang memuat ${penanda} tidak ditemukan`);
}

/** Badan aturan untuk satu selektor, atau string kosong. */
function aturan(selektor: string): string {
  const mulai = css.lastIndexOf(`\n${selektor} {`);
  if (mulai < 0) return "";
  const tutup = css.indexOf("}", mulai);
  return css.slice(mulai, tutup + 1);
}

describe("S4 — daftar pemasok jadi kartu di layar sempit", () => {
  const kartu = blokMedia("760px", ".directory-table");

  it("kepala tabel disembunyikan dan baris jadi blok", () => {
    expect(kartu).toContain(".directory-table thead");
    expect(kartu).toMatch(/\.directory-table thead \{[^}]*display: none/);
    expect(kartu).toMatch(/\.directory-table td \{[^}]*display: flex/);
  });

  it("label tiap nilai datang dari data-label (bukan dari teks bawaan sel)", () => {
    expect(kartu).toContain("td::before");
    expect(kartu).toContain("content: attr(data-label)");
  });

  it("sel pertama tampil sebagai judul kartu, tanpa label", () => {
    expect(kartu).toContain("td:first-child");
    expect(kartu).toMatch(/td:first-child::before \{[^}]*content: none/);
  });

  it("tidak ada piksel mentah untuk ukuran huruf di blok ini", () => {
    // Token ukuran wajib (kontrak design token): font-size hanya lewat var(--fs-*).
    const ukuran = kartu.match(/font-size:[^;]+;/g) ?? [];
    expect(ukuran.length).toBeGreaterThan(0);
    for (const baris of ukuran) expect(baris).toMatch(/var\(--fs-\d\)/);
  });
});

describe("S4 — bilah kontrol daftar pemasok", () => {
  it("satu baris fleksibel dengan jarak token, bukan margin mentah", () => {
    const bilah = aturan(".directory-toolbar");
    expect(bilah).toContain("display: flex");
    expect(bilah).toContain("flex-wrap: wrap");
    expect(bilah).toContain("var(--space-2)");
  });

  it("tombol penyaring jangkauan menyatakan keadaannya (aria-pressed) dan punya cincin fokus", () => {
    expect(aturan('.directory-reach-toggle[aria-pressed="true"]')).toContain("var(--accent-strong)");
    expect(css).toContain(".directory-reach-toggle:focus-visible");
    expect(css).toMatch(/\.directory-reach-toggle:focus-visible \{[^}]*outline: 2px solid var\(--focus-ring\)/);
  });

  it("target sentuh 44 px dipenuhi di layar sempit", () => {
    const sempit = blokMedia("720px", ".directory-reach-toggle");
    expect(sempit).toMatch(/\.directory-reach-toggle \{[^}]*min-height: 44px/);
  });

  it("aturan baris lama sudah tidak ada", () => {
    expect(css).not.toContain(".board-summary-row {");
  });
});
