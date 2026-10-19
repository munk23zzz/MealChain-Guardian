import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak tata letak Decision & Evidence (19 Okt 2026).
 *
 * Keluhan pemilik: "halaman ini seperti tidak berubah, tolong hapus space
 * kosongnya". Penyebabnya bukan satu kelas, melainkan tiga baris yang selalu
 * selebar kartu 909 px padahal isinya pendek:
 *   1. kepala keputusan  — tiap baris (label 140 px, judul 167 px, "langkah
 *      berikutnya" 149 px) memakai lebar penuh → separuh kanan kosong.
 *   2. bukti              — tiga kartu 4/12: dua kartu 110 px di baris setinggi
 *      222 px → ~112 px kosong di bawah masing-masing.
 *   3. jejak & bukti      — riwayat 217 px di samping panel 546 px → 329 px
 *      kosong di bawah riwayat.
 * Yang diuji di sini hanya penempatan (markup & teks tidak berubah), karena
 * kerusakannya tidak terlihat di tes render.
 */
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

function blok(selector: string): string {
  const cocok = new RegExp(`^${selector}\\s*\\{([^}]*)\\}`, "ms").exec(css);
  if (!cocok) throw new Error(`blok CSS tidak ditemukan: ${selector}`);
  return cocok[1];
}

describe("CSS Decision & Evidence — tanpa baris selebar kartu berisi pendek", () => {
  it("kepala keputusan memakai grid ber-area: judul bersanding langkah berikutnya", () => {
    const hero = blok(".evidence-hero");
    expect(hero).toContain("grid-template-areas");
    expect(hero).toMatch(/"eyebrow\s+next"/);
    expect(hero).toMatch(/"title\s+next"/);
    // Metrik & temuan tetap selebar kartu supaya 4 tile tidak pecah 3+1.
    expect(hero).toMatch(/"metrics\s+metrics"/);
    expect(hero).toMatch(/"flags\s+flags"/);
  });

  it("di ponsel kepala keputusan kembali satu kolom", () => {
    expect(css).toMatch(/@media \(max-width: 900px\) \{\s*\.evidence-hero \{/);
    expect(blok(".evidence-hero-eyebrow")).toBeTruthy();
  });

  it("bukti mengalir dua kolom koran, bukan baris grid setinggi kartu terpanjang", () => {
    // Tinggi kartu bergantung keputusan (Biaya bisa 615 px, Keamanan 355 px):
    // baris grid menyisakan 260-400 px kosong; kolom menyeimbangkan sendiri.
    const grid = blok(".evidence-grid");
    expect(grid).toContain("columns: 2");
    expect(grid).not.toContain("grid-template-columns");
    expect(blok(".evidence-grid > .card")).toContain("break-inside: avoid");
    expect(css).toMatch(/@media \(max-width: 900px\) \{\s*\.evidence-grid \{ columns: 1; \}/);
  });

  it("jejak & bukti tersimpan ditumpuk, bukan 5/7 yang menyisakan 329 px", () => {
    expect(blok(".evidence-bottom")).toContain("grid-template-columns: minmax(0, 1fr)");
    expect(css).not.toMatch(/\.evidence-bottom \{[^}]*5fr[^}]*7fr/);
  });

  it("fakta di kartu bukti sebaris label→nilai (≥721 px), nilai rata kanan", () => {
    // Bentuk menumpuk (label di atas nilai) membuat tiap fakta dua baris 56 px
    // dan separuh kanan kartu kosong; satu baris = 32-34 px.
    const media = css.slice(css.indexOf("@media (min-width: 721px)"));
    expect(media.slice(0, 700)).toMatch(
      /\.evidence-grid \.fact-row \{\s*grid-template-columns: minmax\(0, 38%\) minmax\(0, 1fr\)/
    );
    expect(css).toMatch(/\.evidence-grid \.fact-row dd \{\s*text-align: right;/);
    // Di ponsel tetap menumpuk.
    expect(css).toMatch(/@media \(max-width: 720px\) \{\s*\.fact-row \{\s*grid-template-columns: 1fr;/);
  });

  it("lencana status + meter persetujuan berbagi satu baris", () => {
    expect(blok(".gov-status")).toContain("grid-template-columns: max-content minmax(0, 1fr)");
    expect(blok(".gov-progress")).toContain("max-width: none");
    expect(css).toMatch(/\.gov-roles,[\s\S]{0,120}grid-column: 1 \/ -1;/);
  });

  it("dua bukti (ledger & dossier) berdampingan saat ruang cukup", () => {
    const trust = blok(".integrity-trust");
    expect(trust).toContain("repeat(auto-fit, minmax(260px, 1fr))");
  });
});
