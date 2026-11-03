// S6 (29 Okt 2026) — kontrak responsif, sentuh, dan gerak untuk halaman Pemasok.
//
// Tes ini tidak menjalankan peramban; ia mengunci ATURAN yang membuat tiga lebar
// (360 / 760 / 1200 px) dan perangkat sentuh bekerja. Bukti visual tetap milik
// pemilik halaman; yang dijaga di sini adalah hal-hal yang paling mudah hilang
// saat orang menambah kolom atau tombol baru:
//
//   * target sentuh 44×44 untuk setiap kontrol yang memang ditekan;
//   * cincin fokus tidak boleh hilang (prioritas 1 skill: Accessibility);
//   * transisi berhenti saat pengguna meminta gerak dikurangi;
//   * tidak ada lagi tabel Pemasok yang dipaksa lebar minimum (itu yang memaksa
//     geseran mendatar di ponsel).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const app = join(process.cwd(), "app");
const globals = readFileSync(join(app, "globals.css"), "utf8");
const receipts = readFileSync(join(app, "supplier-receipts.css"), "utf8");
const summary = readFileSync(join(app, "supplier-summary.css"), "utf8");

/** Blok @media yang memuat penanda, diambil dengan mencocokkan kurung kurawal. */
function blokMedia(css: string, kepala: string, penanda: string): string {
  let dari = 0;
  while (dari < css.length) {
    const mulai = css.indexOf(kepala, dari);
    if (mulai < 0) break;
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
  throw new Error(`${kepala} yang memuat ${penanda} tidak ada`);
}

describe("S6 — target sentuh 44×44 untuk kontrol Pemasok", () => {
  const sentuh = blokMedia(globals, "@media (pointer: coarse), (max-width: 720px)", ".board-search-clear");

  it("tombol, penyaring jangkauan, dan hapus pencarian mencapai 44 px", () => {
    expect(sentuh).toMatch(/\.button \{[^}]*min-height: 44px/);
    expect(sentuh).toMatch(/\.directory-reach-toggle \{[^}]*min-height: 44px/);
    expect(sentuh).toMatch(/\.board-search-clear \{[^}]*width: 44px[^}]*height: 44px/);
  });

  it("teks pencarian tidak tertutup tombol hapus yang kini 44 px", () => {
    expect(sentuh).toMatch(/\.board-search-input \{[^}]*padding-right: 46px/);
  });

  it("pil penyaring riwayat penerimaan juga 44 px", () => {
    const pil = blokMedia(receipts, "@media (pointer: coarse), (max-width: 720px)", ".receipt-chip");
    expect(pil).toMatch(/\.receipt-chip \{[^}]*min-height: 44px/);
  });
});

describe("S6 — cincin fokus terlihat di setiap kontrol Pemasok", () => {
  it("kontrol konsol", () => {
    for (const selektor of [".directory-reach-toggle:focus-visible", ".board-search-clear:focus-visible", ".pager-btn:focus-visible"]) {
      expect(globals, `${selektor} tidak ada`).toContain(selektor);
    }
    // `.button` memakai ring lewat daftar gabungan di awal berkas.
    expect(globals).toMatch(/\n\.button:focus-visible,[\s\S]{0,80}outline: 2px solid var\(--accent-strong\)/);
  });

  it("kontrol riwayat penerimaan", () => {
    expect(receipts).toContain(".receipt-chip:focus-visible");
    expect(receipts).toMatch(/\.receipt-chip:focus-visible \{[^}]*outline: 2px solid var\(--focus-ring\)/);
  });
});

describe("S6 — gerak dihentikan saat pengguna meminta", () => {
  it("kontrol konsol yang bertransisi ikut dimatikan", () => {
    const kurangi = blokMedia(globals, "@media (prefers-reduced-motion: reduce)", ".directory-reach-toggle");
    expect(kurangi).toMatch(/transition: none/);
    for (const selektor of [".button", ".count-pill", ".summary-kpi"]) {
      expect(kurangi, `${selektor} belum ikut`).toContain(selektor);
    }
  });

  it("pil riwayat penerimaan punya pagarnya sendiri", () => {
    const kurangi = blokMedia(receipts, "@media (prefers-reduced-motion: reduce)", ".receipt-chip");
    expect(kurangi).toMatch(/\.receipt-chip \{[^}]*transition: none/);
  });
});

describe("S6 — tiga lebar: 360 / 760 / 1200 px", () => {
  it("≤760 px: tiga tabel Pemasok berubah jadi kartu berlabel", () => {
    for (const [css, selektor] of [
      [globals, ".directory-table"],
      [globals, ".shipment-table"],
      [receipts, "receipt-table"],
    ] as const) {
      const kartu = blokMedia(css, "@media (max-width: 760px)", selektor);
      expect(kartu, `${selektor} belum jadi kartu`).toContain("content: attr(data-label)");
      expect(kartu, `${selektor} masih nowrap`).toMatch(/white-space: normal/);
    }
  });

  it("tidak ada tabel Pemasok yang dipaksa lebar minimum (biang geseran di 360 px)", () => {
    for (const [nama, css] of [["globals.css", globals], ["supplier-receipts.css", receipts]] as const) {
      // Hanya properti, bukan query: `@container (min-width: 680px)` dan
      // `@media (min-width: 721px)` sah dan bukan lebar paksa elemen.
      const paksa = Array.from(css.matchAll(/(?<![(@])min-width:\s*(6\d\d|7\d\d)px/g)).map((m) => m[1]);
      expect(paksa, `${nama} memaksa lebar minimum`).toEqual([]);
    }
  });

  it("≥1200 px: register & usul berdampingan; di bawahnya satu kolom", () => {
    const dua = blokMedia(globals, "@media (min-width: 1200px)", ".register-grid");
    expect(dua).toMatch(/grid-template-columns:\s*minmax\(0, 1\.45fr\)/);
    const dasar = globals.slice(globals.indexOf(".register-grid {"));
    expect(dasar.slice(0, 200)).toMatch(/grid-template-columns:\s*minmax\(0, 1fr\)/);
  });

  it("≤720 px: bilah kontrol dan pil bergerak ke lebar penuh", () => {
    const sempit = blokMedia(globals, "@media (max-width: 720px)", ".directory-reach-toggle");
    expect(sempit).toMatch(/\.directory-reach-toggle \{[^}]*width: 100%/);
    expect(sempit).toMatch(/\.board-search \{[^}]*width: 100%/);
  });

  it("navigasi lima bagian tidak digulir buta di ponsel", () => {
    // Sebelumnya satu baris `overflow-x: auto` dengan scrollbar disembunyikan:
    // dua tujuan terakhir hilang tanpa tanda. Sekarang barisnya membungkus.
    const sempit = blokMedia(globals, "@media (max-width: 720px)", ".section-jump-list");
    expect(sempit).toMatch(/\.section-jump \{[^}]*flex-wrap: wrap/);
    expect(sempit).toMatch(/\.section-jump-list \{[^}]*flex-wrap: wrap/);
  });

  it("tabel register eksklusi ikut jadi kartu di ≤760 px", () => {
    const kartu = blokMedia(globals, "@media (max-width: 760px)", ".register-table");
    expect(kartu).toMatch(/\.register-table thead \{[^}]*display: none/);
    expect(kartu).toContain("content: attr(data-label)");
  });

  it("angka ringkasan tetap terbaca di 360 px (kolom promosi penuh)", () => {
    const sempit = blokMedia(summary, "@media (max-width: 720px)", "summary-kpi");
    expect(sempit).toMatch(/flex-basis: 100%/);
  });
});
